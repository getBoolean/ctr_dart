import 'dart:io';

/// Finds devices on the local network and sends apps to them.
///
/// Each target that loads apps over the network implements this with its own
/// ports and messages: CTR uses the Homebrew Launcher netloader, and a later
/// HAC target would use nxlink's different ports and messages.
abstract interface class DeviceTransport {
  /// The addresses of devices that answer within [wait], each emitted once,
  /// in the order they first answer. The stream closes when [wait] expires;
  /// cancel it to stop early.
  Stream<InternetAddress> discover(Duration wait);

  /// Sends [app] to [device], which launches it with [arguments].
  ///
  /// [onProgress], when given, is called with the bytes sent so far and the
  /// total as the transfer advances.
  Future<void> upload(
    InternetAddress device,
    File app, {
    List<String> arguments = const [],
    void Function(int sent, int total)? onProgress,
  });
}
