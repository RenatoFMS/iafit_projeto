import 'dart:async';

import 'package:camera_platform_interface/camera_platform_interface.dart';
import 'package:fitness_app/screens/workouts/workout_detail_screen.dart';
import 'package:flutter/foundation.dart';
import 'package:flutter/material.dart';
import 'package:flutter_test/flutter_test.dart';
// ignore: depend_on_referenced_packages
import 'package:permission_handler_platform_interface/permission_handler_platform_interface.dart';

class _TestPermissionPlatform extends PermissionHandlerPlatform {
  @override
  Future<PermissionStatus> checkPermissionStatus(Permission permission) async =>
      PermissionStatus.granted;

  @override
  Future<Map<Permission, PermissionStatus>> requestPermissions(
    List<Permission> permissions,
  ) async => {for (final p in permissions) p: PermissionStatus.granted};
}

class _TestCameraPlatform extends CameraPlatform {
  final _frames = StreamController<CameraImageData>.broadcast();
  final _errors = <int, StreamController<CameraErrorEvent>>{};

  @override
  Future<List<CameraDescription>> availableCameras() async => const [
    CameraDescription(
      name: 'front',
      lensDirection: CameraLensDirection.front,
      sensorOrientation: 270,
    ),
  ];

  @override
  Widget buildPreview(int cameraId) =>
      const ColoredBox(key: ValueKey('native-preview'), color: Colors.black);

  @override
  bool supportsImageStreaming() => true;

  @override
  Future<int> createCameraWithSettings(
    CameraDescription description,
    MediaSettings mediaSettings,
  ) async => 1;

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
      (_errors[cameraId] = StreamController<CameraErrorEvent>()).stream;

  @override
  Future<void> initializeCamera(
    int cameraId, {
    ImageFormatGroup imageFormatGroup = ImageFormatGroup.unknown,
  }) async {}

  @override
  Stream<CameraImageData> onStreamedFrameAvailable(
    int cameraId, {
    CameraImageStreamOptions? options,
  }) => _frames.stream;

  @override
  Future<void> dispose(int cameraId) async {
    _errors[cameraId]?.add(CameraErrorEvent(cameraId, 'closed'));
    await _errors[cameraId]?.close();
  }
}

void main() {
  testWidgets(
    'opens camera from active series and returns to the same exercise',
    (tester) async {
      debugDefaultTargetPlatformOverride = TargetPlatform.windows;
      addTearDown(() => debugDefaultTargetPlatformOverride = null);
      await tester.pumpWidget(
        const MaterialApp(
          home: WorkoutSessionScreen(
            workoutName: 'Treino de pernas',
            duration: 20,
            calories: 100,
            exercises: [
              {
                'name': 'Agachamento livre',
                'sets': 3,
                'reps': '12',
                'rest': 30,
                'muscle': 'Pernas',
              },
            ],
          ),
        ),
      );
      final button = find.text('VER MINHA EXECUÇÃO');
      await tester.ensureVisible(button);
      await tester.tap(button);
      await tester.pumpAndSettle();
      expect(find.text('Ver minha execução'), findsOneWidget);
      expect(find.textContaining('Android e iPhone'), findsOneWidget);
      await tester.scrollUntilVisible(find.text('Voltar à série'), 200);
      await tester.tap(find.text('Voltar à série'));
      await tester.pumpAndSettle();
      expect(find.text('Agachamento livre'), findsOneWidget);
      expect(find.text('1/3'), findsOneWidget);
      expect(find.text('CONCLUIR SÉRIE'), findsOneWidget);
      await tester.pumpWidget(const SizedBox.shrink());
      debugDefaultTargetPlatformOverride = null;
    },
  );

  testWidgets(
    'finishing session in camera screen and tapping Voltar à série advances series counter (1/3 -> 2/3)',
    (tester) async {
      tester.view.physicalSize = const Size(320, 720);
      tester.view.devicePixelRatio = 1;
      addTearDown(tester.view.resetPhysicalSize);
      addTearDown(tester.view.resetDevicePixelRatio);

      final previousCamera = CameraPlatform.instance;
      final previousPermission = PermissionHandlerPlatform.instance;
      CameraPlatform.instance = _TestCameraPlatform();
      PermissionHandlerPlatform.instance = _TestPermissionPlatform();
      debugDefaultTargetPlatformOverride = TargetPlatform.android;
      addTearDown(() {
        CameraPlatform.instance = previousCamera;
        PermissionHandlerPlatform.instance = previousPermission;
        debugDefaultTargetPlatformOverride = null;
      });

      await tester.pumpWidget(
        const MaterialApp(
          home: WorkoutSessionScreen(
            workoutName: 'Treino de pernas',
            duration: 20,
            calories: 100,
            exercises: [
              {
                'name': 'Agachamento livre',
                'sets': 3,
                'reps': '12',
                'rest': 30,
                'muscle': 'Pernas',
              },
            ],
          ),
        ),
      );

      expect(find.text('1/3'), findsOneWidget);
      expect(find.text('0 de 3 séries concluídas'), findsOneWidget);

      final openCameraButton = find.text('VER MINHA EXECUÇÃO');
      await tester.ensureVisible(openCameraButton);
      await tester.pumpAndSettle();
      await tester.tap(openCameraButton);
      await tester.pumpAndSettle();

      expect(find.text('Ver minha execução'), findsOneWidget);

      final startButton = find.text('Iniciar análise');
      await tester.scrollUntilVisible(startButton, 250);
      await tester.tap(startButton);
      await tester.pumpAndSettle();

      final pauseButton = find.text('Pausar análise');
      await tester.ensureVisible(pauseButton);
      await tester.tap(pauseButton);
      await tester.pumpAndSettle();
      await tester.runAsync(
        () async => Future<void>.delayed(const Duration(milliseconds: 50)),
      );
      await tester.pumpAndSettle();

      final finishButton = find.text('Finalizar sessão');
      await tester.ensureVisible(finishButton);
      await tester.pump(const Duration(milliseconds: 100));
      await tester.tap(finishButton);
      await tester.pumpAndSettle();
      await tester.runAsync(
        () async => Future<void>.delayed(const Duration(milliseconds: 50)),
      );
      await tester.pumpAndSettle();

      await tester.drag(find.byType(ListView), const Offset(0, 1000));
      await tester.pumpAndSettle();
      expect(find.text('Resumo da análise'), findsOneWidget);

      final backToSeries = find.text('Voltar à série');
      await tester.scrollUntilVisible(backToSeries, 250);
      await tester.ensureVisible(backToSeries);
      await tester.pumpAndSettle();
      await tester.tap(backToSeries);
      await tester.pumpAndSettle();

      expect(find.text('Agachamento livre'), findsOneWidget);
      expect(find.text('2/3'), findsOneWidget);
      expect(find.text('1 de 3 séries concluídas'), findsOneWidget);

      await tester.pumpWidget(const SizedBox.shrink());
      await tester.pumpAndSettle();
      debugDefaultTargetPlatformOverride = null;
    },
  );
}
