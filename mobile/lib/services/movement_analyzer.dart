import 'dart:math' as math;

enum MovementKind { squat, curl, shoulder, abdominal, lateral, mirror }

enum MovementPhase { waiting, initial, moving, target }

/// Dart port of IAFit/main.py. Thresholds and counting on the target phase are
/// preserved. Three consecutive observations reject brief landmark jitter.
class MovementRule {
  const MovementRule(
    this.kind,
    this.joint,
    this.start,
    this.target, {
    this.increasing = false,
  });
  final MovementKind kind;
  final String joint;
  final double start;
  final double target;
  final bool increasing;
  bool initial(double angle) => increasing ? angle < start : angle > start;
  bool reached(double angle) => increasing ? angle > target : angle < target;

  static MovementRule forExercise(String name) =>
      switch (name.toLowerCase().trim()) {
        'agachamento livre' ||
        'agachamento' ||
        'squat' => const MovementRule(MovementKind.squat, 'Joelho', 160, 90),
        'rosca direta' ||
        'rosca martelo' ||
        'rosca concentrada' ||
        'biceps' => const MovementRule(MovementKind.curl, 'Cotovelo', 160, 50),
        'desenvolvimento' || 'desenvolvimento de ombros' || 'shoulder' =>
          const MovementRule(MovementKind.shoulder, 'Ombro', 160, 80),
        'abdominal' || 'abdominal dinâmico' || 'abdominal tradicional' =>
          const MovementRule(MovementKind.abdominal, 'Quadril', 160, 100),
        'elevação lateral' || 'lateral' => const MovementRule(
          MovementKind.lateral,
          'Ombro',
          40,
          90,
          increasing: true,
        ),
        _ => const MovementRule(MovementKind.mirror, 'Sem regra', 0, 0),
      };
}

class MovementAnalyzer {
  MovementAnalyzer(String name) : rule = MovementRule.forExercise(name);
  final MovementRule rule;
  MovementKind get kind => rule.kind;
  int repetitions = 0;
  int incompleteMovements = 0;
  MovementPhase phase = MovementPhase.waiting;
  bool _armed = false;
  bool _attempted = false;
  int _stableFrames = 0;
  int _movingFrames = 0;
  bool? _lastCandidate;

  String get phaseLabel => switch (phase) {
    MovementPhase.waiting => 'Aguardando posição inicial',
    MovementPhase.initial =>
      kind == MovementKind.shoulder ? 'Braço elevado' : 'Posição inicial',
    MovementPhase.moving => 'Em movimento',
    MovementPhase.target => switch (kind) {
      MovementKind.squat => 'Flexão do joelho',
      MovementKind.curl => 'Flexão do cotovelo',
      MovementKind.shoulder => 'Retorno do braço',
      MovementKind.abdominal => 'Flexão do quadril',
      MovementKind.lateral => 'Elevação do braço',
      _ => 'Sem regra',
    },
  };

  void loseTracking() {
    _armed = false;
    _attempted = false;
    _stableFrames = 0;
    _movingFrames = 0;
    _lastCandidate = null;
    phase = MovementPhase.waiting;
  }

  String update(double angle) {
    if (kind == MovementKind.mirror) {
      return 'Este exercício ainda não possui regra de avaliação.';
    }
    if (!angle.isFinite || angle < 0 || angle > 180) {
      loseTracking();
      return 'Ângulo inválido. Reposicione-se para retomar o acompanhamento.';
    }
    final initial = rule.initial(angle);
    final target = rule.reached(angle);
    if (!initial && !target) {
      _stableFrames = 0;
      _lastCandidate = null;
      phase = _armed ? MovementPhase.moving : MovementPhase.waiting;
      if (_armed && (angle - rule.start).abs() > 20 && ++_movingFrames >= 3) {
        _attempted = true;
      }
      return _armed
          ? _angleFeedback(angle)
          : 'Assuma a posição inicial: ${rule.increasing ? "abaixo" : "acima"} de ${rule.start.round()}° no ${rule.joint.toLowerCase()}.';
    }
    _stableFrames = _lastCandidate == target ? _stableFrames + 1 : 1;
    _lastCandidate = target;
    if (_stableFrames >= 3) {
      if (initial) {
        final incomplete = _armed && _attempted;
        if (incomplete) incompleteMovements++;
        _armed = true;
        _attempted = false;
        _movingFrames = 0;
        phase = MovementPhase.initial;
        if (incomplete) {
          return 'Possível movimento incompleto: retornou sem atingir o limiar de ${rule.target.round()}°. É uma estimativa 2D.';
        }
      } else if (_armed) {
        // Same event as Python: increment when reaching the target, once.
        repetitions++;
        _armed = false;
        _attempted = false;
        phase = MovementPhase.target;
      }
    }
    return _angleFeedback(angle);
  }

  String _angleFeedback(double angle) => switch (kind) {
    MovementKind.squat when angle < 70 => 'Flexão abaixo de 70° estimada. Confira uma amplitude confortável com orientação profissional.',
    MovementKind.squat when angle > 170 =>
      'Joelho próximo da extensão, acima de 170°.',
    MovementKind.squat => 'Flexão do joelho acompanhada. Mova-se com controle.',
    MovementKind.curl when angle > 160 => 'Braço estendido, acima de 160°.',
    MovementKind.curl when angle < 50 =>
      'Flexão do cotovelo abaixo de 50° detectada.',
    MovementKind.curl => 'Flexão do cotovelo em andamento.',
    MovementKind.shoulder when angle > 160 =>
      'Braço elevado acima da cabeça. Retorne com controle.',
    MovementKind.shoulder when angle < 80 =>
      'Braço em posição mais baixa, abaixo de 80°.',
    MovementKind.shoulder => 'Ângulo do ombro em acompanhamento.',
    MovementKind.abdominal when angle > 160 =>
      'Quadril próximo da extensão, acima de 160°.',
    MovementKind.abdominal when angle < 100 =>
      'Flexão do quadril abaixo de 100° detectada.',
    MovementKind.abdominal => 'Flexão do quadril em andamento.',
    MovementKind.lateral when angle < 40 =>
      'Braço próximo ao corpo, abaixo de 40°.',
    MovementKind.lateral when angle > 90 => 'Elevação acima de 90° estimada. Respeite a amplitude orientada para você.',
    MovementKind.lateral => 'Elevação do braço em andamento.',
    _ => 'Sem regra de análise para este exercício.',
  };

  /// Equivalent to calcular_angulo in both Python files; reject coincident
  /// points, which numpy.arctan2 would otherwise turn into a plausible angle.
  static double angle(
    math.Point<double> a,
    math.Point<double> b,
    math.Point<double> c,
  ) {
    if ((a - b).magnitude < .001 || (c - b).magnitude < .001) return double.nan;
    final degrees =
        ((math.atan2(c.y - b.y, c.x - b.x) - math.atan2(a.y - b.y, a.x - b.x)) *
                180 /
                math.pi)
            .abs();
    return degrees > 180 ? 360 - degrees : degrees;
  }
}
