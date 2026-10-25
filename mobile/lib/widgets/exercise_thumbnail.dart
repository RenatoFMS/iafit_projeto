import 'package:flutter/material.dart';

import '../theme/app_theme.dart';

class ExerciseThumbnail extends StatelessWidget {
  const ExerciseThumbnail({
    super.key,
    required this.videoId,
    this.height = 150,
  });
  final String videoId;
  final double height;
  @override
  Widget build(BuildContext context) => SizedBox(
    height: height,
    width: double.infinity,
    child: Stack(
      fit: StackFit.expand,
      children: [
        ColoredBox(
          color: AppColors.deep,
          child: Image.network(
            'https://img.youtube.com/vi/$videoId/hqdefault.jpg',
            fit: BoxFit.cover,
            cacheWidth: 640,
            excludeFromSemantics: true,
            errorBuilder: (context, error, stack) => const Center(
              child: Icon(
                Icons.fitness_center_rounded,
                color: AppColors.sky,
                size: 44,
              ),
            ),
            loadingBuilder: (context, child, progress) => progress == null
                ? child
                : const Center(
                    child: Icon(
                      Icons.fitness_center_rounded,
                      color: AppColors.sky,
                      size: 44,
                    ),
                  ),
          ),
        ),
        const DecoratedBox(
          decoration: BoxDecoration(
            gradient: LinearGradient(
              begin: Alignment.topCenter,
              end: Alignment.bottomCenter,
              colors: [Color(0x00080F1F), Color(0xC0080F1F)],
            ),
          ),
        ),
        Center(
          child: Container(
            padding: const EdgeInsets.all(10),
            decoration: BoxDecoration(
              color: AppColors.primary.withValues(alpha: .9),
              shape: BoxShape.circle,
              border: Border.all(color: Colors.white.withValues(alpha: .35)),
            ),
            child: const Icon(
              Icons.play_arrow_rounded,
              color: Colors.white,
              size: 24,
            ),
          ),
        ),
      ],
    ),
  );
}
