// Public entries use the CTR hard-float ABI. Every private import explicitly
// uses base AAPCS, matching the pinned software-float newlib archive.
#define UNARY(Name, Target)                                                   \
  extern "C" double ctr_soft_##Target(double) __attribute__((pcs("aapcs")));   \
  extern "C" double CtrLibm##Name(double value) {                             \
    return ctr_soft_##Target(value);                                         \
  }
#define BINARY(Name, Target)                                                  \
  extern "C" double ctr_soft_##Target(double, double)                         \
      __attribute__((pcs("aapcs")));                                         \
  extern "C" double CtrLibm##Name(double left, double right) {                 \
    return ctr_soft_##Target(left, right);                                   \
  }

BINARY(Pow, __ieee754_pow)
BINARY(Atan2, __ieee754_atan2)
UNARY(Sin, sin)
UNARY(Cos, cos)
UNARY(Tan, tan)
UNARY(Asin, __ieee754_asin)
UNARY(Acos, __ieee754_acos)
UNARY(Atan, atan)
UNARY(Exp, __ieee754_exp)
UNARY(Log, __ieee754_log)
UNARY(Floor, floor)
UNARY(Ceil, ceil)
UNARY(Trunc, trunc)
UNARY(Round, round)

#undef BINARY
#undef UNARY
