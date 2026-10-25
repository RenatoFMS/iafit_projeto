import 'package:flutter/foundation.dart';
import 'package:path/path.dart';
import 'package:sqflite/sqflite.dart';
import 'package:sqflite_common_ffi_web/sqflite_ffi_web.dart';

import 'database_factory_stub.dart'
    if (dart.library.io) 'database_factory_io.dart';

import '../models/user_model.dart';
import '../models/workout_history_model.dart';
import '../models/weight_history_model.dart';

class DatabaseService {
  static final DatabaseService instance = DatabaseService._internal();

  static Database? _database;

  DatabaseService._internal();

  Future<Database> get database async {
    if (_database != null) {
      return _database!;
    }

    _database = await _initDatabase();

    return _database!;
  }

  /// Versão atual do esquema.
  ///
  /// v2: tabela weight_history.
  /// v3: colunas do motor IAFit em workout_history (repetições, erros de postura,
  /// calorias/duração exatas e remoteId para evitar importações duplicadas).
  static const int _schemaVersion = 3;

  Future<Database> _initDatabase() async {
    if (kIsWeb) {
      databaseFactory = databaseFactoryFfiWeb;

      return await databaseFactory.openDatabase(
        'fitness_pro_web.db',
        options: OpenDatabaseOptions(
          version: _schemaVersion,
          onCreate: _createDatabase,
          onUpgrade: _upgradeDatabase,
        ),
      );
    }

    initDatabaseFactoryForDesktop();

    final databasePath = await getDatabasesPath();

    final path = join(databasePath, 'fitness_pro.db');

    return await openDatabase(
      path,
      version: _schemaVersion,
      onCreate: _createDatabase,
      onUpgrade: _upgradeDatabase,
    );
  }

  Future<void> _createDatabase(Database db, int version) async {
    await db.execute('''
      CREATE TABLE users (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        name TEXT NOT NULL,
        weight REAL NOT NULL,
        height REAL NOT NULL,
        goal TEXT NOT NULL
      )
    ''');

    await db.execute('''
      CREATE TABLE workout_history (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        workoutName TEXT NOT NULL,
        duration INTEGER NOT NULL,
        calories INTEGER NOT NULL,
        date TEXT NOT NULL,
        repetitions INTEGER,
        postureErrors INTEGER,
        caloriesExact REAL,
        durationSeconds INTEGER,
        isometric INTEGER,
        remoteId TEXT
      )
    ''');

    await _createRemoteIdIndex(db);

    await db.execute('''
      CREATE TABLE weight_history (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        weight REAL NOT NULL,
        date TEXT NOT NULL
      )
    ''');
  }

  Future<void> _createRemoteIdIndex(Database db) async {
    await db.execute(
      'CREATE UNIQUE INDEX IF NOT EXISTS idx_workout_history_remote_id '
      'ON workout_history (remoteId)',
    );
  }

  Future<void> _upgradeDatabase(
    Database db,
    int oldVersion,
    int newVersion,
  ) async {
    if (oldVersion < 2) {
      await db.execute('''
        CREATE TABLE IF NOT EXISTS weight_history (
          id INTEGER PRIMARY KEY AUTOINCREMENT,
          weight REAL NOT NULL,
          date TEXT NOT NULL
        )
      ''');
    }

    if (oldVersion < 3) {
      // Colunas opcionais: o histórico antigo permanece válido (valores NULL).
      const columns = {
        'repetitions': 'INTEGER',
        'postureErrors': 'INTEGER',
        'caloriesExact': 'REAL',
        'durationSeconds': 'INTEGER',
        'isometric': 'INTEGER',
        'remoteId': 'TEXT',
      };
      for (final entry in columns.entries) {
        await db.execute(
          'ALTER TABLE workout_history ADD COLUMN ${entry.key} ${entry.value}',
        );
      }
      await _createRemoteIdIndex(db);
    }
  }

  Future<int> insertUser(UserModel user) async {
    final db = await database;

    return await db.insert(
      'users',
      user.toMap(),
      conflictAlgorithm: ConflictAlgorithm.replace,
    );
  }

