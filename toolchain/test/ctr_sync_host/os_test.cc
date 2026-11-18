// Fault injection at the OS service boundary; the real OS adapter computes
// clock conversions, returns entropy failures, and rejects clock failures.
#include "platform/assert.h"
#include "vm/os.h"
#include <3ds.h>
#include <cstdio>
#include <cstdlib>
#include <cstring>
#include <sys/wait.h>
#include <time.h>
#include <unistd.h>
namespace dart {
void Assert::Fail(const char *, ...) const { _exit(77); }
} // namespace dart
static bool clock_failure = false;
extern "C" int __wrap_clock_gettime(clockid_t, struct timespec *now) {
  if (clock_failure)
    return -1;
  now->tv_sec = 1234;
  now->tv_nsec = 567000000;
  return 0;
}
#define CHECK(c)                                                               \
  do {                                                                         \
    if (!(c)) {                                                                \
      fprintf(stderr, "failed: %s\n", #c);                                     \
      abort();                                                                 \
    }                                                                          \
  } while (0)
int main() {
  using dart::OS;
  CHECK(OS::GetCurrentTimeMicros() == 1234567000);
  CHECK(OS::GetCurrentTimeMillis() == 1234567);
  fixture_ticks = 11 * SYSCLOCK_ARM11 + SYSCLOCK_ARM11 / 2;
  CHECK(OS::GetCurrentMonotonicMicros() == 11500000);
  fixture_ticks = INT64_MAX;
  CHECK(OS::GetCurrentMonotonicMicros() > 0);
  uint8_t bytes[16] = {};
  CHECK(OS::GetEntropy(bytes, sizeof(bytes)) && bytes[0] == 0x5a);
  CHECK(fixture_entropy_closed);
  fixture_entropy_closed = false;
  fixture_entropy_init = -1;
  CHECK(!OS::GetEntropy(bytes, sizeof(bytes)) && bytes[0] == 0);
  CHECK(!fixture_entropy_closed);
  fixture_entropy_init = 0;
  fixture_entropy_fill = -2;
  CHECK(!OS::GetEntropy(bytes, sizeof(bytes)) && bytes[15] == 0);
  CHECK(fixture_entropy_closed);
  pid_t child = fork();
  if (child == 0) {
    clock_failure = true;
    OS::GetCurrentTimeMicros();
    _exit(1);
  }
  int status;
  CHECK(waitpid(child, &status, 0) == child);
  CHECK(WIFEXITED(status) && WEXITSTATUS(status) == 77);
  child = fork();
  if (child == 0) {
    fixture_ticks = -1;
    OS::GetCurrentMonotonicTicks();
    _exit(1);
  }
  CHECK(waitpid(child, &status, 0) == child);
  CHECK(WIFEXITED(status) && WEXITSTATUS(status) == 77);
  puts("CTR OS adapter: clocks, overflow, entropy failures passed");
}
