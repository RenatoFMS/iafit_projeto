// Manual Android release smoke probe. Never used by lib/main.dart.
// Uses real native camera/ML Kit/WebView plugins, without a connected phone.
import 'dart:async';
import 'dart:convert';

import 'package:camera/camera.dart';
import 'package:flutter/material.dart';
import 'package:google_mlkit_pose_detection/google_mlkit_pose_detection.dart';
import 'package:youtube_player_iframe/youtube_player_iframe.dart';
import 'package:fitness_app/services/camera_session_service.dart';
import 'package:fitness_app/services/pose_frame_converter.dart';
import 'package:fitness_app/services/video_service.dart';
import 'package:fitness_app/services/exercise_youtube_controller.dart';
import 'package:fitness_app/models/exercise_catalog.dart';

void main() {
  WidgetsFlutterBinding.ensureInitialized();
  runApp(const MaterialApp(home: RuntimeProbe()));
}

class RuntimeProbe extends StatefulWidget {
  const RuntimeProbe({super.key});
  @override
  State<RuntimeProbe> createState() => _RuntimeProbeState();
}

class _RuntimeProbeState extends State<RuntimeProbe> {
  YoutubePlayerController? _youtube;
  String _status = 'Native Android release probe';
  void _record(String test, Object result) {
    debugPrint(
      '[FITNESS_NATIVE_PROBE] ${jsonEncode({'test': test, 'result': result})}',
    );
    if (mounted) setState(() => _status = test);
  }

  @override
  void initState() {
    super.initState();
    WidgetsBinding.instance.addPostFrameCallback((_) {
      unawaited(_run());
    });
  }

  Future<void> _pose() async {
    final camera = CameraSessionService();
    final detector = PoseDetector(options: PoseDetectorOptions());
    try {
      await camera.initialize();
      final controller = camera.controller;
      if (controller == null) {
        throw StateError('Camera: ${camera.failure?.message}');
      }
      final captured = Completer<CameraImage>();
      await camera.startFrames((image) {
        if (!captured.isCompleted) captured.complete(image);
      });
      if (camera.streamFailure != null) throw StateError(camera.streamFailure!);
      final image = await captured.future.timeout(const Duration(seconds: 15));
      await camera.stopFrames();
      final input = PoseFrameConverter.convert(
        image,
        controller.description,
        controller.value.deviceOrientation,
        isAndroid: true,
      );
      final poses = await detector
          .processImage(input.image)
          .timeout(const Duration(seconds: 30));
      _record('real_camera_mlkit', {
        'ok': true,
        'width': image.width,
        'height': image.height,
        'planes': image.planes.length,
        'format': image.format.group.name,
        'poses': poses.length,
        'note': 'Emulated camera scene; this validates the native pipeline, not human movement accuracy',
      });
    } catch (error, stack) {
      _record('real_camera_mlkit', {
        'ok': false,
        'error': error.toString(),
        'stack': stack.toString(),
      });
    } finally {
      await camera.shutdown();
      camera.dispose();
      await detector.close();
    }
  }

  Future<Map<String, Object?>> _state(YoutubePlayerController c) async => {
    'error': c.value.error.code,
    'state': c.value.playerState.code,
    'time': await c.currentTime,
    'id': (await c.videoData).videoId,
  };

  Future<bool> _waitPlaying(YoutubePlayerController c, String id) async {
    for (var attempt = 0; attempt < 45; attempt++) {
      await Future<void>.delayed(const Duration(seconds: 1));
      if (c.value.playerState == PlayerState.playing &&
          await c.currentTime > .2 &&
          (await c.videoData).videoId == id) {
        return true;
      }
      if (c.value.hasError) return false;
    }
    return false;
  }

  Future<void> _video() async {
    final origin = await VideoService.appOrigin();
    _record('identity', {'origin': origin});
    final c = ExerciseYoutubeController(
      initialVideoId: ExerciseCatalog.exercises.first.videoId,
      params: YoutubePlayerParams(
        origin: origin,
        showControls: true,
        showFullscreenButton: true,
        mute: true, // The headless emulator has no physical audio output.
      ),
    );
    setState(() => _youtube = c);
    try {
      await c.videoData.timeout(const Duration(seconds: 45));
      for (final exercise in ExerciseCatalog.exercises) {
        final id = exercise.videoId;
        if (id != ExerciseCatalog.exercises.first.videoId) {
          await c.loadVideoById(videoId: id);
        }
        await c.playVideo();
        final playing = await _waitPlaying(c, id);
        _record('exercise_video', {
          'exercise': exercise.name,
          'requestedId': id,
          'playing': playing,
          ...await _state(c),
        });
      }
    } catch (error, stack) {
      _record('youtube_failure', {
        'error': error.toString(),
        'stack': stack.toString(),
      });
    }
  }

  Future<void> _run() async {
    await _pose();
    await _video();
    _record('finished', true);
  }

  @override
  void dispose() {
    unawaited(_youtube?.close());
    super.dispose();
  }

  @override
  Widget build(BuildContext context) => Scaffold(
    appBar: AppBar(title: const Text('Android native verification')),
    body: Column(
      children: [
        Text(_status),
        if (_youtube != null) YoutubePlayer(controller: _youtube!),
      ],
    ),
  );
}
