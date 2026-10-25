import 'package:camera/camera.dart';
import 'package:flutter/services.dart';
import 'package:google_mlkit_pose_detection/google_mlkit_pose_detection.dart';

class PoseFrame {
  const PoseFrame(this.image, this.size, this.rotation, this.lens);
  final InputImage image;
  final Size size;
  final InputImageRotation rotation;
  final CameraLensDirection lens;
}

class PoseFrameConverter {
  static int rotationDegrees(
    int sensor,
    DeviceOrientation orientation,
    CameraLensDirection lens,
  ) {
    final device = switch (orientation) {
      DeviceOrientation.portraitUp => 0,
      DeviceOrientation.landscapeLeft => 90,
      DeviceOrientation.portraitDown => 180,
      DeviceOrientation.landscapeRight => 270,
    };
    return lens == CameraLensDirection.front
        ? (sensor + device) % 360
        : (sensor - device + 360) % 360;
  }

  static PoseFrame convert(
    CameraImage frame,
    CameraDescription camera,
    DeviceOrientation orientation, {
    required bool isAndroid,
  }) {
    final rotation = InputImageRotationValue.fromRawValue(
      isAndroid
          ? rotationDegrees(
              camera.sensorOrientation,
              orientation,
              camera.lensDirection,
            )
          : camera.sensorOrientation,
    );
    if (rotation == null) {
      throw const FormatException('Rotação da câmera não reconhecida.');
    }
    final size = Size(frame.width.toDouble(), frame.height.toDouble());
    late final Uint8List bytes;
    late final InputImageFormat format;
    late final int row;
    if (isAndroid) {
      format = InputImageFormat.nv21;
      row = frame.width;
      if (frame.planes.length == 1 &&
          frame.format.group == ImageFormatGroup.nv21) {
        bytes = frame.planes.first.bytes;
        if (bytes.length < frame.width * frame.height * 3 ~/ 2) {
          throw const FormatException('Quadro NV21 incompleto.');
        }
      } else if (frame.planes.length == 3 &&
          frame.format.group == ImageFormatGroup.yuv420) {
        bytes = yuv420ToNv21(
          frame.width,
          frame.height,
          frame.planes
              .map(
                (p) => PlaneBytes(p.bytes, p.bytesPerRow, p.bytesPerPixel ?? 1),
              )
              .toList(),
        );
      } else {
        throw FormatException(
          'Formato de análise não suportado: ${frame.format.group}, ${frame.planes.length} planos.',
        );
      }
    } else {
      if (frame.format.group != ImageFormatGroup.bgra8888 ||
          frame.planes.length != 1) {
        throw const FormatException(
          'A análise requer um quadro BGRA8888 neste aparelho.',
        );
      }
      format = InputImageFormat.bgra8888;
      bytes = frame.planes.first.bytes;
      row = frame.planes.first.bytesPerRow;
    }
    return PoseFrame(
      InputImage.fromBytes(
        bytes: bytes,
        metadata: InputImageMetadata(
          size: size,
          rotation: rotation,
          format: format,
          bytesPerRow: row,
        ),
      ),
      size,
      rotation,
      camera.lensDirection,
    );
  }

  /// Handles planar and interleaved chroma, row padding and pixel strides.
  static Uint8List yuv420ToNv21(
    int width,
    int height,
    List<PlaneBytes> planes,
  ) {
    if (width.isOdd || height.isOdd || planes.length != 3) {
      throw const FormatException('Dimensões YUV420 inválidas.');
    }
    final result = Uint8List(width * height * 3 ~/ 2);
    var offset = 0;
    int pixel(PlaneBytes plane, int x, int y) {
      final index = y * plane.rowStride + x * plane.pixelStride;
      if (index >= plane.bytes.length) {
        throw const FormatException('Plano YUV420 incompleto.');
      }
      return plane.bytes[index];
    }

    for (var y = 0; y < height; y++) {
      for (var x = 0; x < width; x++) {
        result[offset++] = pixel(planes[0], x, y);
      }
    }
    for (var y = 0; y < height ~/ 2; y++) {
      for (var x = 0; x < width ~/ 2; x++) {
        result[offset++] = pixel(planes[2], x, y); // NV21: V, U
        result[offset++] = pixel(planes[1], x, y);
      }
    }
    return result;
  }
}

class PlaneBytes {
  const PlaneBytes(this.bytes, this.rowStride, this.pixelStride);
  final Uint8List bytes;
  final int rowStride;
  final int pixelStride;
}
