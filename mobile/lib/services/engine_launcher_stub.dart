/// Stub do inicializador do motor Python para plataformas sem `dart:io` (Web).
class EngineLauncher {
  bool get isSupportedDesktop => false;

  bool get hasRunningProcess => false;

  Future<bool> startProcess() async => false;

  void stopProcess() {}
}

