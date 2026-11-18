#include <stdint.h>
#include "vm/ctr_double_helpers.h"
#include "pow_cases.h"

static bool (*volatile special)(double, double, double*) = CtrDoublePowSpecial;
extern "C" double pow_half(double value) {
  double result;
  return special(value, 0.5, &result) ? result : 0.0;
}
#if defined(CTR_POW_FREESTANDING)
extern "C" void test_write(const char*, unsigned);
extern "C" int test_abi(double (*)(double));
#else
#include <stdio.h>
#endif

int main() {
#if defined(CTR_POW_FREESTANDING)
  uint32_t fpscr;
  asm volatile("vmrs %0, fpscr" : "=r"(fpscr));
  if ((fpscr & 0x03000000) != 0x03000000) return 2;
#endif
  for (unsigned i = 0; i < sizeof(cases) / sizeof(cases[0]); ++i) {
    double base, exponent, result;
    __builtin_memcpy(&base, &cases[i].base, 8);
    __builtin_memcpy(&exponent, &cases[i].exponent, 8);
    const uint64_t sentinel = UINT64_C(0x123456789abcdef0);
    __builtin_memcpy(&result, &sentinel, 8);
    const bool handled = special(base, exponent, &result);
    uint64_t actual;
    __builtin_memcpy(&actual, &result, 8);
    const uint64_t expected = cases[i].expected;
    const bool nan = (expected & UINT64_C(0x7fffffffffffffff)) > UINT64_C(0x7ff0000000000000);
    const bool same = nan
        ? (actual & UINT64_C(0x7fffffffffffffff)) > UINT64_C(0x7ff0000000000000) &&
          (actual & UINT64_C(0x0008000000000000)) != 0
        : actual == expected;
    if (handled != cases[i].handled || !same) {
      char message[] = "pow mismatch: case=00000000\n";
      for (unsigned n = 0; n < 8; ++n) {
        message[19 + n] = "0123456789abcdef"[(i >> (28 - 4 * n)) & 15];
      }
#if defined(CTR_POW_FREESTANDING)
      test_write(message, sizeof(message) - 1);
#else
      fprintf(stderr, "%s", message);
#endif
      return 1;
    }
  }
#if defined(CTR_POW_FREESTANDING)
  if (test_abi(pow_half)) return 3;
  asm volatile("vmrs %0, fpscr" : "=r"(fpscr));
  if ((fpscr & 0x03000000) != 0x03000000) return 4;
#endif
  return 0;
}
