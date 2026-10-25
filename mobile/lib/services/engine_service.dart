import 'dart:async';
import 'dart:convert';
import 'dart:ui' show Size;

import 'package:flutter/foundation.dart';
import 'package:google_mlkit_pose_detection/google_mlkit_pose_detection.dart';
import 'package:http/http.dart' as http;

import '../models/workout_history_model.dart';
import 'database_service.dart';
import 'engine_launcher.dart';
import 'settings_service.dart';

/// Resultado de um comando enviado ao motor, com texto pronto para a interface.
class EngineResult {
  const EngineResult(this.ok, this.message);

  final bool ok;
  final String message;
}

/// Estado em tempo real da série em curso no motor Python (`POST /analisar_pose` e `GET /estado`).
class EngineLiveState {
  const EngineLiveState({
    required this.exerciseId,
    required this.exerciseName,
    required this.repetitions,
    required this.seconds,
    required this.postureErrors,
    required this.status,
    required this.phase,
    required this.feedback,
    required this.isometric,
    this.percentage = 0,
    this.angle,
    this.asymmetryAlert = false,
    this.fatigueDetected = false,
    this.postureCorrect = true,
    this.outOfFrame = false,
  });

  factory EngineLiveState.fromJson(Map<String, dynamic> json) {
    final rawId = json['id_exercicio'] ?? json['exercicio_id'] ?? '';
    return EngineLiveState(
      exerciseId: rawId.toString(),
      exerciseName: (json['exercicio'] ?? '').toString(),
      repetitions: (json['repeticoes'] as num?)?.toInt() ?? 0,
      seconds: (json['segundos'] as num?)?.toInt() ?? 0,
      postureErrors: (json['erros_postura'] as num?)?.toInt() ?? 0,
      status: (json['estado'] ?? '').toString(),
      phase: (json['fase'] ?? '').toString(),
      feedback: (json['feedback'] ?? '').toString(),
      isometric: json['isometrico'] == true,
      percentage: (json['porc'] as num?)?.toInt() ?? 0,
      angle: (json['angulo'] as num?)?.toDouble(),
      asymmetryAlert: json['alerta_assimetria'] == true,
      fatigueDetected: json['fadiga_detectada'] == true,
      postureCorrect: json['postura_correta'] != false,
      outOfFrame: json['fora_enquadramento'] == true,
    );
  }

  final String exerciseId;
  final String exerciseName;
  final int repetitions;
  final int seconds;
  final int postureErrors;
  final String status;
  final String phase;
  final String feedback;
  final bool isometric;
  final int percentage;
  final double? angle;
  final bool asymmetryAlert;
  final bool fatigueDetected;
  final bool postureCorrect;
  final bool outOfFrame;
}

/// Cliente da API local do motor Python (`core/ponte_flutter.py`).
///
/// Endereço ativo por padrão em [defaultUrl] (`http://127.0.0.1:8765`),
/// com inicialização automática do processo Python em segundo plano no Desktop.
class EngineService {
  EngineService({
    http.Client? client,
    String Function()? urlProvider,
    String Function()? tokenProvider,
    DatabaseService? database,
    EngineLauncher? launcher,
    this.timeout = const Duration(seconds: 4),
    this.pollDelay = const Duration(milliseconds: 350),
  }) : _client = client ?? http.Client(),
       _urlProvider =
           urlProvider ?? (() => SettingsService.instance.engineUrl.value),
       _tokenProvider =
           tokenProvider ?? (() => SettingsService.instance.engineToken.value),
       _database = database ?? DatabaseService.instance,
       _launcher = launcher ?? EngineLauncher();

  static const String defaultUrl = 'http://127.0.0.1:8765';

  static final EngineService instance = EngineService();

  final http.Client _client;
  final String Function() _urlProvider;
  final String Function() _tokenProvider;
  final DatabaseService _database;
  final EngineLauncher _launcher;
  final Duration timeout;
  final Duration pollDelay;

