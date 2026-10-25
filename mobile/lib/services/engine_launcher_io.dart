import 'dart:async';
import 'dart:io';

import 'package:flutter/foundation.dart';
import 'package:path/path.dart' as p;

/// Inicializa automaticamente o processo Python do motor IAFit (`main.py`)
/// em segundo plano quando o app Flutter executa no Desktop (Linux/Windows/macOS).
class EngineLauncher {
  Process? _process;

  bool get isSupportedDesktop {
    if (kIsWeb) return false;
    if (Platform.environment['FLUTTER_TEST'] == 'true') return false;
    return Platform.isLinux || Platform.isWindows || Platform.isMacOS;
  }

  bool get hasRunningProcess => _process != null;

  /// Inicia `../backend/venv/bin/python ../backend/main.py` (ou equivalente no Windows / bundle)
  /// em segundo plano via [Process.start].
  Future<bool> startProcess() async {
    if (!isSupportedDesktop) return false;
    if (_process != null) return true;

    final command = _resolveEngineCommand();
    if (command == null) {
      debugPrint('IAFit: main.py não encontrado para auto-start.');
      return false;
    }

    try {
      final proc = await Process.start(
        command.pythonExecutable,
        [command.scriptPath],
        workingDirectory: command.workingDirectory,
        environment: {
          'IAFIT_HEADLESS': '1',
          'PYTHONUNBUFFERED': '1',
          'IAFIT_PARENT_PID': '$pid',
        },
      );
      _process = proc;

      // Drena stdout/stderr para nunca encher o buffer de pipe do SO (64 KB).
      unawaited(proc.stdout.drain<void>().catchError((Object _) {}));
      unawaited(proc.stderr.drain<void>().catchError((Object _) {}));

      unawaited(
        proc.exitCode.then((code) {
          debugPrint('IAFit: processo Python encerrado (código $code).');
          if (identical(_process, proc)) {
            _process = null;
          }
        }),
      );
      return true;
    } on Object catch (error) {
      debugPrint('IAFit: falha ao iniciar o motor Python: $error');
      return false;
    }
  }

  void stopProcess() {
    final proc = _process;
    _process = null;
    proc?.kill(ProcessSignal.sigterm);
  }

  _EngineCommand? _resolveEngineCommand() {
    // 1. Caminho direto relativo à pasta mobile/: ../backend/venv/bin/python ../backend/main.py
    final relativeBackendDir = Directory(
      Platform.isWindows ? r'..\backend' : '../backend',
    );
    final relativeMain = File(
      Platform.isWindows ? r'..\backend\main.py' : '../backend/main.py',
    );
    final relativePython = File(
      Platform.isWindows
          ? r'..\backend\venv\Scripts\python.exe'
          : '../backend/venv/bin/python',
    );

    if (relativeMain.existsSync() && relativePython.existsSync()) {
      return _EngineCommand(
        pythonExecutable: relativePython.absolute.path,
        scriptPath: relativeMain.absolute.path,
        workingDirectory: relativeBackendDir.absolute.path,
      );
    }

    // 2. Busca subindo diretórios a partir do diretório atual ou do executável compilado
    final seeds = <Directory>[
      Directory.current,
      File(Platform.resolvedExecutable).parent,
    ];

    for (final seed in seeds) {
      var dir = seed.absolute;
      for (var depth = 0; depth < 7; depth++) {
        final candidateDirs = <Directory>[
          Directory(p.join(dir.path, 'backend')),
          dir,
        ];
        for (final backendDir in candidateDirs) {
          final mainFile = File(p.join(backendDir.path, 'main.py'));
          if (mainFile.existsSync()) {
            final venvPython = Platform.isWindows
                ? File(p.join(backendDir.path, 'venv', 'Scripts', 'python.exe'))
                : File(p.join(backendDir.path, 'venv', 'bin', 'python'));
            final pythonExe = venvPython.existsSync()
                ? venvPython.path
                : (Platform.isWindows ? 'python' : 'python3');
            return _EngineCommand(
              pythonExecutable: pythonExe,
              scriptPath: mainFile.path,
              workingDirectory: backendDir.path,
            );
          }
        }
        final parent = dir.parent;
        if (parent.path == dir.path) break;
        dir = parent;
      }
    }

    return null;
  }
}

class _EngineCommand {
  const _EngineCommand({
    required this.pythonExecutable,
    required this.scriptPath,
    required this.workingDirectory,
  });

  final String pythonExecutable;
  final String scriptPath;
  final String workingDirectory;
}

