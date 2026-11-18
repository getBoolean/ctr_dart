#pragma once
#include <cstdint>
using u32 = uint32_t;
using Result = int32_t;
using vu32 = volatile u32;
#define R_SUCCEEDED(result) ((result) >= 0)
extern vu32* hidSharedMem;
Result hidInit();
void hidExit();
void hidScanInput();
u32 hidKeysDown();
