#include "timer_worker.h"
#include <algorithm>
#include <limits>
namespace ctr {
bool TimerWorker::Start() {
  Lock guard(lock_);
  if (started_) return true;
  stopping_ = false;
  deadline_ = -1;
  started_ = worker_.Start(Entry, this);
  return started_;
}
bool TimerWorker::Schedule(int64_t port, int64_t deadline) {
  Lock guard(lock_);
  if (!started_ || stopping_ || port <= 0 || deadline < -1) return false;
  port_ = port;
  deadline_ = deadline;
  changed_.Signal();
  return true;
}
void TimerWorker::Stop() {
  {
    Lock guard(lock_);
    stopping_ = true;
    deadline_ = -1;
    changed_.Signal();
  }
  worker_.Join();
  Lock guard(lock_);
  started_ = false;
  port_ = 0;
}
void TimerWorker::Entry(void* self) { static_cast<TimerWorker*>(self)->Run(); }
void TimerWorker::Run() {
  Lock guard(lock_);
  while (!stopping_) {
    if (deadline_ < 0) { changed_.Wait(lock_); continue; }
    int64_t now = transport_.Now();
    if (deadline_ > now) {
      // Bound conversion to relative nanoseconds without changing the deadline.
      const int64_t maximum = std::numeric_limits<int64_t>::max() / 1000000;
      changed_.Wait(lock_, std::min(deadline_ - now, maximum));
      continue;
    }
    const int64_t port = port_;
    deadline_ = -1;
    // Posting while locked makes cancellation/shutdown a publication barrier.
    if (!transport_.Post(port)) transport_.Failed();
  }
}
}
