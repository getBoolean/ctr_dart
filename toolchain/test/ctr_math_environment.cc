// Single-threaded errno storage for freestanding QEMU math fixtures.
// An unexpected abort exits with failure; no console service is implemented.
extern "C" int* __errno() {
  static int value;
  return &value;
}

extern "C" __attribute__((noreturn)) void abort() {
  register unsigned code asm("r0") = 99;
  register unsigned number asm("r7") = 1;
  asm volatile("svc 0" : : "r"(code), "r"(number) : "memory");
  __builtin_unreachable();
}