  /// Incrementa sempre que novos treinos são importados; as telas escutam para recarregar.
  final ValueNotifier<int> revision = ValueNotifier<int>(0);

  /// Indica se a API `/saude` respondeu com sucesso na verificação mais recente.
  final ValueNotifier<bool> online = ValueNotifier<bool>(false);

  Timer? _autoSync;
  Timer? _postFinishSync;
  Future<bool>? _ensuring;
  String? _desiredExerciseId;
  String? _selectingId;
  Future<EngineResult>? _selectingFuture;
  String? _lastConfirmedExerciseId;
  EngineResult? _lastSelectResult;
  int _confirmedSequence = 0;
  bool _syncing = false;

  bool get enabled => _baseUri != null;

  /// ID do exercício atualmente aberto na interface do Flutter.
  String? get activeExerciseId => _desiredExerciseId;

  Uri? get _baseUri {
    final raw = _urlProvider().trim();
    if (raw.isEmpty) return null;
    final uri = Uri.tryParse(raw.contains('://') ? raw : 'http://$raw');
    if (uri == null || !uri.hasAuthority || uri.host.isEmpty) return null;
    return uri;
  }

  /// URL da rota de streaming MJPEG (`/video_feed`) do motor Python.
  Uri? get videoFeedUri => videoFeedUriFor(exerciseId: _desiredExerciseId);

  /// URL da rota `/video_feed` parametrizada com [exerciseId] (e token opcional),
  /// garantindo que o motor Python carregue o exercício da tela ao iniciar o vídeo.
  Uri? videoFeedUriFor({String? exerciseId}) {
    final base = _baseUri;
    if (base == null) return null;
    final token = _tokenProvider().trim();
    final targetId = (exerciseId ?? _desiredExerciseId ?? '').trim();
    final query = <String, String>{
      if (targetId.isNotEmpty) 'exercicio': targetId,
      if (token.isNotEmpty) 'token': token,
    };
    return _endpoint(base, '/video_feed', query.isEmpty ? null : query);
  }

  /// Cabeçalhos de autenticação opcionais para conexões de streaming.
  Map<String, String> get streamHeaders {
    final token = _tokenProvider().trim();
    return {if (token.isNotEmpty) 'X-IAFit-Token': token};
  }

  Uri _endpoint(Uri base, String path, [Map<String, String>? query]) {
    final prefix = base.path.endsWith('/')
        ? base.path.substring(0, base.path.length - 1)
        : base.path;
    return base.replace(path: '$prefix$path', queryParameters: query);
  }

  Map<String, String> get _headers {
    final token = _tokenProvider().trim();
    return {
      'Content-Type': 'application/json',
      if (token.isNotEmpty) 'X-IAFit-Token': token,
    };
  }

  bool _isLocalhost(Uri base) {
    final host = base.host.toLowerCase();
    return host == '127.0.0.1' || host == 'localhost' || host == '::1';
  }

  Future<bool> _pingHealth(Uri base) async {
    try {
      final response = await _client
          .get(_endpoint(base, '/saude'), headers: _headers)
          .timeout(const Duration(milliseconds: 1500));
      return response.statusCode == 200;
    } on Object {
      return false;
    }
  }

  /// Verifica se `GET /saude` responde com HTTP 200.
  Future<bool> checkHealth() async {
    final base = _baseUri;
    if (base == null) {
      online.value = false;
      return false;
    }
    final wasOnline = online.value;
    final ok = await _pingHealth(base);
    if (ok && !wasOnline && _desiredExerciseId != null) {
      await _postSelectExercise(base, _desiredExerciseId!, markOnline: false);
    }
    online.value = ok;
    return ok;
  }

  /// Verifica se o motor Python está disponível em `/saude`; caso não responda
  /// no Desktop (Linux/Windows/macOS), inicia `../venv/bin/python ../main.py`
  /// automaticamente em segundo plano, aplica o exercício ativo (se houver) e
  /// aguarda ficar pronto.
  Future<bool> ensureRunning() {
    final base = _baseUri;
    if (base == null) return Future<bool>.value(false);
    final pending = _ensuring;
    if (pending != null) return pending;

    final future = _doEnsureRunning(base);
    _ensuring = future.whenComplete(() {
      _ensuring = null;
    });
    return _ensuring!;
  }

