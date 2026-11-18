// Execute real native ownership/reaper code with host threads. The VM object
// boundary stalls TLS cleanup to expose shutdown ordering, not target behavior.
#include "vm/os_thread.h"
#include <3ds.h>
#include <cstdio>
#include <cstdlib>

extern "C" {
u32 __ctru_heap = 0x10000000;
u32 __stacksize__ = 0x8000;
#ifndef CTR_TEST_TLS_ALIGNMENT
#define CTR_TEST_TLS_ALIGNMENT 4
#endif
extern const u32 __tdata_align = CTR_TEST_TLS_ALIGNMENT;
}
namespace dart {
void Assert::Fail(const char* format, ...) const {
  va_list args;
  va_start(args, format);
  vfprintf(stderr, format, args);
  va_end(args);
  std::abort();
}
thread_local OSThreadPtr OSThread::current_os_thread_ = {};
OSThread::OSThread() : BaseThread(true), id_(GetCurrentThreadId()),
                      name_(nullptr), log_(nullptr) {}
OSThread::~OSThread() {}
OSThread* OSThread::CreateOSThread() { return new OSThread(); }
void OSThread::SetName(const char*) {}
uword OSThread::GetCurrentStackPointer() {
  return fixture_native ? 0x20000000 : 0x10001000;
}
void OSThread::SetCurrentTLS(BaseThread* value) {
  current_os_thread_.set(static_cast<OSThread*>(value));
  if (!value && fixture_native && fixture_native->handle != 1) {
    std::unique_lock lock(fixture_state_lock);
    fixture_worker_clearing = true;
    fixture_state_changed.notify_all();
    fixture_state_changed.wait(lock, [] { return fixture_release_worker; });
  }
}
char* Utils::StrDup(const char* text) { return strdup(text); }
}  // namespace dart

static void Callback(dart::uword) {}
int main(int argc, char**) {
  using dart::OSThread;
  dart::InitializeCtrThreads();
  if (argc > 1) {
    fixture_fail_creation = true;
    if (OSThread::TryStart("failed creation test", Callback, 0) == 0) return 2;
    dart::CleanupCtrThreads();
    std::lock_guard lock(fixture_state_lock);
    if (!fixture_threads.empty() || fixture_freed != 1) return 1;
    puts("CTR native ownership adapter: failed creation releases reservation");
    return 0;
  }
  if (OSThread::TryStart("detached ownership test", Callback, 0)) return 2;
  {
    std::unique_lock lock(fixture_state_lock);
    fixture_state_changed.wait(lock, [] { return fixture_worker_clearing; });
  }
  bool stopped_early = false;
  std::thread scheduler([&] {
    std::unique_lock lock(fixture_state_lock);
    fixture_state_changed.wait(lock, [] {
      return fixture_reaper_exited || fixture_reaper_waits >= 2;
    });
    stopped_early = fixture_reaper_exited;
    fixture_release_worker = true;
    fixture_state_changed.notify_all();
  });
  dart::CleanupCtrThreads();
  scheduler.join();
  bool released;
  {
    std::lock_guard lock(fixture_state_lock);
    released = fixture_threads.empty() && fixture_freed == 2;
  }
  if (stopped_early || !released) {
    fprintf(stderr, "reaper stopped before TLS cleanup: early=%d freed=%d/2\n",
            stopped_early, fixture_freed);
    FixtureDrainLeaks();
    return 1;
  }
  puts("CTR native ownership adapter: shutdown waits for detached TLS cleanup");
}
