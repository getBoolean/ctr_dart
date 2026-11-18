#include "input.h"
#include <cassert>

static u32 shared[256];
vu32* hidSharedMem = nullptr;
static Result result;
static bool missing_mapping, partial;
static int references, starts, stops, scans;
Result hidInit() {
  ++starts;
  if (R_SUCCEEDED(result) || partial) {
    ++references;
    hidSharedMem = missing_mapping ? nullptr : shared;
  }
  return result;
}
void hidExit() {
  assert(references > 0);
  --references;
  ++stops;
  if (references == 0) hidSharedMem = nullptr;
}
void hidScanInput() { assert(hidSharedMem && references > 0); ++scans; }
u32 hidKeysDown() { return 8; }
int main() {
  u32 keys = 0;
  // A CRT-owned service reference must survive the launcher's own lifetime.
  references = 1;
  hidSharedMem = shared;
  {
    ctr::Input input;
    assert(input.Start() && input.status() == 0 && references == 2);
    assert(input.Start() && starts == 1 && references == 2);
    assert(input.Poll(&keys) && keys == 8 && scans == 1);
    input.Stop();
    assert(references == 1 && stops == 1);
  }
  assert(references == 1 && stops == 1);
  references = 0;
  hidSharedMem = nullptr;
  result = -42;
  {
    ctr::Input input;
    assert(!input.Start() && input.status() == -42);
    assert(!input.Poll(&keys) && scans == 1);
  }
  assert(references == 0 && stops == 1);
  result = 0;
  missing_mapping = true;
  {
    ctr::Input input;
    assert(!input.Start());
    assert(!input.Poll(&keys) && scans == 1);
  }
  assert(references == 0 && stops == 2);
  missing_mapping = false;
  partial = true;
  result = -43;
  {
    ctr::Input input;
    assert(!input.Start());
    assert(!input.Poll(&keys) && scans == 1);
  }
  assert(references == 0 && stops == 3);
  partial = false;
  result = 0;
  {
    ctr::Input input;
    assert(input.Start());
    hidSharedMem = nullptr;
    assert(!input.Poll(&keys) && scans == 1);
  }
  assert(references == 0 && stops == 4);
}
