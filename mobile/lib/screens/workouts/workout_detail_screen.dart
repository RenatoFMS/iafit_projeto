import 'dart:async';

import 'package:flutter/material.dart';

import '../../models/engine_exercise_map.dart';
import '../../models/workout_history_model.dart';
import '../../services/database_service.dart';
import '../../services/engine_service.dart';
import '../../models/exercise_catalog.dart';
import '../../theme/app_theme.dart';
import '../../widgets/engine_live_card.dart';
import '../../widgets/premium_components.dart';
import '../exercises/engine_workout_screen.dart';
import '../videos/video_detail_screen.dart';
import 'movement_camera_screen.dart';

class WorkoutDetailScreen extends StatelessWidget {
  final String workoutName;
  final int duration;
  final int calories;

  const WorkoutDetailScreen({
    super.key,
    required this.workoutName,
    required this.duration,
    required this.calories,
  });

  static const Color blue = Color(0xFF2563EB);
  static const Color deepBlue = Color(0xFF10295C);

  List<Map<String, dynamic>> get exercises {
    switch (workoutName) {
      case 'Costas + Bíceps':
        return [
          {
            'name': 'Puxada frontal',
            'muscle': 'Costas',
            'sets': 3,
            'reps': '10-12',
            'rest': 60,
          },
          {
            'name': 'Remada baixa',
            'muscle': 'Costas',
            'sets': 3,
            'reps': '10-12',
            'rest': 60,
          },
          {
            'name': 'Remada curvada',
            'muscle': 'Costas',
            'sets': 3,
            'reps': '8-10',
            'rest': 75,
          },
          {
            'name': 'Pullover',
            'muscle': 'Costas',
            'sets': 3,
            'reps': '12-15',
            'rest': 60,
          },
          {
            'name': 'Rosca direta',
            'muscle': 'Bíceps',
            'sets': 3,
            'reps': '10-12',
            'rest': 60,
          },
          {
            'name': 'Rosca martelo',
            'muscle': 'Bíceps',
            'sets': 3,
            'reps': '10-12',
            'rest': 60,
          },
          {
            'name': 'Rosca concentrada',
            'muscle': 'Bíceps',
            'sets': 3,
            'reps': '10-12',
            'rest': 60,
          },
        ];

      case 'Pernas':
        return [
          {
            'name': 'Agachamento livre',
            'muscle': 'Quadríceps',
            'sets': 4,
            'reps': '8-12',
            'rest': 90,
          },
          {
            'name': 'Leg press',
            'muscle': 'Pernas',
            'sets': 4,
            'reps': '10-12',
            'rest': 90,
          },
          {
            'name': 'Cadeira extensora',
            'muscle': 'Quadríceps',
            'sets': 3,
            'reps': '12-15',
            'rest': 60,
          },
          {
            'name': 'Mesa flexora',
            'muscle': 'Posterior',
            'sets': 3,
            'reps': '10-12',
            'rest': 60,
          },
          {
            'name': 'Stiff',
            'muscle': 'Posterior',
            'sets': 3,
            'reps': '8-12',
            'rest': 75,
          },
          {
            'name': 'Elevação pélvica',
            'muscle': 'Glúteos',
            'sets': 3,
            'reps': '10-15',
            'rest': 75,
          },
          {
            'name': 'Panturrilha em pé',
            'muscle': 'Panturrilhas',
            'sets': 4,
            'reps': '12-15',
            'rest': 45,
          },
          {
            'name': 'Panturrilha sentado',
            'muscle': 'Panturrilhas',
            'sets': 3,
            'reps': '15-20',
            'rest': 45,
          },
        ];

      case 'Ombros':
        return [
          {
            'name': 'Desenvolvimento',
            'muscle': 'Ombros',
            'sets': 3,
            'reps': '8-12',
            'rest': 75,
          },
          {
            'name': 'Elevação lateral',
            'muscle': 'Ombros',
            'sets': 3,
            'reps': '12-15',
            'rest': 60,
          },
          {
            'name': 'Elevação frontal',
            'muscle': 'Ombros',
            'sets': 3,
            'reps': '10-12',
            'rest': 60,
          },
          {
            'name': 'Crucifixo inverso',
            'muscle': 'Ombros',
            'sets': 3,
            'reps': '12-15',
            'rest': 60,
          },
          {
            'name': 'Encolhimento',
            'muscle': 'Trapézio',
            'sets': 3,
            'reps': '10-15',
            'rest': 60,
          },
        ];

      case 'Abdômen':
        return [
          {
            'name': 'Prancha',
            'muscle': 'Abdômen',
            'sets': 3,
            'reps': '30-60s',
            'rest': 45,
          },
          {
            'name': 'Abdominal supra',
            'muscle': 'Abdômen',
            'sets': 3,
            'reps': '15-20',
            'rest': 45,
          },
          {
            'name': 'Abdominal infra',
            'muscle': 'Abdômen',
            'sets': 3,
            'reps': '12-15',
            'rest': 45,
          },
          {
            'name': 'Abdominal bicicleta',
            'muscle': 'Abdômen',
            'sets': 3,
            'reps': '15-20',
            'rest': 45,
          },
          {
            'name': 'Elevação de pernas',
            'muscle': 'Abdômen',
            'sets': 3,
            'reps': '10-15',
            'rest': 45,
          },
          {
            'name': 'Prancha lateral',
            'muscle': 'Core',
            'sets': 3,
            'reps': '30-45s',
            'rest': 45,
          },
        ];

      case 'Cardio':
        return [
          {
            'name': 'Caminhada',
            'muscle': 'Cardio',
            'sets': 1,
            'reps': '5 min',
            'rest': 30,
          },
          {
            'name': 'Corrida',
            'muscle': 'Cardio',
            'sets': 1,
            'reps': '15 min',
            'rest': 30,
          },
          {
            'name': 'Bicicleta',
            'muscle': 'Cardio',
            'sets': 1,
            'reps': '5 min',
            'rest': 30,
          },
          {
            'name': 'Caminhada leve',
            'muscle': 'Cardio',
            'sets': 1,
            'reps': '5 min',
            'rest': 30,
          },
        ];

      default:
        return [
          {
            'name': 'Supino reto',
            'muscle': 'Peito',
            'sets': 3,
            'reps': '8-12',
            'rest': 75,
          },
          {
            'name': 'Supino inclinado',
            'muscle': 'Peito',
            'sets': 3,
            'reps': '8-12',
            'rest': 75,
          },
          {
            'name': 'Crucifixo',
            'muscle': 'Peito',
            'sets': 3,
            'reps': '10-15',
            'rest': 60,
          },
          {
            'name': 'Tríceps pulley',
            'muscle': 'Tríceps',
            'sets': 3,
            'reps': '10-12',
            'rest': 60,
          },
          {
            'name': 'Tríceps francês',
            'muscle': 'Tríceps',
            'sets': 3,
            'reps': '10-12',
            'rest': 60,
          },
          {
            'name': 'Tríceps testa',
            'muscle': 'Tríceps',
            'sets': 3,
            'reps': '8-12',
            'rest': 60,
          },
        ];
    }
  }

