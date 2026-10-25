import 'package:flutter/material.dart';

import '../../theme/app_theme.dart';
import '../../widgets/weekly_activity.dart';

import '../../models/weight_history_model.dart';
import '../../models/workout_history_model.dart';
import '../../services/database_service.dart';
import '../../services/engine_service.dart';

class ProgressScreen extends StatefulWidget {
  const ProgressScreen({super.key});

  @override
  State<ProgressScreen> createState() => _ProgressScreenState();
}

class _ProgressScreenState extends State<ProgressScreen> {
  final DatabaseService _database = DatabaseService.instance;

  bool _loading = true;

  int _totalCalories = 0;
  int _totalWorkouts = 0;
  int _totalDuration = 0;
  int _totalRepetitions = 0;
  int _totalPostureErrors = 0;

  double? _currentWeight;
  double? _weightVariation;

  List<WorkoutHistoryModel> _workoutHistory = [];
  List<WeightHistoryModel> _weightHistory = [];

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

  /// Novos treinos chegaram do motor IAFit: recarrega histórico e gráficos.
  void _onEngineData() {
    if (mounted) _loadData();
  }

  Future<void> _loadData() async {
    if (!mounted) return;
    setState(() {
      _loading = true;
    });

    final user = await _database.getUser();
    _weightVariation = null;

    if (user != null) {
      _currentWeight = user.weight;
    }

    final calories = await _database.getTotalCalories();
    final workouts = await _database.getTotalWorkouts();
    final duration = await _database.getTotalDuration();
    final repetitions = await _database.getTotalRepetitions();
    final postureErrors = await _database.getTotalPostureErrors();

    final workoutHistory = await _database.getWorkoutHistory();

    final weightHistory = await _database.getWeightHistory();

    if (weightHistory.isNotEmpty) {
      _currentWeight = weightHistory.last.weight;

      if (weightHistory.length >= 2) {
        _weightVariation =
            weightHistory.last.weight - weightHistory.first.weight;
      }
    }

    if (!mounted) {
      return;
    }

    setState(() {
      _totalCalories = calories;
      _totalWorkouts = workouts;
      _totalDuration = duration;
      _totalRepetitions = repetitions;
      _totalPostureErrors = postureErrors;
      _workoutHistory = workoutHistory;
      _weightHistory = weightHistory;
      _loading = false;
    });
  }

  String _formatDuration(int minutes) {
    if (minutes < 60) {
      return '$minutes min';
    }

    final hours = minutes ~/ 60;
    final remaining = minutes % 60;

    if (remaining == 0) {
      return '${hours}h';
    }

    return '${hours}h ${remaining}min';
  }

  String _formatDate(String date) {
    final parsed = DateTime.tryParse(date);

    if (parsed == null) {
      return date;
    }

    return '${parsed.day.toString().padLeft(2, '0')}/'
        '${parsed.month.toString().padLeft(2, '0')}/'
        '${parsed.year}';
  }

  Future<void> _addWeight() async {
    final controller = TextEditingController(
      text: _currentWeight?.toStringAsFixed(1) ?? '',
    );

    final weight = await showDialog<double>(
      context: context,
      builder: (context) {
        final theme = Theme.of(context);
        final colorScheme = theme.colorScheme;

        return AlertDialog(
          title: const Text(
            'Registrar peso',
            style: TextStyle(fontWeight: FontWeight.w700),
          ),
          content: TextField(
            controller: controller,
            keyboardType: const TextInputType.numberWithOptions(decimal: true),
            decoration: InputDecoration(
              labelText: 'Peso',
              suffixText: 'kg',
              prefixIcon: const Icon(Icons.monitor_weight_outlined),
              filled: true,
              fillColor: colorScheme.surface,
            ),
          ),
          actions: [
            TextButton(
              onPressed: () {
                Navigator.pop(context);
              },
              child: const Text('Cancelar'),
            ),
            ElevatedButton(
              onPressed: () {
                final value = double.tryParse(
                  controller.text.replaceAll(',', '.'),
                );

                if (value != null && value > 0) {
                  Navigator.pop(context, value);
                }
              },
              child: const Text('Salvar'),
            ),
          ],
        );
      },
    );

    controller.dispose();

    if (weight == null) {
      return;
    }

    final now = DateTime.now();

    await _database.insertWeight(
      WeightHistoryModel(weight: weight, date: now.toIso8601String()),
    );

    final user = await _database.getUser();

    if (user != null) {
      await _database.updateUser(user.copyWith(weight: weight));
    }

    await _loadData();
  }

