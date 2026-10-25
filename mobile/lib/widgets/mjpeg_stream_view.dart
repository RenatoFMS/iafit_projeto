import 'dart:async';
import 'dart:convert';
import 'dart:typed_data';

import 'package:flutter/material.dart';
import 'package:http/http.dart' as http;

import '../services/engine_service.dart';
import '../theme/app_theme.dart';

/// Extrai quadros JPEG completos a partir de chunks TCP de um stream
/// `multipart/x-mixed-replace` (MJPEG).
class MjpegFrameParser {
  final List<int> _buffer = <int>[];
  int? _expectedLength;

  /// Adiciona um [chunk] de bytes e devolve o quadro JPEG completo mais recente
  /// (descartando quadros intermediários caso cheguem vários no mesmo pacote,
  /// mantendo latência mínima).
  Uint8List? addChunk(List<int> chunk) {
    if (chunk.isEmpty) return null;
    _buffer.addAll(chunk);
    Uint8List? latestFrame;

    while (true) {
      if (_expectedLength == null) {
        final headerEnd = _indexOfHeaderEnd(_buffer);
        if (headerEnd == -1) {
          if (_buffer.length > 65536) {
            return _extractBySoiEoi();
          }
          break;
        }

        final headerText = ascii.decode(
          _buffer.sublist(0, headerEnd),
          allowInvalid: true,
        );
        final match = RegExp(
          r'content-length:\s*(\d+)',
          caseSensitive: false,
        ).firstMatch(headerText);

        if (match == null) {
          return _extractBySoiEoi();
        }

        final parsedLength = int.tryParse(match.group(1)!);
        _buffer.removeRange(0, headerEnd + 4);
        if (parsedLength == null || parsedLength <= 0) {
          continue;
        }
        _expectedLength = parsedLength;
      }

      final needed = _expectedLength!;
      if (_buffer.length < needed) {
        break;
      }

      latestFrame = Uint8List.fromList(_buffer.sublist(0, needed));
      var consume = needed;
      if (_buffer.length >= needed + 2 &&
          _buffer[needed] == 13 &&
          _buffer[needed + 1] == 10) {
        consume += 2;
      }
      _buffer.removeRange(0, consume);
      _expectedLength = null;
    }

    return latestFrame;
  }

  void clear() {
    _buffer.clear();
    _expectedLength = null;
  }

  int _indexOfHeaderEnd(List<int> bytes) {
    final limit = bytes.length - 3;
    for (var i = 0; i < limit; i++) {
      if (bytes[i] == 13 &&
          bytes[i + 1] == 10 &&
          bytes[i + 2] == 13 &&
          bytes[i + 3] == 10) {
        return i;
      }
    }
    return -1;
  }

  Uint8List? _extractBySoiEoi() {
    Uint8List? latest;
    while (true) {
      final soi = _indexOfPair(_buffer, 0xFF, 0xD8, 0);
      if (soi == -1) {
        if (_buffer.length > 2) {
          _buffer.removeRange(0, _buffer.length - 2);
        }
        break;
      }
      final eoi = _indexOfPair(_buffer, 0xFF, 0xD9, soi + 2);
      if (eoi == -1) {
        if (soi > 0) {
          _buffer.removeRange(0, soi);
        }
        break;
      }
      latest = Uint8List.fromList(_buffer.sublist(soi, eoi + 2));
      _buffer.removeRange(0, eoi + 2);
    }
    return latest;
  }

  int _indexOfPair(List<int> bytes, int first, int second, int start) {
    final limit = bytes.length - 1;
    for (var i = start; i < limit; i++) {
      if (bytes[i] == first && bytes[i + 1] == second) {
        return i;
      }
    }
    return -1;
  }
}

enum _MjpegStatus { connecting, streaming, paused, error }

/// Exibe em tempo real o stream MJPEG (`/video_feed`) processado pelo MediaPipe/OpenCV.
class MjpegStreamView extends StatefulWidget {
  const MjpegStreamView({
    super.key,
    required this.streamUri,
    this.headers = const <String, String>{},
    this.paused = false,
    this.fit = BoxFit.contain,
    this.aspectRatio = 4 / 3,
    this.maxHeight = 320,
    this.onBeforeConnect,
    this.clientFactory,
  });

