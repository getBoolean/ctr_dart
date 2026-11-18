#include <stdint.h>
#include "vm/ctr_double_helpers.h"
#include "remainder_cases.h"
#if defined(CTR_REMAINDER_FREESTANDING)
extern "C" void test_write(const char*, unsigned);
extern "C" int test_abi(double (*)(double));
#else
#include <stdio.h>
#endif

static double (*volatile remainder_call)(double, double) = CtrDoubleRemainder;
static double (*volatile modulo_call)(double, double) = CtrDoubleModulo;

extern "C" double remainder_abi(double value) {
  const uint64_t pattern = UINT64_C(0x000fffffffffffff);
  double divisor;
  __builtin_memcpy(&divisor, &pattern, 8);
  return remainder_call(value, divisor);
}
extern "C" double modulo_abi(double value) {
  const uint64_t pattern = UINT64_C(0x000fffffffffffff);
  double divisor;
  __builtin_memcpy(&divisor, &pattern, 8);
  return modulo_call(value, divisor);
}
static bool Same(double value, uint64_t expected) {
  uint64_t actual;
  __builtin_memcpy(&actual, &value, 8);
  if ((expected & UINT64_C(0x7fffffffffffffff)) > UINT64_C(0x7ff0000000000000)) {
    return (actual & UINT64_C(0x7fffffffffffffff)) > UINT64_C(0x7ff0000000000000) &&
           (actual & UINT64_C(0x0008000000000000)) != 0;
  }
  return actual == expected;
}
int main() {
#if defined(CTR_REMAINDER_FREESTANDING)
  uint32_t fpscr;
  asm volatile("vmrs %0, fpscr" : "=r"(fpscr));
  if ((fpscr & 0x03000000) != 0x03000000) return 2;
#endif
  for (unsigned i = 0; i < sizeof(cases) / sizeof(cases[0]); ++i) {
    double x, y;
    __builtin_memcpy(&x, &cases[i].left, 8);
    __builtin_memcpy(&y, &cases[i].right, 8);
    if (!Same(remainder_call(x, y), cases[i].remainder) ||
        !Same(modulo_call(x, y), cases[i].modulo)) {
      char message[] = "remainder mismatch: case=00000000\n";
      for (unsigned n = 0; n < 8; ++n) {
        message[25 + n] = "0123456789abcdef"[(i >> (28 - 4 * n)) & 15];
      }
#if defined(CTR_REMAINDER_FREESTANDING)
      test_write(message, sizeof(message) - 1);
#else
      fprintf(stderr, "%s", message);
#endif
      return 1;
    }
  }
#if defined(CTR_REMAINDER_FREESTANDING)
  if (test_abi(remainder_abi) || test_abi(modulo_abi)) return 3;
  asm volatile("vmrs %0, fpscr" : "=r"(fpscr));
  if ((fpscr & 0x03000000) != 0x03000000) return 4;
#endif
  return 0;
}
