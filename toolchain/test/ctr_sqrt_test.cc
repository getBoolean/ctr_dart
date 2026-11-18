#include <stdint.h>
#if !defined(CTR_SQRT_FREESTANDING)
#include <stdio.h>
#include <math.h>
#endif
#if defined(CTR_SQRT_BASELINE)
static double CtrDoubleSqrt(double value) {
#if defined(CTR_SQRT_FREESTANDING)
  double result;
  asm volatile("vsqrt.f64 %P0, %P1" : "=w"(result) : "w"(value));
  return result;
#else
  return sqrt(value);
#endif
}
#else
#include "vm/ctr_double_helpers.h"
#endif
#include "sqrt_cases.h"

static double (*volatile square_root)(double) = CtrDoubleSqrt;
#if defined(CTR_SQRT_FREESTANDING)
extern "C" void test_write(const char*, unsigned);
extern "C" int test_abi(double (*)(double));
#endif

static bool NaN(uint64_t bits) {
  return (bits & UINT64_C(0x7fffffffffffffff)) > UINT64_C(0x7ff0000000000000);
}

int main() {
#if defined(CTR_SQRT_FREESTANDING)
  uint32_t fpscr;
  asm volatile("vmrs %0, fpscr" : "=r"(fpscr));
  if ((fpscr & 0x03000000) != 0x03000000) return 2;
#endif
  for (unsigned i = 0; i < sizeof(cases) / sizeof(cases[0]); ++i) {
    double input;
    __builtin_memcpy(&input, &cases[i].input, 8);
    double result = square_root(input);
    uint64_t actual;
    __builtin_memcpy(&actual, &result, 8);
    const uint64_t expected = cases[i].expected;
    const bool same = NaN(expected)
        ? NaN(actual) && (actual & UINT64_C(0x0008000000000000)) != 0
        : actual == expected;
    if (!same) {
      char message[] = "sqrt mismatch: case=00000000\n";
      for (unsigned n = 0; n < 8; ++n) {
        message[20 + n] = "0123456789abcdef"[(i >> (28 - 4 * n)) & 15];
      }
#if defined(CTR_SQRT_FREESTANDING)
      test_write(message, sizeof(message) - 1);
#else
      fprintf(stderr, "%s", message);
#endif
      return 1;
    }
  }
#if defined(CTR_SQRT_FREESTANDING)
  if (test_abi(CtrDoubleSqrt) != 0) return 3;
  asm volatile("vmrs %0, fpscr" : "=r"(fpscr));
  if ((fpscr & 0x03000000) != 0x03000000) return 4;
#endif
  return 0;
}
