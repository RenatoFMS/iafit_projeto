import 'package:flutter/material.dart';

import '../../theme/app_theme.dart';
import '../../widgets/premium_components.dart';
import '../../widgets/weekly_activity.dart';

import '../../models/user_model.dart';
import '../../models/workout_history_model.dart';
import '../../services/database_service.dart';
import '../../services/engine_service.dart';
import '../../services/gamification_service.dart';

import '../workouts/workout_detail_screen.dart';
import '../exercises/exercises_screen.dart';
import '../videos/videos_screen.dart';
import '../progress/progress_screen.dart';
import '../content/content_screen.dart';
import '../settings/settings_screen.dart';

class HomeScreen extends StatefulWidget {
  const HomeScreen({super.key});

  @override
  State<HomeScreen> createState() => _HomeScreenState();
}

class _HomeScreenState extends State<HomeScreen> {
  UserModel? _user;
  List<WorkoutHistoryModel> _workouts = [];

  GamificationData? _gamification;

  int _totalCalories = 0;
  int _totalWorkouts = 0;
  int _totalDuration = 0;

  bool _isLoading = true;

  @override
  void initState() {
    super.initState();
    EngineService.instance.revision.addListener(_onEngineData);
    _loadData();
  }

  @override
  void dispose() {
    EngineService.instance.revision.removeListener(_onEngineData);
    super.dispose();
  }

  /// Novos treinos chegaram do motor IAFit: recarrega os dados da tela inicial.
  void _onEngineData() {
    if (mounted) _loadData();
  }

  Future<void> _loadData() async {
    if (mounted) {
      setState(() {
        _isLoading = true;
      });
    }

    final database = DatabaseService.instance;

    final user = await database.getUser();
    final workouts = await database.getWorkoutHistory();
    final calories = await database.getTotalCalories();
    final totalWorkouts = await database.getTotalWorkouts();
    final duration = await database.getTotalDuration();

    final gamification = GamificationService.calculate(workouts);

    if (!mounted) return;

    setState(() {
      _user = user;
      _workouts = workouts;
      _totalCalories = calories;
      _totalWorkouts = totalWorkouts;
      _totalDuration = duration;
      _gamification = gamification;
      _isLoading = false;
    });
  }

  String get _greeting {
    final hour = DateTime.now().hour;

    if (hour < 12) return 'Bom dia';
    if (hour < 18) return 'Boa tarde';
    return 'Boa noite';
  }

  String get _firstName {
    if (_user == null || _user!.name.trim().isEmpty) {
      return 'Atleta';
    }

    return _user!.name.trim().split(' ').first;
  }

  WorkoutHistoryModel? get _lastWorkout {
    if (_workouts.isEmpty) return null;
    return _workouts.first;
  }

  String get _recommendedWorkoutName {
    switch (_user?.goal) {
      case 'Ganhar massa muscular':
        return 'Hipertrofia Completa';
      case 'Perder peso':
        return 'Cardio + Abdômen';
      case 'Manter o peso':
        return 'Full Body';
      case 'Melhorar condicionamento':
        return 'Cardio e Resistência';
      default:
        return 'Full Body';
    }
  }

  int get _recommendedWorkoutDuration {
    switch (_user?.goal) {
      case 'Ganhar massa muscular':
        return 55;
      case 'Perder peso':
        return 40;
      case 'Manter o peso':
        return 45;
      case 'Melhorar condicionamento':
        return 50;
      default:
        return 45;
    }
  }

  int get _recommendedWorkoutCalories {
    switch (_user?.goal) {
      case 'Ganhar massa muscular':
        return 430;
      case 'Perder peso':
        return 380;
      case 'Manter o peso':
        return 400;
      case 'Melhorar condicionamento':
        return 450;
      default:
        return 400;
    }
  }

  String get _recommendedWorkoutExercises {
    final plan = WorkoutDetailScreen(
      workoutName: _recommendedWorkoutName,
      duration: _recommendedWorkoutDuration,
      calories: _recommendedWorkoutCalories,
    );
    return '${plan.exercises.length} exercícios';
  }

  String get _recommendedDescription {
    switch (_user?.goal) {
      case 'Ganhar massa muscular':
        return 'Foco em força e hipertrofia';
      case 'Perder peso':
        return 'Foco em gasto calórico';
      case 'Manter o peso':
        return 'Treino completo para o corpo';
      case 'Melhorar condicionamento':
        return 'Foco em resistência e cardio';
      default:
        return 'Treino completo para o corpo';
    }
  }