  final Uri? streamUri;
  final Map<String, String> headers;
  final bool paused;
  final BoxFit fit;
  final double aspectRatio;
  final double maxHeight;
  final Future<void> Function()? onBeforeConnect;
  final http.Client Function()? clientFactory;

  @override
  State<MjpegStreamView> createState() => _MjpegStreamViewState();
}

class _MjpegStreamViewState extends State<MjpegStreamView> {
  final MjpegFrameParser _parser = MjpegFrameParser();
  final ValueNotifier<Uint8List?> _currentFrame = ValueNotifier<Uint8List?>(
    null,
  );

  http.Client? _client;
  StreamSubscription<List<int>>? _subscription;
  Timer? _retryTimer;
  _MjpegStatus _status = _MjpegStatus.connecting;
  int _retryAttempts = 0;
  int _connectionGeneration = 0;

  @override
  void initState() {
    super.initState();
    EngineService.instance.online.addListener(_onEngineOnlineChanged);
    if (widget.paused) {
      _status = _MjpegStatus.paused;
    } else {
      _connect();
    }
  }

  @override
  void didUpdateWidget(covariant MjpegStreamView oldWidget) {
    super.didUpdateWidget(oldWidget);
    if (widget.paused != oldWidget.paused) {
      if (widget.paused) {
        _disconnect();
        setState(() => _status = _MjpegStatus.paused);
      } else {
        _retryAttempts = 0;
        _connect();
      }
      return;
    }
    if (widget.streamUri != oldWidget.streamUri) {
      _retryAttempts = 0;
      _currentFrame.value = null;
      _connect();
    }
  }

  void _onEngineOnlineChanged() {
    if (!mounted || widget.paused) return;
    if (EngineService.instance.online.value &&
        _status == _MjpegStatus.error) {
      _retryAttempts = 0;
      _connect();
    }
  }

  void _disconnect() {
    _connectionGeneration++;
    _retryTimer?.cancel();
    _retryTimer = null;
    final sub = _subscription;
    _subscription = null;
    if (sub != null) {
      unawaited(sub.cancel().catchError((Object _) {}));
    }
    _client?.close();
    _client = null;
    _parser.clear();
  }

  Future<void> _connect() async {
    _disconnect();
    if (!mounted || widget.paused || widget.streamUri == null) {
      if (mounted && widget.streamUri == null) {
        setState(() => _status = _MjpegStatus.error);
      }
      return;
    }

    final generation = _connectionGeneration;
    setState(() => _status = _MjpegStatus.connecting);

    if (widget.onBeforeConnect != null) {
      try {
        await widget.onBeforeConnect!();
      } on Object {
        // Segue para tentativa de conexão / reagendamento padrão.
      }
      if (!mounted || generation != _connectionGeneration || widget.paused) {
        return;
      }
    }

    final uri = widget.streamUri;
    if (uri == null) {
      setState(() => _status = _MjpegStatus.error);
      return;
    }

    final client = (widget.clientFactory ?? http.Client.new)();
    _client = client;

    try {
      final request = http.Request('GET', uri);
      request.headers.addAll(widget.headers);
      final response = await client
          .send(request)
          .timeout(const Duration(seconds: 4));

      if (!mounted || generation != _connectionGeneration) {
        client.close();
        return;
      }

      if (response.statusCode != 200) {
        client.close();
        _scheduleRetry();
        return;
      }

      _retryAttempts = 0;
      setState(() => _status = _MjpegStatus.streaming);

      _subscription = response.stream.listen(
        (chunk) {
          if (!mounted || generation != _connectionGeneration) return;
          final frame = _parser.addChunk(chunk);
          if (frame != null) {
            _currentFrame.value = frame;
          }
        },
        onError: (Object _) {
          if (!mounted || generation != _connectionGeneration) return;
          _scheduleRetry();
        },
        onDone: () {
          if (!mounted || generation != _connectionGeneration) return;
          _scheduleRetry();
        },
        cancelOnError: true,
      );
    } on Object {
      if (!mounted || generation != _connectionGeneration) {
        client.close();
        return;
      }
      client.close();
      _scheduleRetry();
    }
  }

