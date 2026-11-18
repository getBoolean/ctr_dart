#include <cstddef>
#include <cstdint>
#include <type_traits>
#include "vm/compiler/ffi/abi.h"

using dart::compiler::ffi::Abi;
static_assert(static_cast<int>(Abi::kWindowsX64) == 23);
static_assert(static_cast<int>(Abi::kCtrArm) == 24);
static_assert(dart::compiler::ffi::num_abis == 25);

#if defined(__3DS__)
struct Layout { char c; double d; uint64_t u; void* p; };
static_assert(sizeof(char) == 1 && sizeof(short) == 2);
static_assert(sizeof(int) == 4 && sizeof(long) == 4);
static_assert(sizeof(long long) == 8 && sizeof(void*) == 4);
static_assert(sizeof(float) == 4 && sizeof(double) == 8);
static_assert(alignof(double) == 8 && alignof(uint64_t) == 8);
static_assert(offsetof(Layout, d) == 8 && offsetof(Layout, u) == 16);
static_assert(offsetof(Layout, p) == 24 && sizeof(Layout) == 32);
static_assert(std::is_unsigned_v<char>);
static_assert(std::is_same_v<int32_t, long>);
static_assert(std::is_same_v<uint32_t, unsigned long>);
#endif

int main() {
  return dart::compiler::ffi::TargetAbi() == Abi::kCtrArm ? 0 : 1;
}
