import '../models/workout_history_model.dart';

class GamificationData {
  final int xp;
  final int level;
  final int currentLevelXp;
  final int nextLevelXp;
  final int currentStreak;
  final List<String> achievements;

  GamificationData({
    required this.xp,
    required this.level,
    required this.currentLevelXp,
    required this.nextLevelXp,
    required this.currentStreak,
    required this.achievements,
  });

  double get progress {
    final levelDifference = nextLevelXp - currentLevelXp;

    if (levelDifference <= 0) {
      return 1;
    }

    return (xp - currentLevelXp) / levelDifference;
  }
}

class GamificationService {
  static GamificationData calculate(List<WorkoutHistoryModel> workouts) {
    int xp = 0;

    for (final workout in workouts) {
      xp += 100;
      xp += workout.calories ~/ 10;
    }

    final level = (xp ~/ 500) + 1;

    final currentLevelXp = (level - 1) * 500;

    final nextLevelXp = level * 500;

    final streak = _calculateStreak(workouts);

    final achievements = _calculateAchievements(workouts);

    return GamificationData(
      xp: xp,
      level: level,
      currentLevelXp: currentLevelXp,
      nextLevelXp: nextLevelXp,
      currentStreak: streak,
      achievements: achievements,
    );
  }

  static int _calculateStreak(List<WorkoutHistoryModel> workouts) {
    if (workouts.isEmpty) {
      return 0;
    }

    final dates = <DateTime>{};

    for (final workout in workouts) {
      final date = DateTime.tryParse(workout.date);

      if (date != null) {
        dates.add(DateTime(date.year, date.month, date.day));
      }
    }

    if (dates.isEmpty) {
      return 0;
    }

    final sortedDates = dates.toList()..sort((a, b) => b.compareTo(a));

    final today = DateTime.now();

    final todayDate = DateTime(today.year, today.month, today.day);

    final yesterday = todayDate.subtract(const Duration(days: 1));

    if (sortedDates.first != todayDate && sortedDates.first != yesterday) {
      return 0;
    }

    int streak = 1;

    for (int i = 1; i < sortedDates.length; i++) {
      final difference = sortedDates[i - 1].difference(sortedDates[i]).inDays;

      if (difference == 1) {
        streak++;
      } else {
        break;
      }
    }

    return streak;
  }

  static List<String> _calculateAchievements(
    List<WorkoutHistoryModel> workouts,
  ) {
    final achievements = <String>[];

    final totalWorkouts = workouts.length;

    final totalCalories = workouts.fold<int>(
      0,
      (total, workout) => total + workout.calories,
    );

    final totalDuration = workouts.fold<int>(
      0,
      (total, workout) => total + workout.duration,
    );

    if (totalWorkouts >= 1) {
      achievements.add('Primeiro treino');
    }

    if (totalWorkouts >= 5) {
      achievements.add('5 treinos concluídos');
    }

    if (totalWorkouts >= 10) {
      achievements.add('10 treinos concluídos');
    }

    if (totalWorkouts >= 25) {
      achievements.add('25 treinos concluídos');
    }

    if (totalWorkouts >= 50) {
      achievements.add('50 treinos concluídos');
    }

    if (totalCalories >= 1000) {
      achievements.add('1.000 kcal gastas');
    }

    if (totalCalories >= 5000) {
      achievements.add('5.000 kcal gastas');
    }

    if (totalDuration >= 300) {
      achievements.add('5 horas treinadas');
    }

    if (totalDuration >= 1000) {
      achievements.add('1.000 minutos treinados');
    }

    return achievements;
  }
}
