#include <stdint.h>
#if !defined(CTR_DOUBLE_FREESTANDING)
#include <stdio.h>
#endif
#if defined(CTR_DOUBLE_BASELINE)
static int CtrDoubleCompare(double left, double right) {
  if (left != left || right != right) return 2;
  return left < right ? -1 : left > right ? 1 : 0;
}
#else
#include "vm/ctr_double_helpers.h"
#endif
#include "compare_cases.h"

static double FromBits(uint64_t bits) {
  double value;
  __builtin_memcpy(&value, &bits, sizeof(value));
  return value;
}
static int (*volatile compare)(double, double) = CtrDoubleCompare;
#if defined(CTR_DOUBLE_FREESTANDING)
extern "C" void test_write(const char*, unsigned);
extern "C" int test_abi(int (*)(double, double));
#endif

int main() {
#if defined(CTR_DOUBLE_FREESTANDING)
  uint32_t fpscr;
  asm volatile("vmrs %0, fpscr" : "=r"(fpscr));
  if ((fpscr & 0x03000000) != 0x03000000) return 2;
#endif
  for (unsigned i = 0; i < sizeof(cases) / sizeof(cases[0]); ++i) {
    const int actual = compare(FromBits(cases[i].left), FromBits(cases[i].right));
    if (actual != cases[i].expected) {
      char message[] = "comparison mismatch: case=00000000\n";
      for (unsigned n = 0; n < 8; ++n) {
        message[26 + n] = "0123456789abcdef"[(i >> (28 - 4 * n)) & 15];
      }
#if defined(CTR_DOUBLE_FREESTANDING)
      test_write(message, sizeof(message) - 1);
#else
      fprintf(stderr, "%sactual=%d expected=%d\n", message, actual, cases[i].expected);
#endif
      return 1;
    }
  }
#if defined(CTR_DOUBLE_FREESTANDING)
  if (test_abi(CtrDoubleCompare) != 0) return 3;
  asm volatile("vmrs %0, fpscr" : "=r"(fpscr));
  if ((fpscr & 0x03000000) != 0x03000000) return 4;
#endif
  return 0;
}