  String _formatDuration(int minutes) {
    if (minutes < 60) return '$minutes min';

    final hours = minutes ~/ 60;
    final remaining = minutes % 60;

    if (remaining == 0) return '${hours}h';

    return '${hours}h ${remaining}min';
  }

  String _formatDate(String date) {
    final parsed = DateTime.tryParse(date);

    if (parsed == null) return date;

    final day = parsed.day.toString().padLeft(2, '0');
    final month = parsed.month.toString().padLeft(2, '0');

    return '$day/$month/${parsed.year}';
  }

  Future<void> _openWorkout(String name, int duration, int calories) async {
    await Navigator.push(
      context,
      MaterialPageRoute(
        builder: (_) => WorkoutDetailScreen(
          workoutName: name,
          duration: duration,
          calories: calories,
        ),
      ),
    );

    await _loadData();
  }

  void _openExercises() {
    Navigator.push(
      context,
      MaterialPageRoute(builder: (_) => const ExercisesScreen()),
    );
  }

  void _openVideos() {
    Navigator.push(
      context,
      MaterialPageRoute(builder: (_) => const VideosScreen()),
    );
  }

  void _openProgress() {
    Navigator.push(
      context,
      MaterialPageRoute(builder: (_) => const ProgressScreen()),
    );
  }

  void _openContent() {
    Navigator.push(
      context,
      MaterialPageRoute(builder: (_) => const ContentScreen()),
    );
  }

  void _openSettings() {
    Navigator.push(
      context,
      MaterialPageRoute(builder: (_) => const SettingsScreen()),
    );
  }

  Future<void> _openRecommendedWorkout() async {
    await _openWorkout(
      _recommendedWorkoutName,
      _recommendedWorkoutDuration,
      _recommendedWorkoutCalories,
    );
  }