  void _scheduleRetry() {
    _disconnect();
    if (!mounted || widget.paused) return;
    setState(() => _status = _MjpegStatus.error);

    if (_retryAttempts >= 10) return;
    _retryAttempts++;
    _retryTimer = Timer(const Duration(milliseconds: 1400), () {
      if (mounted && !widget.paused) {
        _connect();
      }
    });
  }

  Future<void> _manualReconnect() async {
    _retryAttempts = 0;
    setState(() => _status = _MjpegStatus.connecting);
    await EngineService.instance.ensureRunning();
    if (mounted && !widget.paused) {
      await _connect();
    }
  }

  @override
  void dispose() {
    EngineService.instance.online.removeListener(_onEngineOnlineChanged);
    _disconnect();
    _currentFrame.dispose();
    super.dispose();
  }

  @override
  Widget build(BuildContext context) {
    return ConstrainedBox(
      constraints: BoxConstraints(maxHeight: widget.maxHeight),
      child: AspectRatio(
        aspectRatio: widget.aspectRatio,
        child: ColoredBox(
          color: const Color(0xFF0A0F1A),
          child: ValueListenableBuilder<Uint8List?>(
            valueListenable: _currentFrame,
            builder: (context, frameBytes, _) {
              if (frameBytes != null &&
                  (_status == _MjpegStatus.streaming ||
                      _status == _MjpegStatus.paused)) {
                return Stack(
                  fit: StackFit.expand,
                  children: [
                    Opacity(
                      opacity: _status == _MjpegStatus.paused ? 0.45 : 1.0,
                      child: Image.memory(
                        frameBytes,
                        gaplessPlayback: true,
                        fit: widget.fit,
                        filterQuality: FilterQuality.medium,
                      ),
                    ),
                    if (_status == _MjpegStatus.paused)
                      const Center(
                        child: DecoratedBox(
                          decoration: BoxDecoration(
                            color: Color(0xCC0A0F1A),
                            borderRadius: BorderRadius.all(Radius.circular(16)),
                          ),
                          child: Padding(
                            padding: EdgeInsets.symmetric(
                              horizontal: 16,
                              vertical: 10,
                            ),
                            child: Text(
                              'VÍDEO EM PAUSA',
                              style: TextStyle(
                                color: Colors.white,
                                fontSize: 12,
                                fontWeight: FontWeight.w800,
                                letterSpacing: 1.2,
                              ),
                            ),
                          ),
                        ),
                      ),
                  ],
                );
              }

              return _buildPlaceholder();
            },
          ),
        ),
      ),
    );
  }

  Widget _buildPlaceholder() {
    final isConnecting = _status == _MjpegStatus.connecting;
    final isPaused = _status == _MjpegStatus.paused;

    return Center(
      child: Padding(
        padding: const EdgeInsets.all(12),
        child: FittedBox(
          fit: BoxFit.scaleDown,
          child: SizedBox(
            width: 260,
            child: Column(
              mainAxisSize: MainAxisSize.min,
              children: [
                Icon(
                  isPaused
                      ? Icons.pause_circle_outline_rounded
                      : isConnecting
                      ? Icons.sensors_rounded
                      : Icons.videocam_off_outlined,
                  color: AppColors.sky,
                  size: 30,
                ),
                const SizedBox(height: 8),
                Text(
                  isPaused
                      ? 'Transmissão em pausa'
                      : isConnecting
                      ? 'Conectando à câmera IA (MediaPipe 3D)…'
                      : 'Iniciando ou aguardando o motor IAFit…',
                  textAlign: TextAlign.center,
                  style: const TextStyle(
                    color: Colors.white,
                    fontSize: 12.5,
                    fontWeight: FontWeight.w700,
                  ),
                ),
                const SizedBox(height: 4),
                Text(
                  isPaused
                      ? 'Retome o treino para voltar à análise em tempo real.'
                      : 'Stream local em 127.0.0.1:8765/video_feed',
                  textAlign: TextAlign.center,
                  style: const TextStyle(color: AppColors.muted, fontSize: 11),
                ),
                if (_status == _MjpegStatus.error) ...[
                  const SizedBox(height: 10),
                  OutlinedButton.icon(
                    onPressed: _manualReconnect,
                    icon: const Icon(Icons.refresh_rounded, size: 15),
                    label: const Text('Reconectar IA'),
                  ),
                ],
              ],
            ),
          ),
        ),
      ),
    );
  }
}

