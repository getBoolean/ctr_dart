@pragma('vm:never-inline')
Never throwMarker() => throw StateError('ctr exception marker');

void main(List<String> arguments) {
  try {
    throwMarker();
  } on StateError catch (error, stack) {
    if (error.message != 'ctr exception marker' ||
        !stack.toString().contains('throwMarker')) {
      throw StateError('exception or stack trace was lost');
    }
    print('exception:pass');
    return;
  }
}
