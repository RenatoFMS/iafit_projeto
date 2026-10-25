import 'dart:convert';

import 'package:flutter/foundation.dart';
import 'package:flutter/services.dart';
import 'package:youtube_player_iframe/youtube_player_iframe.dart';

import 'video_service.dart';

/// Keep the existing iframe player and controls, but always initialize YouTube
/// with a valid exercise ID and omit absent optional API arguments.
/// The upstream 6.0.2 template otherwise starts /embed/ without a video, and
/// its queue methods transmit startSeconds:null/endSeconds:null on Android.
class ExerciseYoutubeController extends YoutubePlayerController {
  ExerciseYoutubeController({
    required this.initialVideoId,
    required super.params,
    super.onWebResourceError,
  }) : super(key: initialVideoId) {
    VideoService.watchUrl(initialVideoId);
  }
  final String initialVideoId;

  static Map<String, Object> queueArguments(
    String id, {
    double? startSeconds,
    double? endSeconds,
  }) {
    VideoService.watchUrl(id);
    if (startSeconds != null && (!startSeconds.isFinite || startSeconds < 0)) {
      throw ArgumentError.value(startSeconds, 'startSeconds');
    }
    if (endSeconds != null &&
        (!endSeconds.isFinite || endSeconds <= (startSeconds ?? 0))) {
      throw ArgumentError.value(endSeconds, 'endSeconds');
    }
    return {
      'videoId': id,
      'startSeconds': ?startSeconds,
      'endSeconds': ?endSeconds,
    };
  }

  static String prepareTemplate(String template, String videoId) {
    VideoService.watchUrl(videoId);
    // This adapter targets the pinned SDK. Fail explicitly if its template
    // contract changes during a dependency upgrade, rather than loading /embed/.
    if (!template.contains('host: host,')) {
      throw StateError(
        'O template do player é incompatível com esta versão do aplicativo.',
      );
    }
    return template
        .replaceFirst(
          'host: host,',
          'host: host,\n          videoId: ${jsonEncode(videoId)},',
        )
        .replaceFirst(
          "sendMessage('Ready', event);",
          "sendMessage('Ready', {});",
        );
  }

  @override
  Future<void> load({
    required YoutubePlayerParams params,
    String? baseUrl,
    String id = 'player',
  }) async {
    final template = prepareTemplate(
      await rootBundle.loadString(
        'packages/youtube_player_iframe/assets/player.html',
      ),
      initialVideoId,
    );
    final variables = {
      'playerId': id,
      'pointerEvents': params.pointerEvents.name,
      'playerVars': jsonEncode({...params.toMap(), 'autoplay': 0}),
      'platform': kIsWeb ? 'web' : defaultTargetPlatform.name.toLowerCase(),
      'host': params.host,
      'videoStateUpdateInterval': params.videoStateUpdateInterval.toString(),
    };
    final html = template.replaceAllMapped(
      RegExp(r'<<([a-zA-Z]+)>>'),
      (m) => variables[m.group(1)] ?? m.group(0)!,
    );
    await webViewController.loadHtmlString(html, baseUrl: baseUrl);
  }

  Future<void> _queue(
    String method,
    String id,
    double? start,
    double? end,
  ) async {
    final arguments = queueArguments(id, startSeconds: start, endSeconds: end);
    // Public getter waits for the SDK's onReady handshake on all platforms.
    await videoData.timeout(const Duration(seconds: 30));
    await webViewController.runJavaScript(
      'player.$method(${jsonEncode(arguments)});',
    );
  }

  @override
  Future<void> cueVideoById({
    required String videoId,
    double? startSeconds,
    double? endSeconds,
  }) => _queue('cueVideoById', videoId, startSeconds, endSeconds);
  @override
  Future<void> loadVideoById({
    required String videoId,
    double? startSeconds,
    double? endSeconds,
  }) => _queue('loadVideoById', videoId, startSeconds, endSeconds);
}
