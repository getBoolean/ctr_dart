@pragma('vm:never-inline')
int add(int left, int right) => left + right;

void main(List<String> arguments) {
  final value = add(arguments.length, 42);
  if (value != 42) {
    throw StateError('Unexpected entry arguments or arithmetic result: $value');
  }
  print('hello:$value');
}
