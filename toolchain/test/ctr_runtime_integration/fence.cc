#include "platform/globals.h"
#include "platform/atomic.h"

extern "C" void publish(int* data, int* ready) {
  *data = 42;
  dart::StoreStoreFence();
  *ready = 1;
  // The compiler must retain the pre-fence store even with a later overwrite.
  *data = 43;
}
