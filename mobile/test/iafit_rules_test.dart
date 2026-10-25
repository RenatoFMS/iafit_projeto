import 'dart:math';

import 'package:flutter_test/flutter_test.dart';
import 'package:fitness_app/services/movement_analyzer.dart';

void main() {
  // Independent reference of the five transitions in the supplied main.py.
  const cases = [
    ('Agachamento livre', 175.0, 85.0, 160.0, 90.0, false),
    ('Rosca direta', 175.0, 45.0, 160.0, 50.0, false),
    ('Desenvolvimento', 175.0, 75.0, 160.0, 80.0, false),
    ('Abdominal', 175.0, 95.0, 160.0, 100.0, false),
    ('Elevação lateral', 30.0, 100.0, 40.0, 90.0, true),
  ];
  for (final (name, start, target, startThreshold, targetThreshold, increasing)
      in cases) {
    test('IAFit thresholds and target-phase count are preserved for $name', () {
      final analyzer = MovementAnalyzer(name);
      expect(analyzer.rule.start, startThreshold);
      expect(analyzer.rule.target, targetThreshold);
      expect(analyzer.rule.increasing, increasing);
      var armed = false;
      var referenceCount = 0;
      for (final sample in [
        target,
        start,
        target,
        target,
        start,
        target,
        start,
      ]) {
        if (increasing ? sample < startThreshold : sample > startThreshold) {
          armed = true;
        }
        if ((increasing
                ? sample > targetThreshold
                : sample < targetThreshold) &&
            armed) {
          armed = false;
          referenceCount++;
        }
        // Stable observations are the only adaptation of Python's immediate step.
        for (var i = 0; i < 3; i++) {
          analyzer.update(sample);
        }
        expect(analyzer.repetitions, referenceCount);
      }
    });
  }

  test('strict boundaries and jitter do not create repetitions', () {
    final analyzer = MovementAnalyzer('Agachamento livre');
    for (var i = 0; i < 3; i++) {
      analyzer.update(175);
    }
    for (final a in [89.0, 92.0, 88.0, 93.0, 90.0, 90.0, 90.0]) {
      analyzer.update(a);
    }
    expect(analyzer.repetitions, 0);
    analyzer.update(double.nan);
    for (var i = 0; i < 3; i++) {
      analyzer.update(85);
    }
    expect(analyzer.repetitions, 0);
  });

  test(
    'partial excursion is reported only after return without reaching target',
    () {
      final analyzer = MovementAnalyzer('Rosca direta');
      for (final a in [175.0, 100.0, 175.0]) {
        for (var i = 0; i < 3; i++) {
          analyzer.update(a);
        }
      }
      expect(analyzer.incompleteMovements, 1);
      expect(analyzer.repetitions, 0);
      expect(MovementAnalyzer('Prancha abdominal').kind, MovementKind.mirror);
    },
  );

  test(
    'Python atan2 calculation folds reflex angles and rejects zero vectors',
    () {
      expect(
        MovementAnalyzer.angle(
          const Point(1.0, 0.0),
          const Point(0.0, 0.0),
          const Point(0.0, -1.0),
        ),
        90,
      );
      expect(
        MovementAnalyzer.angle(
          const Point(-1.0, .01),
          const Point(0.0, 0.0),
          const Point(-1.0, -.01),
        ),
        closeTo(1.1459, .001),
      );
      expect(
        MovementAnalyzer.angle(
          const Point(0.0, 0.0),
          const Point(0.0, 0.0),
          const Point(0.0, 1.0),
        ).isNaN,
        isTrue,
      );
    },
  );
}
