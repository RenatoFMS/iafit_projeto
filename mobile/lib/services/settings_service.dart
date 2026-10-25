import 'package:flutter/foundation.dart';
import 'package:shared_preferences/shared_preferences.dart';

class SettingsService {
  static final SettingsService instance = SettingsService._internal();

  SettingsService._internal();

  static const String defaultEngineUrl = 'http://127.0.0.1:8765';

  final ValueNotifier<bool> isDarkMode = ValueNotifier<bool>(true);

  final ValueNotifier<bool> notificationsEnabled = ValueNotifier<bool>(true);

  final ValueNotifier<bool> workoutReminderEnabled = ValueNotifier<bool>(true);

  final ValueNotifier<bool> onboardingCompleted = ValueNotifier<bool>(false);

  /// Endereço da API local do motor IAFit.
  ///
  /// Ativo por padrão em `http://127.0.0.1:8765` para funcionar imediatamente
  /// no Desktop sem configuração manual.
  final ValueNotifier<String> engineUrl = ValueNotifier<String>(
    const String.fromEnvironment(
      'IAFIT_ENGINE_URL',
      defaultValue: defaultEngineUrl,
    ),
  );

  /// Token opcional (`IAFIT_API_TOKEN` no motor), enviado em `X-IAFit-Token`.
  final ValueNotifier<String> engineToken = ValueNotifier<String>(
    const String.fromEnvironment('IAFIT_ENGINE_TOKEN'),
  );

  SharedPreferences? _preferences;

  Future<void> load() async {
    _preferences = await SharedPreferences.getInstance();

    isDarkMode.value = _preferences?.getBool('dark_mode') ?? true;

    notificationsEnabled.value = _preferences?.getBool('notifications') ?? true;

    workoutReminderEnabled.value =
        _preferences?.getBool('workout_reminder') ?? true;

    onboardingCompleted.value =
        _preferences?.getBool('onboarding_completed') ?? false;

    final engineDisabled = _preferences?.getBool('engine_disabled') ?? false;
    final savedUrl = _preferences?.getString('engine_url');
    if (engineDisabled) {
      engineUrl.value = '';
    } else if (savedUrl != null && savedUrl.trim().isNotEmpty) {
      engineUrl.value = savedUrl.trim();
    } else {
      engineUrl.value = const String.fromEnvironment(
        'IAFIT_ENGINE_URL',
        defaultValue: defaultEngineUrl,
      );
    }

    engineToken.value =
        _preferences?.getString('engine_token') ?? engineToken.value;
  }

  Future<void> setEngineConnection({
    required String url,
    required String token,
  }) async {
    final cleanedUrl = url.trim();
    engineUrl.value = cleanedUrl;
    engineToken.value = token.trim();

    await _preferences?.setBool('engine_disabled', cleanedUrl.isEmpty);
    await _preferences?.setString('engine_url', engineUrl.value);
    await _preferences?.setString('engine_token', engineToken.value);
  }

  Future<void> setDarkMode(bool value) async {
    isDarkMode.value = value;

    await _preferences?.setBool('dark_mode', value);
  }

  Future<void> setNotifications(bool value) async {
    notificationsEnabled.value = value;

    await _preferences?.setBool('notifications', value);

    if (!value) {
      await setWorkoutReminder(false);
    }
  }

  Future<void> setWorkoutReminder(bool value) async {
    workoutReminderEnabled.value = value;

    await _preferences?.setBool('workout_reminder', value);
  }

  Future<void> completeOnboarding() async {
    onboardingCompleted.value = true;

    await _preferences?.setBool('onboarding_completed', true);
  }

  Future<void> resetSettings() async {
    await setDarkMode(true);
    await setNotifications(true);
    await setWorkoutReminder(true);
    await setEngineConnection(url: defaultEngineUrl, token: '');
  }
}
