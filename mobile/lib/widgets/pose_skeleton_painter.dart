import 'package:camera/camera.dart';
import 'package:flutter/material.dart';
import 'package:flutter/foundation.dart';

import 'dart:math' as math;

import 'package:google_mlkit_pose_detection/google_mlkit_pose_detection.dart';

import '../services/pose_frame_converter.dart';
import '../theme/app_theme.dart';

/// ML Kit returns upright coordinates. Mirror only the front lens.
/// The canvas must have the same aspect ratio as CameraPreview, without cropping.
class PoseSkeletonPainter extends CustomPainter {
  PoseSkeletonPainter(this.landmarks, this.frame, {this.joint, this.angle});
  final PoseLandmarkType? joint;
  final double? angle;
  final Map<PoseLandmarkType, PoseLandmark> landmarks;
  final PoseFrame frame;

  static Offset project(
    Offset point,
    Size image,
    Size canvas,
    InputImageRotation rotation,
    CameraLensDirection lens,
  ) {
    final rotated =
        frameIsAndroid &&
        (rotation == InputImageRotation.rotation90deg ||
            rotation == InputImageRotation.rotation270deg);
    final upright = rotated ? Size(image.height, image.width) : image;
    final scale = math.max(
      canvas.width / upright.width,
      canvas.height / upright.height,
    );
    final x = point.dx * scale - (upright.width * scale - canvas.width) / 2;
    final y = point.dy * scale - (upright.height * scale - canvas.height) / 2;
    return Offset(lens == CameraLensDirection.front ? canvas.width - x : x, y);
  }

  static bool get frameIsAndroid =>
      defaultTargetPlatform == TargetPlatform.android;

  static const _links = [
    [PoseLandmarkType.leftShoulder, PoseLandmarkType.rightShoulder],
    [PoseLandmarkType.leftShoulder, PoseLandmarkType.leftElbow],
    [PoseLandmarkType.leftElbow, PoseLandmarkType.leftWrist],
    [PoseLandmarkType.rightShoulder, PoseLandmarkType.rightElbow],
    [PoseLandmarkType.rightElbow, PoseLandmarkType.rightWrist],
    [PoseLandmarkType.leftShoulder, PoseLandmarkType.leftHip],
    [PoseLandmarkType.rightShoulder, PoseLandmarkType.rightHip],
    [PoseLandmarkType.leftHip, PoseLandmarkType.rightHip],
    [PoseLandmarkType.leftHip, PoseLandmarkType.leftKnee],
    [PoseLandmarkType.leftKnee, PoseLandmarkType.leftAnkle],
    [PoseLandmarkType.rightHip, PoseLandmarkType.rightKnee],
    [PoseLandmarkType.rightKnee, PoseLandmarkType.rightAnkle],
    [PoseLandmarkType.leftAnkle, PoseLandmarkType.leftHeel],
    [PoseLandmarkType.leftHeel, PoseLandmarkType.leftFootIndex],
    [PoseLandmarkType.rightAnkle, PoseLandmarkType.rightHeel],
    [PoseLandmarkType.rightHeel, PoseLandmarkType.rightFootIndex],
  ];

  @override
  void paint(Canvas canvas, Size size) {
    canvas.clipRect(Offset.zero & size);
    final line = Paint()
      ..color = AppColors.cyan
      ..strokeWidth = 3
      ..strokeCap = StrokeCap.round;
    final dot = Paint()..color = AppColors.white;
    final points = <PoseLandmarkType, Offset>{};
    for (final entry in landmarks.entries) {
      final p = entry.value;
      if (p.likelihood >= .6 && p.x.isFinite && p.y.isFinite) {
        points[entry.key] = project(
          Offset(p.x, p.y),
          frame.size,
          size,
          frame.rotation,
          frame.lens,
        );
      }
    }
    for (final link in _links) {
      final a = points[link[0]], b = points[link[1]];
      if (a != null && b != null) canvas.drawLine(a, b, line);
    }
    for (final point in points.values) {
      canvas.drawCircle(point, 4, dot);
    }
    final center = points[joint];
    if (center != null && angle != null) {
      canvas.drawCircle(center, 9, Paint()..color = AppColors.electric);
      final text = TextPainter(
        text: TextSpan(
          text: '${angle!.round()}°',
          style: const TextStyle(
            color: AppColors.white,
            fontSize: 16,
            fontWeight: FontWeight.w800,
          ),
        ),
        textDirection: TextDirection.ltr,
      )..layout();
      final origin = Offset(
        (center.dx + 12).clamp(
          4,
          (size.width - text.width - 12).clamp(4, size.width),
        ),
        (center.dy - 24).clamp(
          4,
          (size.height - text.height - 12).clamp(4, size.height),
        ),
      );
      canvas.drawRRect(
        RRect.fromRectAndRadius(
          (origin - const Offset(5, 4)) &
              Size(text.width + 10, text.height + 8),
          const Radius.circular(6),
        ),
        Paint()..color = AppColors.deep,
      );
      text.paint(canvas, origin);
    }
  }

  @override
  bool shouldRepaint(covariant PoseSkeletonPainter oldDelegate) =>
      oldDelegate.landmarks != landmarks ||
      oldDelegate.frame != frame ||
      oldDelegate.angle != angle;
}
