#ifndef CTR_UNSUPPORTED_H_
#define CTR_UNSUPPORTED_H_
#include "dart_api.h"
namespace ctr {
// Native resolver for dart:io, which has no CTR implementation. Every name
// resolves, so the VM never aborts on a missing native (AOT links natives at
// first call); calling one throws a catchable UnsupportedError whose message
// is "<NativeName> is not supported on CTR (dart:io)". Resolution never throws.
Dart_NativeFunction ResolveUnsupported(Dart_Handle name, int argc, bool* scope);
}
#endif
