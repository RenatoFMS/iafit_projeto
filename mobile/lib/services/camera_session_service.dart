import 'dart:async';

import 'package:camera/camera.dart';
import 'package:camera_platform_interface/camera_platform_interface.dart';
import 'package:flutter/foundation.dart';
import 'package:permission_handler/permission_handler.dart';

enum CameraAccess { granted, denied, permanentlyDenied, restricted }

enum CameraPhase { idle, loading, ready, suspended, failed, closed }

class CameraFailure {
  const CameraFailure(this.code, this.message, {this.openSettings = false});
  final String code;
  final String message;
  final bool openSettings;
  factory CameraFailure.from(Object error) {
    final code = error is CameraException
        ? error.code
        : error.runtimeType.toString();
    return CameraFailure(
      code,
      switch (code) {
        'CameraAccessDenied' => 'O acesso à câmera foi negado. Toque em tentar novamente para solicitar a permissão.',
        'CameraAccessDeniedWithoutPrompt' || 'permission-permanent' => 'A permissão da câmera foi bloqueada. Ative-a nas configurações do aplicativo.',
        'CameraAccessRestricted' => 'O sistema restringiu a câmera. Verifique os controles de acesso do aparelho.',
        'no-cameras' => 'O Android não informou nenhuma câmera. Confira o acesso à câmera nas configurações do sistema.',
        'CameraAccess' || 'camera-in-use' => 'Não foi possível acessar a câmera. Feche outros aplicativos que estejam usando a câmera e tente novamente.',
        'camera-timeout' => 'A câmera demorou para responder. Tente novamente ou selecione outra câmera.',
        _ =>
          'A câmera não conseguiu iniciar ($code). Tente novamente ou selecione outra câmera.',
      },
      openSettings: const [
        'CameraAccessDeniedWithoutPrompt',
        'permission-permanent',
        'CameraAccessRestricted',
      ].contains(code),
    );
  }
}

class CameraSessionService extends ChangeNotifier {
  CameraSessionService({
    Future<CameraAccess> Function()? requestPermission,
    Future<List<CameraDescription>> Function()? listCameras,
  }) : _requestPermission = requestPermission ?? _permission,
       _listCameras = listCameras ?? availableCameras;

  final Future<CameraAccess> Function() _requestPermission;
  final Future<List<CameraDescription>> Function() _listCameras;
  CameraController? controller;
  List<CameraDescription> cameras = [];
  CameraPhase phase = CameraPhase.idle;
  CameraFailure? failure;
  String? streamFailure;
  bool _closed = false;
  bool _active = true;
  bool _permissionPending = false;
  CameraLensDirection _lens = CameraLensDirection.front;
  Future<void> _queue = Future.value();

  static Future<CameraAccess> _permission() async {
    var status = await Permission.camera.status;
    if (!status.isGranted &&
        !status.isPermanentlyDenied &&
        !status.isRestricted) {
      status = await Permission.camera.request();
    }
    if (status.isGranted) return CameraAccess.granted;
    if (status.isPermanentlyDenied) return CameraAccess.permanentlyDenied;
    if (status.isRestricted) return CameraAccess.restricted;
    return CameraAccess.denied;
  }

  bool get canSwitch => cameras.map((c) => c.lensDirection).toSet().length > 1;
  bool get streaming => controller?.value.isStreamingImages ?? false;
  Future<void> get settled => _queue;
  void _changed() {
    if (!_closed) notifyListeners();
  }

  // All native mutations are serialized. A failure must never poison retries.
  Future<void> _enqueue(Future<void> Function() work) {
    _queue = _queue.then((_) async {
      try {
        await work();
      } catch (error, stack) {
        debugPrint('[FitnessPro/camera] $error\n$stack');
        failure = CameraFailure.from(error);
        phase = CameraPhase.failed;
        _changed();
      }
    });
    return _queue;
  }

