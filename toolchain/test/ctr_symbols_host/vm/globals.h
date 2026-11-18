#ifndef CTR_SYMBOLS_TEST_GLOBALS_H_
#define CTR_SYMBOLS_TEST_GLOBALS_H_
#include <cassert>
#include <cstdint>
#include <cstdlib>
#include <cstring>
#define DART_HOST_OS_CTR 1
#define ASSERT(condition) assert(condition)
namespace dart {
using uword = uintptr_t;
}
#endif
