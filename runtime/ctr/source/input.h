#ifndef CTR_INPUT_H_
#define CTR_INPUT_H_
#include <3ds.h>

namespace ctr {
// Own one checked reference independently of libctru's unchecked CRT startup.
class Input {
 public:
  ~Input() { Stop(); }
  Input() = default;
  Input(const Input&) = delete;
  Input& operator=(const Input&) = delete;
  bool Start() {
    if (!owned_) {
      status_ = hidInit();
      // libctru can fail IRRST initialization after mapping base HID. Balance
      // that partially initialized reference too, while reporting failure.
      owned_ = R_SUCCEEDED(status_) || hidSharedMem != nullptr;
    }
    return owned_ && R_SUCCEEDED(status_) && hidSharedMem != nullptr;
  }
  Result status() const { return status_; }
  bool Poll(u32* keys) {
    if (!owned_ || !R_SUCCEEDED(status_) || !hidSharedMem) return false;
    hidScanInput();
    *keys = hidKeysDown();
    return true;
  }
  void Stop() {
    if (owned_) { owned_ = false; hidExit(); }
  }
 private:
  Result status_ = -1;
  bool owned_ = false;
};
}
#endif
