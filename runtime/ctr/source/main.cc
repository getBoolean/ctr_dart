#include <3ds.h>
#include <atomic>
#include <cstdlib>
#include <cstring>
#include "embedder.h"
#include "input.h"
#include "vm/os.h"
#include "vm/os_thread.h"

// Supplied by the AOT/JIT packaging layer. Linked image/kernel ownership remains
// with that layer until this launcher has joined the runner and cleaned the VM.
extern const ctr::Program ctr_program;
// Reserve real main-stack space for VM initialization; measure it on the device.
extern "C" { u32 __stacksize__ = 512 * 1024; }

namespace {
struct Run {
  ctr::Runner runner;
  ctr::Report report;
  ctr::Outcome outcome = ctr::Outcome::fail;
  std::atomic<bool> done{false};
  dart::ThreadJoinId join = dart::OSThread::kInvalidThreadJoinId;
};
void Execute(dart::uword parameter) {
  auto* run = reinterpret_cast<Run*>(parameter);
  run->join = dart::OSThread::GetCurrentThreadJoinId(dart::OSThread::Current());
  ctr::Embedder application(ctr_program, run->runner, run->report);
  run->outcome = run->runner.Run(application);
  run->done.store(true, std::memory_order_release);
}
bool Entropy(uint8_t* buffer, intptr_t length) {
  return dart::OS::GetEntropy(buffer, length);
}
}
int main() {
  gfxInitDefault();
  consoleInit(GFX_TOP, nullptr);
  Result filesystem = fsInit();
  if (R_FAILED(filesystem)) { gfxExit(); return 1; }
  Run run;
  FILE* config = fopen("sdmc:/ctr-runtime-run.cfg", "r");
  FILE* journal = fopen("sdmc:/ctr-runtime.log", "a");
  bool began = run.report.Begin(config, journal, ctr_program.build);
  if (config) fclose(config);
  bool initialized = false, cleanup = true;
  ctr::Input input;
  if (began) {
    const bool input_ready = input.Start();
    if (!input_ready) {
      char message[160];
      snprintf(message, sizeof(message),
               "CTR input initialization failed: result=0x%08x shared_memory=%p",
               static_cast<unsigned int>(input.status()),
               static_cast<void*>(const_cast<u32*>(hidSharedMem)));
      run.report.Output(message);
    }
    const bool precompiled = Dart_IsPrecompiledRuntime();
    bool mode = !strcmp(ctr_program.build.mode, precompiled ? "aot" : "jit");
    // Match the SDK AOT launcher: stack walking and native linking use this mode.
    const char* aot_flags[] = {"--precompilation"};
    char* error = mode && input_ready ? Dart_SetVMFlags(precompiled ? 1 : 0,
                                        precompiled ? aot_flags : nullptr) : nullptr;
    if (!mode) run.report.Output("artifact mode differs from linked runtime");
    if (error) { run.report.Output(error); free(error); }
    else if (mode && input_ready) {
      Dart_InitializeParams params = {};
      params.version = DART_INITIALIZE_PARAMS_CURRENT_VERSION;
      params.entropy_source = Entropy;
      // No service/kernel isolate, dart:io bootstrap, or executable-page probe.
      error = Dart_Initialize(&params);
      if (error) { run.report.Output(error); free(error); }
      else initialized = true;
    }
    if (initialized) {
      if (dart::OSThread::TryStart("CTR application", Execute,
                                  reinterpret_cast<dart::uword>(&run)) != 0) {
        run.report.Output("application runner creation failed");
      } else {
        bool input_lost = false;
        while (!run.done.load(std::memory_order_acquire)) {
          if (!aptMainLoop()) run.runner.RequestStop();
          else if (!input_lost) {
            u32 keys = 0;
            if (!input.Poll(&keys)) {
              input_lost = true;
              cleanup = false;
              run.runner.Fail();
            } else if (keys & KEY_START) run.runner.RequestStop();
          }
          gspWaitForVBlank();
        }
        dart::OSThread::Join(run.join);
        if (input_lost)
          run.report.Output("CTR input shared memory became unavailable");
      }
      error = Dart_Cleanup();
      if (error) { cleanup = false; run.report.Output(error); free(error); }
    }
    input.Stop();
    run.outcome = run.report.End(run.outcome, cleanup);
  }
  if (journal && fclose(journal)) run.outcome = ctr::Outcome::fail;
  fsExit();
  gfxExit();
  return began && run.outcome == ctr::Outcome::pass ? 0 : 1;
}
