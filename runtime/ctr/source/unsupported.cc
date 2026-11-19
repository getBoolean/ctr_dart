#include "unsupported.h"
#include <array>
#include <cstdio>
#include <cstdlib>
#include <cstring>
#include <utility>
namespace ctr {
namespace {
// A native function receives only its arguments, so each distinct name gets
// its own slot function. The SDK's dart:io declares 184 distinct natives.
// Only the single mutator thread resolves natives (one isolate).
constexpr int kSlots = 256;
const char* names[kSlots];
int used = 0;
// Dart_ThrowException does not return: no objects with destructors here.
void Throw(const char* native) {
  char message[128];
  snprintf(message, sizeof(message), "%s is not supported on CTR (dart:io)", native);
  Dart_Handle core = Dart_LookupLibrary(Dart_NewStringFromCString("dart:core"));
  Dart_Handle type = Dart_GetNonNullableType(core, Dart_NewStringFromCString("UnsupportedError"), 0, nullptr);
  Dart_Handle text = Dart_NewStringFromCString(message);
  Dart_Handle error = Dart_IsError(type) ? type : Dart_New(type, Dart_Null(), 1, &text);
  Dart_PropagateError(Dart_ThrowException(error));
}
template <int N> void Slot(Dart_NativeArguments) { Throw(names[N]); }
void Overflow(Dart_NativeArguments) { Throw("a dart:io native"); }
template <int... N>
constexpr std::array<Dart_NativeFunction, kSlots> Slots(std::integer_sequence<int, N...>) {
  return {Slot<N>...};
}
constexpr auto slots = Slots(std::make_integer_sequence<int, kSlots>());
}
Dart_NativeFunction ResolveUnsupported(Dart_Handle name, int, bool* scope) {
  *scope = true;
  const char* text;
  if (Dart_IsError(Dart_StringToCString(name, &text))) return Overflow;
  for (int i = 0; i < used; i++)
    if (!strcmp(names[i], text)) return slots[i];
  if (used == kSlots) return Overflow;
  // The resolver's string is scope-owned; slots keep a process-lifetime copy.
  const size_t size = strlen(text) + 1;
  char* copy = static_cast<char*>(malloc(size));
  if (!copy) return Overflow;
  memcpy(copy, text, size);
  names[used] = copy;
  return slots[used++];
}
}