  @override
  Widget build(BuildContext context) {
    final theme = Theme.of(context);
    final colorScheme = theme.colorScheme;

    return Scaffold(
      appBar: AppBar(
        title: const Text('Meu progresso'),
        actions: [
          Container(
            margin: const EdgeInsets.only(right: 12),
            decoration: BoxDecoration(
              color: colorScheme.surface,
              borderRadius: BorderRadius.circular(12),
              border: Border.all(
                color: colorScheme.outline.withValues(alpha: 0.35),
              ),
            ),
            child: IconButton(
              onPressed: _loadData,
              icon: const Icon(Icons.refresh_rounded),
              tooltip: 'Atualizar',
            ),
          ),
        ],
      ),
      body: _loading
          ? Center(child: CircularProgressIndicator(color: colorScheme.primary))
          : RefreshIndicator(
              color: colorScheme.primary,
              onRefresh: _loadData,
              child: SingleChildScrollView(
                physics: const AlwaysScrollableScrollPhysics(),
                padding: const EdgeInsets.fromLTRB(20, 8, 20, 110),
                child: Column(
                  crossAxisAlignment: CrossAxisAlignment.start,
                  children: [
                    _buildIntro(),
                    const SizedBox(height: 22),
                    _buildOverview(),
                    const SizedBox(height: 28),
                    WeeklyActivity(workouts: _workoutHistory),
                    const SizedBox(height: 28),
                    _buildWeightSection(),
                    const SizedBox(height: 28),
                    _buildWorkoutSection(),
                    const SizedBox(height: 28),
                    _buildHistorySection(),
                  ],
                ),
              ),
            ),
    );
  }

  Widget _buildIntro() {
    return Container(
      width: double.infinity,
      padding: const EdgeInsets.all(19),
      decoration: BoxDecoration(
        gradient: LinearGradient(
          colors: [AppColors.deep, AppColors.primary],
          begin: Alignment.topLeft,
          end: Alignment.bottomRight,
        ),
        borderRadius: BorderRadius.circular(23),
      ),
      child: Row(
        children: [
          Container(
            width: 48,
            height: 48,
            decoration: BoxDecoration(
              color: Colors.white.withValues(alpha: 0.14),
              borderRadius: BorderRadius.circular(15),
            ),
            child: const Icon(
              Icons.insights_rounded,
              color: Colors.white,
              size: 25,
            ),
          ),
          const SizedBox(width: 13),
          const Expanded(
            child: Column(
              crossAxisAlignment: CrossAxisAlignment.start,
              children: [
                Text(
                  'Sua evolução',
                  style: TextStyle(
                    color: Colors.white,
                    fontSize: 17,
                    fontWeight: FontWeight.w700,
                  ),
                ),
                SizedBox(height: 3),
                Text(
                  'Acompanhe seus resultados e mantenha o ritmo.',
                  style: TextStyle(
                    color: Colors.white70,
                    fontSize: 12,
                    height: 1.4,
                  ),
                ),
              ],
            ),
          ),
        ],
      ),
    );
  }

