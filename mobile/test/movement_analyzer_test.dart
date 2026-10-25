import 'dart:math';

import 'package:flutter_test/flutter_test.dart';
import 'package:fitness_app/services/movement_analyzer.dart';

void main() {
  void frames(MovementAnalyzer analyzer, double angle, [int count = 15]) {
    for (var i = 0; i < count; i++) {
      analyzer.update(angle);
    }
  }

  test('counts only after initial extension then the IAFit target phase', () {
    final analyzer = MovementAnalyzer('Agachamento livre');
    frames(analyzer, 85);
    frames(analyzer, 175);
    expect(analyzer.repetitions, 0);
    frames(analyzer, 85);
    frames(analyzer, 175);
    expect(analyzer.repetitions, 1);
    frames(analyzer, 175);
    expect(analyzer.repetitions, 1);
  });

  test('partial movements and tracking loss do not complete repetitions', () {
    final analyzer = MovementAnalyzer('Rosca direta');
    frames(analyzer, 175);
    frames(analyzer, 100);
    frames(analyzer, 175);
    expect(analyzer.repetitions, 0);
    frames(analyzer, 45);
    expect(analyzer.repetitions, 1); // IAFit counts when reaching flexion.
    analyzer.loseTracking();
    frames(analyzer, 175);
    expect(analyzer.repetitions, 1);
    frames(analyzer, 45);
    frames(analyzer, 175);
    expect(analyzer.repetitions, 2);
  });

  test('unsupported exercises use mirror mode', () {
    expect(MovementAnalyzer('Leg press').kind, MovementKind.mirror);
  });

  test('joint angle handles perpendicular and degenerate points', () {
    expect(
      MovementAnalyzer.angle(
        const Point(1.0, 0.0),
        const Point(0.0, 0.0),
        const Point(0.0, 1.0),
      ),
      closeTo(90, .001),
    );
    expect(
      MovementAnalyzer.angle(
        const Point(0.0, 0.0),
        const Point(0.0, 0.0),
        const Point(0.0, 1.0),
      ).isNaN,
      isTrue,
    );
  });
}
