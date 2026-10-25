import 'dart:async';
import 'dart:math' as math;

import 'package:camera/camera.dart';
import 'package:flutter/foundation.dart';
import 'package:flutter/services.dart';
import 'package:google_mlkit_pose_detection/google_mlkit_pose_detection.dart';

import '../models/engine_exercise_map.dart';
import 'engine_service.dart';
import 'movement_analyzer.dart';
import 'pose_frame_converter.dart';

class PoseTrackingService extends ChangeNotifier {
  PoseTrackingService(
    this.exerciseName, {
    this.frameInterval = const Duration(milliseconds: 120),
    EngineService? engine,
  }) : analyzer = MovementAnalyzer(exerciseName),
       _engine = engine ?? EngineService.instance,
       engineExerciseId = EngineExerciseMap.idFor(exerciseName);
  final Duration frameInterval;
  Future<void> get settled => _pending ?? Future.value();
  final String exerciseName;
  final EngineService _engine;
  final String? engineExerciseId;
  MovementAnalyzer analyzer;
  EngineLiveState? engineState;
  DateTime? _lastEngineFailure;
  PoseDetector? _detector;
  Future<void>? _pending;
  bool _closed = false;
  bool running = false;
  int _generation = 0;
  DateTime _lastFrame = DateTime.fromMillisecondsSinceEpoch(0);
  DateTime? lastDetection;
  PoseLandmarkType? _joint;
  Map<PoseLandmarkType, PoseLandmark> landmarks = {};
  PoseFrame? frame;
  String feedback = 'Inicie a análise e enquadre o corpo inteiro.';
  String? error;
  String? errorDetails;
  double? angle;
  final Stopwatch clock = Stopwatch();
  bool get supportsCounting =>
      analyzer.kind != MovementKind.mirror ||
      (engineExerciseId != null && engineState != null);
  PoseLandmarkType? get trackedJoint => _joint;
  bool get isSyncedWithEngine => engineState != null;
  bool get isIsometric => engineState?.isometric ?? false;
  int get postureErrors => engineState?.postureErrors ?? 0;
  int get percentage => engineState?.percentage ?? 0;
  int get effectiveRepetitions => engineState != null
      ? (engineState!.isometric
            ? engineState!.seconds
            : engineState!.repetitions)
      : analyzer.repetitions;
  String get effectivePhaseLabel =>
      (engineState != null && engineState!.phase.isNotEmpty)
      ? engineState!.phase
      : analyzer.phaseLabel;
  void _changed() {
    if (!_closed) notifyListeners();
  }

  void start({bool reset = true}) {
    if (_closed) return;
    if (reset) {
      analyzer = MovementAnalyzer(exerciseName);
      engineState = null;
      _lastEngineFailure = null;
    }
    analyzer.loseTracking();
    error = null;
    errorDetails = null;
    angle = null;
    landmarks = {};
    _joint = null;
    running = true;
    _generation++;
    if (reset) clock.reset();
    clock.start();
    feedback = 'Enquadre uma pessoa de lado, com as articulações visíveis.';
    _changed();
  }

  void process(
    CameraImage image,
    CameraDescription camera,
    DeviceOrientation orientation,
  ) {
    if (!running ||
        _closed ||
        _pending != null ||
        DateTime.now().difference(_lastFrame) < frameInterval) {
      return;
    }
    _lastFrame = DateTime.now();
    final generation = _generation;
    _pending = _process(
      image,
      camera,
      orientation,
      generation,
    ).whenComplete(() => _pending = null);
  }

  Future<void> _process(
    CameraImage image,
    CameraDescription camera,
    DeviceOrientation orientation,
    int generation,
  ) async {
    try {
      final input = PoseFrameConverter.convert(
        image,
        camera,
        orientation,
        isAndroid: defaultTargetPlatform == TargetPlatform.android,
      );
      final detector = _detector ??= PoseDetector(
        options: PoseDetectorOptions(mode: PoseDetectionMode.stream),
      );
      final poses = await detector
          .processImage(input.image)
          .timeout(const Duration(seconds: 5));
      if (_closed || !running || generation != _generation) return;
      frame = input;
      if (poses.isEmpty) {
        landmarks = {};
        angle = null;
        analyzer.loseTracking();
        feedback =
            'Corpo não detectado. Ajuste a distância, a luz e o enquadramento.';
      } else if (poses.length > 1) {
        landmarks = {};
        angle = null;
        analyzer.loseTracking();
        feedback = 'Mantenha somente uma pessoa no enquadramento para evitar contagens misturadas.';
      } else {
        if (lastDetection != null &&
            DateTime.now().difference(lastDetection!).inMilliseconds > 1000) {
          analyzer.loseTracking();
        }
        lastDetection = DateTime.now();
        landmarks = poses.first.landmarks;
        _measure();
        await _syncWithEngine(input, generation);
      }
      _changed();
    } catch (failure, stack) {
      if (_closed || generation != _generation) return;
      debugPrint('[FitnessPro/pose] $failure\n$stack');
      errorDetails = '$failure\n$stack';
      error = failure is FormatException
          ? failure.message
          : failure is PlatformException
          ? 'A análise corporal encontrou uma falha (${failure.code}). Tente novamente. A prévia da câmera continua disponível.'
          : 'Não foi possível concluir a análise (${failure.runtimeType}). Tente novamente. A prévia da câmera continua disponível.';
      feedback =
          'Análise interrompida. A prévia da câmera continua disponível.';
      analyzer.loseTracking();
      angle = null;
      landmarks = {};
      running = false;
      clock.stop();
      _changed();
    }
  }