  Future<bool> _doEnsureRunning(Uri base) async {
    if (await _pingHealth(base)) {
      final targetId = _desiredExerciseId;
      if (targetId != null && targetId.isNotEmpty) {
        await _postSelectExercise(base, targetId, markOnline: false);
      }
      online.value = true;
      return true;
    }

    online.value = false;
    if (!_isLocalhost(base) || !_launcher.isSupportedDesktop) {
      return false;
    }

    final started = await _launcher.startProcess();
    if (!started) return false;

    for (var attempt = 0; attempt < 45; attempt++) {
      await _waitCancellable(pollDelay);
      if (await _pingHealth(base)) {
        final targetId = _desiredExerciseId;
        if (targetId != null && targetId.isNotEmpty) {
          await _postSelectExercise(base, targetId, markOnline: false);
        }
        online.value = true;
        return true;
      }
    }
    return false;
  }

  Future<void> _waitCancellable(Duration duration) {
    final completer = Completer<void>();
    Timer(duration, () {
      if (!completer.isCompleted) completer.complete();
    });
    return completer.future;
  }

  /// Aciona o exercício [engineId] (chave do catálogo Python) no motor.
  /// Regista imediatamente o exercício desejado para que, mesmo durante um
  /// arranque a frio do processo Python, a troca seja disparada assim que a API
  /// ficar disponível, antes da abertura do stream de vídeo.
  Future<EngineResult> selectExercise(String engineId) {
    final normalized = engineId.trim();
    if (normalized.isEmpty) {
      return Future<EngineResult>.value(
        const EngineResult(false, 'ID de exercício inválido.'),
      );
    }
    _desiredExerciseId = normalized;

    if (_selectingFuture != null && _selectingId == normalized) {
      return _selectingFuture!;
    }

    _selectingId = normalized;
    final future = _doSelectExercise(normalized);
    _selectingFuture = future.whenComplete(() {
      if (_selectingId == normalized) {
        _selectingId = null;
        _selectingFuture = null;
      }
    });
    return _selectingFuture!;
  }

  Future<EngineResult> _doSelectExercise(String engineId) async {
    final base = _baseUri;
    if (base == null) {
      return const EngineResult(
        false,
        'Motor IAFit não configurado. Defina o endereço em Configurações.',
      );
    }

    final firstAttempt = await _postSelectExercise(base, engineId);
    if (firstAttempt != null) return firstAttempt;

    final seqBeforeEnsure = _confirmedSequence;
    final ready = await ensureRunning();
    if (ready) {
      final effectiveId = _desiredExerciseId ?? engineId;
      if (_confirmedSequence != seqBeforeEnsure &&
          _lastConfirmedExerciseId == effectiveId &&
          _lastSelectResult != null) {
        return _lastSelectResult!;
      }
      final retry = await _postSelectExercise(base, effectiveId);
      if (retry != null) return retry;
    }

    return const EngineResult(
      false,
      'Não foi possível contactar o motor IAFit. Verifique o ambiente Python.',
    );
  }

  Future<EngineResult?> _postSelectExercise(
    Uri base,
    String engineId, {
    bool markOnline = true,
  }) async {
    try {
      final response = await _client
          .post(
            _endpoint(base, '/exercicio'),
            headers: _headers,
            body: jsonEncode({'id': engineId}),
          )
          .timeout(timeout);
      if (response.statusCode == 202) {
        if (markOnline) {
          online.value = true;
        }
        final data = jsonDecode(utf8.decode(response.bodyBytes));
        final name = data is Map ? data['nome'] : null;
        final result = EngineResult(
          true,
          'Motor IAFit ativo${name is String ? ': $name' : ''}. Posicione-se na câmera.',
        );
        _lastConfirmedExerciseId = engineId;
        _lastSelectResult = result;
        _confirmedSequence++;
        return result;
      }
      return EngineResult(false, _httpError(response.statusCode));
    } on Object {
      if (markOnline) {
        online.value = false;
      }
      _lastConfirmedExerciseId = null;
      return null;
    }
  }

