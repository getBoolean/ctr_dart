#include "lifecycle.h"
namespace ctr {
void Runner::Notify() { Lock guard(lock_); ++pending_; changed_.Signal(); }
void Runner::RequestStop() { Lock guard(lock_); stop_ = true; changed_.Signal(); }
void Runner::Fail() { Lock guard(lock_); failed_ = true; changed_.Signal(); }
Outcome Runner::Run(Application& app) {
  Outcome result = Outcome::pass;
  if (!app.Bootstrap()) result = Outcome::fail;
  while (result == Outcome::pass) {
    {
      Lock guard(lock_);
      if (failed_) { result = Outcome::fail; break; }
      if (stop_) { result = Outcome::incomplete; break; }
    }
    if (!app.HasLivePorts()) break;
    {
      Lock guard(lock_);
      while (pending_ == 0 && !stop_ && !failed_) changed_.Wait(lock_);
      if (stop_ || failed_) continue;
      --pending_;
    }
    if (!app.HandleMessage()) result = Outcome::fail;
  }
  Shutdown(app);
  return result;
}
void Runner::Shutdown(Application& app) {
  if (shutdown_) return;
  app.StopTimers();
  app.ShutdownIsolate();
  shutdown_ = true;
}
}
