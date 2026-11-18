#include "lifecycle.h"
#include <cassert>
#include <vector>

struct VM : ctr::Application {
  bool bootstrap = true, live = true, error = false;
  int messages = 0;
  std::vector<int> cleanup;
  bool Bootstrap() override { return bootstrap; }
  bool HasLivePorts() override { return live; }
  bool HandleMessage() override {
    ++messages;
    if (messages == 2) live = false;
    return !error;
  }
  void StopTimers() override { cleanup.push_back(1); }
  void ShutdownIsolate() override { cleanup.push_back(2); }
};
int main() {
  ctr::Runner runner;
  VM vm;
  // Main returning is not a completion signal: the live port survives it.
  runner.Notify(); runner.Notify();
  assert(runner.Run(vm) == ctr::Outcome::pass);
  assert(vm.messages == 2);
  assert((vm.cleanup == std::vector<int>{1, 2}));
  runner.Shutdown(vm);
  assert(vm.cleanup.size() == 2);
  ctr::Runner failed;
  VM partial; partial.bootstrap = false;
  assert(failed.Run(partial) == ctr::Outcome::fail);
  assert((partial.cleanup == std::vector<int>{1, 2}));
  ctr::Runner uncaught;
  VM bad; bad.error = true; uncaught.Notify();
  assert(uncaught.Run(bad) == ctr::Outcome::fail);
  ctr::Runner stopped;
  VM periodic; stopped.RequestStop();
  assert(stopped.Run(periodic) == ctr::Outcome::incomplete);
  assert(periodic.messages == 0 && periodic.live);
}
