#ifndef CTR_TIMER_WORKER_H_
#define CTR_TIMER_WORKER_H_
#include "sync.h"
namespace ctr {
struct TimerTransport {
  virtual ~TimerTransport() = default;
  virtual int64_t Now() = 0;
  virtual bool Post(int64_t port) = 0;
  virtual void Failed() = 0;
};
class TimerWorker {
 public:
  explicit TimerWorker(TimerTransport& transport) : transport_(transport) {}
  ~TimerWorker() { Stop(); }
  bool Start();
  bool Schedule(int64_t port, int64_t deadline);
  void Stop();
 private:
  static void Entry(void* self);
  void Run();
  TimerTransport& transport_;
  Mutex lock_;
  Condition changed_;
  Worker worker_;
  bool started_ = false, stopping_ = false;
  int64_t port_ = 0, deadline_ = -1;
};
}
#endif
