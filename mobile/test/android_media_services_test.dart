import 'dart:async';

import 'package:camera_platform_interface/camera_platform_interface.dart';
import 'package:flutter/foundation.dart';
import 'package:flutter/services.dart';
import 'package:flutter_test/flutter_test.dart';
import 'package:fitness_app/services/camera_session_service.dart';
import 'package:fitness_app/services/pose_frame_converter.dart';
import 'package:fitness_app/services/video_service.dart';
import 'package:fitness_app/widgets/exercise_video_player.dart';
import 'package:fitness_app/widgets/pose_skeleton_painter.dart';
import 'package:fitness_app/screens/workouts/movement_camera_screen.dart';
import 'package:fitness_app/services/pose_tracking_service.dart';
import 'package:flutter/material.dart';
import 'package:google_mlkit_pose_detection/google_mlkit_pose_detection.dart';

const cameras = [
  CameraDescription(
    name: 'front',
    lensDirection: CameraLensDirection.front,
    sensorOrientation: 270,
  ),
  CameraDescription(
    name: 'back',
    lensDirection: CameraLensDirection.back,
    sensorOrientation: 90,
  ),
];

class TestCameraPlatform extends CameraPlatform {
  @override
  Widget buildPreview(int cameraId) =>
      const ColoredBox(key: ValueKey('native-preview'), color: Colors.black);
  @override
  bool supportsImageStreaming() => true;
  int created = 0;
  bool rejectMedium = false;
  bool rejectStream = false;
  final disposed = <int>[];
  final settings = <MediaSettings>[];
  final descriptions = <CameraDescription>[];
  final frames = StreamController<CameraImageData>.broadcast();
  final errors = <int, StreamController<CameraErrorEvent>>{};

  @override
  Future<int> createCameraWithSettings(
    CameraDescription description,
    MediaSettings mediaSettings,
  ) async {
    created++;
    settings.add(mediaSettings);
    descriptions.add(description);
    return created;
  }

  @override
  Stream<DeviceOrientationChangedEvent> onDeviceOrientationChanged() =>
      const Stream.empty();
  @override
  Stream<CameraInitializedEvent> onCameraInitialized(int cameraId) =>
      Stream.value(
        CameraInitializedEvent(
          cameraId,
          640,
          480,
          ExposureMode.auto,
          true,
          FocusMode.auto,
          true,
        ),
      );
  @override
  Stream<CameraErrorEvent> onCameraError(int cameraId) =>
      (errors[cameraId] = StreamController<CameraErrorEvent>()).stream;
  @override
  Future<void> initializeCamera(
    int cameraId, {
    ImageFormatGroup imageFormatGroup = ImageFormatGroup.unknown,
  }) async {
    if (rejectMedium &&
        settings.last.resolutionPreset == ResolutionPreset.medium) {
      throw PlatformException(
        code: 'camera-in-use',
        message: 'test HAL rejected preset',
      );
    }
  }

  @override
  Stream<CameraImageData> onStreamedFrameAvailable(
    int cameraId, {
    CameraImageStreamOptions? options,
  }) {
    if (rejectStream) {
      throw CameraException('stream-rejected', 'test HAL rejected stream');
    }
    return frames.stream;
  }

  @override
  Future<void> dispose(int cameraId) async {
    disposed.add(cameraId);
    errors[cameraId]?.add(CameraErrorEvent(cameraId, 'closed'));
    await errors[cameraId]?.close();
  }
}

