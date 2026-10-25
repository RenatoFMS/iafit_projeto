import 'dart:async';
import 'dart:ui';

import 'package:flutter/material.dart';

import 'widgets/premium_components.dart';

import 'screens/main_navigation.dart';
import 'screens/onboarding/onboarding_screen.dart';
import 'theme/app_theme.dart';
import 'services/database_factory_stub.dart'
    if (dart.library.io) 'services/database_factory_io.dart';
import 'services/database_service.dart';
import 'services/engine_service.dart';
import 'services/settings_service.dart';

Future<void> main() async {
  WidgetsFlutterBinding.ensureInitialized();

  // Em plataformas desktop (Linux, Windows, macOS), inicializa o motor SQLite FFI
  // antes de qualquer chamada ao getDatabasesPath() ou DatabaseService.
  initDatabaseFactoryForDesktop();

  await DatabaseService.instance.database;

  await SettingsService.instance.load();

  // No Desktop (Linux/Windows/macOS), verifica 127.0.0.1:8765/saude e inicia
  // automaticamente o motor Python (../venv/bin/python ../main.py) se offline.
  unawaited(EngineService.instance.ensureRunning());

  // Importa em segundo plano os treinos concluídos no motor IAFit.
  EngineService.instance.startAutoSync();

  runApp(const FitnessApp());
}

class FitnessApp extends StatefulWidget {
  const FitnessApp({super.key});

  @override
  State<FitnessApp> createState() => _FitnessAppState();
}

class _FitnessAppState extends State<FitnessApp> {
  AppLifecycleListener? _lifecycleListener;

  @override
  void initState() {
    super.initState();
    _lifecycleListener = AppLifecycleListener(
      onExitRequested: () async {
        EngineService.instance.shutdown();
        return AppExitResponse.exit;
      },
      onDetach: () => EngineService.instance.shutdown(),
    );
  }

  @override
  void dispose() {
    _lifecycleListener?.dispose();
    super.dispose();
  }

  @override
  Widget build(BuildContext context) {
    return ValueListenableBuilder<bool>(
      valueListenable: SettingsService.instance.isDarkMode,
      builder: (context, isDarkMode, child) {
        return MaterialApp(
          debugShowCheckedModeBanner: false,
          title: 'Fitness Pro',
          theme: AppTheme.lightTheme,
          darkTheme: AppTheme.darkTheme,
          themeMode: isDarkMode ? ThemeMode.dark : ThemeMode.light,
          home: const StartupScreen(),
          builder: (context, child) => ColoredBox(
            color: Theme.of(context).scaffoldBackgroundColor,
            child: Align(
              alignment: Alignment.topCenter,
              child: ConstrainedBox(
                constraints: const BoxConstraints(maxWidth: 900),
                child: child ?? const SizedBox.shrink(),
              ),
            ),
          ),
        );
      },
    );
  }
}

class StartupScreen extends StatefulWidget {
  const StartupScreen({super.key});

  @override
  State<StartupScreen> createState() => _StartupScreenState();
}

class _StartupScreenState extends State<StartupScreen> {
  @override
  void initState() {
    super.initState();

    _startApp();
  }

  Future<void> _startApp() async {
    await Future.delayed(const Duration(milliseconds: 1200));

    if (!mounted) {
      return;
    }

    final completed = SettingsService.instance.onboardingCompleted.value;

    Navigator.of(context).pushReplacement(
      MaterialPageRoute(
        builder: (_) =>
            completed ? const MainNavigation() : const OnboardingScreen(),
      ),
    );
  }

  @override
  Widget build(BuildContext context) {
    return Scaffold(
      body: Center(
        child: Column(
          mainAxisAlignment: MainAxisAlignment.center,
          children: [
            const Entrance(child: StrengthArtwork(size: 180)),

            const SizedBox(height: 25),

            const Text(
              'Fitness Pro',
              style: TextStyle(fontSize: 30, fontWeight: FontWeight.w800),
            ),

            const SizedBox(height: 8),

            Text(
              'Treine. Evolua. Supere-se.',
              style: const TextStyle(fontSize: 14, color: AppColors.muted),
            ),

            const SizedBox(height: 35),

            const SizedBox(
              width: 28,
              height: 28,
              child: CircularProgressIndicator(
                strokeWidth: 3,
                color: Color(0xFF2563EB),
              ),
            ),
          ],
        ),
      ),
    );
  }
}