  @override
  Widget build(BuildContext context) {
    final theme = Theme.of(context);

    return Scaffold(
      backgroundColor: theme.scaffoldBackgroundColor,
      appBar: AppBar(
        title: const Text(
          'Detalhes do treino',
          style: TextStyle(fontWeight: FontWeight.w800),
        ),
      ),
      body: ListView(
        padding: const EdgeInsets.fromLTRB(20, 6, 20, 30),
        children: [
          _buildWorkoutHero(context),

          const SizedBox(height: 28),

          _buildSectionTitle(context, 'Exercícios'),

          const SizedBox(height: 12),

          ...List.generate(exercises.length, (index) {
            final exercise = exercises[index];

            return _exerciseCard(context, index, exercise);
          }),

          const SizedBox(height: 8),

          SizedBox(
            height: 58,
            child: ElevatedButton.icon(
              onPressed: () {
                final list = exercises;
                if (list.isNotEmpty && EngineService.instance.enabled) {
                  final firstId = EngineExerciseMap.idFor(
                    list.first['name'] as String,
                  );
                  if (firstId != null) {
                    unawaited(EngineService.instance.selectExercise(firstId));
                  }
                }
                Navigator.push(
                  context,
                  MaterialPageRoute(
                    builder: (_) => WorkoutSessionScreen(
                      workoutName: workoutName,
                      duration: duration,
                      calories: calories,
                      exercises: list,
                    ),
                  ),
                );
              },
              icon: const Icon(Icons.play_arrow_rounded, color: Colors.white),
              label: const Text(
                'COMEÇAR TREINO',
                style: TextStyle(
                  color: Colors.white,
                  fontWeight: FontWeight.w800,
                  letterSpacing: 0.4,
                ),
              ),
            ),
          ),
        ],
      ),
    );
  }

  Widget _buildWorkoutHero(BuildContext context) => Container(
    padding: const EdgeInsets.all(24),
    decoration: BoxDecoration(
      gradient: AppColors.heroGradient,
      borderRadius: BorderRadius.circular(28),
      border: Border.all(color: AppColors.sky.withValues(alpha: .3)),
    ),
    child: Column(
      crossAxisAlignment: CrossAxisAlignment.start,
      children: [
        Row(
          children: [
            const Expanded(
              child: Text(
                'SEU PLANO DE EVOLUÇÃO',
                style: TextStyle(
                  color: AppColors.white,
                  fontSize: 10,
                  letterSpacing: 2,
                  fontWeight: FontWeight.w700,
                ),
              ),
            ),
            const StrengthArtwork(size: 90),
          ],
        ),
        Text(
          workoutName,
          style: const TextStyle(
            color: Colors.white,
            fontSize: 32,
            height: 1.08,
            fontWeight: FontWeight.w800,
            letterSpacing: -.8,
          ),
        ),
        const SizedBox(height: 12),
        const Text(
          'Um movimento de cada vez. Um passo além.',
          style: TextStyle(color: Color(0xFFBFDBFE)),
        ),
        const SizedBox(height: 24),
        Wrap(
          spacing: 20,
          runSpacing: 12,
          children: [
            _summaryItem(Icons.schedule_rounded, '$duration min'),
            _summaryItem(
              Icons.local_fire_department_outlined,
              '~$calories kcal',
            ),
            _summaryItem(
              Icons.fitness_center_rounded,
              '${exercises.length} exercícios',
            ),
          ],
        ),
      ],
    ),
  );
  Widget _summaryItem(IconData icon, String text) {
    return Row(
      mainAxisSize: MainAxisSize.min,
      children: [
        Icon(icon, color: Colors.white, size: 18),
        const SizedBox(width: 6),
        Flexible(
          child: Text(
            text,
            overflow: TextOverflow.ellipsis,
            style: const TextStyle(
              color: Colors.white,
              fontSize: 12,
              fontWeight: FontWeight.w700,
            ),
          ),
        ),
      ],
    );
  }

