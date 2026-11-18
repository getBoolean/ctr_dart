// Host-only scheduling boundary for the real CTR native-thread adapter.
// Synthetic stack/FPSCR values permit ownership tests; they prove no ARM ABI.
#pragma once
#include "../ctr_sync_host/3ds.h"
#include <map>
#include <thread>
#include <vector>

constexpr u64 U64_MAX = UINT64_MAX;
constexpr int RESET_ONESHOT = 0;
struct LightEvent {
  std::mutex mutex;
  std::condition_variable cv;
  bool signaled = false;
};
struct FixtureThread {
  Handle handle;
  std::thread thread;
  bool exited = false;
};
inline std::mutex fixture_state_lock;
inline std::condition_variable fixture_state_changed;
inline std::map<Handle, FixtureThread*> fixture_threads;
inline thread_local FixtureThread* fixture_native = nullptr;
inline thread_local u32 fixture_fpscr = 0;
inline Handle fixture_next_handle = 1;
inline int fixture_freed = 0;
inline int fixture_reaper_waits = 0;
inline bool fixture_reaper_exited = false;
inline bool fixture_worker_clearing = false;
inline bool fixture_release_worker = false;
inline bool fixture_fail_creation = false;
inline void LightEvent_Init(LightEvent* event, int) { event->signaled = false; }
inline void LightEvent_Signal(LightEvent* event) {
  std::lock_guard lock(event->mutex);
  event->signaled = true;
  event->cv.notify_one();
}
inline void LightEvent_Wait(LightEvent* event) {
  if (fixture_native && fixture_native->handle == 1) {
    std::lock_guard lock(fixture_state_lock);
    ++fixture_reaper_waits;
    fixture_state_changed.notify_all();
  }
  std::unique_lock lock(event->mutex);
  event->cv.wait(lock, [&] { return event->signaled; });
  event->signaled = false;
}
inline Thread threadCreate(void (*entry)(void*), void* parameter, size_t,
                           int, int, bool detached) {
  if (detached) std::abort();
  if (fixture_fail_creation) {
    fixture_fail_creation = false;
    return nullptr;
  }
  auto* native = new FixtureThread();
  {
    std::lock_guard lock(fixture_state_lock);
    native->handle = fixture_next_handle++;
    fixture_threads[native->handle] = native;
  }
  native->thread = std::thread([=] {
    fixture_native = native;
    entry(parameter);
    std::lock_guard lock(fixture_state_lock);
    native->exited = true;
    if (native->handle == 1) fixture_reaper_exited = true;
    fixture_state_changed.notify_all();
  });
  return native;
}
inline Handle threadGetHandle(Thread thread) {
  return static_cast<FixtureThread*>(thread)->handle;
}
inline Thread threadGetCurrent() { return fixture_native; }
inline Result svcWaitSynchronization(Handle handle, u64 timeout) {
  if (timeout != U64_MAX) std::abort();
  FixtureThread* native;
  {
    std::lock_guard lock(fixture_state_lock);
    native = fixture_threads.at(handle);
  }
  native->thread.join();
  return 0;
}
inline void threadFree(Thread thread) {
  auto* native = static_cast<FixtureThread*>(thread);
  {
    std::lock_guard lock(fixture_state_lock);
    if (!native->exited || native->thread.joinable()) std::abort();
    fixture_threads.erase(native->handle);
    ++fixture_freed;
  }
  delete native;
}
inline void FixtureDrainLeaks() {
  // Test cleanup after recording a failure, never a simulated adapter success.
  std::vector<FixtureThread*> leaked;
  {
    std::lock_guard lock(fixture_state_lock);
    for (auto [handle, native] : fixture_threads) leaked.push_back(native);
  }
  for (auto* native : leaked) {
    native->thread.join();
    threadFree(native);
  }
}
#define __builtin_arm_get_fpscr() fixture_fpscr
#define __builtin_arm_set_fpscr(value) (fixture_fpscr = (value))
#define __builtin_thread_pointer() reinterpret_cast<void*>(0x20008000 - 8)
