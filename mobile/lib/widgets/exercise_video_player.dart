import 'dart:async';

import 'package:flutter/foundation.dart';
import 'package:flutter/material.dart';
import 'package:video_player/video_player.dart';
import 'package:youtube_player_iframe/youtube_player_iframe.dart';

import '../services/video_service.dart';
import '../services/exercise_youtube_controller.dart';

import '../models/video_source.dart';

/// One player per detail route. Source types never share a controller.
class ExerciseVideoPlayer extends StatefulWidget {
  const ExerciseVideoPlayer({super.key, required this.source});
  final String source;
  @override
  State<ExerciseVideoPlayer> createState() => _ExerciseVideoPlayerState();
}

class _ExerciseVideoPlayerState extends State<ExerciseVideoPlayer>
    with WidgetsBindingObserver {
  VideoPlayerController? _video;
  YoutubePlayerController? _youtube;
  StreamSubscription<YoutubePlayerValue>? _subscription;
  Timer? _timeout;
  String? _error;
  bool _loading = true;
  bool _buffering = false;
  int _generation = 0;
  int? _youtubeErrorCode;

  @override
  void initState() {
    super.initState();
    WidgetsBinding.instance.addObserver(this);
    _initialize();
  }

  @override
  void didUpdateWidget(covariant ExerciseVideoPlayer oldWidget) {
    super.didUpdateWidget(oldWidget);
    if (oldWidget.source != widget.source) _initialize();
  }

  Future<void> _release() async {
    _timeout?.cancel();
    final subscription = _subscription;
    final video = _video;
    final youtube = _youtube;
    _subscription = null;
    _video = null;
    _youtube = null;
    video?.removeListener(_onVideo);
    await subscription?.cancel();
    await video?.dispose();
    if (youtube != null) {
      if (!kIsWeb) {
        try {
          await youtube.webViewController.removeJavaScriptChannel(
            'FitnessVideoError',
          );
        } catch (error) {
          debugPrint('[FitnessPro/video] release diagnostics: $error');
        }
      }
      try {
        await youtube.close();
      } catch (error) {
        debugPrint('[FitnessPro/video] release player: $error');
      }
    }
  }

  Future<void> _initialize() async {
    final generation = ++_generation;
    await _release();
    if (!mounted || generation != _generation) return;
    setState(() {
      _error = null;
      _youtubeErrorCode = null;
      _loading = true;
      _buffering = false;
    });
    final source = VideoSource.parse(widget.source);
    if (source.kind == VideoSourceKind.invalid) {
      _fail(
        'Este vídeo não possui um endereço válido. Escolha outra demonstração.',
      );
      return;
    }
    if (!kIsWeb && defaultTargetPlatform == TargetPlatform.windows) {
      _fail(
        'Abra o aplicativo no Chrome para assistir aos vídeos neste computador.',
      );
      return;
    }
    _timeout = Timer(const Duration(seconds: 30), () {
      if (mounted && generation == _generation && _loading) {
        _fail(
          'O vídeo demorou para responder. Confira sua conexão e tente novamente.',
        );
      }
    });
    try {
      if (source.kind == VideoSourceKind.youtube) {
        final origin = await VideoService.appOrigin();
        if (!mounted || generation != _generation) return;
        final controller = ExerciseYoutubeController(
          initialVideoId: source.value,
          params: YoutubePlayerParams(
            origin: origin,
            showControls: true,
            showFullscreenButton: true,
            interfaceLanguage: 'pt',
            captionLanguage: 'pt',
            enableCaption: true,
            strictRelatedVideos: true,
            showVideoAnnotations: false,
          ),
          onWebResourceError: (error) {
            if (!mounted ||
                generation != _generation ||
                error.isForMainFrame != true) {
              return;
            }
            debugPrint(
              '[FitnessPro/video] WebView ${error.errorCode}: ${error.description}',
            );
            _fail(
              'Não foi possível conectar ao player (WebView ${error.errorCode}). Confira a internet e abra no YouTube se necessário.',
            );
          },
        );
        _youtube = controller;
        if (!kIsWeb) {
          await controller.webViewController.addJavaScriptChannel(
            'FitnessVideoError',
            onMessageReceived: (message) {
              if (!mounted || generation != _generation) return;
              final code = int.tryParse(message.message);
              if (code == null) return;
              _youtubeErrorCode = code;
              final failure = VideoFailure.youtube(code);
              debugPrint('[FitnessPro/video] raw_youtube_error=$code');
              _fail('${failure.message} (Código $code.)');
            },
          );
          if (!mounted || generation != _generation) return;
        }
        _subscription = controller.stream.listen(
          (value) {
            if (!mounted || generation != _generation) return;
            if (value.hasError) {
              final failure = VideoFailure.youtube(
                _youtubeErrorCode ?? value.error.code,
              );
              debugPrint('[FitnessPro/video] youtube_error=${failure.code}');
              _fail('${failure.message} (Código ${failure.code}.)');
            } else if (value.playerState != PlayerState.unknown) {
              _timeout?.cancel();
              setState(() {
                _loading = false;
                _buffering = value.playerState == PlayerState.buffering;
              });
            }
          },
          onError: (_) => _fail(
            'Não foi possível conectar ao vídeo. Verifique sua internet.',
          ),
        );
        unawaited(
          controller.videoData
              .then((_) async {
                if (!mounted || generation != _generation) return;
                _timeout?.cancel();
                setState(() => _loading = false);
                if (kIsWeb) return;
                // Public IFrame API listener preserves new error numbers (e.g. 153)
                // that this SDK version otherwise collapses to unknown (-1).
                try {
                  await controller.webViewController.runJavaScript('''
              window.fitnessReportError = function(event) {
                FitnessVideoError.postMessage(String(event.data));
              };
              player.addEventListener('onError', 'fitnessReportError');
            ''');
                } catch (error) {
                  debugPrint('[FitnessPro/video] error listener: $error');
                }
              })
              .catchError((Object error) {
                if (mounted && generation == _generation) {
                  _fail(
                    'O player não respondeu. Confira sua conexão ou abra no YouTube.',
                  );
                }
              }),
        );
        setState(() {});
      } else {
        final controller = source.kind == VideoSourceKind.asset
            ? VideoPlayerController.asset(source.value)
            : VideoPlayerController.networkUrl(Uri.parse(source.value));
        _video = controller;
        controller.addListener(_onVideo);
        await controller.initialize().timeout(const Duration(seconds: 25));
        if (!mounted || generation != _generation) return;
        _timeout?.cancel();
        setState(() => _loading = false);
      }
    } catch (_) {
      if (mounted && generation == _generation) {
        _fail(
          'Não foi possível carregar o vídeo. Confira sua conexão ou tente novamente.',
        );
      }
    }
  }

  void _fail(String message) {
    _timeout?.cancel();
    if (!mounted || _error == message) return;
    unawaited(_video?.pause());
    unawaited(_youtube?.pauseVideo());
    setState(() {
      _error = message;
      _loading = false;
      _buffering = false;
    });
  }

  void _onVideo() {
    if (!mounted) return;
    final value = _video?.value;
    if (value == null) return;
    if (value.hasError) {
      if (_error == null) {
        _fail(
          'A reprodução foi interrompida. Tente carregar o vídeo novamente.',
        );
      }
      return;
    }
    setState(() => _buffering = value.isBuffering);
  }

  @override
  void didChangeAppLifecycleState(AppLifecycleState state) {
    if (state != AppLifecycleState.resumed) {
      unawaited(_video?.pause());
      unawaited(_youtube?.pauseVideo());
    }
  }

  @override
  void dispose() {
    _generation++;
    WidgetsBinding.instance.removeObserver(this);
    unawaited(_release());
    super.dispose();
  }

  @override
  Widget build(BuildContext context) {
    final video = _video;
    final youtube = _youtube;
    final playing = youtube?.value.playerState == PlayerState.playing;
    return LayoutBuilder(
      builder: (context, constraints) {
        final youtubeSource =
            VideoSource.parse(widget.source).kind == VideoSourceKind.youtube;
        // YouTube requires a viewport of at least 200px high, including on phones.
        final ratio = youtubeSource
            ? (constraints.maxWidth / 200).clamp(1.0, 16 / 9)
            : 16 / 9;
        return Column(
          mainAxisSize: MainAxisSize.min,
          children: [
            ClipRRect(
              borderRadius: BorderRadius.circular(24),
              child: AspectRatio(
                aspectRatio: ratio,
                child: ColoredBox(
                  color: const Color(0xFF030817),
                  child: _error != null
                      ? Center(
                          child: SingleChildScrollView(
                            padding: const EdgeInsets.all(16),
                            child: Column(
                              mainAxisSize: MainAxisSize.min,
                              children: [
                                const Icon(
                                  Icons.wifi_off_rounded,
                                  color: Color(0xFF60A5FA),
                                ),
                                const SizedBox(height: 8),
                                Text(
                                  _error!,
                                  textAlign: TextAlign.center,
                                  style: const TextStyle(color: Colors.white),
                                ),
                                TextButton.icon(
                                  onPressed: _initialize,
                                  icon: const Icon(Icons.refresh),
                                  label: const Text('Tentar novamente'),
                                ),
                              ],
                            ),
                          ),
                        )
                      : Stack(
                          alignment: Alignment.center,
                          children: [
                            if (_youtube != null)
                              YoutubePlayer(
                            key: ValueKey(_youtube),
                                controller: _youtube!,
                                aspectRatio: ratio,
                                autoFullScreen: false,
                                thumbnailFormat: ThumbnailFormat.jpeg,
                              ),
                            if (video != null && video.value.isInitialized)
                              Center(
                                child: AspectRatio(
                                  aspectRatio: video.value.aspectRatio,
                                  child: VideoPlayer(video),
                                ),
                              ),
                            if (_loading || _buffering)
                              const IgnorePointer(
                                child: CircularProgressIndicator(),
                              ),
                            if (video != null && video.value.isInitialized) ...[
                              IconButton.filled(
                                onPressed: () async {
                                  if (video.value.isPlaying) {
                                    await video.pause();
                                  } else {
                                    if (video.value.position >=
                                        video.value.duration) {
                                      await video.seekTo(Duration.zero);
                                    }
                                    await video.play();
                                  }
                                },
                                tooltip: video.value.isPlaying
                                    ? 'Pausar'
                                    : 'Reproduzir',
                                iconSize: 34,
                                icon: Icon(
                                  video.value.isPlaying
                                      ? Icons.pause_rounded
                                      : Icons.play_arrow_rounded,
                                ),
                              ),
                              Positioned(
                                left: 12,
                                right: 12,
                                bottom: 8,
                                child: VideoProgressIndicator(
                                  video,
                                  allowScrubbing: true,
                                  colors: const VideoProgressColors(
                                    playedColor: Color(0xFF3B82F6),
                                  ),
                                ),
                              ),
                            ],
                          ],
                        ),
                ),
              ),
            ),
            // Keep the initial play control outside the provider's loading overlay.
            // Some YouTube embeds remain unStarted after cueing and that overlay
            // intercepts the native play button, particularly on web.
            if (youtube != null && _error == null)
              Padding(
                padding: const EdgeInsets.only(top: 12),
                child: SizedBox(
                  width: double.infinity,
                  child: FilledButton.icon(
                    onPressed: () async {
                      try {
                        if (playing) {
                          await youtube.pauseVideo().timeout(
                            const Duration(seconds: 20),
                          );
                        } else {
                          await youtube.playVideo().timeout(
                            const Duration(seconds: 20),
                          );
                        }
                      } catch (_) {
                        _fail(
                          'O vídeo não respondeu. Confira sua conexão e tente novamente.',
                        );
                      }
                    },
                    icon: Icon(
                      playing ? Icons.pause_rounded : Icons.play_arrow_rounded,
                    ),
                    label: Text(playing ? 'Pausar vídeo' : 'Reproduzir vídeo'),
                  ),
                ),
              ),
            if (youtube != null && _error == null)
              TextButton.icon(
                onPressed: youtube.enterFullScreen,
                icon: const Icon(Icons.fullscreen_rounded),
                label: const Text('Tela cheia'),
              ),
            if (VideoSource.parse(widget.source).kind ==
                VideoSourceKind.youtube)
              OutlinedButton.icon(
                onPressed: () async {
                  try {
                    final opened = await VideoService.openYouTube(
                      VideoSource.parse(widget.source).value,
                    );
                    if (!opened && context.mounted) {
                      ScaffoldMessenger.of(context).showSnackBar(
                        const SnackBar(
                          content: Text(
                            'Nenhum aplicativo conseguiu abrir o link. Verifique o YouTube ou o navegador do aparelho.',
                          ),
                        ),
                      );
                    }
                  } catch (error) {
                    debugPrint('[FitnessPro/video] external_open: $error');
                    if (context.mounted) {
                      ScaffoldMessenger.of(context).showSnackBar(
                        const SnackBar(
                          content: Text(
                            'Não foi possível abrir o YouTube. Verifique se há um navegador instalado.',
                          ),
                        ),
                      );
                    }
                  }
                },
                icon: const Icon(Icons.open_in_new_rounded),
                label: const Text('Abrir no YouTube'),
              ),
          ],
        );
      },
    );
  }
}
