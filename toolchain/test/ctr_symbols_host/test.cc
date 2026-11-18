#include "vm/native_symbol.h"
#include <cassert>
#include <cstddef>
#include <cstdio>
#include <cstring>
#include <initializer_list>

extern "C" char ctr_test_image_start[], ctr_test_image_end[];
using dart::NativeSymbolResolver;
using dart::uword;

int main() {
  const uword base = reinterpret_cast<uword>(ctr_test_image_start);
  const uword end = reinterpret_cast<uword>(ctr_test_image_end);
  NativeSymbolResolver::Init();
  uword result = 123;
  const char *image = nullptr;
  assert(NativeSymbolResolver::LookupSharedObject(base, &result, &image));
  assert(result == base && strcmp(image, "ctr-static-image") == 0);
  assert(NativeSymbolResolver::LookupSharedObject(end - 1));
  assert(!NativeSymbolResolver::LookupSharedObject(base - 1));
  assert(!NativeSymbolResolver::LookupSharedObject(end));
  result = 123;
  assert(!NativeSymbolResolver::LookupSymbolName(base + 8, &result));
  assert(result == 123);
  // The SDK's opaque table layout, with immutable embedder-owned storage.
  struct Table {
    uint32_t count;
    uint32_t entries[3][3];
    char names[17];
  } table = {3, {{8, 4, 0}, {16, 8, 6}, {32, 0, 11}}, "first\0next\0empty"};
  NativeSymbolResolver::AddSymbols("other-image", &table, sizeof(table));
  assert(!NativeSymbolResolver::LookupSymbolName(base + 8, nullptr));
  NativeSymbolResolver::AddSymbols(image, &table, sizeof(table));
  const char *first = NativeSymbolResolver::LookupSymbolName(base + 8, &result);
  assert(first && strcmp(first, "first") == 0 && result == base + 8);
  const char *again =
      NativeSymbolResolver::LookupSymbolName(base + 11, nullptr);
  assert(again && again != first && strcmp(again, first) == 0);
  for (uword offset : {0u, 7u, 12u, 15u, 24u, 31u, 32u, 127u, 128u}) {
    assert(!NativeSymbolResolver::LookupSymbolName(base + offset, nullptr));
  }
  const char *next = NativeSymbolResolver::LookupSymbolName(base + 23, &result);
  assert(next && strcmp(next, "next") == 0 && result == base + 16);
  NativeSymbolResolver::FreeSymbolName(next);
  // A truncated registration must not expose memory outside its supplied size.
  NativeSymbolResolver::AddSymbols(image, &table, 4);
  uint32_t impossible_count = UINT32_MAX;
  NativeSymbolResolver::AddSymbols(image, &impossible_count,
                                   sizeof(impossible_count));
  Table invalid = table;
  invalid.entries[0][2] = UINT32_MAX;
  NativeSymbolResolver::AddSymbols(image, &invalid, sizeof(invalid));
  Table unterminated = table;
  memset(unterminated.names, 'x', sizeof(unterminated.names));
  NativeSymbolResolver::AddSymbols(image, &unterminated,
                                   offsetof(Table, names) +
                                       sizeof(unterminated.names));
  Table unsorted = table;
  unsorted.entries[1][0] = 0;
  NativeSymbolResolver::AddSymbols(image, &unsorted, sizeof(unsorted));
  const char *retained =
      NativeSymbolResolver::LookupSymbolName(base + 8, nullptr);
  assert(retained && strcmp(retained, "first") == 0);
  NativeSymbolResolver::FreeSymbolName(retained);
  // Read table words without imposing an alignment absent from the API.
  char unaligned[sizeof(table) + 1];
  memcpy(unaligned + 1, &table, sizeof(table));
  NativeSymbolResolver::AddSymbols(image, unaligned + 1, sizeof(table));
  retained = NativeSymbolResolver::LookupSymbolName(base + 23, nullptr);
  assert(retained && strcmp(retained, "next") == 0);
  NativeSymbolResolver::FreeSymbolName(retained);
  assert(strcmp(first, "first") == 0);
  NativeSymbolResolver::Cleanup();
  assert(!NativeSymbolResolver::LookupSymbolName(base + 8, nullptr));
  assert(strcmp(first, "first") == 0 && strcmp(again, "first") == 0);
  assert(table.count == 3 && strcmp(table.names, "first") == 0);
  NativeSymbolResolver::FreeSymbolName(first);
  NativeSymbolResolver::FreeSymbolName(again);
  NativeSymbolResolver::FreeSymbolName(nullptr);
  NativeSymbolResolver::Init();
  NativeSymbolResolver::AddSymbols(image, &table, sizeof(table));
  first = NativeSymbolResolver::LookupSymbolName(base + 8, nullptr);
  assert(first && strcmp(first, "first") == 0);
  NativeSymbolResolver::FreeSymbolName(first);
  NativeSymbolResolver::Cleanup();
  NativeSymbolResolver::Cleanup();
  puts("PASS registered boundaries, unknowns, owned names, cleanup/reinit");
}
