/// Associa os exercícios do app aos IDs do catálogo do motor Python
/// (`core/config_exercicios.py`).
///
/// Só entram exercícios que o motor sabe analisar; os demais (ex.: máquinas
/// como leg press) devolvem `null` e não acionam o motor.
abstract final class EngineExerciseMap {
  static const Map<String, String> _idsByName = {
    'rosca direta': '1',
    'rosca biceps': '1',
    'rosca concentrada': '1',
    'agachamento livre': '2',
    'agachamento': '2',
    'flexao de bracos': '3',
    'flexao de braco': '3',
    'flexao': '3',
    'desenvolvimento': '4',
    'desenvolvimento ombro': '4',
    'abdominal supra': '5',
    'abdominal bicicleta': '5',
    'afundo': '6',
    'stiff': '7',
    'prancha': '8',
    'prancha isometrica': '8',
    'remada curvada': '9',
    'remada baixa': '9',
    'supino reto': '10',
    'supino inclinado': '10',
    'supino halteres': '10',
    'elevacao lateral': '11',
    'elevacao pelvica': '12',
    'mergulho no banco': '13',
    'rosca martelo': '14',
    'agachamento sumo': '15',
    'barra fixa': '16',
    'puxada frontal': '16',
    'triceps testa': '17',
    'triceps frances': '17',
    'triceps pulley': '17',
    'crucifixo': '18',
    'crucifixo inverso': '18',
    'pullover': '18',
    'stiff unilateral': '19',
    'elevacao frontal': '20',
    'panturrilha em pe': '21',
    'panturrilha sentado': '21',
    'prancha lateral': '22',
    'agachamento bulgaro': '23',
    'encolhimento': '24',
    'abdominal infra': '25',
    'elevacao de pernas': '25',
    'remada alta': '26',
    'bom dia': '27',
    'triceps coice': '28',
    'agachamento isometrico': '29',
    'polichinelo': '30',
  };

  static const Map<String, String> _accents = {
    'á': 'a', 'à': 'a', 'â': 'a', 'ã': 'a', 'ä': 'a',
    'é': 'e', 'è': 'e', 'ê': 'e', 'ë': 'e',
    'í': 'i', 'ì': 'i', 'î': 'i', 'ï': 'i',
    'ó': 'o', 'ò': 'o', 'ô': 'o', 'õ': 'o', 'ö': 'o',
    'ú': 'u', 'ù': 'u', 'û': 'u', 'ü': 'u',
    'ç': 'c',
  };

  /// Minúsculas, sem acentos e sem espaços repetidos.
  static String normalize(String name) {
    final buffer = StringBuffer();
    for (final rune in name.toLowerCase().runes) {
      final char = String.fromCharCode(rune);
      buffer.write(_accents[char] ?? char);
    }
    return buffer.toString().trim().replaceAll(RegExp(r'\s+'), ' ');
  }

  /// ID do exercício no motor Python ou `null` se o motor não o analisa.
  static String? idFor(String exerciseName) =>
      _idsByName[normalize(exerciseName)];
}