  @override
  Widget build(BuildContext context) {
    final theme = Theme.of(context);
    final data = _gamification;
    return Scaffold(
      body: SafeArea(
        bottom: false,
        child: RefreshIndicator(
          onRefresh: _loadData,
          child: _isLoading
              ? const Center(child: CircularProgressIndicator())
              : ListView(
                  padding: const EdgeInsets.fromLTRB(20, 16, 20, 28),
                  children: [
                    Entrance(
                      child: Row(
                        children: [
                          Container(
                            width: 48,
                            height: 48,
                            decoration: BoxDecoration(
                              gradient: AppColors.heroGradient,
                              borderRadius: BorderRadius.circular(16),
                            ),
                            child: const Icon(
                              Icons.bolt_rounded,
                              color: Colors.white,
                              size: 28,
                            ),
                          ),
                          const SizedBox(width: 12),
                          Expanded(
                            child: Column(
                              crossAxisAlignment: CrossAxisAlignment.start,
                              children: [
                                Text(
                                  'FITNESS PRO',
                                  style: TextStyle(
                                    color: theme.colorScheme.onSurface,
                                    fontSize: 14,
                                    letterSpacing: 2,
                                    fontWeight: FontWeight.w800,
                                  ),
                                ),
                                const Text(
                                  'SEU PRÓXIMO NÍVEL',
                                  style: TextStyle(
                                    fontSize: 9,
                                    letterSpacing: 1.6,
                                    color: AppColors.sky,
                                  ),
                                ),
                              ],
                            ),
                          ),
                          IconButton.outlined(
                            onPressed: _openSettings,
                            tooltip: 'Configurações',
                            icon: const Icon(Icons.tune_rounded),
                          ),
                        ],
                      ),
                    ),
                    const SizedBox(height: 28),
                    Entrance(
                      child: Column(
                        crossAxisAlignment: CrossAxisAlignment.start,
                        children: [
                          Text(
                            '$_greeting, $_firstName',
                            style: theme.textTheme.headlineLarge,
                          ),
                          const SizedBox(height: 6),
                          const Text('Cada movimento conta. Vamos evoluir?'),
                        ],
                      ),
                    ),
                    const SizedBox(height: 24),
                    Entrance(child: _todayCard()),
                    const SizedBox(height: 24),
                    const SectionHeading('Seu ritmo', eyebrow: 'VISÃO GERAL'),
                    const SizedBox(height: 14),
                    LayoutBuilder(
                      builder: (context, constraints) => Wrap(
                        spacing: 10,
                        runSpacing: 10,
                        children: [
                          _metric(
                            Icons.fitness_center_rounded,
                            '$_totalWorkouts',
                            'Treinos',
                            constraints.maxWidth,
                          ),
                          _metric(
                            Icons.schedule_rounded,
                            _formatDuration(_totalDuration),
                            'Tempo total',
                            constraints.maxWidth,
                          ),
                          _metric(
                            Icons.local_fire_department_outlined,
                            '$_totalCalories',
                            'kcal estimadas',
                            constraints.maxWidth,
                          ),
                        ],
                      ),
                    ),
                    const SizedBox(height: 24),
                    WeeklyActivity(workouts: _workouts),
                    const SizedBox(height: 24),
                    const SectionHeading(
                      'Explore seu potencial',
                      eyebrow: 'DO SEU JEITO',
                    ),
                    const SizedBox(height: 14),
                    LayoutBuilder(
                      builder: (context, constraints) => Wrap(
                        spacing: 12,
                        runSpacing: 12,
                        children: [
                          _quickAction(
                            Icons.accessibility_new_rounded,
                            'Exercícios',
                            'Aprenda cada movimento',
                            _openExercises,
                            constraints.maxWidth,
                          ),
                          _quickAction(
                            Icons.play_circle_outline_rounded,
                            'Vídeos',
                            'Técnica em detalhes',
                            _openVideos,
                            constraints.maxWidth,
                          ),
                          _quickAction(
                            Icons.insights_rounded,
                            'Progresso',
                            'Sua evolução real',
                            _openProgress,
                            constraints.maxWidth,
                          ),
                          _quickAction(
                            Icons.auto_stories_outlined,
                            'Conteúdos',
                            'Conhecimento que move',
                            _openContent,
                            constraints.maxWidth,
                          ),
                        ],
                      ),
                    ),
                    if (data != null) ...[
                      const SizedBox(height: 24),
                      PremiumCard(
                        child: Row(
                          children: [
                            WorkoutDial(
                              value: data.progress,
                              title: '${data.level}',
                              subtitle: 'NÍVEL',
                              size: 104,
                            ),
                            const SizedBox(width: 14),
                            Expanded(
                              child: Column(
                                crossAxisAlignment: CrossAxisAlignment.start,
                                children: [
                                  Text(
                                    'Sua consistência vale XP',
                                    style: theme.textTheme.titleMedium,
                                  ),
                                  const SizedBox(height: 6),
                                  Text(
                                    '${data.xp} XP · ${data.nextLevelXp - data.xp} para o próximo nível',
                                  ),
                                  const SizedBox(height: 8),
                                  Text(
                                    '${data.currentStreak} dias de sequência',
                                    style: const TextStyle(
                                      color: AppColors.sky,
                                      fontWeight: FontWeight.w600,
                                    ),
                                  ),
                                  if (data.achievements.isNotEmpty)
                                    Text(
                                      data.achievements.last,
                                      style: theme.textTheme.bodySmall,
                                    ),
                                ],
                              ),
                            ),
                          ],
                        ),
                      ),
                    ],
                    const SizedBox(height: 24),
                    const SectionHeading('Última conquista'),
                    const SizedBox(height: 14),
                    PremiumCard(
                      child: _lastWorkout == null
                          ? const Row(
                              children: [
                                Icon(Icons.flag_outlined, color: AppColors.sky),
                                SizedBox(width: 12),
                                Expanded(
                                  child: Text(
                                    'Seu primeiro treino começa uma nova história. Vamos nessa?',
                                  ),
                                ),
                              ],
                            )
                          : Row(
                              children: [
                                const Icon(
                                  Icons.check_circle_outline_rounded,
                                  color: AppColors.cyan,
                                  size: 32,
                                ),
                                const SizedBox(width: 14),
                                Expanded(
                                  child: Column(
                                    crossAxisAlignment:
                                        CrossAxisAlignment.start,
                                    children: [
                                      Text(
                                        _lastWorkout!.workoutName,
                                        style: theme.textTheme.titleMedium,
                                      ),
                                      Text(
                                        '${_formatDate(_lastWorkout!.date)} · ${_lastWorkout!.duration} min',
                                      ),
                                    ],
                                  ),
                                ),
                              ],
                            ),
                    ),
                  ],
                ),
        ),
      ),
    );
  }

