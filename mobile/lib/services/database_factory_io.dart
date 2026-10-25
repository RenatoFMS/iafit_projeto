import 'dart:io';

import 'package:flutter/foundation.dart';
import 'package:sqflite_common_ffi/sqflite_ffi.dart';

/// Inicializa o motor SQLite via FFI quando executado em plataformas Desktop
/// (Linux, Windows, macOS). Em Android e iOS, o sqflite utiliza os canais
/// nativos do sistema.
void initDatabaseFactoryForDesktop({bool force = false}) {
  if (!kIsWeb &&
      (Platform.isLinux || Platform.isWindows || Platform.isMacOS)) {
    if (force) {
      sqfliteFfiInit();
      databaseFactory = databaseFactoryFfi;
      return;
    }

    try {
      databaseFactory;
    } catch (_) {
      sqfliteFfiInit();
      databaseFactory = databaseFactoryFfi;
    }
  }
}

