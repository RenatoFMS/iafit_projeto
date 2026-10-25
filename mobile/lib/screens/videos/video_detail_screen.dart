import 'package:flutter/material.dart';

import '../../models/video_source.dart';
import '../../widgets/exercise_video_player.dart';
import '../../widgets/premium_components.dart';
import '../../theme/app_theme.dart';

class VideoDetailScreen extends StatelessWidget {
  const VideoDetailScreen({
    super.key,
    required this.title,
    required this.category,
    required this.duration,
    required this.description,
    this.videoId,
    this.videoUrl,
  }) : assert(videoId != null || videoUrl != null);
  final String title;
  final String category;
  final String duration;
  final String description;
  final String? videoId;
  final String? videoUrl;

  @override
  Widget build(BuildContext context) {
    final source = videoId ?? videoUrl ?? '';
    final youtube = VideoSource.parse(source).kind == VideoSourceKind.youtube;
    return Scaffold(
      appBar: AppBar(title: const Text('Demonstração')),
      body: ListView(
        padding: const EdgeInsets.fromLTRB(20, 8, 20, 32),
        children: [
          ExerciseVideoPlayer(source: source),
          const SizedBox(height: 24),
          Wrap(
            spacing: 10,
            runSpacing: 8,
            children: [
              Chip(label: Text(category)),
              Chip(
                avatar: const Icon(Icons.play_circle_outline_rounded, size: 17),
                label: Text(youtube ? 'YouTube' : 'Vídeo demonstrativo'),
              ),
            ],
          ),
          const SizedBox(height: 14),
          Text(title, style: Theme.of(context).textTheme.headlineLarge),
          const SizedBox(height: 12),
          Text(description),
          const SizedBox(height: 26),
          PremiumCard(
            child: Column(
              crossAxisAlignment: CrossAxisAlignment.start,
              children: [
                const SectionHeading(
                  'Observe os detalhes',
                  eyebrow: 'TÉCNICA EM PRIMEIRO LUGAR',
                ),
                const SizedBox(height: 18),
                for (final item in [
                  (
                    Icons.accessibility_new_rounded,
                    'Postura e alinhamento do corpo',
                  ),
                  (Icons.speed_rounded, 'Controle durante todo o movimento'),
                  (
                    Icons.open_in_full_rounded,
                    'Amplitude confortável e execução estável',
                  ),
                ])
                  Padding(
                    padding: const EdgeInsets.only(bottom: 16),
                    child: Row(
                      children: [
                        Icon(item.$1, color: AppColors.sky, size: 22),
                        const SizedBox(width: 12),
                        Expanded(child: Text(item.$2)),
                      ],
                    ),
                  ),
                const Text(
                  'Use os controles do vídeo para reproduzir, pausar e rever o movimento.',
                ),
              ],
            ),
          ),
          const SizedBox(height: 18),
          Text(
            youtube
                ? 'Demonstração de terceiros, reproduzida pelo player oficial do YouTube. É necessária conexão com a internet.'
                : 'O vídeo é carregado somente nesta página e liberado ao sair.',
            style: Theme.of(context).textTheme.bodySmall,
          ),
        ],
      ),
    );
  }
}
