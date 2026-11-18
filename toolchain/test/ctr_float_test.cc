#include <stdint.h>
#if !defined(CTR_FLOAT_FREESTANDING)
#include <stdio.h>
#endif
#if defined(CTR_FLOAT_BASELINE)
static void CtrFloatConvert(uint32_t* words, intptr_t narrow) {
  if (narrow) {
    double value;
    __builtin_memcpy(&value, words, 8);
    const float result = static_cast<float>(value);
    __builtin_memcpy(words, &result, 4);
  } else {
    float value;
    __builtin_memcpy(&value, words, 4);
    const double result = static_cast<double>(value);
    __builtin_memcpy(words, &result, 8);
  }
}
#else
#include "vm/ctr_double_helpers.h"
#endif
#include "float_cases.h"

static void (*volatile convert)(uint32_t*, intptr_t) = CtrFloatConvert;
#if defined(CTR_FLOAT_FREESTANDING)
extern "C" void test_write(const char*, unsigned);
extern "C" int test_abi(double (*)(double, double));
#endif

extern "C" double FloatABIProbe(double value, double) {
  uint32_t words[2];
  __builtin_memcpy(words, &value, 8);
  convert(words, 1);
  convert(words, 0);
  __builtin_memcpy(&value, words, 8);
  return value;
}

int main() {
#if defined(CTR_FLOAT_FREESTANDING)
  uint32_t fpscr;
  asm volatile("vmrs %0, fpscr" : "=r"(fpscr));
  if ((fpscr & 0x03000000) != 0x03000000) return 2;
#endif
  for (unsigned i = 0; i < sizeof(cases) / sizeof(cases[0]); ++i) {
    const auto& row = cases[i];
    alignas(8) uint32_t buffer[] = {0x13579bdf, 0x2468ace0,
        static_cast<uint32_t>(row.input), static_cast<uint32_t>(row.input >> 32),
        0xfdb97531, 0xeca86420};
    convert(buffer + 2, row.narrow);
    uint64_t actual;
    __builtin_memcpy(&actual, buffer + 2, 8);
    const uint64_t mask = row.narrow ? UINT64_C(0xffffffff) : UINT64_MAX;
    actual &= mask;
    const uint64_t magnitude = row.narrow ? UINT64_C(0x7fffffff)
                                          : UINT64_C(0x7fffffffffffffff);
    const uint64_t infinity = row.narrow ? UINT64_C(0x7f800000)
                                         : UINT64_C(0x7ff0000000000000);
    const bool same = (row.expected & magnitude) > infinity
                         ? (actual & magnitude) > infinity
                         : actual == row.expected;
    if (!same || buffer[0] != 0x13579bdf || buffer[1] != 0x2468ace0 ||
        buffer[4] != 0xfdb97531 || buffer[5] != 0xeca86420 ||
        (row.narrow && buffer[3] != static_cast<uint32_t>(row.input >> 32))) {
      char message[] = "float mismatch: case=00000000\n";
      for (unsigned n = 0; n < 8; ++n) {
        message[21 + n] = "0123456789abcdef"[(i >> (28 - 4 * n)) & 15];
      }
#if defined(CTR_FLOAT_FREESTANDING)
      test_write(message, sizeof(message) - 1);
#else
      fprintf(stderr, "%s", message);
#endif
      return 1;
    }
  }
#if defined(CTR_FLOAT_FREESTANDING)
  if (test_abi(FloatABIProbe) != 0) return 3;
  asm volatile("vmrs %0, fpscr" : "=r"(fpscr));
  if ((fpscr & 0x03000000) != 0x03000000) return 4;
#endif
  return 0;
}
