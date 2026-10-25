import 'package:flutter/material.dart';

import '../../theme/app_theme.dart';
import '../../widgets/premium_components.dart';

import 'workout_detail_screen.dart';

class WorkoutsScreen extends StatelessWidget {
  const WorkoutsScreen({super.key});

  final List<Map<String, dynamic>> workouts = const [
    {
      'title': 'Peito + Tríceps',
      'description': 'Treino completo para peito e tríceps',
      'exercises': 6,
      'duration': 45,
      'calories': 420,
      'icon': Icons.fitness_center,
    },
    {
      'title': 'Costas + Bíceps',
      'description': 'Treino para costas e braços',
      'exercises': 7,
      'duration': 50,
      'calories': 450,
      'icon': Icons.accessibility_new,
    },
    {
      'title': 'Pernas',
      'description': 'Treino completo para membros inferiores',
      'exercises': 8,
      'duration': 55,
      'calories': 520,
      'icon': Icons.directions_run,
    },
    {
      'title': 'Ombros',
      'description': 'Desenvolvimento completo dos ombros',
      'exercises': 5,
      'duration': 40,
      'calories': 380,
      'icon': Icons.sports_gymnastics,
    },
    {
      'title': 'Abdômen',
      'description': 'Fortalecimento e definição do abdômen',
      'exercises': 6,
      'duration': 25,
      'calories': 220,
      'icon': Icons.self_improvement,
    },
    {
      'title': 'Cardio',
      'description': 'Treino cardiovascular para condicionamento',
      'exercises': 4,
      'duration': 30,
      'calories': 300,
      'icon': Icons.directions_bike,
    },
  ];

  @override
  Widget build(BuildContext context) => Scaffold(
    appBar: AppBar(title: const Text('Seus treinos')),
    body: CustomScrollView(
      slivers: [
        SliverPadding(
          padding: const EdgeInsets.fromLTRB(20, 8, 20, 24),
          sliver: SliverToBoxAdapter(
            child: Entrance(
              child: Column(
                crossAxisAlignment: CrossAxisAlignment.start,
                children: [
                  const Text(
                    'FORÇA. FOCO. CONSISTÊNCIA.',
                    style: TextStyle(
                      color: AppColors.sky,
                      fontSize: 10,
                      letterSpacing: 2,
                      fontWeight: FontWeight.w700,
                    ),
                  ),
                  const SizedBox(height: 8),
                  Text(
                    'Encontre seu\npróximo desafio.',
                    style: Theme.of(context).textTheme.headlineLarge,
                  ),
                  const SizedBox(height: 10),
                  const Text(
                    'Rotinas por grupo muscular. Escolha seu foco de hoje.',
                  ),
                ],
              ),
            ),
          ),
        ),
        SliverPadding(
          padding: const EdgeInsets.fromLTRB(20, 0, 20, 28),
          sliver: SliverList.separated(
            itemCount: workouts.length,
            separatorBuilder: (_, _) => const SizedBox(height: 16),
            itemBuilder: (context, index) {
              final workout = workouts[index];
              return Material(
                color: Theme.of(context).cardColor,
                borderRadius: BorderRadius.circular(26),
                clipBehavior: Clip.antiAlias,
                child: InkWell(
                  onTap: () => Navigator.push(
                    context,
                    MaterialPageRoute(
                      builder: (_) => WorkoutDetailScreen(
                        workoutName: workout['title'],
                        duration: workout['duration'],
                        calories: workout['calories'],
                      ),
                    ),
                  ),
                  child: Padding(
                    padding: const EdgeInsets.all(22),
                    child: Column(
                      crossAxisAlignment: CrossAxisAlignment.start,
                      children: [
                        Row(
                          crossAxisAlignment: CrossAxisAlignment.start,
                          children: [
                            Expanded(
                              child: Column(
                                crossAxisAlignment: CrossAxisAlignment.start,
                                children: [
                                  Text(
                                    'PLANO 0${index + 1}',
                                    style: const TextStyle(
                                      color: AppColors.sky,
                                      fontSize: 10,
                                      letterSpacing: 2,
                                      fontWeight: FontWeight.w700,
                                    ),
                                  ),
                                  const SizedBox(height: 12),
                                  Text(
                                    workout['title'],
                                    style: Theme.of(context)
                                        .textTheme
                                        .headlineMedium,
                                  ),
                                  const SizedBox(height: 8),
                                  Text(workout['description']),
                                ],
                              ),
                            ),
                            const SizedBox(width: 12),
                            Container(
                              width: 68,
                              height: 78,
                              decoration: BoxDecoration(
                                gradient: AppColors.heroGradient,
                                borderRadius: BorderRadius.circular(22),
                              ),
                              child: Icon(
                                workout['icon'],
                                color: AppColors.white,
                                size: 32,
                              ),
                            ),
                          ],
                        ),
                        const SizedBox(height: 20),
                        const Divider(),
                        const SizedBox(height: 12),
                        Wrap(
                          spacing: 16,
                          runSpacing: 8,
                          children: [
                            _info(
                              context,
                              Icons.schedule_rounded,
                              '${workout['duration']} min',
                            ),
                            _info(
                              context,
                              Icons.fitness_center_rounded,
                              '${workout['exercises']} exercícios',
                            ),
                            _info(
                              context,
                              Icons.local_fire_department_outlined,
                              '~${workout['calories']} kcal',
                            ),
                          ],
                        ),
                        const SizedBox(height: 16),
                        const Row(
                          children: [
                            Text(
                              'Explorar treino',
                              style: TextStyle(
                                color: AppColors.sky,
                                fontWeight: FontWeight.w700,
                              ),
                            ),
                            Spacer(),
                            Icon(
                              Icons.arrow_forward_rounded,
                              color: AppColors.sky,
                              size: 20,
                            ),
                          ],
                        ),
                      ],
                    ),
                  ),
                ),
              );
            },
          ),
        ),
      ],
    ),
  );

  Widget _info(BuildContext context, IconData icon, String value) => Row(
    mainAxisSize: MainAxisSize.min,
    children: [
      Icon(icon, size: 15, color: Theme.of(context).colorScheme.primary),
      const SizedBox(width: 5),
      Text(value, style: Theme.of(context).textTheme.bodySmall),
    ],
  );
}
