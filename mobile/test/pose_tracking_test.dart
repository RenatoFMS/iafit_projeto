// Synthetic platform-channel fixtures test the adapter, not ML model accuracy.
import 'dart:math' as math;

import 'package:camera/camera.dart';
import 'package:camera_platform_interface/camera_platform_interface.dart';
import 'package:flutter/foundation.dart';
import 'package:flutter/services.dart';
import 'package:flutter_test/flutter_test.dart';
import 'package:google_mlkit_pose_detection/google_mlkit_pose_detection.dart';
import 'package:fitness_app/services/pose_tracking_service.dart';
import 'package:fitness_app/widgets/pose_skeleton_painter.dart';

void main() {
  TestWidgetsFlutterBinding.ensureInitialized();
  const channel = MethodChannel('google_mlkit_pose_detector');
  const camera = CameraDescription(
    name: 'test',
    lensDirection: CameraLensDirection.back,
    sensorOrientation: 90,
  );
  late List<dynamic> detected;
  late List<MethodCall> calls;
  var reject = false;
  final image = CameraImage.fromPlatformInterface(
    CameraImageData(
      format: const CameraImageFormat(ImageFormatGroup.nv21, raw: 17),
      planes: [
        CameraImagePlane(
          bytes: Uint8List(640 * 480 * 3 ~/ 2),
          bytesPerRow: 640,
        ),
      ],
      width: 640,
      height: 480,
    ),
  );

  List<dynamic> squat(double angle, {double confidence = .99}) {
    final radians = angle * math.pi / 180;
    return [
      [
        {
          'type': PoseLandmarkType.leftHip.index,
          'x': 200.0,
          'y': 100.0,
          'z': 0.0,
          'likelihood': confidence,
        },
        {
          'type': PoseLandmarkType.leftKnee.index,
          'x': 200.0,
          'y': 200.0,
          'z': 0.0,
          'likelihood': confidence,
        },
        {
          'type': PoseLandmarkType.leftAnkle.index,
          'x': 200 + 100 * math.sin(radians),
          'y': 200 - 100 * math.cos(radians),
          'z': 0.0,
          'likelihood': confidence,
        },
      ],
    ];
  }

  setUp(() {
    detected = [];
    calls = [];
    reject = false;
    debugDefaultTargetPlatformOverride = TargetPlatform.android;
    TestDefaultBinaryMessengerBinding.instance.defaultBinaryMessenger
        .setMockMethodCallHandler(channel, (call) async {
          calls.add(call);
          if (call.method == 'vision#startPoseDetector') {
            if (reject) throw PlatformException(code: 'detector-test-failure');
            return detected;
          }
          return null;
        });
  });
  tearDown(() {
    debugDefaultTargetPlatformOverride = null;
    TestDefaultBinaryMessengerBinding.instance.defaultBinaryMessenger
        .setMockMethodCallHandler(channel, null);
  });

  Future<void> observe(
    PoseTrackingService service,
    List<dynamic> result, [
    int frames = 3,
  ]) async {
    detected = result;
    for (var i = 0; i < frames; i++) {
      service.process(image, camera, DeviceOrientation.portraitUp);
      await service.settled;
    }
  }

  test('NV21 frames reach native detector; real landmark coordinates drive IAFit counting', () async {
    final service = PoseTrackingService(
      'Agachamento livre',
      frameInterval: Duration.zero,
    )..start();
    await observe(service, squat(175));
    await observe(service, squat(85));
    expect(service.analyzer.repetitions, 1);
    expect(service.angle, closeTo(85, .001));
    expect(service.trackedJoint, PoseLandmarkType.leftKnee);
    final args = calls.first.arguments as Map;
    final data = args['imageData'] as Map;
    expect(data['bytes'], hasLength(640 * 480 * 3 ~/ 2));
    await service.stop();
    expect(service.clock.isRunning, isFalse);
    service.start(reset: false);
    expect(service.analyzer.repetitions, 1);
    await observe(service, squat(85));
    expect(service.analyzer.repetitions, 1); // Must reacquire the initial pose.
    await service.close();
    service.dispose();
    expect(calls.any((c) => c.method == 'vision#closePoseDetector'), isTrue);
  });

  test(
    'low confidence, no person and multiple people cannot complete a cycle',
    () async {
      final service = PoseTrackingService(
        'Agachamento livre',
        frameInterval: Duration.zero,
      )..start();
      await observe(service, squat(175));
      await observe(service, squat(85, confidence: .2));
      expect(service.angle, isNull);
      await observe(service, squat(85));
      expect(service.analyzer.repetitions, 0);
      await observe(service, squat(175));
      await observe(service, []);
      await observe(service, squat(85));
      expect(service.analyzer.repetitions, 0);
      await observe(service, [...squat(175), ...squat(175)]);
      expect(service.landmarks, isEmpty);
      expect(service.feedback, contains('uma pessoa'));
      await service.close();
      service.dispose();
    },
  );

  test(
    'lateral measures shoulder rather than the original incorrect elbow angle',
    () async {
      final service = PoseTrackingService(
        'Elevação lateral',
        frameInterval: Duration.zero,
      )..start();
      List<dynamic> pose(double angle) {
        final radians = angle * math.pi / 180;
        return [
          [
            {
              'type': PoseLandmarkType.leftHip.index,
              'x': 200.0,
              'y': 300.0,
              'z': 0.0,
              'likelihood': .99,
            },
            {
              'type': PoseLandmarkType.leftShoulder.index,
              'x': 200.0,
              'y': 200.0,
              'z': 0.0,
              'likelihood': .99,
            },
            {
              'type': PoseLandmarkType.leftElbow.index,
              'x': 200 + 100 * math.sin(radians),
              'y': 200 + 100 * math.cos(radians),
              'z': 0.0,
              'likelihood': .99,
            },
          ],
        ];
      }

      await observe(service, pose(20));
      await observe(service, pose(100));
      expect(service.trackedJoint, PoseLandmarkType.leftShoulder);
      expect(service.angle, closeTo(100, .001));
      expect(service.analyzer.repetitions, 1);
      await service.close();
      service.dispose();
    },
  );

  test(
    'native detector failure stops analysis with an explicit error',
    () async {
      final service = PoseTrackingService(
        'Agachamento livre',
        frameInterval: Duration.zero,
      )..start();
      reject = true;
      await observe(service, squat(175), 1);
      expect(service.running, isFalse);
      expect(service.error, contains('detector-test-failure'));
      expect(service.error, isNot(contains('PlatformException(')));
      expect(service.errorDetails, contains('PlatformException(detector-test-failure'));
      expect(service.analyzer.repetitions, 0);
      await service.close();
      service.dispose();
    },
  );

  test('projection mirrors the lens independently of sensor rotation and centers crops', () {
    for (final rotation in [
      InputImageRotation.rotation90deg,
      InputImageRotation.rotation270deg,
    ]) {
      expect(
        PoseSkeletonPainter.project(
          const Offset(100, 200),
          const Size(640, 480),
          const Size(240, 320),
          rotation,
          CameraLensDirection.back,
        ),
        const Offset(50, 100),
      );
      expect(
        PoseSkeletonPainter.project(
          const Offset(100, 200),
          const Size(640, 480),
          const Size(240, 320),
          rotation,
          CameraLensDirection.front,
        ),
        const Offset(190, 100),
      );
    }
    expect(
      PoseSkeletonPainter.project(
        const Offset(320, 240),
        const Size(640, 480),
        const Size(320, 180),
        InputImageRotation.rotation0deg,
        CameraLensDirection.back,
      ),
      const Offset(160, 90),
    );
  });
}
