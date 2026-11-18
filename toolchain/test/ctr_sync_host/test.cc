#include "platform/synchronization.h"
#include <chrono>
#include <cstdio>
#include <cstdlib>
#include <thread>

namespace dart {
void Assert::Fail(const char *format, ...) const {
  va_list args;
  va_start(args, format);
  vfprintf(stderr, format, args);
  va_end(args);
  abort();
}
} // namespace dart
#define CHECK(c)                                                               \
  do {                                                                         \
    if (!(c)) {                                                                \
      fprintf(stderr, "failed: %s:%d %s\n", __FILE__, __LINE__, #c);           \
      abort();                                                                 \
    }                                                                          \
  } while (0)
int main() {
  using namespace dart;
  Mutex mutex;
  ConditionVariable cv;
  const auto main_id = platform::GetCurrentThreadId();
  bool waiting = false, release = false;
  std::thread worker([&] {
    CHECK(platform::GetCurrentThreadId() != main_id);
    mutex.Lock();
    CHECK(mutex.IsOwnedByCurrentThread());
    waiting = true;
    cv.NotifyAll();
    while (!release) {
      cv.Wait(&mutex);
      CHECK(mutex.IsOwnedByCurrentThread());
    }
    mutex.Unlock();
  });
  mutex.Lock();
  while (!waiting)
    cv.Wait(&mutex);
  auto before = std::chrono::steady_clock::now();
  CHECK(cv.WaitMicros(&mutex, 20000) == ConditionVariable::kTimedOut);
  CHECK(mutex.IsOwnedByCurrentThread());
  auto elapsed = std::chrono::steady_clock::now() - before;
  CHECK(elapsed >= std::chrono::milliseconds(10));
  CHECK(elapsed < std::chrono::seconds(2));
  release = true;
  cv.Notify();
  mutex.Unlock();
  worker.join();
  // A finite wait in milliseconds must not become microseconds or infinite.
  mutex.Lock();
  before = std::chrono::steady_clock::now();
  CHECK(cv.Wait(&mutex, 20) == ConditionVariable::kTimedOut);
  CHECK(std::chrono::steady_clock::now() - before >=
        std::chrono::milliseconds(10));
  CHECK(mutex.IsOwnedByCurrentThread());
  mutex.Unlock();
  puts("CTR synchronization adapter: signal, timeout units, ownership passed");
}
