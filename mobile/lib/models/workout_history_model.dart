class WorkoutHistoryModel {
  final int? id;
  final String workoutName;
  final int duration;
  final int calories;
  final String date;

  /// Repetições concluídas (ou segundos, se [isometric]) vindas do motor IAFit.
  final int? repetitions;

  /// Erros de postura contabilizados pelo motor IAFit na série.
  final int? postureErrors;

  /// Gasto calórico com casas decimais (o campo [calories] guarda o arredondado).
  final double? caloriesExact;

  /// Duração exata da série em segundos (o campo [duration] guarda minutos).
  final int? durationSeconds;

  /// Indica que [repetitions] representa segundos de um exercício isométrico.
  final bool? isometric;

  /// ID do treino no motor IAFit; é a chave que evita importações duplicadas.
  final String? remoteId;

  WorkoutHistoryModel({
    this.id,
    required this.workoutName,
    required this.duration,
    required this.calories,
    required this.date,
    this.repetitions,
    this.postureErrors,
    this.caloriesExact,
    this.durationSeconds,
    this.isometric,
    this.remoteId,
  });

  /// Treino registrado pelo motor Python de Visão Computacional.
  bool get fromEngine => remoteId != null;

  /// Duração em segundos, mesmo para treinos antigos que só têm minutos.
  int get effectiveSeconds => durationSeconds ?? duration * 60;

  /// Calorias com precisão decimal sempre que o motor a informou.
  double get effectiveCalories => caloriesExact ?? calories.toDouble();

  String get caloriesLabel => caloriesExact != null
      ? '${caloriesExact!.toStringAsFixed(1)} kcal'
      : '$calories kcal';

  String get durationLabel {
    final seconds = durationSeconds;
    if (seconds != null && seconds > 0 && seconds < 60) return '${seconds}s';
    return '$duration min';
  }

  /// Resumo "12 reps · 2 erros de postura" exibido no histórico (só motor IAFit).
  String? get engineSummary {
    if (!fromEngine) return null;
    final amount = isometric == true
        ? '${repetitions ?? 0}s sob tensão'
        : '${repetitions ?? 0} reps';
    final errors = postureErrors ?? 0;
    final errorsLabel = errors == 0
        ? 'postura sem erros'
        : '$errors ${errors == 1 ? 'erro' : 'erros'} de postura';
    return '$amount · $errorsLabel';
  }

  Map<String, dynamic> toMap() {
    return {
      'id': id,
      'workoutName': workoutName,
      'duration': duration,
      'calories': calories,
      'date': date,
      'repetitions': repetitions,
      'postureErrors': postureErrors,
      'caloriesExact': caloriesExact,
      'durationSeconds': durationSeconds,
      'isometric': isometric == null ? null : (isometric! ? 1 : 0),
      'remoteId': remoteId,
    };
  }

  factory WorkoutHistoryModel.fromMap(Map<String, dynamic> map) {
    final isometricValue = map['isometric'];
    return WorkoutHistoryModel(
      id: map['id'] as int?,
      workoutName: map['workoutName'] as String,
      duration: (map['duration'] as num).toInt(),
      calories: (map['calories'] as num).toInt(),
      date: map['date'] as String,
      repetitions: (map['repetitions'] as num?)?.toInt(),
      postureErrors: (map['postureErrors'] as num?)?.toInt(),
      caloriesExact: (map['caloriesExact'] as num?)?.toDouble(),
      durationSeconds: (map['durationSeconds'] as num?)?.toInt(),
      isometric: isometricValue == null ? null : isometricValue == 1,
      remoteId: map['remoteId'] as String?,
    );
  }

  /// Converte um treino do contrato JSON do motor Python (`GET /treinos`).
  ///
  /// Campos: `exercicio`, `repeticoes`, `erros_postura`, `calorias`,
  /// `duracao_seg`, `isometrico`, `data` (ISO 8601) e `id`. Devolve `null` se
  /// o registro não tiver `id` (não seria possível evitar duplicados).
  static WorkoutHistoryModel? fromEngineJson(Map<String, dynamic> json) {
    final remoteId = json['id'];
    if (remoteId is! String || remoteId.isEmpty) return null;

    final isometric = json['isometrico'] == true;
    final reps = (json['repeticoes'] as num?)?.toInt() ?? 0;
    final reportedSeconds = (json['duracao_seg'] as num?)?.toInt() ?? 0;
    // Em isométricos a "repetição" já é o tempo; serve de reserva se faltar a duração.
    final seconds = reportedSeconds > 0 ? reportedSeconds : (isometric ? reps : 0);
    final kcal = (json['calorias'] as num?)?.toDouble() ?? 0.0;
    final date = DateTime.tryParse('${json['data']}')?.toLocal() ?? DateTime.now();

    return WorkoutHistoryModel(
      workoutName: (json['exercicio'] as String?)?.trim().isNotEmpty == true
          ? (json['exercicio'] as String).trim()
          : 'Exercício',
      duration: (seconds + 59) ~/ 60,
      calories: kcal.round(),
      date: date.toIso8601String(),
      repetitions: reps,
      postureErrors: (json['erros_postura'] as num?)?.toInt() ?? 0,
      caloriesExact: kcal,
      durationSeconds: seconds,
      isometric: isometric,
      remoteId: remoteId,
    );
  }
}
