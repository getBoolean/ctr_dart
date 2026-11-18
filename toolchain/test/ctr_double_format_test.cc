// Execute the real decimal dependency with dynamic operands, without a Dart VM.
#include <stdint.h>
#include <string.h>
#include "third_party/double-conversion/src/double-conversion.h"
#include "third_party/double-conversion/src/bignum-dtoa.h"
#include "decimal_cases.h"
#if defined(CTR_DOUBLE_FREESTANDING)
extern "C" void test_write(const char*, unsigned);
extern "C" __attribute__((noreturn)) void test_abort();
extern "C" __attribute__((noreturn)) void abort() { test_abort(); }
static void Print(const char* text) { test_write(text, strlen(text)); }
static unsigned Fpscr() {
  unsigned result;
  asm volatile("vmrs %0, fpscr" : "=r"(result));
  return result;
}
#else
#include <stdio.h>
static void Print(const char* text) { fputs(text, stdout); }
#endif
static uint64_t Bits(double value) {
  uint64_t result;
  memcpy(&result, &value, sizeof(result));
  return result;
}
static void PrintBits(uint64_t value) {
  char text[18];
  for (int i = 0; i < 16; ++i)
    text[i] = "0123456789abcdef"[(value >> (60 - 4 * i)) & 15];
  text[16] = '\n';
  text[17] = 0;
  Print(text);
}
int main() {
  using namespace double_conversion;
#if defined(CTR_DOUBLE_FREESTANDING)
  if ((Fpscr() & 0x03c00000) != 0x03000000) return 7;
#endif
  DoubleToStringConverter formatter(
      DoubleToStringConverter::EMIT_POSITIVE_EXPONENT_SIGN |
      DoubleToStringConverter::EMIT_TRAILING_DECIMAL_POINT |
      DoubleToStringConverter::EMIT_TRAILING_ZERO_AFTER_POINT,
      "Infinity", "NaN", 'e', -6, 21, 6, 0);
  StringToDoubleConverter parser(StringToDoubleConverter::NO_FLAGS, 0, 0,
                                 "Infinity", "NaN");
  const int digits[] = {0, 1, 6, 20};
  const int precisions[] = {1, 6, 17, 21};
  for (unsigned i = 0; i < sizeof(format_cases) / sizeof(format_cases[0]); ++i) {
    volatile uint64_t dynamic = format_cases[i];
    uint64_t raw = dynamic;
    double value;
    memcpy(&value, &raw, sizeof(value));
    for (int mode = 0; mode < 16; ++mode) {
      char buffer[256];
      StringBuilder builder(buffer, sizeof(buffer));
      bool ok;
      if (mode == 0) ok = formatter.ToShortest(value, &builder);
      else if (mode < 5) ok = formatter.ToFixed(value, digits[mode - 1], &builder);
      else if (mode < 10) ok = formatter.ToExponential(value, mode == 5 ? -1 : digits[mode - 6], &builder);
      else if (mode < 14) ok = formatter.ToPrecision(value, precisions[mode - 10], &builder);
      else if (mode == 15) {
        DoubleToStringConverter unique_zero(
            DoubleToStringConverter::UNIQUE_ZERO,
            "Infinity", "NaN", 'e', -6, 21, 6, 0);
        ok = unique_zero.ToShortest(value, &builder);
      } else {
        // Force the fallback; fast-path success must not hide its defects.
        if ((raw & 0x7fffffffffffffffULL) == 0 ||
            (raw & 0x7ff0000000000000ULL) == 0x7ff0000000000000ULL) continue;
        uint64_t magnitude = raw & 0x7fffffffffffffffULL;
        double positive;
        memcpy(&positive, &magnitude, sizeof(positive));
        int length, point;
        BignumDtoa(positive, BIGNUM_DTOA_SHORTEST, 0,
                   Vector<char>(buffer, sizeof(buffer)), &length, &point);
        buffer[length] = 0;
        Print(buffer);
        Print("\n");
        PrintBits(static_cast<uint64_t>(point));
        continue;
      }
      if (!ok) { Print("rejected\n"); continue; }
      const char* text = builder.Finalize();
      Print(text);
      Print("\n");
      if (mode == 0) {
        int count = 0;
        uint64_t parsed = Bits(parser.StringToDouble(text, strlen(text), &count));
        const bool nan = (raw & 0x7fffffffffffffffULL) > 0x7ff0000000000000ULL;
        if (count != static_cast<int>(strlen(text)) ||
            (nan ? (parsed & 0x7fffffffffffffffULL) <= 0x7ff0000000000000ULL
                 : parsed != raw)) return 3;
      }
    }
  }
  for (unsigned i = 0; i < sizeof(parse_cases) / sizeof(parse_cases[0]); ++i) {
    int count = 0;
    uint64_t actual = Bits(parser.StringToDouble(parse_cases[i].text,
                         strlen(parse_cases[i].text), &count));
    PrintBits(actual);
    if (actual != parse_cases[i].expected ||
        count != static_cast<int>(strlen(parse_cases[i].text))) return 4;
  }
  for (unsigned i = 0; i < sizeof(single_cases) / sizeof(single_cases[0]); ++i) {
    int count = 0;
    float value = parser.StringToFloat(single_cases[i].text,
                                      strlen(single_cases[i].text), &count);
    uint32_t actual;
    memcpy(&actual, &value, sizeof(actual));
    PrintBits(actual);
    if (actual != single_cases[i].expected ||
        count != static_cast<int>(strlen(single_cases[i].text))) return 5;
    char buffer[64];
    StringBuilder builder(buffer, sizeof(buffer));
    if (!formatter.ToShortestSingle(value, &builder)) return 6;
    const char* text = builder.Finalize();
    Print(text);
    Print("\n");
    float back = parser.StringToFloat(text, strlen(text), &count);
    uint32_t back_bits;
    memcpy(&back_bits, &back, sizeof(back_bits));
    if (back_bits != actual) return 6;
  }
#if defined(CTR_DOUBLE_FREESTANDING)
  if ((Fpscr() & 0x03c00000) != 0x03000000) return 8;
#endif
  return 0;
}