  /// Pede ao motor para guardar e encerrar a série em curso, sincronizando em seguida.
  Future<EngineResult> finishSeries({
    bool clearActiveExercise = false,
    String? exerciseId,
    int? repetitions,
    int? durationSeconds,
    int? postureErrors,
  }) async {
    if (clearActiveExercise) {
      _desiredExerciseId = null;
      _lastConfirmedExerciseId = null;
    }
    final base = _baseUri;
    if (base == null) {
      return const EngineResult(false, 'Motor IAFit não configurado.');
    }
    try {
      final payload = <String, Object>{
        if (exerciseId != null && exerciseId.trim().isNotEmpty)
          'id_exercicio': exerciseId.trim(),
        if (repetitions != null && repetitions > 0) 'repeticoes': repetitions,
        if (durationSeconds != null && durationSeconds > 0)
          'duracao_seg': durationSeconds,
        if (postureErrors != null && postureErrors >= 0)
          'erros_postura': postureErrors,
      };
      final response = await _client
          .post(
            _endpoint(base, '/finalizar'),
            headers: _headers,
            body: jsonEncode(payload),
          )
          .timeout(timeout);
      if (response.statusCode == 202) {
        online.value = true;
        unawaited(sync());
        _postFinishSync?.cancel();
        _postFinishSync = Timer(const Duration(milliseconds: 350), () {
          unawaited(sync());
        });
        return const EngineResult(
          true,
          'Série concluída e sincronizada com o histórico.',
        );
      }
      return EngineResult(false, _httpError(response.statusCode));
    } on Object {
      return const EngineResult(
        false,
        'Não foi possível contactar o motor IAFit.',
      );
    }
  }

  /// Converte os 33 landmarks do Google ML Kit num array JSON normalizado `[0.0, 1.0]`
  /// compatível com o endpoint `POST /analisar_pose` do motor matemático Python.
  static List<Map<String, double>> serializeMlKitLandmarks(
    Map<PoseLandmarkType, PoseLandmark> landmarks, {
    Size? frameSize,
  }) {
    final width = (frameSize != null && frameSize.width > 0)
        ? frameSize.width
        : 0.0;
    final height = (frameSize != null && frameSize.height > 0)
        ? frameSize.height
        : 0.0;

    final list = <Map<String, double>>[];
    for (final type in PoseLandmarkType.values) {
      final lm = landmarks[type];
      if (lm == null || !lm.x.isFinite || !lm.y.isFinite || !lm.z.isFinite) {
        list.add(const <String, double>{
          'x': 0.0,
          'y': 0.0,
          'z': 0.0,
          'visibilidade': 0.0,
        });
        continue;
      }

      var x = lm.x;
      var y = lm.y;
      var z = lm.z;
      if (width > 0 && height > 0 && (x > 1.0 || y > 1.0)) {
        x = (x / width).clamp(0.0, 1.0);
        y = (y / height).clamp(0.0, 1.0);
        z = z / width;
      }
      final vis = lm.likelihood.isFinite ? lm.likelihood.clamp(0.0, 1.0) : 0.0;
      list.add(<String, double>{
        'x': x,
        'y': y,
        'z': z,
        'visibilidade': vis,
      });
    }
    return list;
  }

