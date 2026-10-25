import 'dart:async';

import 'package:flutter/material.dart';

import '../services/engine_service.dart';
import '../services/settings_service.dart';
import '../theme/app_theme.dart';

/// Cartão de telemetria biomecânica ao vivo do motor matemático Python
/// (`POST /analisar_pose` e `GET /estado`).
class EngineLiveCard extends StatefulWidget {
  const EngineLiveCard({
    super.key,
    required this.engineId,
    required this.exerciseName,
    this.paused = false,
    this.showFinishButton = false,
    this.maxVideoHeight = 320,
    this.onExpand,
    this.onSeriesFinished,
  });

  final String engineId;
  final String exerciseName;
  final bool paused;
  final bool showFinishButton;
  final double maxVideoHeight;
  final VoidCallback? onExpand;
  final ValueChanged<EngineLiveState?>? onSeriesFinished;

  @override
  State<EngineLiveCard> createState() => _EngineLiveCardState();
}

class _EngineLiveCardState extends State<EngineLiveCard> {
  Timer? _stateTimer;
  EngineLiveState? _liveState;
  bool _finishing = false;

  @override
  void initState() {
    super.initState();
    SettingsService.instance.engineUrl.addListener(_onUrlChanged);
    _activateExercise();
    _startPolling();
  }

  @override
  void didUpdateWidget(covariant EngineLiveCard oldWidget) {
    super.didUpdateWidget(oldWidget);
    if (oldWidget.engineId != widget.engineId) {
      _liveState = null;
      _activateExercise();
    }
    if (oldWidget.paused != widget.paused) {
      if (widget.paused) {
        _stateTimer?.cancel();
        _stateTimer = null;
      } else {
        _startPolling();
      }
    }
  }

  void _onUrlChanged() {
    if (!mounted) return;
    setState(() {});
    _activateExercise();
  }

  void _activateExercise() {
    if (!EngineService.instance.enabled) return;
    unawaited(EngineService.instance.selectExercise(widget.engineId));
  }

  void _startPolling() {
    _stateTimer?.cancel();
    if (widget.paused || !EngineService.instance.enabled) return;
    unawaited(_refreshState());
    _stateTimer = Timer.periodic(const Duration(milliseconds: 650), (_) {
      if (mounted && !widget.paused && EngineService.instance.enabled) {
        unawaited(_refreshState());
      }
    });
  }

  Future<void> _refreshState() async {
    final state = await EngineService.instance.fetchState();
    if (!mounted || state == null) return;
    if (state.exerciseId.isNotEmpty && state.exerciseId != widget.engineId) {
      await EngineService.instance.selectExercise(widget.engineId);
      final synced = await EngineService.instance.fetchState();
      if (!mounted || synced == null || synced.exerciseId != widget.engineId) {
        return;
      }
      setState(() => _liveState = synced);
      return;
    }
    setState(() => _liveState = state);
  }

  Future<void> _finishCurrentSeries() async {
    if (_finishing) return;
    setState(() => _finishing = true);
    final snapshot = _liveState;
    try {
      final result = await EngineService.instance.finishSeries();
      if (!mounted) return;
      ScaffoldMessenger.of(
        context,
      ).showSnackBar(SnackBar(content: Text(result.message)));
      if (result.ok) {
        widget.onSeriesFinished?.call(snapshot);
      }
    } finally {
      if (mounted) setState(() => _finishing = false);
    }
  }

  @override
  void dispose() {
    SettingsService.instance.engineUrl.removeListener(_onUrlChanged);
    _stateTimer?.cancel();
    _stateTimer = null;
    super.dispose();
  }

