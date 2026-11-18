#include "report.h"
#include <cstring>
namespace ctr {
static std::string Quote(const std::string& text) {
  std::string out = "\"";
  const char* hex = "0123456789abcdef";
  for (unsigned char c : text) {
    if (c == '"' || c == '\\') { out += '\\'; out += c; }
    else if (c < 32) { out += "\\u00"; out += hex[c >> 4]; out += hex[c & 15]; }
    else out += c;
  }
  return out + '"';
}
static bool Hex(const std::string& text, size_t size) {
  return text.size() == size && text.find_first_not_of("0123456789abcdef") == std::string::npos;
}
Report::~Report() = default;
void Report::Emit(const std::string& record) {
  if (fprintf(stdout, "CTR_RUNTIME %s\n", record.c_str()) < 0 || fflush(stdout)) failed_ = true;
  if (fprintf(journal_, "CTR_RUNTIME %s\n", record.c_str()) < 0 || fflush(journal_)) failed_ = true;
}
bool Report::Begin(FILE* config, FILE* journal, const BuildIdentity& build) {
  if (active_ || !config || !journal) return false;
  const char* keys[] = {"schema", "run_id", "fixture", "mode", "compatibility",
                        "artifact_sha256", "build_id", "environment"};
  std::string values[8];
  char line[192];
  for (unsigned i = 0; i < 8; ++i) {
    if (!fgets(line, sizeof(line), config) || !strchr(line, '\n')) return false;
    line[strcspn(line, "\r\n")] = 0;
    char* value = strchr(line, '=');
    if (!value) return false;
    *value++ = 0;
    if (strcmp(line, keys[i])) return false;
    values[i] = value;
  }
  if (fgets(line, sizeof(line), config) || ferror(config)) return false;
  if (values[0] != "1" || !Hex(values[1], 32) ||
      values[2] != build.fixture || values[3] != build.mode ||
      values[4] != build.compatibility || !Hex(values[4], 64) ||
      !Hex(values[5], 64) || values[6] != build.build_id || !Hex(values[6], 64) ||
      (values[7] != "hardware" && values[7] != "azahar" && values[7] != "host")) return false;
  if (values[3] != "aot" && values[3] != "jit") return false;
  journal_ = journal;
  run_ = values[1];
  active_ = true;
  std::string begin = "{\"event\":\"begin\",\"schema\":1";
  for (unsigned i = 1; i < 8; ++i) begin += "," + Quote(keys[i]) + ":" + Quote(values[i]);
  Emit(begin + "}");
  return !failed_;
}
void Report::Output(const char* text) {
  if (!active_ || ended_) { failed_ = true; return; }
  Emit("{\"event\":\"output\",\"run_id\":" + Quote(run_) + ",\"text\":" + Quote(text) + "}");
}
Outcome Report::End(Outcome execution, bool cleanup) {
  if (!active_ || ended_) return Outcome::fail;
  if (!cleanup || failed_) execution = Outcome::fail;
  const char* outcome = execution == Outcome::pass ? "pass" : execution == Outcome::fail ? "fail" : "incomplete";
  Emit("{\"event\":\"assert\",\"run_id\":" + Quote(run_) +
       ",\"name\":\"cleanup\",\"status\":" + Quote(cleanup ? "pass" : "fail") + "}");
  if (failed_) { execution = Outcome::fail; outcome = "fail"; }
  Emit("{\"event\":\"terminal\",\"run_id\":" + Quote(run_) + ",\"outcome\":" + Quote(outcome) + ",\"assertions\":1}");
  ended_ = true;
  return failed_ ? Outcome::fail : execution;
}
}
