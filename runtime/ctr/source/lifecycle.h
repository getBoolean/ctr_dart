#ifndef CTR_LIFECYCLE_H_
#define CTR_LIFECYCLE_H_
#include "sync.h"
namespace ctr {
enum class Outcome { pass, fail, incomplete };
struct Application {
  virtual ~Application() = default;
  virtual bool Bootstrap() = 0;
  virtual bool HasLivePorts() = 0;
  virtual bool HandleMessage() = 0;
  virtual void StopTimers() = 0;
  virtual void ShutdownIsolate() = 0;
};
class Runner {
 public:
  void Notify();
  void RequestStop();
  void Fail();
  Outcome Run(Application& application);
  void Shutdown(Application& application);
 private:
  Mutex lock_;
  Condition changed_;
  uint64_t pending_ = 0;
  bool stop_ = false, failed_ = false, shutdown_ = false;
};
}
#endif
