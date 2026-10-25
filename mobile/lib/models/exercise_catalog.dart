class ExerciseInfo {
  const ExerciseInfo(
    this.name,
    this.category,
    this.description,
    this.videoId,
    this.instructions,
  );
  final String name;
  final String category;
  final String description;
  final String videoId;
  final List<String> instructions;
  String get videoUrl => 'https://www.youtube.com/watch?v=$videoId';
  String get thumbnail => 'https://img.youtube.com/vi/$videoId/hqdefault.jpg';
}

/// Existing exercise catalog, with real demonstration links instead of test MP4s.
abstract final class ExerciseCatalog {
  static const exercises = [
    ExerciseInfo(
      'Supino reto',
      'Peito',
      'Exercício para desenvolvimento do peitoral, com participação dos tríceps e ombros.',
      'EZMYCLKuGow',
      [
        'Apoie os pés e mantenha as costas estáveis no banco.',
        'Desça a barra de forma controlada.',
        'Retorne sem perder a estabilidade dos ombros.',
      ],
    ),
    ExerciseInfo(
      'Agachamento livre',
      'Pernas',
      'Movimento composto que trabalha quadríceps, glúteos e posteriores.',
      'zgk71dUUt0Y',
      [
        'Encontre uma base estável e mantenha os pés apoiados.',
        'Flexione quadris e joelhos com controle.',
        'Retorne mantendo o equilíbrio e uma amplitude confortável.',
      ],
    ),
    ExerciseInfo(
      'Rosca direta',
      'Bíceps',
      'Exercício de flexão do cotovelo para trabalhar os bíceps.',
      'c__3LAiXYOk',
      [
        'Mantenha os cotovelos próximos ao tronco.',
        'Flexione os braços sem balançar o corpo.',
        'Desça a carga de maneira controlada.',
      ],
    ),
    ExerciseInfo(
      'Puxada frontal',
      'Costas',
      'Exercício para os músculos das costas, especialmente o latíssimo do dorso.',
      'pJM_rHhluK8',
      [
        'Ajuste o assento e o apoio das pernas.',
        'Puxe a barra à frente do corpo com controle.',
        'Retorne sem soltar a carga bruscamente.',
      ],
    ),
    ExerciseInfo(
      'Desenvolvimento',
      'Ombros',
      'Movimento de empurrar para desenvolver os músculos dos ombros.',
      'L-iQfHVeuVg',
      [
        'Mantenha o tronco estável.',
        'Eleve a carga sem compensar com a lombar.',
        'Retorne lentamente à posição inicial.',
      ],
    ),
    ExerciseInfo(
      'Tríceps pulley',
      'Tríceps',
      'Extensão do cotovelo realizada na polia.',
      'BI881NpBDHs',
      [
        'Mantenha os cotovelos junto ao corpo.',
        'Estenda os braços sem movimentar os ombros.',
        'Retorne de forma controlada.',
      ],
    ),
    ExerciseInfo(
      'Prancha',
      'Abdômen',
      'Exercício isométrico para o abdômen e a musculatura do core.',
      'qNRqGqESAWU',
      [
        'Apoie os antebraços e as pontas dos pés.',
        'Mantenha o corpo alinhado e respire normalmente.',
        'Interrompa quando não conseguir manter a posição.',
      ],
    ),
    ExerciseInfo(
      'Elevação lateral',
      'Ombros',
      'Movimento para trabalhar a região lateral dos ombros.',
      'IwWvZ0rlNXs',
      [
        'Mantenha o tronco estável e os cotovelos levemente flexionados.',
        'Eleve os braços lateralmente com controle.',
        'Retorne sem balançar o corpo.',
      ],
    ),
  ];

  static ExerciseInfo? find(String name) {
    final normalized = name.toLowerCase().trim();
    if (normalized == 'agachamento') return exercises[1];
    for (final exercise in exercises) {
      if (exercise.name.toLowerCase() == normalized) return exercise;
    }
    return null;
  }
}