  void _measure() {
    if (!supportsCounting) {
      feedback = 'Pontos corporais detectados. A contagem deste exercício ainda não está disponível.';
      return;
    }
    // YOLO COCO 17-point triples from main.py mapped to ML Kit's 33 names.
    // Lateral intentionally fixes the original elbow-angle bug: use the shoulder.
    final sides = switch (analyzer.kind) {
      MovementKind.squat => [
        [
          PoseLandmarkType.leftHip,
          PoseLandmarkType.leftKnee,
          PoseLandmarkType.leftAnkle,
        ],
        [
          PoseLandmarkType.rightHip,
          PoseLandmarkType.rightKnee,
          PoseLandmarkType.rightAnkle,
        ],
      ],
      MovementKind.curl => [
        [
          PoseLandmarkType.leftShoulder,
          PoseLandmarkType.leftElbow,
          PoseLandmarkType.leftWrist,
        ],
        [
          PoseLandmarkType.rightShoulder,
          PoseLandmarkType.rightElbow,
          PoseLandmarkType.rightWrist,
        ],
      ],
      MovementKind.abdominal => [
        [
          PoseLandmarkType.leftShoulder,
          PoseLandmarkType.leftHip,
          PoseLandmarkType.leftKnee,
        ],
        [
          PoseLandmarkType.rightShoulder,
          PoseLandmarkType.rightHip,
          PoseLandmarkType.rightKnee,
        ],
      ],
      _ => [
        [
          PoseLandmarkType.leftHip,
          PoseLandmarkType.leftShoulder,
          PoseLandmarkType.leftElbow,
        ],
        [
          PoseLandmarkType.rightHip,
          PoseLandmarkType.rightShoulder,
          PoseLandmarkType.rightElbow,
        ],
      ],
    };
    final valid = sides
        .where(
          (side) => side.every((type) {
            final p = landmarks[type];
            return p != null &&
                p.likelihood >= .75 &&
                p.x.isFinite &&
                p.y.isFinite;
          }),
        )
        .toList();
    if (valid.isEmpty) {
      angle = null;
      analyzer.loseTracking();
      feedback = 'Articulações pouco visíveis. Posicione o celular de lado e melhore a iluminação.';
      return;
    }
    final side = valid.firstWhere(
      (side) => side[1] == _joint,
      orElse: () => valid.first,
    );
    if (_joint != side[1]) {
      analyzer.loseTracking();
      _joint = side[1];
    }
    final points = side.map((type) => landmarks[type]!).toList();
    final measured = MovementAnalyzer.angle(
      math.Point(points[0].x, points[0].y),
      math.Point(points[1].x, points[1].y),
      math.Point(points[2].x, points[2].y),
    );
    if (!measured.isFinite) {
      angle = null;
      analyzer.loseTracking();
      return;
    }
    angle = measured;
    feedback = analyzer.update(measured);
  }

  Future<void> _syncWithEngine(PoseFrame input, int generation) async {
    final targetId = engineExerciseId;
    if (targetId == null || !_engine.enabled || landmarks.isEmpty) return;
    if (_lastEngineFailure != null &&
        DateTime.now().difference(_lastEngineFailure!) <
            const Duration(seconds: 3)) {
      return;
    }

    final rotated =
        defaultTargetPlatform == TargetPlatform.android &&
        (input.rotation == InputImageRotation.rotation90deg ||
            input.rotation == InputImageRotation.rotation270deg);
    final uprightSize = rotated
        ? Size(input.size.height, input.size.width)
        : input.size;

    final remote = await _engine.analyzeMlKitPose(
      exerciseId: targetId,
      landmarks: landmarks,
      frameSize: uprightSize,
    );
    if (_closed || !running || generation != _generation) return;
    if (remote == null) {
      _lastEngineFailure = DateTime.now();
      return;
    }

    _lastEngineFailure = null;
    engineState = remote;
    if (remote.feedback.isNotEmpty) {
      feedback = remote.feedback;
    }
    if (remote.angle != null && remote.angle!.isFinite) {
      angle = remote.angle;
    }
  }

  Future<void> stop() async {
    running = false;
    _generation++;
    clock.stop();
    await _pending;
    analyzer.loseTracking();
    landmarks = {};
    angle = null;
    _changed();
  }

  Future<void> close() async {
    _closed = true;
    await stop();
    try {
      await _detector?.close().timeout(const Duration(seconds: 5));
    } catch (failure) {
      debugPrint('[FitnessPro/pose] close: $failure');
    }
    _detector = null;
  }

  @override
  void dispose() {
    unawaited(close());
    super.dispose();
  }
}
