#include "platform/utils.h"
#include <cstdio>
#include <cstdlib>
#include <cstring>

int main() {
  struct Case { const char* path; const char* expected; };
  const Case cases[] = {
      {"main.dart", "main.dart"}, {"sdmc:/app/main.dart", "main.dart"},
      {"/a/b///", "b"}, {"/", "/"}, {"////", "/"}, {"", "."},
      {".", "."}, {"..", ".."}, {"relative/dir///", "dir"},
      {"a//b", "b"}, {"///a///", "a"}, {"sdmc:/", "sdmc:"},
  };
  if (dart::Utils::Basename(nullptr) != nullptr) return 1;
  for (const auto& item : cases) {
    char* input = dart::Utils::StrDup(item.path);
    char* result = dart::Utils::Basename(input);
    if (!result || strcmp(result, item.expected) || strcmp(input, item.path)) {
      fprintf(stderr, "basename failed for '%s'\n", item.path);
      return 1;
    }
    free(input);
    if (strcmp(result, item.expected)) return 1;
    free(result);
  }
  puts("PASS basename values, immutable inputs and owned results");
}
