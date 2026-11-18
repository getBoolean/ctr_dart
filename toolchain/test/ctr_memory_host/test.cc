#include "vm/virtual_memory.h"
#include "vm/cpu_cache_ctr.h"
#include <3ds.h>
#include <cassert>
#include <cstdio>
#include <cstdlib>
#include <cstring>
#include <map>
#include <stdexcept>
#include <string>
#include <vector>
#include <sys/wait.h>
#include <unistd.h>

// Inject at libc/libctru boundaries; compile the real SDK implementations.
static std::map<void*, size_t> allocations;
static void* last_allocation;
static size_t last_extent;
static int releases, duplicates, closes, cache_calls;
static bool cache_ready;
static bool fail_allocation;
static int releases_before_death;
static std::string failure;
struct Protection { u32 address, size, mode; bool process; };
static std::vector<Protection> protections;
// Separate kernel regions may have identical permissions and memory state.
// Model one-page regions so crossing a boundary is always exercised.
static std::map<u32, u32> page_permissions;
extern "C" void* __real_memalign(size_t, size_t);
extern "C" void __real_free(void*);
extern "C" void* __wrap_memalign(size_t alignment, size_t size) {
  if (fail_allocation) return nullptr;
  void* p = __real_memalign(alignment, size);
  assert(p);
  memset(p, 0xa5, size);
  allocations[p] = size;
  for (size_t offset = 0; offset < size; offset += 4096) {
    page_permissions[static_cast<u32>(reinterpret_cast<uintptr_t>(p)) + offset] = MEMPERM_READWRITE;
  }
  last_allocation = p;
  last_extent = size;
  return p;
}
extern "C" void __wrap_free(void* p) {
  auto it = allocations.find(p);
  if (it != allocations.end()) {
    // Owned extent must be writable again before the allocator reuses it.
    for (size_t offset = 0; offset < it->second; offset += 4096) {
      u32 page = static_cast<u32>(reinterpret_cast<uintptr_t>(p)) + offset;
      assert(page_permissions.at(page) == MEMPERM_READWRITE);
      page_permissions.erase(page);
    }
    allocations.erase(it);
    releases++;
  }
  __real_free(p);
}
Result svcControlMemory(u32* out, u32 address, u32 other, u32 size,
                        MemOp op, MemPerm mode) {
  assert(other == 0 && op == MEMOP_PROT);
  *out = address;
  protections.push_back({address, size, static_cast<u32>(mode), false});
  return failure == "protect" ? -11 : 0;
}
Result svcQueryMemory(MemInfo* memory, PageInfo* page, u32 address) {
  if (failure == "query") return -17;
  const u32 base = address & ~4095u;
  auto found = page_permissions.find(base);
  *memory = {base, failure == "bad-query-range" ? 0u : 4096u,
             found == page_permissions.end() ? 0u : found->second,
             found == page_permissions.end() || failure == "unmapped" ? 0u : 5u};
  *page = {};
  return 0;
}
Result svcDuplicateHandle(Handle* out, Handle process) {
  assert(process == CUR_PROCESS_HANDLE);
  duplicates++;
  *out = 17;
  return failure == "duplicate" ? -12 : 0;
}
Result svcCloseHandle(Handle handle) {
  assert(handle == 17);
  closes++;
  return failure == "close" ? -13 : 0;
}
Result svcControlProcessMemory(Handle handle, u32 address, u32 other,
                               u32 size, u32 op, u32 mode) {
  assert(handle == 17 && other == 0 && op == MEMOP_PROT);
  // Reproduce the hardware rejection of an unnecessary protection request,
  // and reject ranges spanning independently queried kernel regions.
  if (size != 4096 || page_permissions.at(address) == mode) {
    return static_cast<Result>(0xd900060cu);
  }
  // Copy-to-executable paths (including VM callback trampolines) do not all
  // call CPU::FlushICache. Executable protection must publish their bytes too.
  if (mode & MEMPERM_EXECUTE) {
    assert(cache_ready);
  }
  protections.push_back({address, size, mode, true});
  if (failure == "execute" || (failure == "protect" && !(mode & MEMPERM_EXECUTE))) return -14;
  page_permissions.at(address) = mode;
  return 0;
}
Result svcGetSystemInfo(s64* version, u32 type, int param) {
  assert(type == 0x10000 && param == 0);
  *version = failure == "no-extension" ? 0 : 1;
  return failure == "detect" ? -15 : 0;
}
extern "C" int32_t DartCtrFlushEntireCache() {
  cache_calls++;
  cache_ready = failure != "cache";
  return failure == "cache" ? -16 : 0;
}
namespace dart {
bool FLAG_write_protect_code = true;
void Assert::Fail(const char* format, ...) const {
  char message[1024];
  va_list args;
  va_start(args, format);
  vsnprintf(message, sizeof(message), format, args);
  va_end(args);
  throw std::runtime_error(message);
}
}  // namespace dart