  @override
  Widget build(BuildContext context) {
    final engine = EngineService.instance;
    if (!engine.enabled) {
      return const SizedBox.shrink();
    }

    final theme = Theme.of(context);
    final state = _liveState;
    final isIsometric = state?.isometric ?? false;
    final countLabel = isIsometric ? 'TEMPO IA' : 'REPS IA';
    final countValue = state == null
        ? '0'
        : isIsometric
        ? '${state.seconds}s'
        : '${state.repetitions}';
    final errorsValue = state == null ? '0' : '${state.postureErrors}';
    final statusBadge = _statusText(state);
    final feedback = state?.feedback.trim() ?? '';
    final hasErrorFeedback = feedback.toUpperCase().startsWith('ERRO');

    return Container(
      clipBehavior: Clip.antiAlias,
      decoration: BoxDecoration(
        color: theme.cardColor,
        borderRadius: BorderRadius.circular(24),
        border: Border.all(
          color: hasErrorFeedback
              ? Colors.redAccent.withValues(alpha: 0.7)
              : AppColors.sky.withValues(alpha: 0.35),
        ),
      ),
      child: Column(
        crossAxisAlignment: CrossAxisAlignment.stretch,
        children: [
          Container(
            padding: const EdgeInsets.symmetric(horizontal: 14, vertical: 10),
            color: const Color(0xFF0D1526),
            child: Row(
              children: [
                const Icon(
                  Icons.center_focus_strong,
                  color: AppColors.cyan,
                  size: 16,
                ),
                const SizedBox(width: 8),
                Expanded(
                  child: Text(
                    statusBadge,
                    maxLines: 1,
                    overflow: TextOverflow.ellipsis,
                    style: const TextStyle(
                      color: AppColors.sky,
                      fontSize: 11,
                      fontWeight: FontWeight.w800,
                      letterSpacing: 0.8,
                    ),
                  ),
                ),
                if (widget.onExpand != null)
                  IconButton(
                    visualDensity: VisualDensity.compact,
                    padding: EdgeInsets.zero,
                    constraints: const BoxConstraints(
                      minWidth: 30,
                      minHeight: 30,
                    ),
                    tooltip: 'Abrir câmera ML Kit',
                    onPressed: widget.onExpand,
                    icon: const Icon(
                      Icons.videocam_outlined,
                      color: Colors.white70,
                      size: 17,
                    ),
                  ),
              ],
            ),
          ),
          Padding(
            padding: const EdgeInsets.all(14),
            child: Column(
              crossAxisAlignment: CrossAxisAlignment.start,
              children: [
                Wrap(
                  spacing: 16,
                  runSpacing: 10,
                  children: [
                    _miniMetric(theme, countLabel, countValue, AppColors.sky),
                    _miniMetric(
                      theme,
                      'ERROS POSTURA',
                      errorsValue,
                      (state?.postureErrors ?? 0) > 0
                          ? Colors.orangeAccent
                          : AppColors.cyan,
                    ),
                    _miniMetric(
                      theme,
                      'FASE',
                      (state?.phase.isNotEmpty ?? false)
                          ? state!.phase.toUpperCase()
                          : 'CALIBRANDO',
                      theme.colorScheme.onSurface,
                    ),
                  ],
                ),
                if (feedback.isNotEmpty) ...[
                  const SizedBox(height: 10),
                  Text(
                    feedback,
                    style: TextStyle(
                      color: hasErrorFeedback
                          ? Colors.redAccent
                          : AppColors.cyan,
                      fontSize: 12.5,
                      fontWeight: FontWeight.w700,
                    ),
                  ),
                ],
                if (widget.showFinishButton) ...[
                  const SizedBox(height: 14),
                  SizedBox(
                    width: double.infinity,
                    child: ElevatedButton.icon(
                      onPressed: _finishing ? null : _finishCurrentSeries,
                      icon: const Icon(Icons.check_circle_outline_rounded),
                      label: Text(
                        _finishing
                            ? 'SALVANDO SÉRIE…'
                            : 'FINALIZAR E SALVAR SÉRIE',
                      ),
                    ),
                  ),
                ],
              ],
            ),
          ),
        ],
      ),
    );
  }

  String _statusText(EngineLiveState? state) {
    final targetName = widget.exerciseName.toUpperCase();
    if (widget.paused) return '● IA PAUSADA · $targetName';
    if (state == null ||
        (state.exerciseId.isNotEmpty && state.exerciseId != widget.engineId)) {
      return '● MOTOR IAFIT · $targetName';
    }
    final normalized = state.status.toUpperCase();
    if (normalized.contains('CALIBR')) {
      return '● CALIBRANDO POSIÇÃO · $targetName';
    }
    if (normalized.contains('FORA')) {
      return '● ENQUADRE O CORPO · $targetName';
    }
    final activeName = state.exerciseName.isNotEmpty
        ? state.exerciseName.toUpperCase()
        : targetName;
    return '● IA AO VIVO · $activeName';
  }

  Widget _miniMetric(
    ThemeData theme,
    String label,
    String value,
    Color valueColor,
  ) {
    return Column(
      crossAxisAlignment: CrossAxisAlignment.start,
      mainAxisSize: MainAxisSize.min,
      children: [
        Text(
          label,
          style: TextStyle(
            color: theme.colorScheme.onSurface.withValues(alpha: 0.58),
            fontSize: 10,
            fontWeight: FontWeight.w700,
            letterSpacing: 1.0,
          ),
        ),
        const SizedBox(height: 2),
        Text(
          value,
          style: TextStyle(
            color: valueColor,
            fontSize: 18,
            fontWeight: FontWeight.w800,
          ),
        ),
      ],
    );
  }
}
