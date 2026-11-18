// Host-only libctru boundary for executing the real Dart synchronization
// adapter. This fixture models blocking/lock ownership, not ARM or kernel
// behavior.
#pragma once
#include <atomic>
#include <condition_variable>
#include <cstdint>
#include <cstring>
#include <mutex>
using Handle = uint32_t;
using Thread = void *;
using u32 = uint32_t;
using Result = int32_t;
using s64 = int64_t;
using u64 = uint64_t;
constexpr u32 CUR_PROCESS_HANDLE = 1;
constexpr int64_t SYSCLOCK_ARM11 = 268123480;
constexpr u32 MEMPERM_READ = 1;
struct MemInfo {
  uintptr_t base_addr;
  size_t size;
  u32 perm;
};
struct PageInfo {};
inline int64_t fixture_ticks = 0;
inline int fixture_entropy_init = 0, fixture_entropy_fill = 0;
inline bool fixture_entropy_closed = false;
#define R_SUCCEEDED(r) ((r) >= 0)
inline Result svcGetProcessId(u32 *id, u32) {
  *id = 7;
  return 0;
}
inline int64_t svcGetSystemTick() { return fixture_ticks; }
inline Result svcGetProcessInfo(s64 *used, u32, u32) {
  *used = 0;
  return -1;
}
inline Result svcQueryMemory(MemInfo *, PageInfo *, uintptr_t) { return -1; }
inline void svcSleepThread(int64_t) {}
inline Result psInit() { return fixture_entropy_init; }
inline void psExit() { fixture_entropy_closed = true; }
inline Result PS_GenerateRandomBytes(void *buffer, size_t length) {
  memset(buffer, 0x5a, length);
  return fixture_entropy_fill;
}
using LightLock = std::mutex;
using CondVar = std::condition_variable;
constexpr u32 CUR_THREAD_HANDLE = 0;
#define R_FAILED(r) ((r) < 0)
inline Result svcGetThreadId(u32 *id, u32) {
  static std::atomic<u32> next{1};
  static thread_local u32 current = next++;
  *id = current;
  return 0;
}
inline void LightLock_Init(LightLock *) {}
inline void LightLock_Lock(LightLock *lock) { lock->lock(); }
inline void LightLock_Unlock(LightLock *lock) { lock->unlock(); }
inline int LightLock_TryLock(LightLock *lock) { return !lock->try_lock(); }
inline void CondVar_Init(CondVar *) {}
inline void CondVar_Wait(CondVar *cv, LightLock *mutex) {
  std::unique_lock<std::mutex> lock(*mutex, std::adopt_lock);
  cv->wait(lock);
  lock.release();
}
inline int CondVar_WaitTimeout(CondVar *cv, LightLock *mutex, int64_t ns) {
  std::unique_lock<std::mutex> lock(*mutex, std::adopt_lock);
  bool timeout = cv->wait_for(lock, std::chrono::nanoseconds(ns)) ==
                 std::cv_status::timeout;
  lock.release();
  return timeout;
}
inline void CondVar_Signal(CondVar *cv) { cv->notify_one(); }
inline void CondVar_Broadcast(CondVar *cv) { cv->notify_all(); }
