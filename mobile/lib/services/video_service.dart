import 'package:flutter/foundation.dart';
import 'package:package_info_plus/package_info_plus.dart';
import 'package:url_launcher/url_launcher.dart';

class VideoFailure {
  const VideoFailure(this.code, this.message);
  final int code;
  final String message;

  factory VideoFailure.youtube(int code) => VideoFailure(code, switch (code) {
    2 => 'O player recebeu parâmetros de reprodução inválidos. Tente novamente ou abra no YouTube.',
    5 => 'O WebView não conseguiu reproduzir este formato. Atualize o Android System WebView ou abra no YouTube.',
    100 || 105 => 'Este vídeo foi removido ou está privado. Consulte a demonstração no YouTube.',
    101 || 150 || 152 =>
      'O provedor restringiu a reprodução incorporada. Use “Abrir no YouTube”.',
    153 => 'O YouTube não conseguiu verificar a identidade do aplicativo. Use “Abrir no YouTube”.',
    _ => 'O player não conseguiu iniciar a demonstração. Tente novamente ou abra no YouTube.',
  });
}

class VideoService {
  /// The actual package/bundle ID identifies this embed, as required by YouTube.
  /// Never impersonate a website or another app with a fabricated origin.
  static Future<String?> appOrigin() async {
    if (kIsWeb) return null; // The iframe library uses the real browser origin.
    final info = await PackageInfo.fromPlatform();
    return originForPackage(info.packageName);
  }

  static String originForPackage(String package) {
    if (!RegExp(r'^[a-zA-Z0-9_]+(\.[a-zA-Z0-9_]+)+$').hasMatch(package)) {
      throw const FormatException('Identificador do aplicativo inválido.');
    }
    return 'https://${package.toLowerCase()}';
  }

  static Uri watchUrl(String id) {
    if (!RegExp(r'^[a-zA-Z0-9_-]{11}$').hasMatch(id)) {
      throw const FormatException('Identificador do vídeo inválido.');
    }
    return Uri.https('www.youtube.com', '/watch', {'v': id});
  }

  static Future<bool> openYouTube(String id) =>
      launchUrl(watchUrl(id), mode: LaunchMode.externalApplication);
}
