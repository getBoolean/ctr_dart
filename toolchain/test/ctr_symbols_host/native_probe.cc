// Link-only probe against real devkitARM/newlib/libctru and SDK headers.
#include "vm/native_symbol.h"

extern "C" char _start[], __bss_end__[], __start__[];
volatile uintptr_t absolute_start;

int main() {
  using dart::NativeSymbolResolver;
  const dart::uword base = reinterpret_cast<dart::uword>(_start);
  absolute_start = reinterpret_cast<uintptr_t>(__start__);
  NativeSymbolResolver::Init();
  dart::uword found;
  const char *image;
  if (!NativeSymbolResolver::LookupSharedObject(base, &found, &image))
    return 1;
  if (found != base)
    return 2;
  struct {
    uint32_t count, offset, size, name;
    char text[6];
  } table = {1, 0, 4, 0, "entry"};
  NativeSymbolResolver::AddSymbols(image, &table, sizeof(table));
  const char *name = NativeSymbolResolver::LookupSymbolName(base, &found);
  if (name == nullptr || strcmp(name, "entry") != 0 || found != base)
    return 3;
  NativeSymbolResolver::FreeSymbolName(name);
  if (NativeSymbolResolver::LookupSharedObject(
          reinterpret_cast<dart::uword>(__bss_end__)))
    return 4;
  NativeSymbolResolver::Cleanup();
  return 0;
}
