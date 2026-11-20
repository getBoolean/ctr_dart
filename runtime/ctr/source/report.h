#ifndef CTR_REPORT_H_
#define CTR_REPORT_H_
#include "lifecycle.h"
#include "link.h"
#include "sync.h"
#include <cstdint>
#include <cstdio>
#include <string>
namespace ctr {
struct BuildIdentity {
  const char* fixture;
  const char* mode;
  const char* compatibility;
  const char* build_id;
};
// Run identity in record key order: schema, run_id, fixture, mode,
// compatibility, artifact_sha256, build_id, environment; plus the optional host.
struct RunConfig {
  std::string values[8];
  bool host = false;
  uint8_t address[4] = {};
  uint16_t port = 0;
};
// Reads sdmc:/ctr-runtime-run.cfg syntax: eight key lines, then for schema 2
// one optional host=<ipv4>:<port> line. Values are validated by Report::Begin.
bool ReadConfig(FILE* config, RunConfig* run);
enum class ArgIdentity { absent, ok, invalid };
// Reads netloader argv identity tokens (docs/runbooks/ctr-runtime.md). The
// host comes from the netloader address (libctru __3dslink_host, zero when
// absent) plus --ctr-host-port. Linked build values fill omitted keys.
ArgIdentity ReadArgs(int argc, char** argv, const BuildIdentity& build,
                     const uint8_t link_host[4], RunConfig* run);
class Report {
 public:
  ~Report();
  bool Begin(FILE* config, FILE* journal, const BuildIdentity& build);
  // A non-empty notice is emitted as the first output record after begin.
  bool Begin(const RunConfig& run, FILE* journal, const BuildIdentity& build,
             const std::string& notice = {});
  void Output(const char* text);
  Outcome End(Outcome execution, bool cleanup);
  // Records also go to the attached sink; a failed write detaches it.
  void Attach(Sink* sink);
  // Bare newline to the attached sink only, never stdout or the journal.
  void Keepalive();
 private:
  void Emit(const std::string& record);
  Mutex mutex_;  // Serializes every record and keepalive.
  Sink* sink_ = nullptr;
  FILE* journal_ = nullptr;  // Borrowed; launcher closes after VM cleanup.
  std::string run_;
  bool active_ = false, ended_ = false, failed_ = false;
};
}
#endif
