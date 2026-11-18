// Host-only service boundary. No ARM instructions or kernel behavior is modeled.
#pragma once
#include <cstdint>
using u32 = uint32_t;
using s64 = int64_t;
using Handle = u32;
using Result = int32_t;
struct MemInfo { u32 base_addr, size, perm, state; };
struct PageInfo { u32 flags; };
enum MemOp { MEMOP_PROT = 6 };
enum MemPerm {
  MEMPERM_READ = 1, MEMPERM_WRITE = 2,
  MEMPERM_EXECUTE = 4, MEMPERM_READWRITE = 3
};
constexpr Handle CUR_PROCESS_HANDLE = 0xffff8001;
#define R_FAILED(result) ((result) < 0)
#define R_SUCCEEDED(result) ((result) >= 0)
Result svcControlMemory(u32*, u32, u32, u32, MemOp, MemPerm);
Result svcControlProcessMemory(Handle, u32, u32, u32, u32, u32);
Result svcDuplicateHandle(Handle*, Handle);
Result svcCloseHandle(Handle);
Result svcGetSystemInfo(s64*, u32, int);
Result svcQueryMemory(MemInfo*, PageInfo*, u32);
