enum VideoSourceKind { youtube, network, asset, invalid }

class VideoSource {
  const VideoSource._(this.kind, this.value);
  final VideoSourceKind kind;
  final String value;

  factory VideoSource.parse(String input) {
    final value = input.trim();
    final idPattern = RegExp(r'^[a-zA-Z0-9_-]{11}$');
    if (idPattern.hasMatch(value)) {
      return VideoSource._(VideoSourceKind.youtube, value);
    }
    if (value.startsWith('assets/') && !value.contains('..')) {
      return VideoSource._(VideoSourceKind.asset, value);
    }
    final uri = Uri.tryParse(value);
    if (uri == null ||
        uri.scheme != 'https' ||
        uri.host.isEmpty ||
        uri.host == 'localhost' ||
        uri.host == '127.0.0.1' ||
        uri.host == '::1') {
      return const VideoSource._(VideoSourceKind.invalid, '');
    }
    final host = uri.host.toLowerCase();
    if (host == 'youtu.be' ||
        host == 'youtube.com' ||
        host.endsWith('.youtube.com')) {
      final segments = uri.pathSegments;
      final id = host == 'youtu.be'
          ? segments.firstOrNull
          : uri.queryParameters['v'] ??
                (segments.length >= 2 &&
                        const [
                          'embed',
                          'shorts',
                          'live',
                        ].contains(segments.first)
                    ? segments[1]
                    : null);
      return id != null && idPattern.hasMatch(id)
          ? VideoSource._(VideoSourceKind.youtube, id)
          : const VideoSource._(VideoSourceKind.invalid, '');
    }
    if (RegExp(
      r'\.(mp4|m3u8|webm)$',
      caseSensitive: false,
    ).hasMatch(uri.path)) {
      return VideoSource._(VideoSourceKind.network, uri.toString());
    }
    return const VideoSource._(VideoSourceKind.invalid, '');
  }

  String? get thumbnail => kind == VideoSourceKind.youtube
      ? 'https://img.youtube.com/vi/$value/hqdefault.jpg'
      : null;
}
