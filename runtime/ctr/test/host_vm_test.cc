// Host integration driver: real VM, real SDK hooks, real native timer messages.
// It is not a console launcher or an additional curated acceptance program.
#include "embedder.h"
#include <cassert>
#include <cstdio>
#include <cstdlib>
#include <fstream>
#include <iterator>
#include <thread>
#include <vector>

int main(int argc, char** argv) {
  assert(argc == 4 || argc == 5);
  std::ifstream file(argv[1], std::ios::binary);
  std::vector<uint8_t> kernel((std::istreambuf_iterator<char>(file)), {});
  assert(!kernel.empty());
  FILE* config = fopen(argv[2], "r");
  FILE* journal = fopen(argv[3], "a");
  std::string hash(64, 'a');
  ctr::Program program = {nullptr, nullptr, kernel.data(),
      static_cast<intptr_t>(kernel.size()), {"async", "jit", hash.c_str(), hash.c_str()}};
  ctr::Runner runner;
  ctr::Report report;
  assert(report.Begin(config, journal, program.build));
  fclose(config);
  char* error = Dart_SetVMFlags(0, nullptr);
  if (error) { fprintf(stderr, "%s\n", error); free(error); return 1; }
  Dart_InitializeParams params = {};
  params.version = DART_INITIALIZE_PARAMS_CURRENT_VERSION;
  error = Dart_Initialize(&params);
  if (error) { fprintf(stderr, "%s\n", error); free(error); return 1; }
  std::thread stop;
  if (argc == 5) stop = std::thread([&] { getchar(); runner.RequestStop(); });
  ctr::Outcome result;
  std::thread owner([&] {
    ctr::Embedder application(program, runner, report);
    result = runner.Run(application);
  });
  owner.join();
  if (stop.joinable()) stop.join();
  error = Dart_Cleanup();
  if (error) report.Output(error);
  result = report.End(result, error == nullptr);
  free(error);
  assert(fclose(journal) == 0);
  return result == ctr::Outcome::pass ? 0 : result == ctr::Outcome::incomplete ? 2 : 1;
}