  Widget _buildOverview() {
    return Column(
      crossAxisAlignment: CrossAxisAlignment.start,
      children: [
        _sectionHeader('Visão geral', 'Seus principais números'),
        const SizedBox(height: 14),
        Row(
          children: [
            Expanded(
              child: _metricCard(
                icon: Icons.local_fire_department_rounded,
                value: '$_totalCalories',
                label: 'kcal',
              ),
            ),
            const SizedBox(width: 12),
            Expanded(
              child: _metricCard(
                icon: Icons.fitness_center_rounded,
                value: '$_totalWorkouts',
                label: 'treinos',
              ),
            ),
          ],
        ),
        const SizedBox(height: 12),
        Row(
          children: [
            Expanded(
              child: _metricCard(
                icon: Icons.timer_rounded,
                value: _formatDuration(_totalDuration),
                label: 'tempo',
              ),
            ),
            const SizedBox(width: 12),
            Expanded(
              child: _metricCard(
                icon: Icons.monitor_weight_outlined,
                value: _currentWeight == null
                    ? '—'
                    : '${_currentWeight!.toStringAsFixed(1)} kg',
                label: 'peso atual',
              ),
            ),
          ],
        ),
        if (_totalRepetitions > 0 || _totalPostureErrors > 0) ...[
          const SizedBox(height: 12),
          Row(
            children: [
              Expanded(
                child: _metricCard(
                  icon: Icons.repeat_rounded,
                  value: '$_totalRepetitions',
                  label: 'repetições',
                ),
              ),
              const SizedBox(width: 12),
              Expanded(
                child: _metricCard(
                  icon: Icons.accessibility_new_rounded,
                  value: '$_totalPostureErrors',
                  label: 'erros de postura',
                ),
              ),
            ],
          ),
        ],
      ],
    );
  }

  Widget _sectionHeader(String title, String subtitle) {
    final colorScheme = Theme.of(context).colorScheme;

    return Column(
      crossAxisAlignment: CrossAxisAlignment.start,
      children: [
        Text(
          title,
          style: TextStyle(
            color: colorScheme.onSurface,
            fontSize: 21,
            fontWeight: FontWeight.w800,
            letterSpacing: -0.2,
          ),
        ),
        const SizedBox(height: 3),
        Text(
          subtitle,
          style: TextStyle(
            color: colorScheme.onSurface.withValues(alpha: 0.50),
            fontSize: 12,
          ),
        ),
      ],
    );
  }

  Widget _metricCard({
    required IconData icon,
    required String value,
    required String label,
  }) {
    final colorScheme = Theme.of(context).colorScheme;

    return Container(
      padding: const EdgeInsets.all(17),
      decoration: BoxDecoration(
        color: colorScheme.surface,
        borderRadius: BorderRadius.circular(19),
        border: Border.all(
          color: colorScheme.outline.withValues(alpha: 0.35),
          width: 0.7,
        ),
      ),
      child: Column(
        crossAxisAlignment: CrossAxisAlignment.start,
        children: [
          Container(
            width: 40,
            height: 40,
            decoration: BoxDecoration(
              color: colorScheme.primary.withValues(alpha: 0.10),
              borderRadius: BorderRadius.circular(12),
            ),
            child: Icon(icon, color: colorScheme.primary, size: 21),
          ),
          const SizedBox(height: 13),
          Text(
            value,
            maxLines: 1,
            overflow: TextOverflow.ellipsis,
            style: TextStyle(
              color: colorScheme.onSurface,
              fontSize: 20,
              fontWeight: FontWeight.w800,
              letterSpacing: -0.3,
            ),
          ),
          const SizedBox(height: 3),
          Text(
            label,
            style: TextStyle(
              color: colorScheme.onSurface.withValues(alpha: 0.50),
              fontSize: 11.5,
              fontWeight: FontWeight.w500,
            ),
          ),
        ],
      ),
    );
  }

