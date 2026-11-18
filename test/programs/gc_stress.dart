@pragma('vm:never-inline')
List<int> allocate(int seed) => List<int>.generate(64, (index) => seed + index);

void main(List<String> arguments) {
  const count = 100000;
  final retained = List<List<int>?>.filled(64, null);
  for (var seed = 0; seed < count; seed++) {
    retained[seed % retained.length] = allocate(seed);
  }
  for (var slot = 0; slot < retained.length; slot++) {
    final seed = ((count - 1 - slot) ~/ retained.length) * retained.length + slot;
    final values = retained[slot]!;
    for (var index = 0; index < values.length; index++) {
      if (values[index] != seed + index) {
        throw StateError('retained allocation corrupted at $slot/$index');
      }
    }
  }
  print('gc:pass');
}
