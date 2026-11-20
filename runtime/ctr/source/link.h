#ifndef CTR_LINK_H_
#define CTR_LINK_H_
#include <cstddef>
#include <cstdint>
#include <string>
namespace ctr {
// Byte stream that receives CTR_RUNTIME record lines next to stdout and the journal.
class Sink {
 public:
  virtual bool Write(const char* data, size_t size) = 0;
 protected:
  ~Sink() = default;
};
// TCP connection to the host that started the run (KTD5). On CTR it owns the
// soc:U service and its 1 MiB buffer from Open until Close.
class Link final : public Sink {
 public:
  ~Link() { Close(); }
  bool Open(const uint8_t address[4], uint16_t port, std::string* error);
  bool Write(const char* data, size_t size) override;
  void Close();
 private:
  int socket_ = -1;
  uint32_t* buffer_ = nullptr;
};
}
#endif
