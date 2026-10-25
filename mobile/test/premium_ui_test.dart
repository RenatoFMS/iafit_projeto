import 'dart:io';
import 'dart:ui' as ui;

import 'package:flutter/material.dart';
import 'package:flutter/rendering.dart';
import 'package:flutter/services.dart';
import 'package:flutter_test/flutter_test.dart';
import 'package:shared_preferences/shared_preferences.dart';
import 'package:sqflite_common_ffi/sqflite_ffi.dart';
import 'package:fitness_app/services/database_service.dart';
import 'package:fitness_app/services/settings_service.dart';
import 'package:fitness_app/theme/app_theme.dart';
import 'package:fitness_app/screens/home/home_screen.dart';
import 'package:fitness_app/screens/workouts/workouts_screen.dart';
import 'package:fitness_app/screens/workouts/workout_detail_screen.dart';
import 'package:fitness_app/screens/exercises/exercises_screen.dart';
import 'package:fitness_app/screens/exercises/exercise_detail_screen.dart';
import 'package:fitness_app/screens/progress/progress_screen.dart';
import 'package:fitness_app/screens/profile/profile_screen.dart';
import 'package:fitness_app/screens/settings/settings_screen.dart';
import 'package:fitness_app/screens/onboarding/onboarding_screen.dart';
import 'package:fitness_app/screens/content/content_screen.dart';
import 'package:fitness_app/screens/content/article_detail_screen.dart';
import 'package:fitness_app/screens/videos/videos_screen.dart';
import 'package:fitness_app/screens/main_navigation.dart';

