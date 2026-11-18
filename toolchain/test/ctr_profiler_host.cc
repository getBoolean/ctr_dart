// Focused execution of the SDK's lifecycle and disabled-service function bodies.
// These doubles test control flow; they do not represent CTR runtime execution.
#include <cassert>
#include <cstdint>
#include <cstring>
#define ASSERT assert
#if defined(DART_PRECOMPILED_RUNTIME)
#define NOT_IN_PRECOMPILED(x)
#else
#define NOT_IN_PRECOMPILED(x) x
#endif

struct SampleBlock {
  int completed = 0;
  void MarkCompleted() { ++completed; }
};
struct Isolate {
  SampleBlock* cpu = nullptr;
  SampleBlock* allocation = nullptr;
  int notifications = 0;
  SampleBlock* exchange_current_sample_block(SampleBlock* next) {
    auto old = cpu;
    cpu = next;
    return old;
  }
  SampleBlock* exchange_current_allocation_sample_block(SampleBlock* next) {
    auto old = allocation;
    allocation = next;
    return old;
  }
  void TrySetHasCompletedBlocks() { ++notifications; }
};
struct IsolateGroup {};
struct Profiler {
  static void IsolateShutdown(Isolate*);
  static void IsolateGroupShutdown(IsolateGroup*);
#if defined(SUPPORT_TIMELINE) && defined(SUPPORT_PERFETTO)
  struct Config { bool enabled; bool stream_to_timeline; };
  static Config config_;
#endif
};
struct Timeline {
  static int drains;
  static int notifications;
  static void DrainCompletedSampleBlocksIntoRecorder(Isolate*) { ++drains; }
  static void NotifyAboutIsolateGroupShutdown(IsolateGroup*) { ++notifications; }
};
int Timeline::drains = 0;
int Timeline::notifications = 0;
#if defined(SUPPORT_TIMELINE) && defined(SUPPORT_PERFETTO)
Profiler::Config Profiler::config_{true, true};
#endif
struct Thread {};
enum TimelineOrSamplesResponseFormat : bool { JSON = false, Perfetto = true };
constexpr int kFeatureDisabled = 100;
struct JSONStream {
  int errors = 0;
  void PrintError(int code, const char* message) {
    assert(code == kFeatureDisabled);
    assert(std::strcmp(message, "Profiler is disabled.") == 0);
    ++errors;
  }
};

// SDK_FUNCTIONS

int main() {
  SampleBlock cpu, allocation;
  Isolate isolate;
  isolate.cpu = &cpu;
  isolate.allocation = &allocation;
  Profiler::IsolateShutdown(&isolate);
  assert(isolate.cpu == nullptr && isolate.allocation == nullptr);
  assert(cpu.completed == 1 && allocation.completed == 1);
  assert(isolate.notifications == 1);
  Profiler::IsolateShutdown(&isolate);
  assert(isolate.notifications == 1);
  IsolateGroup group;
  Profiler::IsolateGroupShutdown(&group);
#if defined(SUPPORT_TIMELINE) && defined(SUPPORT_PERFETTO)
#if defined(DART_PRECOMPILED_RUNTIME)
  assert(Timeline::drains == 0);
#else
  assert(Timeline::drains == 2);
#endif
  assert(Timeline::notifications == 1);
  Profiler::config_.enabled = false;
  Profiler::IsolateGroupShutdown(&group);
  assert(Timeline::notifications == 1);
#else
  assert(Timeline::drains == 0 && Timeline::notifications == 0);
#endif
  JSONStream js;
  Thread thread;
  EnableProfiler(&thread, &js);
  ClearCpuSamples(&thread, &js);
  GetCpuSamplesCommon(JSON, &thread, &js);
  GetAllocationTraces(&thread, &js);
  SetTraceClassAllocation(&thread, &js);
  assert(js.errors == 5);
}