  Widget _todayCard() {
    return Container(
      clipBehavior: Clip.antiAlias,
      decoration: BoxDecoration(
        gradient: AppColors.heroGradient,
        borderRadius: BorderRadius.circular(28),
        border: Border.all(color: AppColors.sky.withValues(alpha: .35)),
        boxShadow: [
          BoxShadow(
            color: AppColors.primary.withValues(alpha: .18),
            blurRadius: 28,
            offset: const Offset(0, 12),
          ),
        ],
      ),
      child: Stack(
        children: [
          const Positioned(
            right: -28,
            top: 12,
            child: Opacity(opacity: .35, child: StrengthArtwork(size: 190)),
          ),
          Padding(
            padding: const EdgeInsets.all(24),
            child: Column(
              crossAxisAlignment: CrossAxisAlignment.start,
              children: [
                const Row(
                  children: [
                    Icon(Icons.bolt_rounded, color: AppColors.sky, size: 16),
                    SizedBox(width: 5),
                    Text(
                      'SEU TREINO DE HOJE',
                      style: TextStyle(
                        color: Colors.white,
                        fontSize: 10,
                        letterSpacing: 1.6,
                        fontWeight: FontWeight.w700,
                      ),
                    ),
                  ],
                ),
                const SizedBox(height: 20),
                FractionallySizedBox(
                  widthFactor: .72,
                  child: Text(
                    _recommendedWorkoutName,
                    style: const TextStyle(
                      fontSize: 30,
                      height: 1.08,
                      fontWeight: FontWeight.w800,
                      letterSpacing: -.8,
                      color: Colors.white,
                    ),
                  ),
                ),
                const SizedBox(height: 10),
                FractionallySizedBox(
                  widthFactor: .75,
                  child: Text(
                    _recommendedDescription,
                    style: const TextStyle(
                      color: Color(0xFFBFDBFE),
                      fontSize: 13,
                    ),
                  ),
                ),
                const SizedBox(height: 18),
                Wrap(
                  spacing: 14,
                  runSpacing: 6,
                  children: [
                    Row(
                      mainAxisSize: MainAxisSize.min,
                      children: [
                        const Icon(
                          Icons.schedule_rounded,
                          size: 14,
                          color: Colors.white,
                        ),
                        const SizedBox(width: 5),
                        Text(
                          '$_recommendedWorkoutDuration min',
                          style: const TextStyle(
                            color: Colors.white,
                            fontSize: 12,
                          ),
                        ),
                      ],
                    ),
                    Text(
                      _recommendedWorkoutExercises,
                      style: const TextStyle(color: Colors.white, fontSize: 12),
                    ),
                    Text(
                      '~$_recommendedWorkoutCalories kcal',
                      style: const TextStyle(color: Colors.white, fontSize: 12),
                    ),
                  ],
                ),
                const SizedBox(height: 22),
                SizedBox(
                  width: double.infinity,
                  child: ElevatedButton.icon(
                    style: ElevatedButton.styleFrom(
                      backgroundColor: Colors.white,
                      foregroundColor: AppColors.primary,
                    ),
                    onPressed: _openRecommendedWorkout,
                    icon: const Icon(Icons.play_arrow_rounded),
                    label: const Text('Começar meu treino'),
                  ),
                ),
              ],
            ),
          ),
        ],
      ),
    );
  }

  Widget _metric(IconData icon, String value, String label, double width) =>
      SizedBox(
        width: width < 330 ? (width - 10) / 2 : (width - 20) / 3,
        child: PremiumCard(
          padding: const EdgeInsets.all(14),
          child: ConstrainedBox(
            constraints: const BoxConstraints(minHeight: 116),
            child: Column(
              crossAxisAlignment: CrossAxisAlignment.start,
              children: [
                Icon(icon, color: AppColors.sky, size: 22),
                const SizedBox(height: 14),
                FittedBox(
                  fit: BoxFit.scaleDown,
                  child: Text(
                    value,
                    style: Theme.of(context).textTheme.titleLarge,
                  ),
                ),
                const SizedBox(height: 4),
                Text(label, style: Theme.of(context).textTheme.bodySmall),
              ],
            ),
          ),
        ),
      );

  Widget _quickAction(
    IconData icon,
    String title,
    String subtitle,
    VoidCallback onTap,
    double width,
  ) => SizedBox(
    width: (width - 12) / 2,
    child: Material(
      color: Theme.of(context).cardColor,
      borderRadius: BorderRadius.circular(22),
      child: InkWell(
        onTap: onTap,
        borderRadius: BorderRadius.circular(22),
        child: Padding(
          padding: const EdgeInsets.all(18),
          child: Column(
            crossAxisAlignment: CrossAxisAlignment.start,
            children: [
              Icon(icon, color: AppColors.sky, size: 27),
              const SizedBox(height: 16),
              Text(title, style: Theme.of(context).textTheme.titleMedium),
              const SizedBox(height: 4),
              Text(subtitle, style: Theme.of(context).textTheme.bodySmall),
            ],
          ),
        ),
      ),
    ),
  );
}
