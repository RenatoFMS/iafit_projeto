import 'package:flutter/material.dart';

import '../models/workout_history_model.dart';
import '../theme/app_theme.dart';
import 'premium_components.dart';

class WeeklyActivity extends StatelessWidget {
  const WeeklyActivity({super.key, required this.workouts});
  final List<WorkoutHistoryModel> workouts;

  static List<int> dailyMinutes(
    List<WorkoutHistoryModel> workouts,
    DateTime now,
  ) {
    final today = DateTime(now.year, now.month, now.day);
    final dates = List.generate(
      7,
      (i) => today.subtract(Duration(days: 6 - i)),
    );
    return dates.map((day) {
      // Soma em segundos (treinos do motor IAFit duram menos de um minuto) e
      // arredonda para cima uma única vez, para qualquer atividade aparecer no gráfico.
      final seconds = workouts
          .where((workout) {
            final parsed = DateTime.tryParse(workout.date)?.toLocal();
            return parsed != null &&
                parsed.year == day.year &&
                parsed.month == day.month &&
                parsed.day == day.day;
          })
          .fold<int>(0, (total, workout) => total + workout.effectiveSeconds);
      return (seconds + 59) ~/ 60;
    }).toList();
  }

  @override
  Widget build(BuildContext context) {
    final now = DateTime.now();
    final minutes = dailyMinutes(workouts, now);
    final maximum = minutes.fold<int>(
      1,
      (max, value) => value > max ? value : max,
    );
    final sum = minutes.fold<int>(0, (total, value) => total + value);
    const days = ['S', 'T', 'Q', 'Q', 'S', 'S', 'D'];
    return PremiumCard(
      child: Column(
        crossAxisAlignment: CrossAxisAlignment.start,
        children: [
          Row(
            children: [
              Expanded(
                child: Text(
                  'Sua semana em movimento',
                  style: Theme.of(context).textTheme.titleMedium,
                ),
              ),
              const Icon(Icons.insights_rounded, color: AppColors.sky),
            ],
          ),
          const SizedBox(height: 6),
          Text('$sum minutos nos últimos 7 dias'),
          const SizedBox(height: 24),
          SizedBox(
            height: 144,
            child: Row(
              crossAxisAlignment: CrossAxisAlignment.end,
              children: List.generate(7, (i) {
                final date = now.subtract(Duration(days: 6 - i));
                return Expanded(
                  child: Semantics(
                    label: '${date.day}/${date.month}: ${minutes[i]} minutos',
                    child: Column(
                      mainAxisAlignment: MainAxisAlignment.end,
                      children: [
                        Text(
                          '${minutes[i]}',
                          style: const TextStyle(
                            fontSize: 10,
                            color: AppColors.sky,
                          ),
                        ),
                        const SizedBox(height: 6),
                        TweenAnimationBuilder<double>(
                          tween: Tween(begin: 0, end: minutes[i] / maximum),
                          duration: MediaQuery.disableAnimationsOf(context)
                              ? Duration.zero
                              : const Duration(milliseconds: 600),
                          builder: (context, value, child) => Container(
                            height: 5 + 65 * value,
                            width: 20,
                            decoration: BoxDecoration(
                              borderRadius: BorderRadius.circular(6),
                              gradient: LinearGradient(
                                begin: Alignment.bottomCenter,
                                end: Alignment.topCenter,
                                colors: minutes[i] == 0
                                    ? [
                                        Theme.of(context).colorScheme.outline,
                                        Theme.of(context).colorScheme.outline,
                                      ]
                                    : [
                                        AppColors.primary,
                                        i == 6 ? AppColors.cyan : AppColors.sky,
                                      ],
                              ),
                            ),
                          ),
                        ),
                        const SizedBox(height: 10),
                        Text(
                          days[date.weekday - 1],
                          style: Theme.of(context).textTheme.bodySmall,
                        ),
                      ],
                    ),
                  ),
                );
              }),
            ),
          ),
          if (sum == 0) ...[
            const SizedBox(height: 12),
            const Text('Conclua um treino para preencher seu gráfico.'),
          ],
        ],
      ),
    );
  }
}
