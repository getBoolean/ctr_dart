#ifndef CTR_REPORT_H_
#define CTR_REPORT_H_
#include "lifecycle.h"
#include <cstdio>
#include <string>
namespace ctr {
struct BuildIdentity {
  const char* fixture;
  const char* mode;
  const char* compatibility;
  const char* build_id;
};
class Report {
 public:
  ~Report();
  bool Begin(FILE* config, FILE* journal, const BuildIdentity& build);
  void Output(const char* text);
  Outcome End(Outcome execution, bool cleanup);
 private:
  void Emit(const std::string& record);
  FILE* journal_ = nullptr;  // Borrowed; launcher closes after VM cleanup.
  std::string run_;
  bool active_ = false, ended_ = false, failed_ = false;
};
}
#endif