  Widget _buildSectionTitle(BuildContext context, String title) {
    final theme = Theme.of(context);

    return Row(
      children: [
        Text(
          title,
          style: TextStyle(
            color: theme.colorScheme.onSurface,
            fontSize: 20,
            fontWeight: FontWeight.w800,
          ),
        ),
        const SizedBox(width: 9),
        Container(
          padding: const EdgeInsets.symmetric(horizontal: 8, vertical: 4),
          decoration: BoxDecoration(
            color: blue.withValues(alpha: 0.10),
            borderRadius: BorderRadius.circular(8),
          ),
          child: Text(
            '${exercises.length}',
            style: const TextStyle(
              color: blue,
              fontSize: 11,
              fontWeight: FontWeight.w800,
            ),
          ),
        ),
      ],
    );
  }

  Widget _exerciseCard(
    BuildContext context,
    int index,
    Map<String, dynamic> exercise,
  ) {
    final theme = Theme.of(context);

    return Container(
      margin: const EdgeInsets.only(bottom: 11),
      decoration: BoxDecoration(
        color: theme.cardColor,
        borderRadius: BorderRadius.circular(19),
        border: Border.all(
          color: theme.colorScheme.outline.withValues(alpha: 0.55),
        ),
      ),
      child: Material(
        color: Colors.transparent,
        child: InkWell(
          borderRadius: BorderRadius.circular(19),
          onTap: () {
            _showExerciseInfo(context, exercise);
          },
          child: Padding(
            padding: const EdgeInsets.all(15),
            child: Row(
              children: [
                Container(
                  width: 48,
                  height: 48,
                  alignment: Alignment.center,
                  decoration: BoxDecoration(
                    color: blue.withValues(
                      alpha: theme.brightness == Brightness.dark ? 0.15 : 0.09,
                    ),
                    borderRadius: BorderRadius.circular(14),
                  ),
                  child: Text(
                    '${index + 1}'.padLeft(2, '0'),
                    style: const TextStyle(
                      color: blue,
                      fontWeight: FontWeight.w800,
                      fontSize: 14,
                    ),
                  ),
                ),

                const SizedBox(width: 13),

                Expanded(
                  child: Column(
                    crossAxisAlignment: CrossAxisAlignment.start,
                    children: [
                      Text(
                        exercise['name'],
                        maxLines: 1,
                        overflow: TextOverflow.ellipsis,
                        style: TextStyle(
                          color: theme.colorScheme.onSurface,
                          fontSize: 15,
                          fontWeight: FontWeight.w800,
                        ),
                      ),

                      const SizedBox(height: 5),

                      Text(
                        '${exercise['sets']} séries • ${exercise['reps']} repetições',
                        style: TextStyle(
                          color: theme.colorScheme.onSurface.withValues(
                            alpha: 0.52,
                          ),
                          fontSize: 12,
                        ),
                      ),

                      const SizedBox(height: 7),

                      Row(
                        children: [
                          const Icon(
                            Icons.accessibility_new_rounded,
                            size: 13,
                            color: blue,
                          ),
                          const SizedBox(width: 4),
                          Text(
                            exercise['muscle'],
                            style: const TextStyle(
                              color: blue,
                              fontSize: 10.5,
                              fontWeight: FontWeight.w700,
                            ),
                          ),
                        ],
                      ),
                    ],
                  ),
                ),

                const SizedBox(width: 8),

                Container(
                  width: 32,
                  height: 32,
                  decoration: BoxDecoration(
                    color: blue.withValues(alpha: 0.08),
                    shape: BoxShape.circle,
                  ),
                  child: const Icon(
                    Icons.info_outline_rounded,
                    color: blue,
                    size: 18,
                  ),
                ),
              ],
            ),
          ),
        ),
      ),
    );
  }

