import 'dart:convert';
import 'dart:io';
import 'dart:ui' show Size;

import 'package:fitness_app/models/engine_exercise_map.dart';
import 'package:fitness_app/models/workout_history_model.dart';
import 'package:fitness_app/services/database_service.dart';
import 'package:fitness_app/services/engine_launcher.dart';
import 'package:fitness_app/services/engine_service.dart';
import 'package:fitness_app/widgets/mjpeg_stream_view.dart';
import 'package:flutter_test/flutter_test.dart';
import 'package:google_mlkit_pose_detection/google_mlkit_pose_detection.dart';
import 'package:http/http.dart' as http;
import 'package:http/testing.dart';
import 'package:path/path.dart' as p;
import 'package:sqflite_common_ffi/sqflite_ffi.dart';

// Fixtures sintéticos: o banco existe apenas numa pasta temporária isolada.
void main() {
  TestWidgetsFlutterBinding.ensureInitialized();
  late Directory temporary;

  setUpAll(() async {
    sqfliteFfiInit();
    databaseFactory = databaseFactoryFfiNoIsolate;
    temporary = await Directory.systemTemp.createTemp('fitness_engine_test_');
    await databaseFactory.setDatabasesPath(temporary.path);

    // Banco na versão 2 (antes da integração) com um treino legado: a abertura
    // pelo DatabaseService deve migrar para a versão 3 sem perder dados.
    final legacy = await databaseFactory.openDatabase(
      p.join(temporary.path, 'fitness_pro.db'),
      options: OpenDatabaseOptions(
        version: 2,
        onCreate: (db, version) async {
          await db.execute('''
            CREATE TABLE workout_history (
              id INTEGER PRIMARY KEY AUTOINCREMENT,
              workoutName TEXT NOT NULL,
              duration INTEGER NOT NULL,
              calories INTEGER NOT NULL,
              date TEXT NOT NULL
            )
          ''');
        },
      ),
    );
    await legacy.insert('workout_history', {
      'workoutName': 'Pernas',
      'duration': 30,
      'calories': 200,
      'date': '2026-10-20T10:00:00.000',
    });
    await legacy.close();
  });

  tearDownAll(() async {
    await DatabaseService.instance.closeDatabase();
    await temporary.delete(recursive: true);
  });

  final repsJson = <String, dynamic>{
    'id': 'abc123',
    'exercicio': 'Flexao de Braco',
    'repeticoes': 12,
    'erros_postura': 2,
    'calorias': 1.26,
    'duracao_seg': 40,
    'exercicio_id': '3',
    'isometrico': false,
    'data': '2026-10-25T05:44:52.948121+00:00',
  };
  final plankJson = <String, dynamic>{
    'id': 'def456',
    'exercicio': 'Prancha Isometrica',
    'repeticoes': 30,
    'erros_postura': 1,
    'calorias': 2.0,
    'duracao_seg': 30,
    'exercicio_id': '8',
    'isometrico': true,
    'data': '2026-10-25T05:50:00+00:00',
  };

  group('WorkoutHistoryModel.fromEngineJson', () {
    test('converte um treino por repetições', () {
      final workout = WorkoutHistoryModel.fromEngineJson(repsJson)!;
      expect(workout.remoteId, 'abc123');
      expect(workout.workoutName, 'Flexao de Braco');
      expect(workout.repetitions, 12);
      expect(workout.postureErrors, 2);
      expect(workout.caloriesExact, 1.26);
      expect(workout.calories, 1);
      expect(workout.durationSeconds, 40);
      expect(workout.duration, 1);
      expect(workout.engineSummary, '12 reps · 2 erros de postura');
      expect(workout.durationLabel, '40s');
      expect(workout.caloriesLabel, '1.3 kcal');
    });

    test('usa as repetições como segundos em isométricos sem duração', () {
      final workout = WorkoutHistoryModel.fromEngineJson({
        ...plankJson,
        'duracao_seg': 0,
        'repeticoes': 45,
        'erros_postura': 0,
      })!;
      expect(workout.durationSeconds, 45);
      expect(workout.engineSummary, '45s sob tensão · postura sem erros');
    });

    test('ignora registros sem id', () {
      expect(WorkoutHistoryModel.fromEngineJson({'exercicio': 'X'}), isNull);
    });

    test('treino legado mantém os rótulos antigos', () {
      final legacy = WorkoutHistoryModel(
        workoutName: 'Pernas',
        duration: 30,
        calories: 200,
        date: '2026-10-20',
      );
      expect(legacy.engineSummary, isNull);
      expect(legacy.caloriesLabel, '200 kcal');
      expect(legacy.durationLabel, '30 min');
      expect(legacy.effectiveSeconds, 1800);
    });
  });

  group('EngineExerciseMap', () {
    test('mapeia nomes do app para IDs do catálogo Python', () {
      expect(EngineExerciseMap.idFor('Agachamento livre'), '2');
      expect(EngineExerciseMap.idFor('Elevação pélvica'), '12');
      expect(EngineExerciseMap.idFor('Panturrilha em pé'), '21');
      expect(EngineExerciseMap.idFor('Panturrilha sentado'), '21');
      expect(EngineExerciseMap.idFor('Puxada frontal'), '16');
      expect(EngineExerciseMap.idFor('Supino inclinado'), '10');
      expect(EngineExerciseMap.idFor('Tríceps pulley'), '17');
      expect(EngineExerciseMap.idFor('Abdominal bicicleta'), '5');
      expect(EngineExerciseMap.idFor('  PRANCHA  '), '8');
    });

    test('exercícios sem análise no motor devolvem null', () {
      expect(EngineExerciseMap.idFor('Leg press'), isNull);
      expect(EngineExerciseMap.idFor('Corrida'), isNull);
    });
  });

  group('EngineService', () {
    test('selectExercise envia o ID e o token ao motor', () async {
      late http.Request received;
      final service = EngineService(
        client: MockClient((request) async {
          received = request;
          return http.Response(
            jsonEncode({'aceito': true, 'id': '3', 'nome': 'Flexao de Braco'}),
            202,
            headers: {'content-type': 'application/json; charset=utf-8'},
          );
        }),
        urlProvider: () => 'http://10.0.2.2:8765/',
        tokenProvider: () => 'segredo',
      );

      final result = await service.selectExercise('3');

      expect(result.ok, isTrue);
      expect(result.message, contains('Flexao de Braco'));
      expect(received.method, 'POST');
      expect(received.url.toString(), 'http://10.0.2.2:8765/exercicio');
      expect(received.headers['X-IAFit-Token'], 'segredo');
      expect(jsonDecode(received.body), {'id': '3'});
    });

    test('sem endereço configurado não faz chamadas de rede', () async {
      var calls = 0;
      final service = EngineService(
        client: MockClient((request) async {
          calls++;
          return http.Response('{}', 200);
        }),
        urlProvider: () => '',
        tokenProvider: () => '',
      );

      expect(service.enabled, isFalse);
      expect((await service.selectExercise('3')).ok, isFalse);
      expect(await service.sync(), isNull);
      expect(calls, 0);
    });

    test('motor offline devolve falha sem lançar exceção', () async {
      final service = EngineService(
        client: MockClient((request) async => throw http.ClientException('x')),
        urlProvider: () => 'http://127.0.0.1:8765',
        tokenProvider: () => '',
      );

      expect((await service.selectExercise('3')).ok, isFalse);
      expect(await service.sync(), isNull);
    });

    test('sync importa para o histórico, sem duplicar, e atualiza totais', () async {
      final service = EngineService(
        client: MockClient((request) async {
          expect(request.url.path, '/treinos');
          return http.Response(
            jsonEncode({
              'treinos': [repsJson, plankJson],
            }),
            200,
            headers: {'content-type': 'application/json; charset=utf-8'},
          );
        }),
        urlProvider: () => 'http://127.0.0.1:8765',
        tokenProvider: () => '',
      );
      final database = DatabaseService.instance;

      // O banco legado v2 foi migrado e o treino antigo continua legível.
      final before = await database.getWorkoutHistory();
      expect(before.single.workoutName, 'Pernas');
      expect(before.single.fromEngine, isFalse);

      expect(await service.sync(), 2);
      expect(service.revision.value, 1);
      expect(await service.sync(), 0); // segunda importação: tudo duplicado
      expect(service.revision.value, 1);

      final history = await database.getWorkoutHistory();
      expect(history.length, 3);
      expect(history.where((w) => w.fromEngine).length, 2);

      expect(await database.getTotalWorkouts(), 3);
      expect(await database.getTotalRepetitions(), 12); // isométricos excluídos
      expect(await database.getTotalPostureErrors(), 3);
      expect(await database.getTotalCalories(), 203); // 200 + 1.26 + 2.0
      expect(await database.getTotalDuration(), 32); // (1800 + 40 + 30) s → min
    });

    test('conexão 127.0.0.1:8765 e video_feed vêm ativos por padrão', () {
      final service = EngineService();
      expect(EngineService.defaultUrl, 'http://127.0.0.1:8765');
      expect(service.enabled, isTrue);
      expect(
        service.videoFeedUri.toString(),
        'http://127.0.0.1:8765/video_feed',
      );
    });

    test('inicia automaticamente o motor Python se /saude não responder', () async {
      var processStarted = false;
      final fakeLauncher = _FakeDesktopLauncher(
        onStart: () {
          processStarted = true;
          return true;
        },
      );

      final service = EngineService(
        launcher: fakeLauncher,
        pollDelay: const Duration(milliseconds: 5),
        urlProvider: () => 'http://127.0.0.1:8765',
        tokenProvider: () => '',
        client: MockClient((request) async {
          if (!processStarted) {
            throw http.ClientException('connection refused');
          }
          if (request.url.path == '/saude') {
            return http.Response(jsonEncode({'ok': true}), 200);
          }
          if (request.url.path == '/exercicio') {
            return http.Response(
              jsonEncode({'aceito': true, 'id': '2', 'nome': 'Agachamento'}),
              202,
              headers: {'content-type': 'application/json; charset=utf-8'},
            );
          }
          return http.Response('{}', 404);
        }),
      );

      final result = await service.selectExercise('2');
      expect(processStarted, isTrue);
      expect(fakeLauncher.startCount, 1);
      expect(result.ok, isTrue);
      expect(result.message, contains('Agachamento'));
    });

    test(
      'sincroniza o exercício aberto na UI antes de marcar online no arranque',
      () async {
        var serverReady = false;
        final events = <String>[];
        final fakeLauncher = _FakeDesktopLauncher(
          onStart: () {
            Future<void>.delayed(const Duration(milliseconds: 12), () {
              serverReady = true;
            });
            return true;
          },
        );

        final service = EngineService(
          launcher: fakeLauncher,
          pollDelay: const Duration(milliseconds: 5),
          urlProvider: () => 'http://127.0.0.1:8765',
          tokenProvider: () => '',
          client: MockClient((request) async {
            if (!serverReady) {
              throw http.ClientException('booting');
            }
            if (request.url.path == '/saude') {
              events.add('saude');
              return http.Response(jsonEncode({'ok': true}), 200);
            }
            if (request.url.path == '/exercicio') {
              final body = jsonDecode(request.body) as Map<String, dynamic>;
              events.add('exercicio:${body['id']}');
              return http.Response(
                jsonEncode({
                  'aceito': true,
                  'id': body['id'],
                  'nome': 'Prancha Isometrica',
                }),
                202,
                headers: {'content-type': 'application/json; charset=utf-8'},
              );
            }
            return http.Response('{}', 404);
          }),
        );

        service.online.addListener(() {
          if (service.online.value) {
            events.add('online_true');
          }
        });

        // Simula main.dart iniciando ensureRunning() antes da tela de treino abrir
        final bootFuture = service.ensureRunning();
        // Logo em seguida a tela de treino abre Prancha (ID '8'), diferente do id_atual estático
        final selectFuture = service.selectExercise('8');

        final result = await selectFuture;
        await bootFuture;

        expect(result.ok, isTrue);
        expect(service.activeExerciseId, '8');
        expect(
          service.videoFeedUriFor(exerciseId: '8').toString(),
          'http://127.0.0.1:8765/video_feed?exercicio=8',
        );
        // Garante que POST /exercicio ocorreu ANTES de online.value notificar o vídeo
        expect(events.indexOf('exercicio:8'), greaterThanOrEqualTo(0));
        expect(
          events.indexOf('exercicio:8'),
          lessThan(events.indexOf('online_true')),
        );
      },
    );

    test(
      'analyzeMlKitPose serializa 33 landmarks normalizados para POST /analisar_pose',
      () async {
        late Map<String, dynamic> receivedPayload;
        final service = EngineService(
          urlProvider: () => 'http://127.0.0.1:8765',
          tokenProvider: () => 'token123',
          client: MockClient((request) async {
            expect(request.method, 'POST');
            expect(request.url.path, '/analisar_pose');
            expect(request.headers['X-IAFit-Token'], 'token123');
            receivedPayload = jsonDecode(request.body) as Map<String, dynamic>;
            return http.Response(
              jsonEncode({
                'ok': true,
                'id_exercicio': '2',
                'exercicio': 'Agachamento',
                'repeticoes': 4,
                'segundos': 0,
                'erros_postura': 1,
                'porc': 85,
                'angulo': 88.5,
                'fase': 'subida',
                'estado': 'Treinando',
                'feedback': 'Boa profundidade! Suba.',
                'isometrico': false,
                'alerta_assimetria': false,
                'fadiga_detectada': false,
                'postura_correta': true,
              }),
              200,
              headers: {'content-type': 'application/json; charset=utf-8'},
            );
          }),
        );

        final mlKitLandmarks = <PoseLandmarkType, PoseLandmark>{
          PoseLandmarkType.leftHip: PoseLandmark(
            type: PoseLandmarkType.leftHip,
            x: 320.0,
            y: 240.0,
            z: -32.0,
            likelihood: 0.98,
          ),
          PoseLandmarkType.leftKnee: PoseLandmark(
            type: PoseLandmarkType.leftKnee,
            x: 320.0,
            y: 360.0,
            z: 0.0,
            likelihood: 0.95,
          ),
          PoseLandmarkType.leftAnkle: PoseLandmark(
            type: PoseLandmarkType.leftAnkle,
            x: 320.0,
            y: 440.0,
            z: 16.0,
            likelihood: 0.92,
          ),
        };

        final state = await service.analyzeMlKitPose(
          exerciseId: '2',
          landmarks: mlKitLandmarks,
          frameSize: const Size(640, 480),
        );

        expect(state, isNotNull);
        expect(state!.exerciseId, '2');
        expect(state.repetitions, 4);
        expect(state.postureErrors, 1);
        expect(state.percentage, 85);
        expect(state.angle, closeTo(88.5, 0.01));
        expect(state.phase, 'subida');
        expect(state.feedback, 'Boa profundidade! Suba.');

        expect(receivedPayload['id_exercicio'], '2');
        final landmarksList = receivedPayload['landmarks'] as List<dynamic>;
        expect(landmarksList.length, 33);
        final leftHip =
            landmarksList[PoseLandmarkType.leftHip.index]
                as Map<String, dynamic>;
        expect(leftHip['x'], closeTo(0.5, 0.001));
        expect(leftHip['y'], closeTo(0.5, 0.001));
        expect(leftHip['z'], closeTo(-0.05, 0.001));
        expect(leftHip['visibilidade'], closeTo(0.98, 0.001));
      },
    );
  });

  group('MjpegFrameParser', () {
    test('reconstrói quadros JPEG fragmentados no stream /video_feed', () {
      final parser = MjpegFrameParser();
      final fakeJpeg = <int>[0xFF, 0xD8, 1, 2, 3, 4, 5, 0xFF, 0xD9];
      final part = <int>[
        ...ascii.encode(
          '--iafitframe\r\n'
          'Content-Type: image/jpeg\r\n'
          'Content-Length: ${fakeJpeg.length}\r\n\r\n',
        ),
        ...fakeJpeg,
        ...ascii.encode('\r\n'),
      ];

      // Envia em dois pacotes cortados no meio
      expect(parser.addChunk(part.sublist(0, 35)), isNull);
      final decoded = parser.addChunk(part.sublist(35));
      expect(decoded, isNotNull);
      expect(decoded, fakeJpeg);
    });
  });
}

class _FakeDesktopLauncher extends EngineLauncher {
  _FakeDesktopLauncher({required this.onStart});

  final bool Function() onStart;
  int startCount = 0;

  @override
  bool get isSupportedDesktop => true;

  @override
  Future<bool> startProcess() async {
    startCount++;
    return onStart();
  }
}


