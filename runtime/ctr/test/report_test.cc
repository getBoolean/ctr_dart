#include "report.h"
#include <cassert>
#include <string>

int main() {
  std::string hash(64, 'a');
  std::string config_text = "schema=1\nrun_id=" + std::string(32, 'b') +
      "\nfixture=hello\nmode=jit\ncompatibility=" + hash + "\nartifact_sha256=" + hash +
      "\nbuild_id=" + hash + "\nenvironment=host\n";
  FILE* config = tmpfile();
  FILE* journal = tmpfile();
  assert(config && journal);
  assert(fputs(config_text.c_str(), config) >= 0);
  rewind(config);
  ctr::Report report;
  assert(report.Begin(config, journal, {"hello", "jit", hash.c_str(), hash.c_str()}));
  report.Output("quotes\" slash\\ and\nstack");
  assert(report.End(ctr::Outcome::pass, true) == ctr::Outcome::pass);
  long size = ftell(journal);
  assert(report.End(ctr::Outcome::pass, true) == ctr::Outcome::fail);
  assert(ftell(journal) == size);
  rewind(config);
  ctr::Report mismatch;
  assert(!mismatch.Begin(config, journal, {"hello", "aot", hash.c_str(), hash.c_str()}));
  fclose(config);
  fclose(journal);
}
