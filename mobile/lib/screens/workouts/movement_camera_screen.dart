import 'dart:async';

import 'package:camera/camera.dart';
import 'package:flutter/foundation.dart';
import 'package:flutter/material.dart';
import 'package:flutter/services.dart';
import 'package:permission_handler/permission_handler.dart';

import '../../models/engine_exercise_map.dart';
import '../../services/camera_session_service.dart';
import '../../services/engine_service.dart';
import '../../services/pose_tracking_service.dart';
import '../../theme/app_theme.dart';
import '../../widgets/pose_skeleton_painter.dart';

class MovementCameraScreen extends StatefulWidget {
  const MovementCameraScreen({
    super.key,
    required this.exerciseName,
    this.cameraSession,
    this.poseTracking,
    this.onSeriesCompleted,
  });
  final String exerciseName;
  final CameraSessionService? cameraSession;
  final PoseTrackingService? poseTracking;
  final VoidCallback? onSeriesCompleted;
  @override
  State<MovementCameraScreen> createState() => _MovementCameraScreenState();
}

class _MovementCameraScreenState extends State<MovementCameraScreen>
    with WidgetsBindingObserver {
  late final _camera = widget.cameraSession ?? CameraSessionService();
  late final _tracking =
      widget.poseTracking ?? PoseTrackingService(widget.exerciseName);
  Timer? _timer;
  bool _busy = false;
  bool _stopping = false;
  bool _hasSession = false;
  bool _finished = false;
  bool get _supported =>
      !kIsWeb &&
      (defaultTargetPlatform == TargetPlatform.android ||
          defaultTargetPlatform == TargetPlatform.iOS);

  @override
  void initState() {
    super.initState();
    WidgetsBinding.instance.addObserver(this);
    _camera.addListener(_changed);
    _tracking.addListener(_changed);
    if (EngineService.instance.enabled) {
      final engineId = EngineExerciseMap.idFor(widget.exerciseName);
      if (engineId != null) {
        unawaited(EngineService.instance.selectExercise(engineId));
      }
    }
    if (_supported) {
      unawaited(_camera.initialize());
    }
    _timer = Timer.periodic(const Duration(seconds: 1), (_) {
      if (mounted && _tracking.running) setState(() {});
    });
  }

  void _changed() {
    if (!mounted) return;
    setState(() {});
    if ((!_tracking.running || _camera.phase == CameraPhase.failed) &&
        _camera.streaming &&
        !_stopping) {
      unawaited(_stop());
    }
  }

  Future<void> _stop() async {
    if (_stopping) return;
    _stopping = true;
    try {
      final stoppedTracking = _tracking.stop();
      await _camera.stopFrames();
      await stoppedTracking;
    } finally {
      _stopping = false;
    }
  }

  Future<void> _toggle() async {
    if (_busy) return;
    setState(() => _busy = true);
    try {
      if (_tracking.running) {
        await _stop();
      } else {
        _tracking.start(reset: !_hasSession);
        _hasSession = true;
        await _camera.startFrames((image) {
          final controller = _camera.controller;
          if (controller != null) {
            _tracking.process(
              image,
              controller.description,
              controller.value.deviceOrientation,
            );
          }
        });
        if (_camera.streamFailure != null || !_camera.streaming) {
          await _tracking.stop();
        }
      }
    } finally {
      if (mounted) setState(() => _busy = false);
    }
  }

  Future<void> _switch() async {
    if (_busy) return;
    setState(() => _busy = true);
    try {
      await _stop();
      await _camera.switchCamera();
    } finally {
      if (mounted) setState(() => _busy = false);
    }
  }

  @override
  void didChangeAppLifecycleState(AppLifecycleState state) {
    if (!_supported || _finished) return;
    if (state == AppLifecycleState.resumed) {
      _camera.setActive(true);
    } else if (state == AppLifecycleState.inactive ||
        state == AppLifecycleState.paused ||
        state == AppLifecycleState.detached) {
      unawaited(_stop());
      _camera.setActive(false);
    }
  }

  Future<void> _shutdown() async {
    await _camera.shutdown();
    await _tracking.close();
    _tracking.dispose();
    _camera.dispose();
  }

  Future<void> _finish() async {
    if (_busy) return;
    setState(() => _busy = true);
    try {
      await _stop();
      _camera.setActive(false);
      await _camera.settled;
      final engineId = EngineExerciseMap.idFor(widget.exerciseName);
      if (EngineService.instance.enabled && engineId != null) {
        unawaited(
          EngineService.instance.finishSeries(
            exerciseId: engineId,
            repetitions: _tracking.effectiveRepetitions,
            durationSeconds: _tracking.clock.elapsed.inSeconds,
            postureErrors: _tracking.postureErrors,
          ),
        );
      }
      if (mounted) {
        setState(() => _finished = true);
        widget.onSeriesCompleted?.call();
      }
    } finally {
      if (mounted) setState(() => _busy = false);
    }
  }

  void _popWithResult() {
    Navigator.pop<int>(
      context,
      _finished
          ? _tracking.effectiveRepetitions
          : (_tracking.effectiveRepetitions > 0
                ? _tracking.effectiveRepetitions
                : null),
    );
  }

  @override
  void dispose() {
    WidgetsBinding.instance.removeObserver(this);
    _timer?.cancel();
    _camera.removeListener(_changed);
    _tracking.removeListener(_changed);
    unawaited(_shutdown());
    super.dispose();
  }

  Widget _preview() {
    final controller = _camera.controller;
    final failure = _camera.failure;
    if (!_supported) {
      return const Padding(
        padding: EdgeInsets.all(24),
        child: Text(
          'A análise pela câmera está disponível no aplicativo para Android e iPhone.',
        ),
      );
    }
    if (failure != null) {
      return Padding(
        padding: const EdgeInsets.all(24),
        child: Column(
          mainAxisSize: MainAxisSize.min,
          children: [
            const Icon(
              Icons.videocam_off_outlined,
              size: 40,
              color: AppColors.sky,
            ),
            const SizedBox(height: 16),
            Text(failure.message, textAlign: TextAlign.center),
            const SizedBox(height: 8),
            Text(
              'Código: ${failure.code}',
              style: const TextStyle(color: AppColors.muted),
            ),
            const SizedBox(height: 16),
            FilledButton(
              onPressed: () => _camera.initialize(),
              child: const Text('Tentar novamente'),
            ),
            if (failure.openSettings)
              TextButton(
                onPressed: () async {
                  final opened = await openAppSettings();
                  if (!opened && mounted) {
                    ScaffoldMessenger.of(context).showSnackBar(
                      const SnackBar(
                        content: Text(
                          'Não foi possível abrir as configurações. Acesse as permissões do Fitness Pro pelo Android.',
                        ),
                      ),
                    );
                  }
                },
                child: const Text('Abrir configurações'),
              ),
            if (_camera.canSwitch)
              TextButton(
                onPressed: _switch,
                child: const Text('Tentar outra câmera'),
              ),
          ],
        ),
      );
    }
    if (controller == null || !controller.value.isInitialized) {
      return const Padding(
        padding: EdgeInsets.all(44),
        child: Column(
          mainAxisSize: MainAxisSize.min,
          children: [
            CircularProgressIndicator(),
            SizedBox(height: 20),
            Text('Preparando a câmera…', textAlign: TextAlign.center),
          ],
        ),
      );
    }
    return ValueListenableBuilder<CameraValue>(
      valueListenable: controller,
      builder: (_, value, _) {
        final portrait =
            value.deviceOrientation == DeviceOrientation.portraitUp ||
            value.deviceOrientation == DeviceOrientation.portraitDown;
        final frame = _tracking.frame;
        final fresh =
            _tracking.lastDetection != null &&
            DateTime.now().difference(_tracking.lastDetection!).inMilliseconds <
                1000;
        return AspectRatio(
          aspectRatio: portrait ? 1 / value.aspectRatio : value.aspectRatio,
          child: Stack(
            fit: StackFit.expand,
            children: [
              CameraPreview(controller),
              if (_tracking.running && frame != null && fresh)
                IgnorePointer(
                  child: CustomPaint(
                    painter: PoseSkeletonPainter(
                      _tracking.landmarks,
                      frame,
                      joint: _tracking.trackedJoint,
                      angle: _tracking.angle,
                    ),
                  ),
                ),
              Positioned(
                top: 14,
                left: 14,
                right: 14,
                child: Align(
                  alignment: Alignment.topLeft,
                  child: DecoratedBox(
                    decoration: BoxDecoration(
                      color: AppColors.background.withValues(alpha: .8),
                      borderRadius: BorderRadius.circular(20),
                    ),
                    child: Padding(
                      padding: const EdgeInsets.symmetric(
                        horizontal: 14,
                        vertical: 8,
                      ),
                      child: Text(
                        _tracking.running
                            ? '● ANÁLISE AO VIVO'
                            : '● CÂMERA AO VIVO',
                        style: const TextStyle(
                          fontSize: 11,
                          fontWeight: FontWeight.w800,
                          color: AppColors.sky,
                        ),
                      ),
                    ),
                  ),
                ),
              ),
            ],
          ),
        );
      },
    );
  }

  @override
  Widget build(BuildContext context) {
    final elapsed = _tracking.clock.elapsed;
    final time =
        '${elapsed.inMinutes.toString().padLeft(2, '0')}:${(elapsed.inSeconds % 60).toString().padLeft(2, '0')}';
    final error = _camera.streamFailure ?? _tracking.error;
    final fresh =
        _tracking.running &&
        _tracking.landmarks.isNotEmpty &&
        _tracking.lastDetection != null &&
        DateTime.now().difference(_tracking.lastDetection!).inMilliseconds <
            1000;
    return Theme(
      data: AppTheme.darkTheme,
      child: Scaffold(
        backgroundColor: AppColors.background,
        appBar: AppBar(
          title: const Text('Ver minha execução'),
          leading: BackButton(onPressed: _popWithResult),
        ),
        body: SafeArea(
          child: ListView(
            padding: const EdgeInsets.fromLTRB(20, 8, 20, 24),
            children: [
              Text(
                widget.exerciseName,
                style: const TextStyle(
                  fontSize: 26,
                  fontWeight: FontWeight.w800,
                ),
              ),
              const SizedBox(height: 8),
              Text(
                _finished
                    ? 'Sessão finalizada. Resultados calculados a partir dos movimentos detectados.'
                    : 'Enquadre o corpo inteiro e mantenha as articulações visíveis.',
                style: const TextStyle(color: AppColors.muted),
              ),
              const SizedBox(height: 20),
              Container(
                clipBehavior: Clip.antiAlias,
                decoration: BoxDecoration(
                  color: AppColors.surface,
                  borderRadius: BorderRadius.circular(28),
                  border: Border.all(color: AppColors.border),
                ),
                child: _finished
                    ? const Padding(
                        padding: EdgeInsets.all(30),
                        child: Column(
                          children: [
                            Icon(
                              Icons.task_alt_rounded,
                              size: 48,
                              color: AppColors.cyan,
                            ),
                            SizedBox(height: 12),
                            Text(
                              'Resumo da análise',
                              style: TextStyle(
                                fontSize: 22,
                                fontWeight: FontWeight.w800,
                              ),
                            ),
                          ],
                        ),
                      )
                    : _preview(),
              ),
              const SizedBox(height: 16),
              Container(
                padding: const EdgeInsets.all(20),
                decoration: BoxDecoration(
                  gradient: const LinearGradient(
                    colors: [AppColors.surface, AppColors.deep],
                  ),
                  borderRadius: BorderRadius.circular(24),
                  border: Border.all(color: AppColors.border),
                ),
                child: Column(
                  crossAxisAlignment: CrossAxisAlignment.start,
                  children: [
                    Wrap(
                      spacing: 24,
                      runSpacing: 16,
                      children: [
                        _metric('SESSÃO', time),
                        if (_tracking.supportsCounting)
                          _metric(
                            _tracking.isIsometric
                                ? 'TEMPO IA'
                                : 'REPETIÇÕES ESTIMADAS',
                            _tracking.isIsometric
                                ? '${_tracking.effectiveRepetitions}s'
                                : '${_tracking.effectiveRepetitions}',
                          ),
                        if (_tracking.isSyncedWithEngine)
                          _metric(
                            'ERROS POSTURA',
                            '${_tracking.postureErrors}',
                          ),
                        _metric(
                          '${_tracking.analyzer.rule.joint.toUpperCase()} · ${_tracking.isSyncedWithEngine ? "3D" : "2D"}',
                          _tracking.angle == null || !fresh
                              ? '—'
                              : '${_tracking.angle!.round()}°',
                        ),
                      ],
                    ),
                    const SizedBox(height: 18),
                    if (_tracking.supportsCounting) ...[
                      Text(
                        _finished
                            ? 'Possíveis movimentos incompletos: ${_tracking.analyzer.incompleteMovements}'
                            : 'Fase: ${_tracking.effectivePhaseLabel}',
                        style: const TextStyle(color: AppColors.sky),
                      ),
                      const SizedBox(height: 10),
                    ],
                    if (!_finished) ...[
                      Text(
                        fresh
                            ? '● Corpo reconhecido'
                            : _tracking.running
                            ? '○ Procurando o corpo…'
                            : '○ Análise pausada',
                        style: TextStyle(
                          color: fresh ? AppColors.cyan : AppColors.muted,
                        ),
                      ),
                      const SizedBox(height: 12),
                    ],
                    Text(
                      _finished
                          ? (_tracking.supportsCounting
                                ? 'Contagem por limiares do projeto IAFit. Uma repetição é registrada ao atingir a fase alvo.'
                                : 'Este exercício não possui regras de contagem ou avaliação disponíveis.')
                          : error ?? _tracking.feedback,
                      style: TextStyle(
                        color: error == null
                            ? AppColors.white
                            : const Color(0xFFFFB4AB),
                      ),
                    ),
                    const SizedBox(height: 12),
                    if (_tracking.errorDetails != null && !_finished)
                      TextButton.icon(
                        onPressed: () => showDialog<void>(
                          context: context,
                          builder: (context) => AlertDialog(
                            title: const Text('Detalhes da análise'),
                            scrollable: true,
                            content: SelectableText(_tracking.errorDetails!),
                            actions: [
                              TextButton(
                                onPressed: () => Navigator.pop(context),
                                child: const Text('Fechar'),
                              ),
                            ],
                          ),
                        ),
                        icon: const Icon(Icons.bug_report_outlined),
                        label: const Text('Detalhes técnicos'),
                      ),
                    const Text(
                      'Estimativa experimental de movimento em 2D. Não determina se a postura está correta e não substitui orientação profissional.',
                      style: TextStyle(color: AppColors.muted, fontSize: 12),
                    ),
                  ],
                ),
              ),
              const SizedBox(height: 18),
              if (!_finished)
                FilledButton.icon(
                  onPressed:
                      _supported && _camera.phase == CameraPhase.ready && !_busy
                      ? _toggle
                      : null,
                  icon: Icon(
                    _tracking.running
                        ? Icons.pause_rounded
                        : Icons.center_focus_strong,
                  ),
                  label: Text(
                    _busy
                        ? 'Aguarde…'
                        : _tracking.running
                        ? 'Pausar análise'
                        : _hasSession
                        ? 'Retomar análise'
                        : 'Iniciar análise',
                  ),
                ),
              if (_hasSession && !_finished)
                OutlinedButton.icon(
                  onPressed: _busy ? null : _finish,
                  icon: const Icon(Icons.stop_rounded),
                  label: const Text('Finalizar sessão'),
                ),
              if (_camera.canSwitch && !_finished)
                OutlinedButton.icon(
                  onPressed: !_busy && _camera.phase == CameraPhase.ready
                      ? _switch
                      : null,
                  icon: const Icon(Icons.cameraswitch_outlined),
                  label: const Text('Trocar câmera'),
                ),
              TextButton(
                onPressed: _popWithResult,
                child: const Text('Voltar à série'),
              ),
            ],
          ),
        ),
      ),
    );
  }

  Widget _metric(String label, String value) => Column(
    crossAxisAlignment: CrossAxisAlignment.start,
    mainAxisSize: MainAxisSize.min,
    children: [
      Text(
        label,
        style: const TextStyle(
          color: AppColors.muted,
          fontSize: 10,
          letterSpacing: 1,
        ),
      ),
      const SizedBox(height: 4),
      Text(
        value,
        style: const TextStyle(
          fontSize: 28,
          fontWeight: FontWeight.w800,
          color: AppColors.sky,
        ),
      ),
    ],
  );
}
