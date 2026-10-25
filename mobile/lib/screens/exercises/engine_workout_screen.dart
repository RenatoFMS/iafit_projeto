import 'dart:async';

import 'package:flutter/material.dart';

import '../../services/engine_service.dart';
import '../../theme/app_theme.dart';
import '../../widgets/engine_live_card.dart';
import '../../widgets/premium_components.dart';
import '../workouts/movement_camera_screen.dart';

/// Tela dedicada de treino/análise biomecânica 3D integrada à câmara ML Kit
/// e à API matemática do motor Python (`POST /analisar_pose` e `GET /estado`).
class EngineWorkoutScreen extends StatefulWidget {
  const EngineWorkoutScreen({
    super.key,
    required this.engineId,
    required this.exerciseName,
    this.category,
    this.onSeriesCompleted,
  });

  final String engineId;
  final String exerciseName;
  final String? category;
  final VoidCallback? onSeriesCompleted;

  @override
  State<EngineWorkoutScreen> createState() => _EngineWorkoutScreenState();
}

class _EngineWorkoutScreenState extends State<EngineWorkoutScreen> {
  bool _paused = false;
  int _completedSeries = 0;
  int? _lastRepetitions;

  @override
  void initState() {
    super.initState();
    unawaited(EngineService.instance.selectExercise(widget.engineId));
  }

  @override
  void didUpdateWidget(covariant EngineWorkoutScreen oldWidget) {
    super.didUpdateWidget(oldWidget);
    if (oldWidget.engineId != widget.engineId) {
      unawaited(EngineService.instance.selectExercise(widget.engineId));
    }
  }

  Future<void> _openCamera() async {
    var seriesCompleted = false;
    final count = await Navigator.of(context).push<int>(
      MaterialPageRoute(
        builder: (_) => MovementCameraScreen(
          exerciseName: widget.exerciseName,
          onSeriesCompleted: () {
            seriesCompleted = true;
          },
        ),
      ),
    );
    if (!mounted) return;
    if (seriesCompleted || count != null) {
      setState(() {
        _completedSeries++;
        _lastRepetitions = count;
      });
      widget.onSeriesCompleted?.call();
    }
  }

  @override
  Widget build(BuildContext context) {
    final theme = Theme.of(context);

    return Scaffold(
      appBar: AppBar(
        title: const Text('Análise IA em Tempo Real'),
        actions: [
          IconButton(
            tooltip: _paused ? 'Retomar vídeo' : 'Pausar vídeo',
            onPressed: () => setState(() => _paused = !_paused),
            icon: Icon(
              _paused ? Icons.play_arrow_rounded : Icons.pause_rounded,
            ),
          ),
        ],
      ),
      body: SafeArea(
        child: ListView(
          padding: const EdgeInsets.fromLTRB(20, 8, 20, 28),
          children: [
            if (widget.category != null && widget.category!.isNotEmpty) ...[
              Text(
                widget.category!.toUpperCase(),
                style: TextStyle(
                  color: theme.colorScheme.primary,
                  fontSize: 11,
                  letterSpacing: 2,
                  fontWeight: FontWeight.w700,
                ),
              ),
              const SizedBox(height: 6),
            ],
            Text(widget.exerciseName, style: theme.textTheme.headlineMedium),
            const SizedBox(height: 6),
            Text(
              'Posicione-se em frente à webcam com o corpo visível. '
              'Após 1-2s de calibração, a IA contará as repetições e avaliará sua postura.',
              style: theme.textTheme.bodyMedium?.copyWith(
                color: theme.colorScheme.onSurface.withValues(alpha: 0.72),
              ),
            ),
            const SizedBox(height: 18),
            EngineLiveCard(
              key: ValueKey('engine-workout-${widget.engineId}'),
              engineId: widget.engineId,
              exerciseName: widget.exerciseName,
              paused: _paused,
              showFinishButton: true,
              maxVideoHeight: 460,
              onExpand: _openCamera,
              onSeriesFinished: (state) {
                setState(() {
                  _completedSeries++;
                  _lastRepetitions = state?.repetitions;
                });
                widget.onSeriesCompleted?.call();
              },
            ),
            if (_completedSeries > 0) ...[
              const SizedBox(height: 12),
              Text(
                'Séries concluídas: $_completedSeries'
                '${_lastRepetitions != null && _lastRepetitions! > 0 ? " · $_lastRepetitions repetições na última série" : ""}',
                style: const TextStyle(
                  color: AppColors.cyan,
                  fontWeight: FontWeight.w700,
                ),
              ),
            ],
            const SizedBox(height: 14),
            OutlinedButton.icon(
              onPressed: _openCamera,
              icon: const Icon(Icons.videocam_outlined),
              label: const Text('ABRIR CÂMERA ML KIT'),
            ),
            const SizedBox(height: 16),
            const PremiumCard(
              child: Row(
                children: [
                  Icon(Icons.auto_graph_rounded, color: AppColors.sky),
                  SizedBox(width: 12),
                  Expanded(
                    child: Text(
                      'Ao finalizar a série (ou após 6s de pausa), repetições, '
                      'calorias e erros de postura são enviados automaticamente '
                      'para o histórico e gráficos do aplicativo.',
                    ),
                  ),
                ],
              ),
            ),
          ],
        ),
      ),
    );
  }
}