void main() {
  TestWidgetsFlutterBinding.ensureInitialized();
  late TestCameraPlatform platform;
  late CameraPlatform previous;
  setUp(() {
    previous = CameraPlatform.instance;
    platform = TestCameraPlatform();
    CameraPlatform.instance = platform;
    debugDefaultTargetPlatformOverride = TargetPlatform.android;
  });
  tearDown(() async {
    await platform.frames.close();
    CameraPlatform.instance = previous;
    debugDefaultTargetPlatformOverride = null;
  });

  CameraSessionService session({Future<CameraAccess> Function()? permission}) =>
      CameraSessionService(
        requestPermission: permission ?? () async => CameraAccess.granted,
        listCameras: () async => cameras,
      );

  test(
    'denial identifies permission and a later retry really initializes',
    () async {
      var grant = false;
      final service = session(
        permission: () async =>
            grant ? CameraAccess.granted : CameraAccess.denied,
      );
      await service.initialize();
      expect(service.failure!.code, 'CameraAccessDenied');
      expect(platform.created, 0);
      grant = true;
      await service.initialize();
      expect(service.phase, CameraPhase.ready);
      expect(service.controller!.value.isInitialized, isTrue);
      await service.shutdown();
      service.dispose();
      expect(platform.disposed, [1]);
    },
  );

  test(
    'permanent denial offers settings rather than claiming broken hardware',
    () async {
      final service = session(
        permission: () async => CameraAccess.permanentlyDenied,
      );
      await service.initialize();
      expect(service.failure!.openSettings, isTrue);
      expect(platform.created, 0);
      await service.shutdown();
      service.dispose();
    },
  );

  test(
    'resolution retry disposes failed controller and disables audio',
    () async {
      platform.rejectMedium = true;
      final service = session();
      await service.initialize();
      expect(service.phase, CameraPhase.ready);
      expect(platform.settings.map((s) => s.resolutionPreset), [
        ResolutionPreset.medium,
        ResolutionPreset.low,
      ]);
      expect(platform.settings.every((s) => s.enableAudio == false), isTrue);
      expect(platform.disposed, [1]);
      await service.shutdown();
      service.dispose();
      expect(platform.disposed, [1, 2]);
    },
  );

  test(
    'analysis stream failure preserves initialized preview and permits retry',
    () async {
      platform.rejectStream = true;
      final service = session();
      await service.initialize();
      await service.startFrames((_) {});
      expect(service.phase, CameraPhase.ready);
      expect(service.controller!.value.isInitialized, isTrue);
      expect(service.streamFailure, contains('stream-rejected'));
      platform.rejectStream = false;
      await service.startFrames((_) {});
      expect(service.streaming, isTrue);
      expect(service.streamFailure, isNull);
      await service.stopFrames();
      expect(service.streaming, isFalse);
      await service.shutdown();
      service.dispose();
    },
  );

  test('switch and shutdown release each native camera', () async {
    final service = session();
    await service.initialize();
    expect(
      service.controller!.description.lensDirection,
      CameraLensDirection.front,
    );
    await service.switchCamera();
    expect(
      service.controller!.description.lensDirection,
      CameraLensDirection.back,
    );
    expect(platform.disposed, [1]);
    await service.shutdown();
    service.dispose();
    expect(platform.disposed, [1, 2]);
  });

  test(
    'permission dialog lifecycle does not open a duplicate camera',
    () async {
      final permission = Completer<CameraAccess>();
      final service = session(permission: () => permission.future);
      final initialization = service.initialize();
      await Future<void>.delayed(Duration.zero);
      service.setActive(false);
      service.setActive(true);
      permission.complete(CameraAccess.granted);
      await initialization;
      expect(platform.created, 1);
      expect(service.phase, CameraPhase.ready);
      await service.shutdown();
      service.dispose();
    },
  );

  test('YUV padding and interleaved chroma produce packed VU NV21', () {
    final bytes = PoseFrameConverter.yuv420ToNv21(4, 2, [
      PlaneBytes(
        Uint8List.fromList([1, 2, 3, 4, 99, 99, 5, 6, 7, 8, 99, 99]),
        6,
        1,
      ),
      PlaneBytes(Uint8List.fromList([11, 99, 12]), 4, 2),
      PlaneBytes(Uint8List.fromList([21, 99, 22]), 4, 2),
    ]);
    expect(bytes, [1, 2, 3, 4, 5, 6, 7, 8, 21, 11, 22, 12]);
    expect(
      () => PoseFrameConverter.yuv420ToNv21(4, 2, [
        PlaneBytes(Uint8List(1), 4, 1),
        PlaneBytes(Uint8List(2), 2, 1),
        PlaneBytes(Uint8List(2), 2, 1),
      ]),
      throwsFormatException,
    );
  });

  test('rotation compensates front/back sensors in portrait and landscape', () {
    expect(
      PoseFrameConverter.rotationDegrees(
        90,
        DeviceOrientation.landscapeLeft,
        CameraLensDirection.back,
      ),
      0,
    );
    expect(
      PoseFrameConverter.rotationDegrees(
        270,
        DeviceOrientation.landscapeRight,
        CameraLensDirection.front,
      ),
      180,
    );
    expect(
      PoseFrameConverter.rotationDegrees(
        270,
        DeviceOrientation.portraitUp,
        CameraLensDirection.front,
      ),
      270,
    );
    expect(
      PoseSkeletonPainter.project(
        const Offset(100, 200),
        const Size(640, 480),
        const Size(240, 320),
        InputImageRotation.rotation90deg,
        CameraLensDirection.back,
      ),
      const Offset(50, 100),
    );
    expect(
      PoseSkeletonPainter.project(
        const Offset(100, 200),
        const Size(640, 480),
        const Size(240, 320),
        InputImageRotation.rotation270deg,
        CameraLensDirection.front,
      ),
      const Offset(190, 100),
    );
  });

  test(
    'YouTube identity uses real package and errors distinguish restriction',
    () {
      expect(
        VideoService.originForPackage('Com.Example.fitness_app'),
        'https://com.example.fitness_app',
      );
      expect(
        () => VideoService.originForPackage('https://youtube.com'),
        throwsFormatException,
      );
      expect(VideoFailure.youtube(153).message, contains('identidade'));
      expect(
        VideoFailure.youtube(150).message,
        contains('reprodução incorporada'),
      );
      expect(VideoFailure.youtube(-1).message, isNot(contains('restringiu')));
      expect(
        VideoService.watchUrl('zgk71dUUt0Y').toString(),
        'https://www.youtube.com/watch?v=zgk71dUUt0Y',
      );
    },
  );

  testWidgets(
    'external YouTube option stays accessible when native player is unsupported',
    (tester) async {
      debugDefaultTargetPlatformOverride = TargetPlatform.windows;
      await tester.pumpWidget(
        const MaterialApp(
          home: Scaffold(
            body: ExerciseVideoPlayer(source: 'https://youtu.be/zgk71dUUt0Y'),
          ),
        ),
      );
      await tester.pumpAndSettle();
      expect(find.text('Abrir no YouTube'), findsOneWidget);
      expect(find.textContaining('Chrome'), findsOneWidget);
      await tester.pumpWidget(const SizedBox.shrink());
      debugDefaultTargetPlatformOverride = null;
    },
  );

  testWidgets(
    'camera screen starts pauses and finishes a session while preserving preview',
    (tester) async {
      tester.view.physicalSize = const Size(320, 720);
      tester.view.devicePixelRatio = 1;
      addTearDown(tester.view.resetPhysicalSize);
      addTearDown(tester.view.resetDevicePixelRatio);
      final service = session();
      final tracking = PoseTrackingService('Agachamento livre');
      await tester.pumpWidget(
        MaterialApp(
          home: MovementCameraScreen(
            exerciseName: 'Agachamento livre',
            cameraSession: service,
            poseTracking: tracking,
          ),
        ),
      );
      await tester.pumpAndSettle();
      expect(find.byKey(const ValueKey('native-preview')), findsOneWidget);
      final start = find.text('Iniciar análise');
      await tester.scrollUntilVisible(start, 250);
      await tester.tap(start);
      await tester.pumpAndSettle();
      expect(service.streaming, isTrue);
      expect(tracking.running, isTrue);
      final pause = find.text('Pausar análise');
      await tester.ensureVisible(pause);
      await tester.tap(pause);
      await tester.pumpAndSettle();
      await tester.runAsync(() async { await service.settled; await tracking.settled; });
      await tester.pumpAndSettle();
      expect(service.streaming, isFalse);
      expect(service.controller!.value.isInitialized, isTrue);
      expect(tracking.clock.isRunning, isFalse);
      final finish = find.text('Finalizar sessão');
      await tester.ensureVisible(finish);
      await tester.pump(const Duration(milliseconds: 100));
      await tester.tap(finish);
      await tester.pumpAndSettle();
      expect(service.controller, isNull);
      await tester.drag(find.byType(ListView), const Offset(0, 1000));
      await tester.pumpAndSettle();
      expect(find.text('Resumo da análise'), findsOneWidget);
      expect(tester.takeException(), isNull);
      await tester.pumpWidget(const SizedBox.shrink());
      await tester.pumpAndSettle();
      debugDefaultTargetPlatformOverride = null;
    },
  );
}