  Widget _buildWeightSection() {
    final colorScheme = Theme.of(context).colorScheme;

    return Column(
      crossAxisAlignment: CrossAxisAlignment.start,
      children: [
        Row(
          crossAxisAlignment: CrossAxisAlignment.end,
          children: [
            Expanded(
              child: _sectionHeader(
                'Evolução do peso',
                'Acompanhe suas medições',
              ),
            ),
            TextButton.icon(
              onPressed: _addWeight,
              icon: const Icon(Icons.add_rounded, size: 17),
              label: const Text('Registrar'),
            ),
          ],
        ),
        const SizedBox(height: 13),
        Container(
          width: double.infinity,
          padding: const EdgeInsets.all(19),
          decoration: BoxDecoration(
            color: colorScheme.surface,
            borderRadius: BorderRadius.circular(22),
            border: Border.all(
              color: colorScheme.outline.withValues(alpha: 0.35),
              width: 0.7,
            ),
          ),
          child: Column(
            children: [
              Row(
                children: [
                  Container(
                    width: 52,
                    height: 52,
                    decoration: BoxDecoration(
                      color: colorScheme.primary.withValues(alpha: 0.10),
                      borderRadius: BorderRadius.circular(16),
                    ),
                    child: Icon(
                      Icons.monitor_weight_outlined,
                      color: colorScheme.primary,
                      size: 26,
                    ),
                  ),
                  const SizedBox(width: 14),
                  Column(
                    crossAxisAlignment: CrossAxisAlignment.start,
                    children: [
                      Text(
                        'Peso atual',
                        style: TextStyle(
                          color: colorScheme.onSurface.withValues(alpha: 0.50),
                          fontSize: 12,
                        ),
                      ),
                      const SizedBox(height: 3),
                      Text(
                        _currentWeight == null
                            ? 'Sem registro'
                            : '${_currentWeight!.toStringAsFixed(1)} kg',
                        style: TextStyle(
                          color: colorScheme.onSurface,
                          fontSize: 23,
                          fontWeight: FontWeight.w800,
                        ),
                      ),
                    ],
                  ),
                  const Spacer(),
                  if (_weightVariation != null) _buildVariation(),
                ],
              ),
              const SizedBox(height: 24),
              if (_weightHistory.length >= 2)
                _buildWeightChart()
              else
                _buildEmptyChart(),
            ],
          ),
        ),
      ],
    );
  }

  Widget _buildVariation() {
    final colorScheme = Theme.of(context).colorScheme;

    final variation = _weightVariation!;
    final positive = variation > 0;
    final negative = variation < 0;

    final icon = positive
        ? Icons.trending_up_rounded
        : negative
        ? Icons.trending_down_rounded
        : Icons.remove_rounded;

    return Container(
      padding: const EdgeInsets.symmetric(horizontal: 10, vertical: 8),
      decoration: BoxDecoration(
        color: colorScheme.primary.withValues(alpha: 0.09),
        borderRadius: BorderRadius.circular(13),
      ),
      child: Column(
        crossAxisAlignment: CrossAxisAlignment.end,
        children: [
          Icon(icon, color: colorScheme.primary, size: 18),
          const SizedBox(height: 2),
          Text(
            '${variation > 0 ? '+' : ''}'
            '${variation.toStringAsFixed(1)} kg',
            style: TextStyle(
              color: colorScheme.primary,
              fontWeight: FontWeight.w800,
              fontSize: 12,
            ),
          ),
        ],
      ),
    );
  }

  Widget _buildWeightChart() {
    final weights = _weightHistory.map((item) => item.weight).toList();

    final minWeight = weights.reduce((a, b) => a < b ? a : b);

    final maxWeight = weights.reduce((a, b) => a > b ? a : b);

    final range = maxWeight - minWeight;

    final chartMin = range == 0 ? minWeight - 2 : minWeight - 1;

    final chartMax = range == 0 ? maxWeight + 2 : maxWeight + 1;

    return SizedBox(
      height: 190,
      child: CustomPaint(
        painter: _WeightChartPainter(
          weights: weights,
          minWeight: chartMin,
          maxWeight: chartMax,
          primaryColor: Theme.of(context).colorScheme.primary,
          gridColor: Theme.of(context).colorScheme.outline
              .withValues(alpha: 0.22),
        ),
        child: const SizedBox.expand(),
      ),
    );
  }