  Future<void> initialize() => _enqueue(_initialize);
  Future<void> _initialize() async {
    if (_closed || !_active) return;
    phase = CameraPhase.loading;
    failure = null;
    streamFailure = null;
    _changed();
    await _releaseController();
    _permissionPending = true;
    late final CameraAccess access;
    try {
      access = await _requestPermission();
    } finally {
      _permissionPending = false;
    }
    if (_closed || !_active) {
      phase = CameraPhase.suspended;
      _changed();
      return;
    }
    if (access != CameraAccess.granted) {
      throw CameraException(switch (access) {
        CameraAccess.permanentlyDenied => 'permission-permanent',
        CameraAccess.restricted => 'CameraAccessRestricted',
        _ => 'CameraAccessDenied',
      }, 'Camera permission: $access');
    }
    cameras = await _listCameras();
    if (cameras.isEmpty) {
      throw CameraException('no-cameras', 'No cameras reported');
    }
    final preferred = cameras.where((c) => c.lensDirection == _lens).toList();
    final candidates = preferred.isEmpty ? cameras : preferred;
    Object? lastError;
    for (final camera in candidates) {
      // Some camera HALs reject a preset. Retry a lower resolution independently.
      for (final preset in [ResolutionPreset.medium, ResolutionPreset.low]) {
        final next = CameraController(
          camera,
          preset,
          enableAudio: false,
          imageFormatGroup: defaultTargetPlatform == TargetPlatform.android
              ? ImageFormatGroup.nv21
              : ImageFormatGroup.bgra8888,
        );
        try {
          await next.initialize().timeout(
            const Duration(seconds: 15),
            onTimeout: () =>
                throw CameraException('camera-timeout', 'initialize timeout'),
          );
          if (_closed || !_active) {
            await _disposeController(next);
            return;
          }
          controller = next;
          next.addListener(_onCameraState);
          _lens = camera.lensDirection;
          phase = CameraPhase.ready;
          _changed();
          return;
        } catch (error, stack) {
          lastError = error;
          debugPrint(
            '[FitnessPro/camera] initialize ${camera.name}/$preset: $error\n$stack',
          );
          await _disposeController(next);
          if (_closed || !_active) return;
          if (error is CameraException &&
              error.code.startsWith('CameraAccessDenied')) {
            rethrow;
          }
        }
      }
    }
    throw lastError ?? CameraException('camera-init', 'No camera initialized');
  }

  Future<void> switchCamera() => _enqueue(() async {
    _lens = _lens == CameraLensDirection.front
        ? CameraLensDirection.back
        : CameraLensDirection.front;
    await _initialize();
  });

  Future<void> startFrames(
    void Function(CameraImage) onFrame,
  ) => _enqueue(() async {
    final camera = controller;
    if (_closed || !_active || camera == null || !camera.value.isInitialized) {
      return;
    }
    if (camera.value.isStreamingImages) return;
    try {
      streamFailure = null;
      if (!camera.supportsImageStreaming()) {
        throw CameraException(
          'stream-unsupported',
          'Image streaming not supported by this camera backend',
        );
      }
      await camera
          .startImageStream(onFrame)
          .timeout(const Duration(seconds: 10));
    } catch (error, stack) {
      // Keep a working preview even if the device rejects the analysis stream.
      debugPrint('[FitnessPro/camera-stream] $error\n$stack');
      streamFailure =
          'Não foi possível iniciar a análise (${error is CameraException ? error.code : error.runtimeType}). A prévia continua disponível.';
    }
    _changed();
  });

  Future<void> stopFrames() => _enqueue(() async {
    final camera = controller;
    if (camera != null && camera.value.isStreamingImages) {
      try {
        await camera.stopImageStream().timeout(const Duration(seconds: 5));
      } catch (error) {
        debugPrint('[FitnessPro/camera-stream] stop: $error');
      }
    }
    _changed();
  });

  void setActive(bool active) {
    if (_closed || _active == active) return;
    _active = active;
    if (_permissionPending) {
      return; // System permission dialog does not restart the camera.
    }
    unawaited(
      _enqueue(() async {
        if (active != _active) {
          return; // A newer lifecycle event supersedes this one.
        }
        if (active) {
          await _initialize();
        } else {
          await _releaseController();
          phase = CameraPhase.suspended;
          _changed();
        }
      }),
    );
  }

  Future<void> _disposeController(CameraController camera) async {
    try {
      if (camera.value.isStreamingImages) {
        await camera.stopImageStream().timeout(const Duration(seconds: 5));
      }
    } catch (error) {
      debugPrint('[FitnessPro/camera] stop during release: $error');
    }
    try {
      await camera.dispose().timeout(const Duration(seconds: 5));
    } on TimeoutException catch (error) {
      debugPrint('[FitnessPro/camera] release timeout: $error');
      if (camera.cameraId >= 0) {
        try {
          await CameraPlatform.instance
              .dispose(camera.cameraId)
              .timeout(const Duration(seconds: 5));
        } catch (failure) {
          debugPrint('[FitnessPro/camera] native release: $failure');
        }
      }
    } catch (error) {
      debugPrint('[FitnessPro/camera] dispose: $error');
    }
  }

  Future<void> _releaseController() async {
    final camera = controller;
    controller = null;
    if (camera != null) {
      camera.removeListener(_onCameraState);
      await _disposeController(camera);
    }
  }

  void _onCameraState() {
    final camera = controller;
    if (_closed || camera == null || !camera.value.hasError) return;
    debugPrint('[FitnessPro/camera] native: ${camera.value.errorDescription}');
    failure = CameraFailure(
      'camera-runtime',
      'A câmera foi interrompida: ${camera.value.errorDescription}. Tente novamente ou troque de câmera.',
    );
    phase = CameraPhase.failed;
    _changed();
  }

  Future<void> shutdown() async {
    _closed = true;
    _active = false;
    await _queue;
    await _releaseController();
    phase = CameraPhase.closed;
  }

  @override
  void dispose() {
    unawaited(shutdown());
    super.dispose();
  }
}
