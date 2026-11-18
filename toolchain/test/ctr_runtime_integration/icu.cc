#include <cassert>
#include <cstdio>
#include <cstring>
#include "unicode/unistr.h"
#include "udatamem.h"
#include "umapfile.h"

int main(int argc, char** argv) {
  assert(argc == 2);
  icu::UnicodeString scalar(static_cast<UChar32>(0x1f642));
  assert(scalar.length() == 2 && scalar.char32At(0) == 0x1f642);
  icu::UnicodeString folded(static_cast<UChar32>(0x212a));
  folded.foldCase();
  assert(folded.length() == 1 && folded.charAt(0) == u'k');
  icu::UnicodeString text;
  const int32_t short_capacity = text.getCapacity();
  assert(short_capacity > 0 && text.length() == 0);
  for (int i = 0; i < 512; ++i) text.append(u'a');
  assert(text.length() == 512 && text.getCapacity() >= 512);
  assert(text.getCapacity() > short_capacity && text.charAt(511) == u'a');

  // Exercise the real stdio-backed ICU data loader and its release path.
  unsigned char bytes[64];
  for (unsigned i = 0; i < sizeof(bytes); ++i) bytes[i] = i ^ 0xa5;
  FILE* file = std::fopen(argv[1], "wb");
  assert(file != nullptr);
  assert(std::fwrite(bytes, 1, sizeof(bytes), file) == sizeof(bytes));
  assert(std::fclose(file) == 0);
  UErrorCode status = U_ZERO_ERROR;
  UDataMemory data;
  assert(uprv_mapFile(&data, argv[1], &status));
  assert(U_SUCCESS(status) && data.length == static_cast<int32_t>(sizeof(bytes)));
  assert(std::memcmp(data.pHeader, bytes, sizeof(bytes)) == 0);
  uprv_unmapFile(&data);
  assert(data.map == nullptr && data.mapAddr == nullptr && data.pHeader == nullptr);
  assert(std::remove(argv[1]) == 0);
  assert(!uprv_mapFile(&data, argv[1], &status));
  std::puts("PASS ICU scalar, fold, stack/heap capacity and stdio load/release");
}