  void _showExerciseInfo(BuildContext context, Map<String, dynamic> exercise) {
    final theme = Theme.of(context);

    showModalBottomSheet(
      context: context,
      showDragHandle: true,
      backgroundColor: theme.cardColor,
      isScrollControlled: true,
      builder: (_) {
        return Padding(
          padding: const EdgeInsets.fromLTRB(24, 4, 24, 30),
          child: Column(
            mainAxisSize: MainAxisSize.min,
            crossAxisAlignment: CrossAxisAlignment.start,
            children: [
              Row(
                children: [
                  Container(
                    width: 48,
                    height: 48,
                    decoration: BoxDecoration(
                      color: blue.withValues(alpha: 0.10),
                      borderRadius: BorderRadius.circular(14),
                    ),
                    child: const Icon(
                      Icons.fitness_center_rounded,
                      color: blue,
                    ),
                  ),
                  const SizedBox(width: 13),
                  Expanded(
                    child: Text(
                      exercise['name'],
                      style: TextStyle(
                        color: theme.colorScheme.onSurface,
                        fontSize: 22,
                        fontWeight: FontWeight.w800,
                      ),
                    ),
                  ),
                ],
              ),

              const SizedBox(height: 9),

              Container(
                padding: const EdgeInsets.symmetric(
                  horizontal: 10,
                  vertical: 6,
                ),
                decoration: BoxDecoration(
                  color: blue.withValues(alpha: 0.10),
                  borderRadius: BorderRadius.circular(9),
                ),
                child: Text(
                  exercise['muscle'],
                  style: const TextStyle(
                    color: blue,
                    fontSize: 12,
                    fontWeight: FontWeight.w700,
                  ),
                ),
              ),

              const SizedBox(height: 24),

              _infoRow(
                theme,
                Icons.repeat_rounded,
                'Séries',
                '${exercise['sets']}',
              ),
              _infoRow(
                theme,
                Icons.format_list_numbered_rounded,
                'Repetições',
                '${exercise['reps']}',
              ),
              _infoRow(
                theme,
                Icons.timer_outlined,
                'Descanso',
                '${exercise['rest']} segundos',
              ),
            ],
          ),
        );
      },
    );
  }

  Widget _infoRow(ThemeData theme, IconData icon, String title, String value) {
    return Padding(
      padding: const EdgeInsets.only(bottom: 17),
      child: Row(
        children: [
          Container(
            width: 38,
            height: 38,
            decoration: BoxDecoration(
              color: blue.withValues(alpha: 0.09),
              borderRadius: BorderRadius.circular(11),
            ),
            child: Icon(icon, color: blue, size: 19),
          ),

          const SizedBox(width: 12),

          Text(
            title,
            style: TextStyle(
              color: theme.colorScheme.onSurface,
              fontWeight: FontWeight.w600,
              fontSize: 14,
            ),
          ),

          const Spacer(),

          Text(
            value,
            style: TextStyle(
              color: theme.colorScheme.onSurface.withValues(alpha: 0.55),
              fontSize: 14,
              fontWeight: FontWeight.w600,
            ),
          ),
        ],
      ),
    );
  }
}

class WorkoutSessionScreen extends StatefulWidget {
  final String workoutName;
  final int duration;
  final int calories;
  final List<Map<String, dynamic>> exercises;

  const WorkoutSessionScreen({
    super.key,
    required this.workoutName,
    required this.duration,
    required this.calories,
    required this.exercises,
  });

  @override
  State<WorkoutSessionScreen> createState() => _WorkoutSessionScreenState();
}

