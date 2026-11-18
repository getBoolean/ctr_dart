#include "timer_worker.h"
#include <cassert>
#include <condition_variable>
#include <mutex>
#include <vector>

struct Transport : ctr::TimerTransport {
  std::mutex lock;
  std::condition_variable changed;
  int64_t now = 0;
  std::vector<int64_t> delivered;
  bool succeeds = true, failed = false;
  int64_t Now() override { return now; }
  bool Post(int64_t port) override {
    std::lock_guard<std::mutex> guard(lock);
    delivered.push_back(port);
    changed.notify_all();
    return succeeds;
  }
  void Failed() override {
    std::lock_guard<std::mutex> guard(lock);
    failed = true;
    changed.notify_all();
  }
  void Await(size_t count) {
    std::unique_lock<std::mutex> guard(lock);
    changed.wait(guard, [&] { return delivered.size() == count; });
  }
};

int main() {
  Transport transport;
  ctr::TimerWorker worker(transport);
  assert(worker.Start());
  // An earlier rearm replaces the old deadline, rather than appending work.
  worker.Schedule(10, 1000000);
  worker.Schedule(11, 0);
  transport.Await(1);
  assert(transport.delivered == std::vector<int64_t>{11});
  // Cancellation removes the only pending native wakeup.
  worker.Schedule(12, 1000000);
  worker.Schedule(12, -1);
  worker.Stop();
  worker.Stop();
  assert(transport.delivered == std::vector<int64_t>{11});
  // A fresh worker has no inherited pending port or deadline.
  assert(worker.Start());
  worker.Schedule(13, 0);
  transport.Await(2);
  worker.Stop();
  assert((transport.delivered == std::vector<int64_t>{11, 13}));
  transport.succeeds = false;
  assert(worker.Start());
  worker.Schedule(14, 0);
  {
    std::unique_lock<std::mutex> guard(transport.lock);
    transport.changed.wait(guard, [&] { return transport.failed; });
  }
  worker.Stop();
}
