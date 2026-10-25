import 'dart:async';

import 'package:flutter/material.dart';
import 'package:flutter_test/flutter_test.dart';
import 'package:video_player_platform_interface/video_player_platform_interface.dart';
import 'package:fitness_app/widgets/exercise_video_player.dart';

class TestVideoPlatform extends VideoPlayerPlatform {
  DataSource? source;
  bool playing = false;
  bool disposed = false;
  @override
  Future<void> init() async {}
  @override
  Future<int> createWithOptions(VideoCreationOptions options) async {
    source = options.dataSource;
    return 1;
  }

  @override
  Stream<VideoEvent> videoEventsFor(int playerId) => Stream.value(
    VideoEvent(
      eventType: VideoEventType.initialized,
      duration: const Duration(seconds: 30),
      size: const Size(1280, 720),
    ),
  );
  @override
  Future<void> dispose(int playerId) async {
    disposed = true;
  }

  @override
  Future<void> setLooping(int playerId, bool looping) async {}
  @override
  Future<void> setVolume(int playerId, double volume) async {}
  @override
  Future<void> setPlaybackSpeed(int playerId, double speed) async {}
  @override
  Future<void> play(int playerId) async {
    playing = true;
  }

  @override
  Future<void> pause(int playerId) async {
    playing = false;
  }

  @override
  Future<void> seekTo(int playerId, Duration position) async {}
  @override
  Future<Duration> getPosition(int playerId) async => Duration.zero;
  @override
  Widget buildViewWithOptions(VideoViewOptions options) =>
      const ColoredBox(color: Colors.blue);
}

void main() {
  testWidgets('MP4 initializes, plays, pauses in background and disposes', (
    tester,
  ) async {
    final platform = TestVideoPlatform();
    VideoPlayerPlatform.instance = platform;
    await tester.pumpWidget(
      const MaterialApp(
        home: Scaffold(
          body: ExerciseVideoPlayer(
            source: 'https://cdn.example.com/squat.mp4',
          ),
        ),
      ),
    );
    await tester.pumpAndSettle();
    expect(platform.source?.sourceType, DataSourceType.network);
    await tester.tap(find.byTooltip('Reproduzir'));
    await tester.pump();
    expect(platform.playing, isTrue);
    tester.binding.handleAppLifecycleStateChanged(AppLifecycleState.inactive);
    await tester.pump();
    expect(platform.playing, isFalse);
    tester.binding.handleAppLifecycleStateChanged(AppLifecycleState.resumed);
    await tester.pumpWidget(const SizedBox.shrink());
    await tester.pump(const Duration(seconds: 1));
    await tester.runAsync(
      () => Future<void>.delayed(const Duration(milliseconds: 20)),
    );
    expect(platform.disposed, isTrue);
  });

  testWidgets(
    'invalid source shows recoverable error instead of black screen',
    (tester) async {
      await tester.pumpWidget(
        const MaterialApp(
          home: Scaffold(body: ExerciseVideoPlayer(source: 'invalid')),
        ),
      );
      await tester.pumpAndSettle();
      expect(find.textContaining('endereço válido'), findsOneWidget);
      expect(find.text('Tentar novamente'), findsOneWidget);
    },
  );
}