class _WorkoutSessionScreenState extends State<WorkoutSessionScreen>
    with WidgetsBindingObserver {
  static const Color blue = Color(0xFF2563EB);

  int _currentExercise = 0;
  int _currentSet = 1;
  int _restSeconds = 0;

  Timer? _timer;
  Timer? _uiTicker;
  final Stopwatch _stopwatch = Stopwatch();

  bool _isResting = false;
  bool _isFinished = false;
  bool _paused = false;
  bool _saving = false;
  int? _cameraRepetitions;

  Future<void> _openMovementCamera() async {
    var seriesCompleted = false;
    final count = await Navigator.of(context).push<int>(
      MaterialPageRoute(
        builder: (_) => MovementCameraScreen(
          exerciseName: currentExercise['name'] as String,
          onSeriesCompleted: () {
            seriesCompleted = true;
          },
        ),
      ),
    );
    if (!mounted) return;
    if (seriesCompleted || count != null) {
      _registerCompletedCameraSeries(count);
    }
  }

  void _registerCompletedCameraSeries(int? repetitions) {
    if (_isFinished || _saving) return;
    _timer?.cancel();

    final sets = currentExercise['sets'] as int;
    ScaffoldMessenger.of(context).showSnackBar(
      const SnackBar(
        content: Text('Série concluída. Mais um passo na sua evolução!'),
        behavior: SnackBarBehavior.fixed,
        duration: Duration(seconds: 2),
      ),
    );

    if (_currentSet < sets) {
      setState(() {
        _isResting = false;
        _restSeconds = 0;
        _cameraRepetitions = repetitions;
        _currentSet++;
      });
      _syncEngineExercise();
      return;
    }

    if (_currentExercise < widget.exercises.length - 1) {
      setState(() {
        _isResting = false;
        _restSeconds = 0;
        _cameraRepetitions = null;
        _currentExercise++;
        _currentSet = 1;
      });
      _syncEngineExercise();
      return;
    }

    setState(() {
      _isResting = false;
      _restSeconds = 0;
      _cameraRepetitions = repetitions;
    });
    unawaited(_finishWorkout());
  }

  @override
  void initState() {
    super.initState();
    WidgetsBinding.instance.addObserver(this);
    _stopwatch.start();
    _uiTicker = Timer.periodic(const Duration(seconds: 1), (_) {
      if (mounted && !_paused && !_isFinished) setState(() {});
    });
    _syncEngineExercise();
  }

  /// Mantém o motor Python no exercício atual do treino (`id_atual` do main.py).
  ///
  /// Exercícios que o motor não analisa encerram a série anterior para que as
  /// repetições dela não sejam atribuídas ao exercício errado. Sem motor
  /// configurado, não faz nada.
  void _syncEngineExercise() {
    final engine = EngineService.instance;
    if (!engine.enabled) return;
    final engineId = EngineExerciseMap.idFor(currentExercise['name'] as String);
    unawaited(
      engineId == null
          ? engine.finishSeries(clearActiveExercise: true)
          : engine.selectExercise(engineId),
    );
  }

  void _setPaused(bool value) {
    if (_isFinished || _saving) return;
    setState(() => _paused = value);
    if (value) {
      _stopwatch.stop();
    } else {
      _stopwatch.start();
    }
  }

  @override
  void didChangeAppLifecycleState(AppLifecycleState state) {
    if (state != AppLifecycleState.resumed && !_paused && mounted) {
      _setPaused(true);
    }
  }

  Future<void> _openDemonstration() async {
    final info = ExerciseCatalog.find(currentExercise['name'] as String);
    if (info == null) return;
    final wasPaused = _paused;
    _setPaused(true);
    await Navigator.push(
      context,
      MaterialPageRoute(
        builder: (_) => VideoDetailScreen(
          title: info.name,
          category: info.category,
          duration: '',
          description: info.description,
          videoId: info.videoId,
        ),
      ),
    );
    if (mounted && !wasPaused) _setPaused(false);
  }

  Map<String, dynamic> get currentExercise =>
      widget.exercises[_currentExercise];

  int get totalSets {
    int total = 0;

    for (final exercise in widget.exercises) {
      total += exercise['sets'] as int;
    }

    return total;
  }

  int get completedSets {
    int completed = 0;

    for (int i = 0; i < _currentExercise; i++) {
      completed += widget.exercises[i]['sets'] as int;
    }

    completed += _currentSet - 1;

    return completed;
  }

  double get progress {
    if (totalSets == 0) return 0;

    return completedSets / totalSets;
  }

  void _completeSet() {
    if (_isResting || _isFinished || _paused || _saving) {
      return;
    }

    final sets = currentExercise['sets'] as int;
    ScaffoldMessenger.of(context).showSnackBar(
      const SnackBar(
        content: Text('Série concluída. Mais um passo na sua evolução!'),
        behavior: SnackBarBehavior.fixed,
        duration: Duration(seconds: 2),
      ),
    );
    setState(() => _cameraRepetitions = null);

    if (_currentSet < sets) {
      if (EngineService.instance.enabled &&
          EngineExerciseMap.idFor(currentExercise['name'] as String) != null) {
        unawaited(EngineService.instance.finishSeries());
      }
      _startRest(currentExercise['rest'] as int);

      return;
    }

    if (_currentExercise < widget.exercises.length - 1) {
      setState(() {
        _currentExercise++;
        _currentSet = 1;
      });
      _syncEngineExercise();

      return;
    }

    _finishWorkout();
  }

  void _startRest(int seconds) {
    _timer?.cancel();

    setState(() {
      _restSeconds = seconds;
      _isResting = true;
    });

    _timer = Timer.periodic(const Duration(seconds: 1), (timer) {
      if (!mounted) {
        timer.cancel();
        return;
      }
      if (_paused) return;

      if (_restSeconds <= 1) {
        timer.cancel();

        setState(() {
          _restSeconds = 0;
          _isResting = false;
          _currentSet++;
        });
        _syncEngineExercise();

        return;
      }

      setState(() {
        _restSeconds--;
      });
    });
  }

  void _addRestTime() {
    if (!mounted) return;

    setState(() {
      _restSeconds += 15;
    });
  }

  void _skipRest() {
    _timer?.cancel();

    if (!mounted) return;

    setState(() {
      _restSeconds = 0;
      _isResting = false;
      _currentSet++;
    });
    _syncEngineExercise();
  }

  Future<void> _finishWorkout() async {
    if (_saving || _isFinished) return;
    setState(() => _saving = true);
    _timer?.cancel();
    _stopwatch.stop();

    final elapsed = _stopwatch.elapsed.inSeconds;
    final actualDuration = (elapsed / 60).ceil();

    final finalDuration = actualDuration > 0 ? actualDuration : widget.duration;

    final workout = WorkoutHistoryModel(
      workoutName: widget.workoutName,
      duration: finalDuration,
      calories: widget.calories,
      date: DateTime.now().toIso8601String(),
    );

    try {
      await DatabaseService.instance.insertWorkout(workout);
    } catch (_) {
      if (!mounted) return;
      setState(() => _saving = false);
      if (!_paused) _stopwatch.start();
      ScaffoldMessenger.of(context).showSnackBar(
        const SnackBar(
          content: Text('Não foi possível salvar o treino. Tente novamente.'),
        ),
      );
      return;
    }

    // Garante que a última série do motor IAFit seja guardada e importada.
    if (EngineService.instance.enabled) {
      unawaited(EngineService.instance.finishSeries());
    }

    if (!mounted) return;

    setState(() {
      _isFinished = true;
    });

    Navigator.of(context).pushReplacement(
      MaterialPageRoute(
        builder: (_) => WorkoutCompletedScreen(
          workoutName: widget.workoutName,
          duration: finalDuration,
          calories: widget.calories,
          exerciseCount: widget.exercises.length,
        ),
      ),
    );
  }

  Future<bool> _confirmExit() async {
    if (_isFinished) return true;

    final result = await showDialog<bool>(
      context: context,
      builder: (dialogContext) {
        return AlertDialog(
          title: const Text(
            'Sair do treino?',
            style: TextStyle(fontWeight: FontWeight.w800),
          ),
          content: const Text(
            'Seu progresso desta sessão não será registrado '
            'se você sair agora.',
          ),
          actions: [
            TextButton(
              onPressed: () {
                Navigator.of(dialogContext).pop(false);
              },
              child: const Text('CONTINUAR'),
            ),
            TextButton(
              onPressed: () {
                Navigator.of(dialogContext).pop(true);
              },
              style: TextButton.styleFrom(foregroundColor: Colors.redAccent),
              child: const Text('SAIR'),
            ),
          ],
        );
      },
    );

    if (!context.mounted) return false;

    return result == true;
  }

  @override
  void dispose() {
    _timer?.cancel();
    _uiTicker?.cancel();
    WidgetsBinding.instance.removeObserver(this);
    _stopwatch.stop();

    super.dispose();
  }

  @override
  Widget build(BuildContext context) {
    final theme = Theme.of(context);
    final exercise = currentExercise;

    return PopScope(
      canPop: false,
      onPopInvokedWithResult: (didPop, result) async {
        if (didPop) return;

        final shouldExit = await _confirmExit();

        if (!context.mounted) return;

        if (shouldExit) {
          Navigator.of(context).pop();
        }
      },
      child: Scaffold(
        backgroundColor: theme.scaffoldBackgroundColor,
        appBar: AppBar(
          title: Text(
            widget.workoutName,
            style: const TextStyle(fontWeight: FontWeight.w800),
          ),
          leading: IconButton(
            onPressed: () async {
              final shouldExit = await _confirmExit();

              if (!context.mounted) return;

              if (shouldExit) {
                Navigator.of(context).pop();
              }
            },
            icon: const Icon(Icons.close_rounded),
          ),
        ),
        body: SafeArea(
          child: Padding(
            padding: const EdgeInsets.fromLTRB(20, 6, 20, 20),
            child: Column(
              children: [
                ClipRRect(
                  borderRadius: BorderRadius.circular(10),
                  child: LinearProgressIndicator(
                    value: progress,
                    minHeight: 8,
                    backgroundColor: theme.brightness == Brightness.dark
                        ? const Color(0xFF263854)
                        : const Color(0xFFDBEAFE),
                    valueColor: const AlwaysStoppedAnimation(blue),
                  ),
                ),

                const SizedBox(height: 10),

                Row(
                  mainAxisAlignment: MainAxisAlignment.spaceBetween,
                  children: [
                    Expanded(
                      child: Text(
                        '$completedSets de $totalSets séries concluídas',
                        style: TextStyle(
                          color: theme.colorScheme.onSurface.withValues(
                            alpha: 0.52,
                          ),
                          fontSize: 12,
                          fontWeight: FontWeight.w500,
                        ),
                      ),
                    ),
                    Container(
                      padding: const EdgeInsets.symmetric(
                        horizontal: 10,
                        vertical: 5,
                      ),
                      decoration: BoxDecoration(
                        color: blue.withValues(alpha: 0.09),
                        borderRadius: BorderRadius.circular(9),
                      ),
                      child: Text(
                        _formatStopwatch(),
                        style: const TextStyle(
                          color: blue,
                          fontWeight: FontWeight.w800,
                          fontSize: 12,
                        ),
                      ),
                    ),
                  ],
                ),

                const SizedBox(height: 24),

                Expanded(
                  child: _isResting
                      ? _buildRestScreen()
                      : _buildExerciseScreen(exercise),
                ),
              ],
            ),
          ),
        ),
      ),
    );
  }

  Widget _buildExerciseScreen(Map<String, dynamic> exercise) {
    final theme = Theme.of(context);
    final exerciseName = exercise['name'] as String;
    final info = ExerciseCatalog.find(exerciseName);
    final engineId = EngineExerciseMap.idFor(exerciseName);
    return SingleChildScrollView(
      child: Column(
        children: [
          Text(
            'EXERCÍCIO ${_currentExercise + 1} DE ${widget.exercises.length}',
            style: const TextStyle(
              color: AppColors.sky,
              fontSize: 10,
              letterSpacing: 2,
              fontWeight: FontWeight.w700,
            ),
          ),
          const SizedBox(height: 14),
          Text(
            exerciseName,
            textAlign: TextAlign.center,
            style: theme.textTheme.headlineLarge,
          ),
          const SizedBox(height: 6),
          Text(exercise['muscle'] as String),
          if (engineId != null && EngineService.instance.enabled) ...[
            const SizedBox(height: 14),
            EngineLiveCard(
              key: ValueKey('engine-live-$engineId'),
              engineId: engineId,
              exerciseName: exerciseName,
              paused: _paused,
              onSeriesFinished: (state) {
                _registerCompletedCameraSeries(state?.repetitions);
              },
              onExpand: () async {
                var seriesCompleted = false;
                final count = await Navigator.of(context).push<int>(
                  MaterialPageRoute(
                    builder: (_) => EngineWorkoutScreen(
                      engineId: engineId,
                      exerciseName: exerciseName,
                      category: exercise['muscle'] as String?,
                      onSeriesCompleted: () {
                        seriesCompleted = true;
                      },
                    ),
                  ),
                );
                if (!mounted) return;
                if (seriesCompleted || count != null) {
                  _registerCompletedCameraSeries(count);
                }
              },
            ),
          ],
          const SizedBox(height: 8),
          WorkoutDial(
            value: progress,
            title: _formatStopwatch(),
            subtitle: _paused ? 'TREINO PAUSADO' : 'TEMPO DA SESSÃO',
            size: 210,
          ),
          const SizedBox(height: 12),
          Row(
            children: [
              Expanded(
                child: PremiumCard(
                  padding: const EdgeInsets.all(16),
                  child: Column(
                    children: [
                      const Text(
                        'SÉRIE',
                        style: TextStyle(
                          color: AppColors.sky,
                          fontSize: 10,
                          letterSpacing: 1.5,
                        ),
                      ),
                      const SizedBox(height: 8),
                      Text(
                        '$_currentSet/${exercise['sets']}',
                        style: theme.textTheme.headlineMedium,
                      ),
                    ],
                  ),
                ),
              ),
              const SizedBox(width: 12),
              Expanded(
                child: PremiumCard(
                  padding: const EdgeInsets.all(16),
                  child: Column(
                    children: [
                      const Text(
                        'REPETIÇÕES',
                        style: TextStyle(
                          color: AppColors.sky,
                          fontSize: 10,
                          letterSpacing: 1.5,
                        ),
                      ),
                      const SizedBox(height: 8),
                      Text(
                        '${exercise['reps']}',
                        style: theme.textTheme.headlineMedium,
                      ),
                    ],
                  ),
                ),
              ),
            ],
          ),
          const SizedBox(height: 16),
          if (info != null) ...[
            SizedBox(
              width: double.infinity,
              child: OutlinedButton.icon(
                onPressed: _saving ? null : _openDemonstration,
                icon: const Icon(Icons.play_circle_outline_rounded),
                label: const Text('VER DEMONSTRAÇÃO'),
              ),
            ),
            const SizedBox(height: 10),
          ],
          SizedBox(
            width: double.infinity,
            child: OutlinedButton.icon(
              onPressed: _paused || _saving ? null : _openMovementCamera,
              icon: const Icon(Icons.videocam_outlined),
              label: const Text('VER MINHA EXECUÇÃO'),
            ),
          ),
          if (_cameraRepetitions != null && _cameraRepetitions! > 0)
            Padding(
              padding: const EdgeInsets.only(top: 10),
              child: Text(
                '$_cameraRepetitions repetições detectadas nesta série',
              ),
            ),
          const SizedBox(height: 16),
          SizedBox(
            width: double.infinity,
            child: ElevatedButton.icon(
              onPressed: _paused || _saving ? null : _completeSet,
              icon: Icon(
                _saving ? Icons.hourglass_top_rounded : Icons.check_rounded,
              ),
              label: Text(
                _saving
                    ? 'SALVANDO...'
                    : _currentSet < exercise['sets']
                    ? 'CONCLUIR SÉRIE'
                    : _currentExercise < widget.exercises.length - 1
                    ? 'PRÓXIMO EXERCÍCIO'
                    : 'FINALIZAR TREINO',
              ),
            ),
          ),
          const SizedBox(height: 8),
          TextButton.icon(
            onPressed: _saving ? null : () => _setPaused(!_paused),
            icon: Icon(
              _paused ? Icons.play_arrow_rounded : Icons.pause_rounded,
            ),
            label: Text(_paused ? 'Retomar treino' : 'Pausar treino'),
          ),
          const SizedBox(height: 8),
          Text(
            'Mantenha o controle do movimento. A qualidade de cada repetição importa.',
            textAlign: TextAlign.center,
            style: theme.textTheme.bodySmall,
          ),
          const SizedBox(height: 16),
        ],
      ),
    );
  }

  Widget _buildRestScreen() => SingleChildScrollView(
    child: Column(
      children: [
        const SizedBox(height: 16),
        const Text(
          'RESPIRE. RECUPERE. REPITA.',
          style: TextStyle(
            color: AppColors.sky,
            fontSize: 10,
            fontWeight: FontWeight.w700,
            letterSpacing: 2,
          ),
        ),
        const SizedBox(height: 24),
        WorkoutDial(
          value:
              (_restSeconds / (currentExercise['rest'] as int).clamp(1, 3600))
                  .clamp(0, 1),
          title: '$_restSeconds',
          subtitle: _paused ? 'DESCANSO PAUSADO' : 'SEGUNDOS DE DESCANSO',
          size: 240,
        ),
        const SizedBox(height: 24),
        Text(
          'Próxima série: ${_currentSet + 1}',
          style: Theme.of(context).textTheme.titleLarge,
        ),
        const SizedBox(height: 6),
        Text(currentExercise['name'] as String),
        const SizedBox(height: 28),
        Row(
          children: [
            Expanded(
              child: OutlinedButton.icon(
                onPressed: _paused ? null : _addRestTime,
                icon: const Icon(Icons.add_rounded),
                label: const Text('+15s'),
              ),
            ),
            const SizedBox(width: 12),
            Expanded(
              child: ElevatedButton(
                onPressed: _paused ? null : _skipRest,
                child: const Text('PULAR'),
              ),
            ),
          ],
        ),
        const SizedBox(height: 12),
        TextButton.icon(
          onPressed: () => _setPaused(!_paused),
          icon: Icon(_paused ? Icons.play_arrow_rounded : Icons.pause_rounded),
          label: Text(_paused ? 'Retomar treino' : 'Pausar treino'),
        ),
      ],
    ),
  );
  String _formatStopwatch() {
    final elapsed = _stopwatch.elapsed;

    final minutes = elapsed.inMinutes.remainder(60).toString().padLeft(2, '0');

    final seconds = elapsed.inSeconds.remainder(60).toString().padLeft(2, '0');

    return '$minutes:$seconds';
  }
}