  Widget _buildEmptyChart() {
    final colorScheme = Theme.of(context).colorScheme;

    return Container(
      height: 150,
      width: double.infinity,
      alignment: Alignment.center,
      decoration: BoxDecoration(
        color: colorScheme.onSurface.withValues(alpha: 0.025),
        borderRadius: BorderRadius.circular(17),
        border: Border.all(color: colorScheme.outline.withValues(alpha: 0.22)),
      ),
      child: Column(
        mainAxisAlignment: MainAxisAlignment.center,
        children: [
          Container(
            width: 48,
            height: 48,
            decoration: BoxDecoration(
              color: colorScheme.primary.withValues(alpha: 0.08),
              shape: BoxShape.circle,
            ),
            child: Icon(
              Icons.show_chart_rounded,
              size: 25,
              color: colorScheme.primary,
            ),
          ),
          const SizedBox(height: 10),
          Text(
            'Registre seu peso pelo menos duas vezes',
            style: TextStyle(
              color: colorScheme.onSurface.withValues(alpha: 0.65),
              fontSize: 12.5,
              fontWeight: FontWeight.w600,
            ),
          ),
          const SizedBox(height: 4),
          Text(
            'para visualizar sua evolução.',
            style: TextStyle(
              color: colorScheme.onSurface.withValues(alpha: 0.45),
              fontSize: 11.5,
            ),
          ),
        ],
      ),
    );
  }

  Widget _buildWorkoutSection() {
    return Column(
      crossAxisAlignment: CrossAxisAlignment.start,
      children: [
        _sectionHeader('Atividade', 'Seu desempenho acumulado'),
        const SizedBox(height: 14),
        Container(
          width: double.infinity,
          padding: const EdgeInsets.all(21),
          decoration: BoxDecoration(
            gradient: LinearGradient(
              colors: [AppColors.deep, AppColors.primary],
              begin: Alignment.topLeft,
              end: Alignment.bottomRight,
            ),
            borderRadius: BorderRadius.circular(23),
          ),
          child: Column(
            crossAxisAlignment: CrossAxisAlignment.start,
            children: [
              Row(
                children: [
                  Container(
                    width: 40,
                    height: 40,
                    decoration: BoxDecoration(
                      color: Colors.white.withValues(alpha: 0.13),
                      borderRadius: BorderRadius.circular(12),
                    ),
                    child: const Icon(
                      Icons.emoji_events_outlined,
                      color: Colors.white,
                      size: 21,
                    ),
                  ),
                  const SizedBox(width: 11),
                  const Text(
                    'DESEMPENHO',
                    style: TextStyle(
                      color: Colors.white70,
                      fontSize: 10,
                      fontWeight: FontWeight.w700,
                      letterSpacing: 1.2,
                    ),
                  ),
                ],
              ),
              const SizedBox(height: 18),
              Text(
                '$_totalWorkouts',
                style: const TextStyle(
                  color: Colors.white,
                  fontSize: 40,
                  fontWeight: FontWeight.w800,
                  height: 1,
                ),
              ),
              const SizedBox(height: 6),
              Text(
                _totalWorkouts == 1 ? 'treino concluído' : 'treinos concluídos',
                style: const TextStyle(color: Colors.white70, fontSize: 13),
              ),
              const SizedBox(height: 22),
              Container(height: 1, color: Colors.white.withValues(alpha: 0.12)),
              const SizedBox(height: 17),
              Row(
                children: [
                  Expanded(
                    child: _activityInfo(
                      Icons.local_fire_department_rounded,
                      '$_totalCalories kcal',
                    ),
                  ),
                  Container(
                    width: 1,
                    height: 30,
                    color: Colors.white.withValues(alpha: 0.12),
                  ),
                  const SizedBox(width: 16),
                  Expanded(
                    child: _activityInfo(
                      Icons.timer_rounded,
                      _formatDuration(_totalDuration),
                    ),
                  ),
                ],
              ),
            ],
          ),
        ),
      ],
    );
  }

  Widget _activityInfo(IconData icon, String value) {
    return Row(
      children: [
        Container(
          width: 34,
          height: 34,
          decoration: BoxDecoration(
            color: Colors.white.withValues(alpha: 0.12),
            shape: BoxShape.circle,
          ),
          child: Icon(icon, color: Colors.white, size: 17),
        ),
        const SizedBox(width: 9),
        Expanded(
          child: Text(
            value,
            maxLines: 1,
            overflow: TextOverflow.ellipsis,
            style: const TextStyle(
              color: Colors.white,
              fontWeight: FontWeight.w700,
              fontSize: 12,
            ),
          ),
        ),
      ],
    );
  }

