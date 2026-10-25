import 'dart:math' as math;

import 'package:flutter/material.dart';

import '../theme/app_theme.dart';

class Entrance extends StatelessWidget {
  const Entrance({super.key, required this.child});
  final Widget child;
  @override
  Widget build(BuildContext context) => TweenAnimationBuilder<double>(
    tween: Tween(
      begin: MediaQuery.disableAnimationsOf(context) ? 1 : 0,
      end: 1,
    ),
    duration: const Duration(milliseconds: 420),
    curve: Curves.easeOutCubic,
    builder: (context, value, child) => Opacity(
      opacity: value,
      child: Transform.translate(
        offset: Offset(0, 14 * (1 - value)),
        child: child,
      ),
    ),
    child: child,
  );
}

class PremiumCard extends StatelessWidget {
  const PremiumCard({
    super.key,
    required this.child,
    this.padding = const EdgeInsets.all(20),
    this.gradient,
  });
  final Widget child;
  final EdgeInsetsGeometry padding;
  final Gradient? gradient;
  @override
  Widget build(BuildContext context) => Container(
    padding: padding,
    decoration: BoxDecoration(
      color: Theme.of(context).cardColor,
      gradient: gradient,
      borderRadius: BorderRadius.circular(24),
      border: Border.all(color: Theme.of(context).colorScheme.outline),
      boxShadow: [
        BoxShadow(
          color: AppColors.primary.withValues(alpha: .04),
          blurRadius: 24,
          offset: const Offset(0, 8),
        ),
      ],
    ),
    child: child,
  );
}

class SectionHeading extends StatelessWidget {
  const SectionHeading(
    this.title, {
    super.key,
    this.action,
    this.onTap,
    this.eyebrow,
  });
  final String title;
  final String? action;
  final String? eyebrow;
  final VoidCallback? onTap;
  @override
  Widget build(BuildContext context) => Row(
    children: [
      Expanded(
        child: Column(
          crossAxisAlignment: CrossAxisAlignment.start,
          children: [
            if (eyebrow != null)
              Text(
                eyebrow!,
                style: const TextStyle(
                  fontSize: 10,
                  letterSpacing: 2,
                  fontWeight: FontWeight.w700,
                  color: AppColors.sky,
                ),
              ),
            Text(title, style: Theme.of(context).textTheme.titleLarge),
          ],
        ),
      ),
      if (action != null) TextButton(onPressed: onTap, child: Text(action!)),
    ],
  );
}

class WorkoutDial extends StatelessWidget {
  const WorkoutDial({
    super.key,
    required this.value,
    required this.title,
    required this.subtitle,
    this.size = 210,
  });
  final double value;
  final String title;
  final String subtitle;
  final double size;
  @override
  Widget build(BuildContext context) => Semantics(
    label: '$subtitle: $title',
    child: SizedBox.square(
      dimension: size,
      child: TweenAnimationBuilder<double>(
        tween: Tween(begin: 0, end: value.clamp(0, 1)),
        duration: MediaQuery.disableAnimationsOf(context)
            ? Duration.zero
            : const Duration(milliseconds: 500),
        builder: (context, progress, child) => CustomPaint(
          painter: _DialPainter(
            progress,
            Theme.of(context).colorScheme.outline,
          ),
          child: child,
        ),
        child: Center(
          child: Padding(
            padding: const EdgeInsets.all(26),
            child: Column(
              mainAxisSize: MainAxisSize.min,
              children: [
                FittedBox(
                  child: Text(
                    title,
                    style: TextStyle(
                      fontSize: size / 4.6,
                      fontWeight: FontWeight.w800,
                      color: Theme.of(context).colorScheme.onSurface,
                      letterSpacing: -1.5,
                      fontFeatures: const [FontFeature.tabularFigures()],
                    ),
                  ),
                ),
                Text(
                  subtitle,
                  textAlign: TextAlign.center,
                  style: Theme.of(context).textTheme.bodySmall,
                ),
              ],
            ),
          ),
        ),
      ),
    ),
  );
}