class WorkoutCompletedScreen extends StatelessWidget {
  final String workoutName;
  final int duration;
  final int calories;
  final int exerciseCount;

  const WorkoutCompletedScreen({
    super.key,
    required this.workoutName,
    required this.duration,
    required this.calories,
    required this.exerciseCount,
  });

  static const Color blue = Color(0xFF2563EB);
  static const Color deepBlue = Color(0xFF10295C);

  @override
  Widget build(BuildContext context) => Scaffold(
    appBar: AppBar(
      automaticallyImplyLeading: false,
      title: const Text('Sessão concluída'),
    ),
    body: SafeArea(
      child: ListView(
        padding: const EdgeInsets.fromLTRB(20, 12, 20, 28),
        children: [
          const Entrance(
            child: Center(
              child: WorkoutDial(
                value: 1,
                title: '100%',
                subtitle: 'VOCÊ CONSEGUIU',
                size: 220,
              ),
            ),
          ),
          const SizedBox(height: 18),
          Text(
            'Mais forte que ontem.',
            textAlign: TextAlign.center,
            style: Theme.of(context).textTheme.headlineLarge,
          ),
          const SizedBox(height: 10),
          Text(workoutName, textAlign: TextAlign.center),
          const SizedBox(height: 28),
          LayoutBuilder(
            builder: (context, constraints) => Wrap(
              spacing: 10,
              runSpacing: 10,
              children: [
                for (final metric in [
                  (Icons.schedule_rounded, '$duration min', 'Duração'),
                  (
                    Icons.local_fire_department_outlined,
                    '~$calories',
                    'kcal estimadas',
                  ),
                  (
                    Icons.fitness_center_rounded,
                    '$exerciseCount',
                    'Exercícios',
                  ),
                ])
                  SizedBox(
                    width: constraints.maxWidth < 330
                        ? (constraints.maxWidth - 10) / 2
                        : (constraints.maxWidth - 20) / 3,
                    child: _resultCard(
                      context,
                      metric.$1,
                      metric.$2,
                      metric.$3,
                    ),
                  ),
              ],
            ),
          ),
          const SizedBox(height: 24),
          const PremiumCard(
            child: Row(
              children: [
                Icon(
                  Icons.emoji_events_outlined,
                  color: AppColors.sky,
                  size: 30,
                ),
                SizedBox(width: 14),
                Expanded(
                  child: Text(
                    'Treino registrado! Seu histórico e seu XP foram atualizados. A consistência constrói resultados.',
                  ),
                ),
              ],
            ),
          ),
          const SizedBox(height: 28),
          ElevatedButton.icon(
            onPressed: () =>
                Navigator.popUntil(context, (route) => route.isFirst),
            icon: const Icon(Icons.arrow_forward_rounded),
            label: const Text('VOLTAR AO INÍCIO'),
          ),
        ],
      ),
    ),
  );
  Widget _resultCard(
    BuildContext context,
    IconData icon,
    String value,
    String label,
  ) {
    final theme = Theme.of(context);

    return Container(
      padding: const EdgeInsets.symmetric(vertical: 15, horizontal: 6),
      decoration: BoxDecoration(
        color: theme.cardColor,
        borderRadius: BorderRadius.circular(17),
        border: Border.all(
          color: theme.colorScheme.outline.withValues(alpha: 0.55),
        ),
      ),
      child: Column(
        children: [
          Container(
            width: 34,
            height: 34,
            decoration: BoxDecoration(
              color: blue.withValues(alpha: 0.09),
              shape: BoxShape.circle,
            ),
            child: Icon(icon, color: blue, size: 18),
          ),

          const SizedBox(height: 7),

          Text(
            value,
            maxLines: 1,
            overflow: TextOverflow.ellipsis,
            style: TextStyle(
              color: theme.colorScheme.onSurface,
              fontSize: 15,
              fontWeight: FontWeight.w800,
            ),
          ),

          const SizedBox(height: 3),

          Text(
            label,
            style: TextStyle(
              color: theme.colorScheme.onSurface.withValues(alpha: 0.50),
              fontSize: 10,
            ),
          ),
        ],
      ),
    );
  }
}