  Future<UserModel?> getUser() async {
    final db = await database;

    final result = await db.query('users', limit: 1);

    if (result.isEmpty) {
      return null;
    }

    return UserModel.fromMap(result.first);
  }

  Future<int> updateUser(UserModel user) async {
    final db = await database;

    return await db.update(
      'users',
      user.toMap(),
      where: 'id = ?',
      whereArgs: [user.id],
    );
  }

  Future<int> insertWorkout(WorkoutHistoryModel workout) async {
    final db = await database;

    return await db.insert('workout_history', workout.toMap());
  }

  Future<List<WorkoutHistoryModel>> getWorkoutHistory() async {
    final db = await database;

    final result = await db.query('workout_history', orderBy: 'id DESC');

    return result.map((map) => WorkoutHistoryModel.fromMap(map)).toList();
  }

  Future<int> getTotalCalories() async {
    final db = await database;

    final result = await db.rawQuery(
      'SELECT SUM(COALESCE(caloriesExact, calories)) as total '
      'FROM workout_history',
    );

    return (result.first['total'] as num?)?.round() ?? 0;
  }

  Future<int> getTotalWorkouts() async {
    final db = await database;

    final result = await db.rawQuery(
      'SELECT COUNT(*) as total FROM workout_history',
    );

    return (result.first['total'] as num?)?.toInt() ?? 0;
  }

  /// Duração total em minutos (soma exata em segundos, arredondada para cima).
  Future<int> getTotalDuration() async {
    final db = await database;

    final result = await db.rawQuery(
      'SELECT SUM(COALESCE(durationSeconds, duration * 60)) as total '
      'FROM workout_history',
    );

    final seconds = (result.first['total'] as num?)?.toInt() ?? 0;

    return (seconds + 59) ~/ 60;
  }

  /// Total de repetições registradas pelo motor IAFit (isométricos excluídos).
  Future<int> getTotalRepetitions() async {
    final db = await database;

    final result = await db.rawQuery(
      'SELECT SUM(repetitions) as total FROM workout_history '
      'WHERE COALESCE(isometric, 0) = 0',
    );

    return (result.first['total'] as num?)?.toInt() ?? 0;
  }

  /// Total de erros de postura contabilizados pelo motor IAFit.
  Future<int> getTotalPostureErrors() async {
    final db = await database;

    final result = await db.rawQuery(
      'SELECT SUM(postureErrors) as total FROM workout_history',
    );

    return (result.first['total'] as num?)?.toInt() ?? 0;
  }

  /// Importa treinos do motor IAFit ignorando os já existentes (por remoteId).
  ///
  /// Devolve quantos treinos novos foram inseridos.
  Future<int> importEngineWorkouts(List<WorkoutHistoryModel> workouts) async {
    if (workouts.isEmpty) return 0;

    final db = await database;

    return await db.transaction((txn) async {
      final existing = await txn.query(
        'workout_history',
        columns: ['remoteId'],
        where: 'remoteId IS NOT NULL',
      );
      final known = existing.map((row) => row['remoteId'] as String).toSet();

      var inserted = 0;
      for (final workout in workouts) {
        final remoteId = workout.remoteId;
        if (remoteId == null || !known.add(remoteId)) continue;

        await txn.insert(
          'workout_history',
          workout.toMap()..remove('id'),
          conflictAlgorithm: ConflictAlgorithm.ignore,
        );
        inserted++;
      }
      return inserted;
    });
  }

  Future<int> insertWeight(WeightHistoryModel weight) async {
    final db = await database;

    return await db.insert('weight_history', weight.toMap());
  }

  Future<List<WeightHistoryModel>> getWeightHistory() async {
    final db = await database;

    final result = await db.query('weight_history', orderBy: 'id ASC');

    return result.map((map) => WeightHistoryModel.fromMap(map)).toList();
  }

  Future<WeightHistoryModel?> getLatestWeight() async {
    final db = await database;

    final result = await db.query(
      'weight_history',
      orderBy: 'id DESC',
      limit: 1,
    );

    if (result.isEmpty) {
      return null;
    }

    return WeightHistoryModel.fromMap(result.first);
  }

  Future<void> closeDatabase() async {
    if (_database != null) {
      await _database!.close();
      _database = null;
    }
  }
}
