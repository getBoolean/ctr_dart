import '../target.dart';

/// The CTR target: homebrew apps launched from Homebrew Launcher.
final class CtrTarget implements Target {
  const CtrTarget();

  @override
  String get name => 'ctr';

  @override
  String get description => 'CTR homebrew applications (.3dsx).';
}