class _DialPainter extends CustomPainter {
  _DialPainter(this.progress, this.track);
  final double progress;
  final Color track;
  @override
  void paint(Canvas canvas, Size size) {
    final center = size.center(Offset.zero);
    final radius = size.width / 2 - 12;
    final rect = Rect.fromCircle(center: center, radius: radius);
    final line = Paint()
      ..style = PaintingStyle.stroke
      ..strokeWidth = 9
      ..strokeCap = StrokeCap.round;
    canvas.drawCircle(center, radius, line..color = track);
    canvas.drawArc(
      rect,
      -math.pi / 2,
      math.pi * 2 * progress,
      false,
      line
        ..shader = const SweepGradient(
          colors: [AppColors.electric, AppColors.cyan, AppColors.sky],
          transform: GradientRotation(-math.pi / 2),
        ).createShader(rect),
    );
    for (var i = 0; i < 48; i++) {
      final angle = i * math.pi / 24;
      final direction = Offset(math.cos(angle), math.sin(angle));
      canvas.drawLine(
        center + direction * (radius - 13),
        center + direction * (radius - 17),
        Paint()
          ..color = track
          ..strokeWidth = 1.5,
      );
    }
  }

  @override
  bool shouldRepaint(_DialPainter oldDelegate) =>
      progress != oldDelegate.progress || track != oldDelegate.track;
}

/// Lightweight vector artwork, rendered locally without image requests.
class StrengthArtwork extends StatelessWidget {
  const StrengthArtwork({super.key, this.size = 160});
  final double size;
  @override
  Widget build(BuildContext context) => ExcludeSemantics(
    child: SizedBox.square(
      dimension: size,
      child: CustomPaint(painter: _StrengthPainter()),
    ),
  );
}

class _StrengthPainter extends CustomPainter {
  @override
  void paint(Canvas canvas, Size size) {
    canvas.translate(size.width / 2, size.height / 2);
    canvas.rotate(-.55);
    final scale = size.width / 160;
    canvas.scale(scale);
    canvas.drawCircle(
      Offset.zero,
      70,
      Paint()
        ..shader = RadialGradient(
          colors: [
            AppColors.electric.withValues(alpha: .35),
            AppColors.electric.withValues(alpha: 0),
          ],
        ).createShader(const Rect.fromLTWH(-70, -70, 140, 140)),
    );
    final handle = RRect.fromRectAndRadius(
      const Rect.fromLTWH(-52, -9, 104, 18),
      const Radius.circular(7),
    );
    canvas.drawRRect(
      handle,
      Paint()
        ..shader = const LinearGradient(
          begin: Alignment.topCenter,
          end: Alignment.bottomCenter,
          colors: [
            AppColors.sky,
            AppColors.white,
            AppColors.primary,
            AppColors.deep,
          ],
        ).createShader(handle.outerRect),
    );
    for (final sign in [-1.0, 1.0]) {
      for (var i = 0; i < 3; i++) {
        final rect = Rect.fromCenter(
          center: Offset(sign * (35 + i * 13), 0),
          width: 18,
          height: 82 - i * 18,
        );
        canvas.drawRRect(
          RRect.fromRectAndRadius(rect, const Radius.circular(8)),
          Paint()
            ..shader = const LinearGradient(
              begin: Alignment.topLeft,
              end: Alignment.bottomRight,
              colors: [
                Color(0xFFBFDBFE),
                AppColors.electric,
                Color(0xFF1E3A8A),
                AppColors.deep,
              ],
            ).createShader(rect),
        );
        canvas.drawRRect(
          RRect.fromRectAndRadius(rect.deflate(.7), const Radius.circular(8)),
          Paint()
            ..color = AppColors.sky.withValues(alpha: .45)
            ..style = PaintingStyle.stroke,
        );
      }
    }
  }

  @override
  bool shouldRepaint(_StrengthPainter oldDelegate) => false;
}
