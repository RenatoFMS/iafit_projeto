import 'package:flutter_test/flutter_test.dart';
import 'package:fitness_app/models/video_source.dart';
import 'package:fitness_app/widgets/weekly_activity.dart';
import 'package:fitness_app/models/workout_history_model.dart';

void main() {
  test('YouTube and direct MP4 sources choose different players', () {
    expect(
      VideoSource.parse('https://youtu.be/fG_03xSzT2s').kind,
      VideoSourceKind.youtube,
    );
    expect(
      VideoSource.parse('https://www.youtube.com/watch?v=fG_03xSzT2s&t=10')
          .value,
      'fG_03xSzT2s',
    );
    expect(
      VideoSource.parse('https://www.youtube.com/shorts/fG_03xSzT2s').value,
      'fG_03xSzT2s',
    );
    expect(
      VideoSource.parse('https://cdn.example.com/exercise.mp4?token=test').kind,
      VideoSourceKind.network,
    );
    expect(
      VideoSource.parse('assets/videos/squat.mp4').kind,
      VideoSourceKind.asset,
    );
  });
  test(
    'rejects local Windows paths, localhost, insecure and malformed URLs',
    () {
      for (final input in [
        r'C:\videos\squat.mp4',
        'http://localhost:8080/squat.mp4',
        'https://localhost/squat.mp4',
        'http://cdn.example.com/squat.mp4',
        'https://youtube.com/watch?v=invalid',
        'https://youtube.com.evil.example/watch?v=fG_03xSzT2s',
        'assets/../private.mp4',
        '',
      ]) {
        expect(
          VideoSource.parse(input).kind,
          VideoSourceKind.invalid,
          reason: input,
        );
      }
    },
  );
  test('weekly chart uses actual dates, aggregates same day, excludes older workouts', () {
    final now = DateTime(2026, 10, 24);
    WorkoutHistoryModel workout(String date, int minutes) =>
        WorkoutHistoryModel(
          workoutName: 'Teste',
          duration: minutes,
          calories: 100,
          date: date,
        );
    final values = WeeklyActivity.dailyMinutes([
      workout('2026-10-24', 20),
      workout('2026-10-24', 10),
      workout('2026-10-18', 40),
      workout('2026-10-17', 99),
      workout('invalid', 99),
    ], now);
    expect(values, [40, 0, 0, 0, 0, 0, 30]);
  });
}