  /// Envia os 33 pontos articulares extraídos na borda (ML Kit) para `POST /analisar_pose`
  /// e devolve a resposta biomecânica calculada pelo motor Python na mesma requisição.
  Future<EngineLiveState?> analyzePose({
    required String exerciseId,
    required List<Map<String, double>> landmarks,
    int? width,
    int? height,
  }) async {
    final base = _baseUri;
    final normalizedId = exerciseId.trim();
    if (base == null || normalizedId.isEmpty) return null;
    _desiredExerciseId = normalizedId;

    try {
      final payload = <String, Object>{
        'id_exercicio': normalizedId,
        'landmarks': landmarks,
        if (width != null && width > 0) 'largura': width,
        if (height != null && height > 0) 'altura': height,
      };
      final response = await _client
          .post(
            _endpoint(base, '/analisar_pose'),
            headers: _headers,
            body: jsonEncode(payload),
          )
          .timeout(const Duration(milliseconds: 1500));
      if (response.statusCode != 200) return null;
      online.value = true;
      final data = jsonDecode(utf8.decode(response.bodyBytes));
      if (data is! Map) return null;
      return EngineLiveState.fromJson(Map<String, dynamic>.from(data));
    } on Object {
      online.value = false;
      return null;
    }
  }

  /// Converte os landmarks do ML Kit e envia-os diretamente para `POST /analisar_pose`.
  Future<EngineLiveState?> analyzeMlKitPose({
    required String exerciseId,
    required Map<PoseLandmarkType, PoseLandmark> landmarks,
    Size? frameSize,
  }) {
    final serialized = serializeMlKitLandmarks(
      landmarks,
      frameSize: frameSize,
    );
    return analyzePose(
      exerciseId: exerciseId,
      landmarks: serialized,
    );
  }

  /// Obtém o estado ao vivo da série em curso (`GET /estado`).
  Future<EngineLiveState?> fetchState() async {
    final base = _baseUri;
    if (base == null) return null;
    try {
      final response = await _client
          .get(_endpoint(base, '/estado'), headers: _headers)
          .timeout(const Duration(milliseconds: 1500));
      if (response.statusCode != 200) return null;
      online.value = true;
      final data = jsonDecode(utf8.decode(response.bodyBytes));
      if (data is! Map) return null;
      return EngineLiveState.fromJson(Map<String, dynamic>.from(data));
    } on Object {
      return null;
    }
  }

  String _httpError(int status) => status == 401
      ? 'Token do motor IAFit inválido. Confira em Configurações.'
      : 'O motor IAFit recusou o pedido (HTTP $status).';

  /// Busca os treinos do motor e importa os novos. Devolve quantos foram inseridos
  /// ou `null` se o motor estiver desativado/inacessível.
  Future<int?> sync() async {
    final base = _baseUri;
    if (base == null || _syncing) return null;
    _syncing = true;
    try {
      final response = await _client
          .get(
            _endpoint(base, '/treinos', {'limite': '500'}),
            headers: _headers,
          )
          .timeout(timeout);
      if (response.statusCode != 200) return null;
      online.value = true;

      final data = jsonDecode(utf8.decode(response.bodyBytes));
      final raw = data is Map ? data['treinos'] : null;
      if (raw is! List) return null;

      final workouts = <WorkoutHistoryModel>[];
      for (final item in raw) {
        if (item is! Map) continue;
        final workout = WorkoutHistoryModel.fromEngineJson(
          Map<String, dynamic>.from(item),
        );
        if (workout != null) workouts.add(workout);
      }

      final inserted = await _database.importEngineWorkouts(workouts);
      if (inserted > 0) revision.value++;
      return inserted;
    } on Object {
      return null;
    } finally {
      _syncing = false;
    }
  }

  /// Importa treinos agora e a cada [interval] (sem efeito se já estiver ativo).
  void startAutoSync({Duration interval = const Duration(seconds: 6)}) {
    if (_autoSync != null) return;
    unawaited(sync());
    _autoSync = Timer.periodic(interval, (_) => unawaited(sync()));
  }

  void stopAutoSync() {
    _autoSync?.cancel();
    _autoSync = null;
    _postFinishSync?.cancel();
    _postFinishSync = null;
  }

  /// Encerra o processo filho do motor Python (se iniciado pelo app) e os timers.
  void shutdown() {
    stopAutoSync();
    _launcher.stopProcess();
  }
}