// Synthetic fixtures exist only inside this isolated temporary test database.
void main() {
  TestWidgetsFlutterBinding.ensureInitialized();
  late Directory temporary;
  setUpAll(() async {
    sqfliteFfiInit();
    databaseFactory = databaseFactoryFfiNoIsolate;
    temporary = await Directory.systemTemp.createTemp('fitness_premium_test_');
    await databaseFactory.setDatabasesPath(temporary.path);
    SharedPreferences.setMockInitialValues({
      'dark_mode': true,
      'onboarding_completed': false,
    });
    await SettingsService.instance.load();
    final db = await DatabaseService.instance.database;
    await db.insert('users', {
      'name': 'Atleta Teste',
      'weight': 75.0,
      'height': 1.75,
      'goal': 'Manter o peso',
    });
    await db.insert('workout_history', {
      'workoutName': 'Pernas',
      'duration': 30,
      'calories': 200,
      'date': DateTime.now().toIso8601String(),
    });
    await db.insert('weight_history', {
      'weight': 75.0,
      'date': DateTime.now().toIso8601String(),
    });
    final font = FontLoader('Manrope')
      ..addFont(rootBundle.load('assets/fonts/Manrope.ttf'));
    await font.load();
    final icons = FontLoader('MaterialIcons')
      ..addFont(rootBundle.load('fonts/MaterialIcons-Regular.otf'));
    await icons.load();
  });
  tearDownAll(() async {
    await DatabaseService.instance.closeDatabase();
    await temporary.delete(recursive: true);
  });

  const session = WorkoutSessionScreen(
    workoutName: 'Pernas',
    duration: 30,
    calories: 200,
    exercises: [
      {
        'name': 'Agachamento livre',
        'sets': 3,
        'reps': '12',
        'rest': 30,
        'muscle': 'Pernas',
      },
    ],
  );
  final pages = <String, Widget>{
    'home': const HomeScreen(),
    'navigation': const MainNavigation(),
    'workouts': const WorkoutsScreen(),
    'workout_detail': const WorkoutDetailScreen(
      workoutName: 'Pernas',
      duration: 55,
      calories: 520,
    ),
    'session': session,
    'exercises': const ExercisesScreen(),
    'videos': const VideosScreen(),
    'exercise_detail': const ExerciseDetailScreen(
      name: 'Prancha',
      category: 'Abdômen',
      description: 'Exercício isométrico.',
      videoUrl: 'qNRqGqESAWU',
    ),
    'progress': const ProgressScreen(),
    'profile': const ProfileScreen(),
    'settings': const SettingsScreen(),
    'onboarding': const OnboardingScreen(),
    'content': const ContentScreen(),
    'article': const ArticleDetailScreen(
      title: 'Aquecimento',
      category: 'Treinamento',
      description: 'Prepare-se para o movimento.',
      icon: '🔥',
    ),
    'completed': const WorkoutCompletedScreen(
      workoutName: 'Pernas',
      duration: 30,
      calories: 200,
      exerciseCount: 8,
    ),
  };

  for (final width in [320.0, 390.0, 800.0]) {
    testWidgets('all pages fit ${width.toInt()}px with larger text', (
      tester,
    ) async {
      tester.view.physicalSize = Size(width, width == 800 ? 900 : 740);
      tester.view.devicePixelRatio = 1;
      addTearDown(tester.view.resetPhysicalSize);
      addTearDown(tester.view.resetDevicePixelRatio);
      for (final entry in pages.entries) {
        final boundaryKey = GlobalKey();
        await tester.pumpWidget(
          MaterialApp(
            theme: AppTheme.darkTheme,
            builder: (context, child) => MediaQuery(
              data: MediaQuery.of(context)
                  .copyWith(textScaler: const TextScaler.linear(1.15)),
              child: child!,
            ),
            home: RepaintBoundary(key: boundaryKey, child: entry.value),
          ),
        );
        await tester.runAsync(
          () => Future<void>.delayed(const Duration(milliseconds: 80)),
        );
        await tester.pumpAndSettle();
        expect(
          tester.takeException(),
          isNull,
          reason: '${entry.key} at $width',
        );
        if (width == 390 && const bool.fromEnvironment('CAPTURE_PREVIEWS')) {
          await tester.runAsync(() async {
            final boundary =
                boundaryKey.currentContext!.findRenderObject()!
                    as RenderRepaintBoundary;
            final image = await boundary.toImage(pixelRatio: 2);
            final bytes = await image.toByteData(
              format: ui.ImageByteFormat.png,
            );
            final output = File('artifacts/previews/${entry.key}.png');
            await output.parent.create(recursive: true);
            await output.writeAsBytes(bytes!.buffer.asUint8List());
            image.dispose();
          });
        }
        await tester.pumpWidget(const SizedBox.shrink());
        await tester.pump();
      }
    });
  }

  testWidgets('light theme preserves readability and layout on small screens', (
    tester,
  ) async {
    tester.view.physicalSize = const Size(320, 740);
    tester.view.devicePixelRatio = 1;
    addTearDown(tester.view.resetPhysicalSize);
    addTearDown(tester.view.resetDevicePixelRatio);
    for (final entry in pages.entries) {
      await tester.pumpWidget(
        MaterialApp(theme: AppTheme.lightTheme, home: entry.value),
      );
      await tester.runAsync(
        () => Future<void>.delayed(const Duration(milliseconds: 80)),
      );
      await tester.pumpAndSettle();
      expect(tester.takeException(), isNull, reason: 'light ${entry.key}');
      await tester.pumpWidget(const SizedBox.shrink());
      await tester.pump();
    }
  });

  testWidgets('saving the profile keeps the page open and persists the edit', (
    tester,
  ) async {
    await tester.pumpWidget(
      MaterialApp(theme: AppTheme.darkTheme, home: const ProfileScreen()),
    );
    await tester.runAsync(
      () => Future<void>.delayed(const Duration(milliseconds: 80)),
    );
    await tester.pumpAndSettle();
    final edit = find.byTooltip('Editar perfil');
    await tester.tap(edit);
    await tester.pumpAndSettle();
    await tester.enterText(find.byType(TextField).first, 'Perfil Atualizado');
    final save = find.text('Salvar alterações');
    await tester.ensureVisible(save);
    await tester.tap(save);
    await tester.runAsync(
      () => Future<void>.delayed(const Duration(milliseconds: 80)),
    );
    await tester.pumpAndSettle();
    expect(find.byType(ProfileScreen), findsOneWidget);
    expect(
      (await DatabaseService.instance.getUser())?.name,
      'Perfil Atualizado',
    );
    await tester.pumpWidget(const SizedBox.shrink());
  });

  testWidgets(
    'pause holds session clock and rest, resume preserves the series',
    (tester) async {
      await tester.pumpWidget(
        MaterialApp(theme: AppTheme.darkTheme, home: session),
      );
      await tester.pump(const Duration(seconds: 2));
      final pause = find.text('Pausar treino');
      await tester.ensureVisible(pause);
      await tester.tap(pause);
      await tester.pump();
      expect(find.text('TREINO PAUSADO'), findsOneWidget);
      expect(
        tester
            .widget<ElevatedButton>(
              find.widgetWithText(ElevatedButton, 'CONCLUIR SÉRIE'),
            )
            .onPressed,
        isNull,
      );
      await tester.tap(find.text('Retomar treino'));
      await tester.pump();
      final complete = find.text('CONCLUIR SÉRIE');
      await tester.ensureVisible(complete);
      await tester.tap(complete);
      await tester.pumpAndSettle();
      expect(find.text('SEGUNDOS DE DESCANSO'), findsOneWidget);
      await tester.ensureVisible(find.text('Pausar treino'));
      await tester.tap(find.text('Pausar treino'));
      await tester.pump(const Duration(seconds: 5));
      await tester.pumpAndSettle();
      expect(find.text('30'), findsOneWidget);
      await tester.ensureVisible(find.text('Retomar treino'));
      await tester.tap(find.text('Retomar treino'));
      await tester.pump();
      await tester.tap(find.text('PULAR'));
      await tester.pump();
      expect(find.text('2/3'), findsOneWidget);
      await tester.pumpWidget(const SizedBox.shrink());
    },
  );
}