  Widget _buildHistorySection() {
    final colorScheme = Theme.of(context).colorScheme;

    return Column(
      crossAxisAlignment: CrossAxisAlignment.start,
      children: [
        _sectionHeader('Histórico de treinos', 'Seus treinos concluídos'),
        const SizedBox(height: 14),
        if (_workoutHistory.isEmpty)
          Container(
            width: double.infinity,
            padding: const EdgeInsets.all(25),
            decoration: BoxDecoration(
              color: colorScheme.surface,
              borderRadius: BorderRadius.circular(20),
              border: Border.all(
                color: colorScheme.outline.withValues(alpha: 0.35),
              ),
            ),
            child: Column(
              children: [
                Container(
                  width: 52,
                  height: 52,
                  decoration: BoxDecoration(
                    color: colorScheme.primary.withValues(alpha: 0.08),
                    shape: BoxShape.circle,
                  ),
                  child: Icon(
                    Icons.fitness_center_outlined,
                    size: 25,
                    color: colorScheme.primary,
                  ),
                ),
                const SizedBox(height: 12),
                Text(
                  'Nenhum treino registrado',
                  style: TextStyle(
                    color: colorScheme.onSurface,
                    fontWeight: FontWeight.w700,
                  ),
                ),
                const SizedBox(height: 5),
                Text(
                  'Complete um treino para vê-lo aqui.',
                  textAlign: TextAlign.center,
                  style: TextStyle(
                    color: colorScheme.onSurface.withValues(alpha: 0.48),
                    fontSize: 12,
                  ),
                ),
              ],
            ),
          )
        else
          ..._workoutHistory.map((workout) => _buildHistoryCard(workout)),
      ],
    );
  }

  Widget _buildHistoryCard(WorkoutHistoryModel workout) {
    final colorScheme = Theme.of(context).colorScheme;

    return Container(
      margin: const EdgeInsets.only(bottom: 11),
      padding: const EdgeInsets.all(15),
      decoration: BoxDecoration(
        color: colorScheme.surface,
        borderRadius: BorderRadius.circular(18),
        border: Border.all(
          color: colorScheme.outline.withValues(alpha: 0.32),
          width: 0.7,
        ),
      ),
      child: Row(
        children: [
          Container(
            width: 49,
            height: 49,
            decoration: BoxDecoration(
              color: colorScheme.primary.withValues(alpha: 0.09),
              borderRadius: BorderRadius.circular(14),
            ),
            child: Icon(
              Icons.fitness_center_rounded,
              color: colorScheme.primary,
              size: 21,
            ),
          ),
          const SizedBox(width: 13),
          Expanded(
            child: Column(
              crossAxisAlignment: CrossAxisAlignment.start,
              children: [
                Text(
                  workout.workoutName,
                  maxLines: 1,
                  overflow: TextOverflow.ellipsis,
                  style: TextStyle(
                    color: colorScheme.onSurface,
                    fontWeight: FontWeight.w700,
                    fontSize: 14.5,
                  ),
                ),
                const SizedBox(height: 5),
                Row(
                  children: [
                    Icon(
                      Icons.calendar_today_outlined,
                      size: 12,
                      color: colorScheme.onSurface.withValues(alpha: 0.42),
                    ),
                    const SizedBox(width: 5),
                    Text(
                      _formatDate(workout.date),
                      style: TextStyle(
                        color: colorScheme.onSurface.withValues(alpha: 0.45),
                        fontSize: 11.5,
                      ),
                    ),
                  ],
                ),
                if (workout.engineSummary != null) ...[
                  const SizedBox(height: 4),
                  Text(
                    workout.engineSummary!,
                    maxLines: 2,
                    overflow: TextOverflow.ellipsis,
                    style: TextStyle(
                      color: (workout.postureErrors ?? 0) > 0
                          ? Colors.orangeAccent
                          : colorScheme.onSurface.withValues(alpha: 0.6),
                      fontSize: 11.5,
                      fontWeight: FontWeight.w600,
                    ),
                  ),
                ],
              ],
            ),
          ),
          const SizedBox(width: 10),
          Column(
            crossAxisAlignment: CrossAxisAlignment.end,
            children: [
              Text(
                workout.caloriesLabel,
                style: TextStyle(
                  color: colorScheme.primary,
                  fontWeight: FontWeight.w800,
                  fontSize: 12,
                ),
              ),
              const SizedBox(height: 5),
              Container(
                padding: const EdgeInsets.symmetric(horizontal: 7, vertical: 4),
                decoration: BoxDecoration(
                  color: colorScheme.onSurface.withValues(alpha: 0.045),
                  borderRadius: BorderRadius.circular(7),
                ),
                child: Text(
                  workout.durationLabel,
                  style: TextStyle(
                    color: colorScheme.onSurface.withValues(alpha: 0.55),
                    fontSize: 10.5,
                    fontWeight: FontWeight.w600,
                  ),
                ),
              ),
            ],
          ),
        ],
      ),
    );
  }
}

