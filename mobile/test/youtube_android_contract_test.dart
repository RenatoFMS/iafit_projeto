import 'package:flutter/services.dart';
import 'package:flutter_test/flutter_test.dart';
import 'package:fitness_app/services/exercise_youtube_controller.dart';
import 'package:fitness_app/models/exercise_catalog.dart';

void main() {
  TestWidgetsFlutterBinding.ensureInitialized();
  test('all catalog IDs initialize the actual pinned iframe template before onReady', () async {
    final template = await rootBundle.loadString(
      'packages/youtube_player_iframe/assets/player.html',
    );
    for (final exercise in ExerciseCatalog.exercises) {
      final html = ExerciseYoutubeController.prepareTemplate(
        template,
        exercise.videoId,
      );
      expect(html, contains('videoId: "${exercise.videoId}"'));
      expect(html, contains("sendMessage('Ready', {});"));
      expect(html, isNot(contains("sendMessage('Ready', event);")));
    }
  });
  test('queue arguments omit absent optional times, preserve zero and reject invalid ranges', () {
    expect(ExerciseYoutubeController.queueArguments('EZMYCLKuGow'), {
      'videoId': 'EZMYCLKuGow',
    });
    expect(
      ExerciseYoutubeController.queueArguments('EZMYCLKuGow', startSeconds: 0),
      {'videoId': 'EZMYCLKuGow', 'startSeconds': 0.0},
    );
    expect(
      ExerciseYoutubeController.queueArguments(
        'EZMYCLKuGow',
        startSeconds: 5,
        endSeconds: 10,
      ),
      {'videoId': 'EZMYCLKuGow', 'startSeconds': 5.0, 'endSeconds': 10.0},
    );
    expect(
      () => ExerciseYoutubeController.queueArguments(
        'EZMYCLKuGow',
        endSeconds: 0,
      ),
      throwsArgumentError,
    );
    expect(
      () => ExerciseYoutubeController.queueArguments(
        'EZMYCLKuGow',
        startSeconds: double.nan,
      ),
      throwsArgumentError,
    );
    expect(
      () => ExerciseYoutubeController.queueArguments('not-a-video-url'),
      throwsFormatException,
    );
    expect(
      () => ExerciseYoutubeController.prepareTemplate(
        'changed upstream format',
        'EZMYCLKuGow',
      ),
      throwsStateError,
    );
  });
}
