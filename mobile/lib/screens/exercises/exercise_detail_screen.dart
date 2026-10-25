import 'dart:async';

import 'package:flutter/material.dart';

import '../../models/engine_exercise_map.dart';
import '../../models/exercise_catalog.dart';
import '../../models/video_source.dart';
import '../../services/engine_service.dart';
import '../../widgets/exercise_thumbnail.dart';
import '../../widgets/premium_components.dart';
import '../../theme/app_theme.dart';
import '../videos/video_detail_screen.dart';
import '../workouts/movement_camera_screen.dart';
import 'engine_workout_screen.dart';

class ExerciseDetailScreen extends StatelessWidget {
  const ExerciseDetailScreen({
    super.key,
    required this.name,
    required this.category,
    required this.description,
    required this.videoUrl,
  });
  final String name;
  final String category;
  final String description;
  final String videoUrl;

  void _watch(BuildContext context) => Navigator.push(
    context,
    MaterialPageRoute(
      builder: (_) => VideoDetailScreen(
        title: name,
        category: category,
        duration: '',
        description: description,
        videoUrl: videoUrl,
      ),
    ),
  );

  /// Abre a tela integrada de análise em tempo real (vídeo MJPEG + telemetria IA)
  /// acionando automaticamente o exercício no motor Python (`id_atual`).
  void _startOnEngine(BuildContext context, String engineId) {
    if (EngineService.instance.enabled) {
      unawaited(EngineService.instance.selectExercise(engineId));
    }
    Navigator.push(
      context,
      MaterialPageRoute(
        builder: (_) => EngineWorkoutScreen(
          engineId: engineId,
          exerciseName: name,
          category: category,
        ),
      ),
    );
  }

  @override
  Widget build(BuildContext context) {
    final exercise = ExerciseCatalog.find(name);
    final engineId = EngineExerciseMap.idFor(name);
    final source = VideoSource.parse(videoUrl);
    final instructions =
        exercise?.instructions ??
        const [
          'Posicione-se antes de iniciar o movimento.',
          'Execute com controle e evite impulso.',
          'Priorize a técnica e respeite seus limites.',
        ];
    return Scaffold(
      appBar: AppBar(title: const Text('O movimento')),
      body: ListView(
        padding: const EdgeInsets.fromLTRB(20, 8, 20, 32),
        children: [
          Entrance(
            child: ClipRRect(
              borderRadius: BorderRadius.circular(28),
              child: InkWell(
                onTap: () => _watch(context),
                child: source.kind == VideoSourceKind.youtube
                    ? ExerciseThumbnail(videoId: source.value, height: 230)
                    : Container(
                        height: 220,
                        decoration: const BoxDecoration(
                          gradient: AppColors.heroGradient,
                        ),
                        child: const Center(
                          child: Icon(
                            Icons.play_circle_fill_rounded,
                            color: Colors.white,
                            size: 64,
                          ),
                        ),
                      ),
              ),
            ),
          ),
          const SizedBox(height: 24),
          Text(
            category.toUpperCase(),
            style: TextStyle(
              color: Theme.of(context).colorScheme.primary,
              fontSize: 11,
              letterSpacing: 2,
              fontWeight: FontWeight.w700,
            ),
          ),
          const SizedBox(height: 10),
          Text(name, style: Theme.of(context).textTheme.headlineLarge),
          const SizedBox(height: 12),
          Text(description),
          const SizedBox(height: 24),
          PremiumCard(
            child: Column(
              crossAxisAlignment: CrossAxisAlignment.start,
              children: [
                const SectionHeading('Como executar', eyebrow: 'PASSO A PASSO'),
                const SizedBox(height: 20),
                for (var i = 0; i < instructions.length; i++)
                  Padding(
                    padding: const EdgeInsets.only(bottom: 18),
                    child: Row(
                      crossAxisAlignment: CrossAxisAlignment.start,
                      children: [
                        CircleAvatar(
                          radius: 16,
                          backgroundColor: AppColors.primary.withValues(
                            alpha: .15,
                          ),
                          child: Text(
                            '0${i + 1}',
                            style: const TextStyle(
                              color: AppColors.sky,
                              fontSize: 11,
                              fontWeight: FontWeight.w800,
                            ),
                          ),
                        ),
                        const SizedBox(width: 14),
                        Expanded(child: Text(instructions[i])),
                      ],
                    ),
                  ),
              ],
            ),
          ),
          const SizedBox(height: 20),
          const PremiumCard(
            child: Row(
              children: [
                Icon(Icons.tune_rounded, color: AppColors.sky),
                SizedBox(width: 12),
                Expanded(
                  child: Text(
                    'Séries, repetições e descanso estão definidos na sua sessão de treino.',
                  ),
                ),
              ],
            ),
          ),
          const SizedBox(height: 24),
          ElevatedButton.icon(
            onPressed: () => _watch(context),
            icon: const Icon(Icons.play_arrow_rounded),
            label: const Text('ASSISTIR DEMONSTRAÇÃO'),
          ),
          const SizedBox(height: 14),
          OutlinedButton.icon(
            onPressed: () => Navigator.push(
              context,
              MaterialPageRoute(
                builder: (_) => MovementCameraScreen(exerciseName: name),
              ),
            ),
            icon: const Icon(Icons.videocam_outlined),
            label: const Text('VER MINHA EXECUÇÃO'),
          ),
          if (engineId != null) ...[
            const SizedBox(height: 14),
            OutlinedButton.icon(
              onPressed: () => _startOnEngine(context, engineId),
              icon: const Icon(Icons.memory_rounded),
              label: const Text('ANALISAR NO MOTOR IAFIT'),
            ),
          ],
          const SizedBox(height: 14),
          Text(
            'Conteúdo educativo. Respeite sua condição física e priorize a execução antes de aumentar a carga.',
            style: Theme.of(context).textTheme.bodySmall,
          ),
        ],
      ),
    );
  }
}
