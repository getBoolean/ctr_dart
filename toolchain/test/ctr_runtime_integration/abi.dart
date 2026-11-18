import 'SDK_ABI_URI' as internal;

void check(bool condition) {
  if (!condition) throw StateError('CTR ABI layout mismatch');
}

void main() {
  check(internal.Abi.values.length == 25);
  check(internal.Abi.values[23] == internal.Abi.windowsX64);
  check(internal.Abi.values[24] == internal.Abi.ctrArm);
  check(internal.Abi.ctrArm.toString() == 'ctr_arm');
  check(internal.abiNames[internal.Abi.ctrArm] == 'ctrArm');
  check(internal.wordSize[internal.Abi.ctrArm] == 4);
  check(internal.nonSizeAlignment[internal.Abi.ctrArm]!.isEmpty);
  check(internal.wordSize[internal.Abi.linuxX64] == 8);
  print('PASS actual transformer CTR ABI tables');
}
