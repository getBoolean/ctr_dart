"""High-precision reference corpus for CTR math; importing performs no work."""
import ctypes as c
import math
import random
import sys

from test_ctr_double import bits, number

NAMES = ('Pow', 'Sin', 'Log', 'Atan2', 'Cos', 'Tan', 'Asin', 'Acos', 'Atan',
         'Exp', 'Floor', 'Ceil', 'Trunc', 'Round')


class Float(c.Structure):
    _fields_ = [('precision', c.c_long), ('sign', c.c_int), ('exponent', c.c_long),
                ('limbs', c.POINTER(c.c_ulong))]


class Reference:
    def __init__(self):
        self.library = c.CDLL('libmpfr.so.6')
        lib, pointer = self.library, c.POINTER(Float)
        lib.mpfr_init2.argtypes = [pointer, c.c_long]
        lib.mpfr_clear.argtypes = [pointer]
        lib.mpfr_set_d.argtypes = [pointer, c.c_double, c.c_int]
        lib.mpfr_get_d.argtypes = [pointer, c.c_int]
        lib.mpfr_get_d.restype = c.c_double
        lib.mpfr_get_version.restype = c.c_char_p
        self.version = lib.mpfr_get_version().decode()
        for i, name in enumerate(NAMES):
            args = [pointer, pointer]
            if i in (0, 3):
                args.append(pointer)
            if i < 10:
                args.append(c.c_int)
            getattr(lib, 'mpfr_' + name.lower()).argtypes = args

    def evaluate(self, op, x, y, precision):
        a, b, result = Float(), Float(), Float()
        lib = self.library
        for value in (a, b, result):
            lib.mpfr_init2(c.byref(value), precision)
        try:
            lib.mpfr_set_d(c.byref(a), number(x), 0)
            lib.mpfr_set_d(c.byref(b), number(y), 0)
            args = [c.byref(result), c.byref(a)]
            if op in (0, 3):
                args.append(c.byref(b))
            if op < 10:
                args.append(0)  # MPFR_RNDN; integral-rounding functions have fixed rules.
            getattr(lib, 'mpfr_' + NAMES[op].lower())(*args)
            value = lib.mpfr_get_d(c.byref(result), 0)
            return 0x7ff8000000000000 if math.isnan(value) else bits(value)
        finally:
            for value in (a, b, result):
                lib.mpfr_clear(c.byref(value))


def cases():
    reference = Reference()
    edges = [0, 1, 2, 3, 0x000fffffffffffff, 0x0010000000000000,
             bits(0.5), bits(1), bits(2), bits(3), bits(math.pi), bits(709), bits(745),
             0x7fefffffffffffff, 0x7ff0000000000000, 0x7ff0000000000001, 0x7ff8000000000001]
    for value in (1.0, 0.5, math.log(math.ulp(0.0)), math.log(sys.float_info.max), math.pi / 2):
        edges += [bits(math.nextafter(value, direction)) for direction in (-math.inf, math.inf)]
    edges += [value | (1 << 63) for value in list(edges)]
    edges = sorted(set(edges))
    rng = random.Random(0x414c4c4d415448)
    inputs = [(0, 0x2f30000000000000, bits(4)), (1, 1, 0), (2, 1, 0), (3, 1, 1)]
    for op in range(len(NAMES)):
        if op in (0, 3):
            inputs += [(op, x, y) for x in edges for y in edges]
            inputs += [(op, rng.getrandbits(64), rng.getrandbits(64)) for _ in range(2048)]
        else:
            inputs += [(op, x, 0) for x in edges]
            inputs += [(op, rng.getrandbits(64), 0) for _ in range(1024)]
    rows = []
    for op, x, y in inputs:
        expected = reference.evaluate(op, x, y, 256)
        if expected != reference.evaluate(op, x, y, 512):
            raise AssertionError('MPFR reference does not stabilize at binary64 precision')
        rows.append((op, x, y, expected))
    return rows, reference.version


def agrees(op, actual, expected):
    if actual == expected:
        return True
    magnitude = 0x7fffffffffffffff
    a, e = actual & magnitude, expected & magnitude
    if e > 0x7ff0000000000000:
        return a > 0x7ff0000000000000 and bool(actual & (1 << 51))
    # Special values, signed zeros and integral rounding stay bit-exact. Do not
    # allow a nonzero subnormal to be replaced by zero within a ULP allowance.
    if op >= 10 or a == 0 or e == 0 or a >= 0x7ff0000000000000 or e >= 0x7ff0000000000000:
        return False
    return actual >> 63 == expected >> 63 and abs(actual - expected) <= 2