int main() {
  using namespace dart;
  VirtualMemory::Init();
  assert(VirtualMemory::PageSize() == 4096);
  for (int i = 0; i < 128; i++) {
    auto* adjacent = VirtualMemory::Allocate(4096, false, "adjacent");
    memset(adjacent->address(), 0x39, 4096);
    auto* memory = VirtualMemory::AllocateAligned(12288, 65536, false, "aligned");
    assert(memory && memory->start() % 65536 == 0 && memory->size() == 12288);
    void* original = last_allocation;
    size_t extent = last_extent;
    assert(extent >= 12288);
    for (int n = 0; n < 12288; n++) assert(static_cast<char*>(memory->address())[n] == 0);
    memory->Truncate(i % 2 ? 0 : 4096);
    delete memory;
    assert(allocations.count(original) == 0);
    assert(protections.empty());  // Entire original extent was already RW.
    for (int n = 0; n < 4096; n++) assert(static_cast<char*>(adjacent->address())[n] == 0x39);
    delete adjacent;
    assert(allocations.empty());
  }
  auto* ordinary = VirtualMemory::Allocate(12288, false, "truncate-whole");
  ordinary->Truncate(4096);
  ordinary->Protect(VirtualMemory::kReadOnly);
  delete ordinary;
  assert(allocations.empty());  // Wrapper validated RW across the original extent.
  alignas(4096) static char image[8192];
  int before_free = releases;
  auto before_protect = protections.size();
  auto* wrapper = VirtualMemory::ForImagePage(image, sizeof(image));
  assert(!wrapper->vm_owns_region());
  delete wrapper;
  assert(releases == before_free && protections.size() == before_protect);
  fail_allocation = true;
  assert(VirtualMemory::Allocate(4096, false, "oom") == nullptr);
  fail_allocation = false;
  // Reclamation is a hint: it must not unmap or overwrite live heap/image data.
  image[0] = 42;
  VirtualMemory::DontNeed(image, sizeof(image));
  assert(image[0] == 42 && protections.size() == before_protect);
  FLAG_write_protect_code = false;
  auto* writable_code = VirtualMemory::Allocate(4096, true, "rwx");
  assert(protections.back().mode == 7 && protections.back().process);
  // Hardware regression: freeing process-protected code must restore RW via
  // the process service before libc may reuse the complete original extent.
  delete writable_code;
  assert(protections.back().process && protections.back().mode == MEMPERM_READWRITE);
  FLAG_write_protect_code = true;
  auto before_code = protections.size();
  auto* code = VirtualMemory::Allocate(8192, true, "code");
  assert(protections.size() == before_code);  // Starts RW with write protection enabled.
  cache_ready = false;
  code->WriteProtectCode();
  assert(protections.back().process);
  assert(protections.back().mode == (MEMPERM_READ | MEMPERM_EXECUTE));
  assert(duplicates == closes && duplicates > 0);
  VirtualMemory::Protect(reinterpret_cast<void*>(code->start() + 17), 4096,
                         VirtualMemory::kReadOnly);
  assert(protections.back().address == static_cast<u32>(code->start() + 4096));
  assert(protections.back().size == 4096);
  assert(page_permissions.at(static_cast<u32>(code->start())) == MEMPERM_READ);
  assert(page_permissions.at(static_cast<u32>(code->start() + 4096)) == MEMPERM_READ);
  for (auto mode : {VirtualMemory::kNoAccess, VirtualMemory::kReadOnly,
                    VirtualMemory::kReadWrite, VirtualMemory::kReadExecute,
                    VirtualMemory::kReadWriteExecute}) {
    code->Protect(mode);
    auto actual = protections.back().mode;
    assert(actual == (mode == VirtualMemory::kNoAccess ? 0u :
                     mode == VirtualMemory::kReadOnly ? 1u :
                     mode == VirtualMemory::kReadWrite ? 3u :
                     mode == VirtualMemory::kReadExecute ? 5u : 7u));
  }
  auto unchanged = protections.size();
  auto unchanged_cache = cache_calls;
  code->Protect(VirtualMemory::kReadWriteExecute);
  assert(protections.size() == unchanged);  // Cache publication still runs.
  assert(cache_calls == unchanged_cache + 1);
  for (const char* error : {"protect", "duplicate", "execute", "close",
                            "query", "unmapped", "bad-query-range"}) {
    failure.clear();
    code->Protect(VirtualMemory::kReadWrite);
    failure = error;
    bool returned = false;
    try {
      code->Protect(failure == "protect" ? VirtualMemory::kReadOnly
                                         : VirtualMemory::kReadExecute);
      returned = true;  // Caller could execute if this wrongly succeeds.
    } catch (const std::runtime_error& error) {
      assert(strstr(error.what(), "CTR") != nullptr);
    }
    assert(!returned);
  }
  failure.clear();
  int before_cache = cache_calls;
  CtrFlushICache(code->start(), 8);
  assert(cache_calls == before_cache + 1);
  CtrFlushICache(code->start(), 0);
  assert(cache_calls == before_cache + 1);
  for (const char* error : {"detect", "no-extension", "cache"}) {
    failure = error;
    bool returned = false;
    int before = cache_calls;
    try { CtrFlushICache(code->start(), 8); returned = true; }
    catch (const std::runtime_error&) {}
    assert(!returned);
    assert(cache_calls == before + (failure == "cache" ? 1 : 0));
  }
  failure = "cache";
  auto before_permissions = protections.size();
  bool published = false;
  try { code->WriteProtectCode(); published = true; }
  catch (const std::runtime_error&) {}
  assert(!published && protections.size() == before_permissions);
  failure.clear();
  code->WriteProtectCode();  // Restoration must require an actual RX-to-RW change.
  pid_t child = fork();
  assert(child >= 0);
  if (child == 0) {
    failure = "protect";
    releases_before_death = releases;
    std::set_terminate([] {
      assert(allocations.size() == 1 && releases == releases_before_death);
      _Exit(71);
    });
    delete code;  // The noexcept destructor must stop before free on failure.
    _Exit(72);
  }
  int status;
  assert(waitpid(child, &status, 0) == child);
  assert(WIFEXITED(status) && WEXITSTATUS(status) == 71);
  delete code;
  assert(allocations.empty());
  VirtualMemory::Cleanup();
  puts("CTR memory adapter: 128 allocation cycles, images, protection/cache errors passed (host only)");
}