class _WeightChartPainter extends CustomPainter {
  final List<double> weights;
  final double minWeight;
  final double maxWeight;
  final Color primaryColor;
  final Color gridColor;

  _WeightChartPainter({
    required this.weights,
    required this.minWeight,
    required this.maxWeight,
    required this.primaryColor,
    required this.gridColor,
  });

  @override
  void paint(Canvas canvas, Size size) {
    if (weights.length < 2) {
      return;
    }

    final chartWidth = size.width - 20;
    final chartHeight = size.height - 20;

    final gridPaint = Paint()
      ..color = gridColor
      ..strokeWidth = 1;

    final linePaint = Paint()
      ..color = primaryColor
      ..strokeWidth = 3
      ..style = PaintingStyle.stroke
      ..strokeCap = StrokeCap.round
      ..strokeJoin = StrokeJoin.round;

    final pointPaint = Paint()
      ..color = primaryColor
      ..style = PaintingStyle.fill;

    final pointOuterPaint = Paint()
      ..color = Colors.white
      ..style = PaintingStyle.fill;

    for (int i = 0; i < 4; i++) {
      final y = 10 + (chartHeight / 3) * i;

      canvas.drawLine(Offset(10, y), Offset(size.width - 10, y), gridPaint);
    }

    final path = Path();

    for (int i = 0; i < weights.length; i++) {
      final x = weights.length == 1
          ? chartWidth / 2
          : 10 + (chartWidth * i / (weights.length - 1));

      final normalized = (weights[i] - minWeight) / (maxWeight - minWeight);

      final y = size.height - 10 - normalized * chartHeight;

      final point = Offset(x, y);

      if (i == 0) {
        path.moveTo(point.dx, point.dy);
      } else {
        path.lineTo(point.dx, point.dy);
      }
    }

    final area = Path.from(path)
      ..lineTo(size.width - 10, size.height - 10)
      ..lineTo(10, size.height - 10)
      ..close();
    canvas.drawPath(
      area,
      Paint()
        ..shader = LinearGradient(
          begin: Alignment.topCenter,
          end: Alignment.bottomCenter,
          colors: [
            primaryColor.withValues(alpha: .28),
            primaryColor.withValues(alpha: 0),
          ],
        ).createShader(Offset.zero & size),
    );
    canvas.drawPath(path, linePaint);

    for (int i = 0; i < weights.length; i++) {
      final x = weights.length == 1
          ? chartWidth / 2
          : 10 + (chartWidth * i / (weights.length - 1));

      final normalized = (weights[i] - minWeight) / (maxWeight - minWeight);

      final y = size.height - 10 - normalized * chartHeight;

      final point = Offset(x, y);

      canvas.drawCircle(point, 6.5, pointOuterPaint);

      canvas.drawCircle(point, 4, pointPaint);
    }
  }

  @override
  bool shouldRepaint(covariant _WeightChartPainter oldDelegate) {
    return oldDelegate.weights != weights ||
        oldDelegate.minWeight != minWeight ||
        oldDelegate.maxWeight != maxWeight ||
        oldDelegate.primaryColor != primaryColor ||
        oldDelegate.gridColor != gridColor;
  }
}
