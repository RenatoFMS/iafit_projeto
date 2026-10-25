import 'package:flutter/material.dart';

import '../../services/engine_service.dart';
import '../../services/settings_service.dart';

class SettingsScreen extends StatelessWidget {
  const SettingsScreen({super.key});

  void _showAbout(BuildContext context) {
    showDialog(
      context: context,
      builder: (dialogContext) {
        return AlertDialog(
          title: const Text(
            'Sobre o Fitness Pro',
            style: TextStyle(fontWeight: FontWeight.bold),
          ),
          content: const Text(
            'Fitness Pro é um aplicativo desenvolvido por João Lucas, Raul Dias e Renato Silva, '
            'como projeto acadêmico de TCC, com foco '
            'em organização de treinos, acompanhamento '
            'de progresso, exercícios e conteúdo educativo.',
            style: TextStyle(height: 1.5),
          ),
          actions: [
            TextButton(
              onPressed: () {
                Navigator.pop(dialogContext);
              },
              child: const Text('FECHAR'),
            ),
          ],
        );
      },
    );
  }

  void _showPrivacy(BuildContext context) {
    showDialog(
      context: context,
      builder: (dialogContext) {
        return AlertDialog(
          title: const Text(
            'Privacidade',
            style: TextStyle(fontWeight: FontWeight.bold),
          ),
          content: const Text(
            'Os dados utilizados pelo aplicativo '
            'são armazenados localmente durante o '
            'funcionamento do projeto. O aplicativo '
            'não envia o perfil ou os históricos para um '
            'servidor externo. Vídeos e miniaturas são carregados '
            'do YouTube, que pode receber dados de conexão conforme '
            'sua própria política de privacidade. A análise de movimento '
            'é local e não grava o vídeo da câmera. Se você ativar o motor '
            'IAFit em Configurações, o aplicativo troca apenas dados de '
            'treino (exercício, repetições, calorias e erros de postura) '
            'com o endereço que você informar.',
            style: TextStyle(height: 1.5),
          ),
          actions: [
            TextButton(
              onPressed: () {
                Navigator.pop(dialogContext);
              },
              child: const Text('FECHAR'),
            ),
          ],
        );
      },
    );
  }

  void _showTerms(BuildContext context) {
    showDialog(
      context: context,
      builder: (dialogContext) {
        return AlertDialog(
          title: const Text(
            'Termos de uso',
            style: TextStyle(fontWeight: FontWeight.bold),
          ),
          content: const Text(
            'O Fitness Pro possui finalidade '
            'educacional e informativa. As informações '
            'apresentadas não substituem orientação '
            'de profissionais de educação física, '
            'nutrição ou saúde.',
            style: TextStyle(height: 1.5),
          ),
          actions: [
            TextButton(
              onPressed: () {
                Navigator.pop(dialogContext);
              },
              child: const Text('FECHAR'),
            ),
          ],
        );
      },
    );
  }

  Future<void> _confirmReset(BuildContext context) async {
    final confirmed = await showDialog<bool>(
      context: context,
      builder: (dialogContext) {
        return AlertDialog(
          title: const Text('Restaurar configurações?'),
          content: const Text(
            'Todas as preferências voltarão '
            'aos valores padrão.',
          ),
          actions: [
            TextButton(
              onPressed: () {
                Navigator.pop(dialogContext, false);
              },
              child: const Text('CANCELAR'),
            ),
            ElevatedButton(
              onPressed: () {
                Navigator.pop(dialogContext, true);
              },
              child: const Text('RESTAURAR'),
            ),
          ],
        );
      },
    );

    if (confirmed != true) {
      return;
    }

    await SettingsService.instance.resetSettings();

    if (!context.mounted) {
      return;
    }

    ScaffoldMessenger.of(
      context,
    ).showSnackBar(const SnackBar(content: Text('Configurações restauradas.')));
  }

  Future<void> _editEngineConnection(BuildContext context) async {
    final settings = SettingsService.instance;
    final urlController = TextEditingController(text: settings.engineUrl.value);
    final tokenController = TextEditingController(
      text: settings.engineToken.value,
    );

    final saved = await showDialog<bool>(
      context: context,
      builder: (dialogContext) {
        return AlertDialog(
          title: const Text(
            'Motor IAFit',
            style: TextStyle(fontWeight: FontWeight.bold),
          ),
          content: SingleChildScrollView(
            child: Column(
              mainAxisSize: MainAxisSize.min,
              crossAxisAlignment: CrossAxisAlignment.start,
              children: [
                const Text(
                  'Ativo por padrão no Desktop em http://127.0.0.1:8765 '
                  '(iniciando o main.py automaticamente). Emulador Android: '
                  'http://10.0.2.2:8765. Telemóvel físico: http://IP-DO-PC:8765 '
                  '(com IAFIT_API_HOST=0.0.0.0). Deixe vazio para desativar.',
                  style: TextStyle(height: 1.4, fontSize: 12.5),
                ),
                const SizedBox(height: 14),
                TextField(
                  controller: urlController,
                  keyboardType: TextInputType.url,
                  autocorrect: false,
                  decoration: const InputDecoration(
                    labelText: 'Endereço',
                    hintText: 'http://127.0.0.1:8765',
                  ),
                ),
                const SizedBox(height: 12),
                TextField(
                  controller: tokenController,
                  autocorrect: false,
                  obscureText: true,
                  decoration: const InputDecoration(
                    labelText: 'Token (opcional)',
                  ),
                ),
              ],
            ),
          ),
          actions: [
            TextButton(
              onPressed: () {
                Navigator.pop(dialogContext, false);
              },
              child: const Text('CANCELAR'),
            ),
            ElevatedButton(
              onPressed: () {
                Navigator.pop(dialogContext, true);
              },
              child: const Text('SALVAR'),
            ),
          ],
        );
      },
    );

    final url = urlController.text;
    final token = tokenController.text;
    urlController.dispose();
    tokenController.dispose();

    if (saved != true) {
      return;
    }

    await settings.setEngineConnection(url: url, token: token);

    if (!context.mounted) {
      return;
    }

    if (EngineService.instance.enabled) {
      await _syncEngineNow(context);
    } else {
      ScaffoldMessenger.of(context).showSnackBar(
        const SnackBar(content: Text('Integração com o motor desativada.')),
      );
    }
  }

  Future<void> _syncEngineNow(BuildContext context) async {
    final messenger = ScaffoldMessenger.of(context);

    if (!EngineService.instance.enabled) {
      messenger.showSnackBar(
        const SnackBar(content: Text('Informe primeiro o endereço do motor.')),
      );
      return;
    }

    final imported = await EngineService.instance.sync();

    messenger.showSnackBar(
      SnackBar(
        content: Text(
          imported == null
              ? 'Não foi possível contactar o motor IAFit.'
              : imported == 0
              ? 'Histórico já está atualizado.'
              : '$imported ${imported == 1 ? 'treino importado' : 'treinos importados'}.',
        ),
      ),
    );
  }

  @override
  Widget build(BuildContext context) {
    final settings = SettingsService.instance;
    final theme = Theme.of(context);
    final colorScheme = theme.colorScheme;
    final isDark = theme.brightness == Brightness.dark;

    return Scaffold(
      appBar: AppBar(
        title: const Text(
          'Configurações',
          style: TextStyle(fontWeight: FontWeight.bold),
        ),
      ),
      body: ListView(
        padding: const EdgeInsets.fromLTRB(20, 12, 20, 40),
        children: [
          _buildIntroCard(context, isDark),

          const SizedBox(height: 28),

          _sectionTitle(context, 'Preferências'),

          const SizedBox(height: 10),

          _settingsCard(
            context: context,
            children: [
              ValueListenableBuilder<bool>(
                valueListenable: settings.notificationsEnabled,
                builder: (context, enabled, child) {
                  return _switchTile(
                    context: context,
                    icon: Icons.notifications_outlined,
                    title: 'Notificações',
                    subtitle: 'Receber avisos do aplicativo',
                    value: enabled,
                    onChanged: settings.setNotifications,
                  );
                },
              ),

              _divider(context),

              ValueListenableBuilder<bool>(
                valueListenable: settings.workoutReminderEnabled,
                builder: (context, enabled, child) {
                  return _switchTile(
                    context: context,
                    icon: Icons.alarm_outlined,
                    title: 'Lembrete de treino',
                    subtitle: 'Lembrar você de treinar',
                    value: enabled,
                    onChanged: settings.notificationsEnabled.value
                        ? settings.setWorkoutReminder
                        : null,
                  );
                },
              ),

              _divider(context),

              ValueListenableBuilder<bool>(
                valueListenable: settings.isDarkMode,
                builder: (context, enabled, child) {
                  return _switchTile(
                    context: context,
                    icon: enabled
                        ? Icons.dark_mode_rounded
                        : Icons.light_mode_outlined,
                    title: 'Modo escuro',
                    subtitle: enabled
                        ? 'Tema escuro ativado'
                        : 'Tema claro ativado',
                    value: enabled,
                    onChanged: settings.setDarkMode,
                  );
                },
              ),
            ],
          ),

          const SizedBox(height: 28),

          _sectionTitle(context, 'Motor IAFit'),

          const SizedBox(height: 10),

          _settingsCard(
            context: context,
            children: [
              ValueListenableBuilder<String>(
                valueListenable: settings.engineUrl,
                builder: (context, url, child) {
                  return _actionTile(
                    context: context,
                    icon: Icons.memory_rounded,
                    title: 'Conexão com o motor',
                    subtitle: url.isEmpty
                        ? 'Desativado · toque para configurar'
                        : url,
                    onTap: () {
                      _editEngineConnection(context);
                    },
                  );
                },
              ),

              _divider(context),

              _actionTile(
                context: context,
                icon: Icons.sync_rounded,
                title: 'Sincronizar agora',
                subtitle: 'Importar treinos concluídos no motor',
                onTap: () {
                  _syncEngineNow(context);
                },
              ),
            ],
          ),

          const SizedBox(height: 28),

          _sectionTitle(context, 'Informações'),

          const SizedBox(height: 10),

          _settingsCard(
            context: context,
            children: [
              _actionTile(
                context: context,
                icon: Icons.info_outline,
                title: 'Sobre o aplicativo',
                subtitle: 'Informações sobre o Fitness Pro',
                onTap: () {
                  _showAbout(context);
                },
              ),

              _divider(context),

              _actionTile(
                context: context,
                icon: Icons.lock_outline,
                title: 'Privacidade',
                subtitle: 'Como seus dados são utilizados',
                onTap: () {
                  _showPrivacy(context);
                },
              ),

              _divider(context),

              _actionTile(
                context: context,
                icon: Icons.description_outlined,
                title: 'Termos de uso',
                subtitle: 'Informações e responsabilidades',
                onTap: () {
                  _showTerms(context);
                },
              ),
            ],
          ),

          const SizedBox(height: 28),

          _sectionTitle(context, 'Aplicativo'),

          const SizedBox(height: 10),

          _settingsCard(
            context: context,
            children: [
              _actionTile(
                context: context,
                icon: Icons.restart_alt_rounded,
                title: 'Restaurar configurações',
                subtitle: 'Voltar às configurações padrão',
                onTap: () {
                  _confirmReset(context);
                },
                danger: true,
              ),

              _divider(context),

              ListTile(
                contentPadding: const EdgeInsets.symmetric(
                  horizontal: 16,
                  vertical: 7,
                ),
                leading: _iconContainer(context, Icons.apps_rounded),
                title: const Text(
                  'Versão',
                  style: TextStyle(fontWeight: FontWeight.w600),
                ),
                subtitle: const Text('Fitness Pro 1.0.0'),
                trailing: Container(
                  padding: const EdgeInsets.symmetric(
                    horizontal: 10,
                    vertical: 6,
                  ),
                  decoration: BoxDecoration(
                    color: colorScheme.primary.withValues(
                      alpha: isDark ? 0.14 : 0.09,
                    ),
                    borderRadius: BorderRadius.circular(10),
                  ),
                  child: Text(
                    '1.0.0',
                    style: TextStyle(
                      color: colorScheme.primary,
                      fontSize: 12,
                      fontWeight: FontWeight.w700,
                    ),
                  ),
                ),
              ),
            ],
          ),

          const SizedBox(height: 36),

          _buildFooter(context),
        ],
      ),
    );
  }

  Widget _buildIntroCard(BuildContext context, bool isDark) {
    final colorScheme = Theme.of(context).colorScheme;

    return Container(
      width: double.infinity,
      padding: const EdgeInsets.all(20),
      decoration: BoxDecoration(
        gradient: LinearGradient(
          colors: [const Color(0xFF10295C), const Color(0xFF2563EB)],
          begin: Alignment.topLeft,
          end: Alignment.bottomRight,
        ),
        borderRadius: BorderRadius.circular(24),
        boxShadow: [
          BoxShadow(
            color: colorScheme.primary.withValues(alpha: isDark ? 0.12 : 0.16),
            blurRadius: 18,
            offset: const Offset(0, 8),
          ),
        ],
      ),
      child: Row(
        children: [
          Container(
            width: 56,
            height: 56,
            decoration: BoxDecoration(
              color: Colors.white.withValues(alpha: 0.14),
              borderRadius: BorderRadius.circular(17),
              border: Border.all(color: Colors.white.withValues(alpha: 0.12)),
            ),
            child: const Icon(
              Icons.tune_rounded,
              color: Colors.white,
              size: 27,
            ),
          ),
          const SizedBox(width: 15),
          const Expanded(
            child: Column(
              crossAxisAlignment: CrossAxisAlignment.start,
              children: [
                Text(
                  'Personalize seu Fitness Pro',
                  style: TextStyle(
                    color: Colors.white,
                    fontSize: 17,
                    fontWeight: FontWeight.bold,
                  ),
                ),
                SizedBox(height: 5),
                Text(
                  'Ajuste suas preferências para deixar '
                  'o aplicativo do seu jeito.',
                  style: TextStyle(
                    color: Colors.white70,
                    fontSize: 12.5,
                    height: 1.4,
                  ),
                ),
              ],
            ),
          ),
        ],
      ),
    );
  }

  Widget _sectionTitle(BuildContext context, String title) {
    return Text(
      title,
      style: TextStyle(
        color: Theme.of(context).colorScheme.onSurface,
        fontSize: 20,
        fontWeight: FontWeight.bold,
      ),
    );
  }

  Widget _settingsCard({
    required BuildContext context,
    required List<Widget> children,
  }) {
    final theme = Theme.of(context);

    return Container(
      decoration: BoxDecoration(
        color: theme.colorScheme.surface,
        borderRadius: BorderRadius.circular(20),
        border: Border.all(
          color: theme.colorScheme.outline.withValues(alpha: 0.55),
          width: 0.7,
        ),
        boxShadow: [
          BoxShadow(
            color: Colors.black.withValues(
              alpha: theme.brightness == Brightness.dark ? 0.08 : 0.025,
            ),
            blurRadius: 14,
            offset: const Offset(0, 5),
          ),
        ],
      ),
      child: ClipRRect(
        borderRadius: BorderRadius.circular(20),
        child: Material(
          color: Colors.transparent,
          child: Column(children: children),
        ),
      ),
    );
  }

  Widget _switchTile({
    required BuildContext context,
    required IconData icon,
    required String title,
    required String subtitle,
    required bool value,
    required ValueChanged<bool>? onChanged,
  }) {
    final theme = Theme.of(context);
    final colorScheme = theme.colorScheme;

    return SwitchListTile(
      value: value,
      onChanged: onChanged,
      contentPadding: const EdgeInsets.symmetric(horizontal: 16, vertical: 7),
      secondary: _iconContainer(context, icon, active: value),
      title: Text(
        title,
        style: const TextStyle(fontWeight: FontWeight.w600, fontSize: 15),
      ),
      subtitle: Text(
        subtitle,
        style: TextStyle(color: colorScheme.onSurfaceVariant, fontSize: 12.5),
      ),
    );
  }

  Widget _iconContainer(
    BuildContext context,
    IconData icon, {
    bool active = false,
  }) {
    final theme = Theme.of(context);
    final colorScheme = theme.colorScheme;
    final isDark = theme.brightness == Brightness.dark;

    return Container(
      width: 44,
      height: 44,
      decoration: BoxDecoration(
        color: colorScheme.primary.withValues(
          alpha: active
              ? isDark
                    ? 0.18
                    : 0.10
              : isDark
              ? 0.12
              : 0.07,
        ),
        borderRadius: BorderRadius.circular(13),
      ),
      child: Icon(icon, color: colorScheme.primary, size: 21),
    );
  }

  Widget _actionTile({
    required BuildContext context,
    required IconData icon,
    required String title,
    required String subtitle,
    required VoidCallback onTap,
    bool danger = false,
  }) {
    final theme = Theme.of(context);
    final colorScheme = theme.colorScheme;

    final iconColor = danger ? Colors.redAccent : colorScheme.primary;

    return ListTile(
      onTap: onTap,
      contentPadding: const EdgeInsets.symmetric(horizontal: 16, vertical: 7),
      leading: Container(
        width: 44,
        height: 44,
        decoration: BoxDecoration(
          color: iconColor.withValues(
            alpha: theme.brightness == Brightness.dark ? 0.13 : 0.08,
          ),
          borderRadius: BorderRadius.circular(13),
        ),
        child: Icon(icon, color: iconColor, size: 21),
      ),
      title: Text(
        title,
        style: TextStyle(
          fontWeight: FontWeight.w600,
          fontSize: 15,
          color: danger ? Colors.redAccent : colorScheme.onSurface,
        ),
      ),
      subtitle: Text(
        subtitle,
        style: TextStyle(color: colorScheme.onSurfaceVariant, fontSize: 12.5),
      ),
      trailing: Icon(
        Icons.chevron_right_rounded,
        color: colorScheme.onSurfaceVariant,
      ),
    );
  }

  Widget _divider(BuildContext context) {
    return Divider(
      height: 1,
      thickness: 0.7,
      indent: 76,
      endIndent: 16,
      color: Theme.of(context).colorScheme.outline.withValues(alpha: 0.45),
    );
  }

  Widget _buildFooter(BuildContext context) {
    final theme = Theme.of(context);
    final colorScheme = theme.colorScheme;

    return Center(
      child: Column(
        children: [
          Container(
            width: 58,
            height: 58,
            decoration: BoxDecoration(
              color: colorScheme.primary.withValues(alpha: 0.09),
              shape: BoxShape.circle,
            ),
            child: Icon(
              Icons.fitness_center_rounded,
              color: colorScheme.primary,
              size: 27,
            ),
          ),
          const SizedBox(height: 12),
          Text(
            'Fitness Pro',
            style: TextStyle(
              color: colorScheme.onSurface,
              fontSize: 17,
              fontWeight: FontWeight.bold,
            ),
          ),
          const SizedBox(height: 4),
          Text(
            'Projeto acadêmico • TCC',
            style: TextStyle(color: colorScheme.onSurfaceVariant, fontSize: 12),
          ),
          const SizedBox(height: 8),
          Container(
            padding: const EdgeInsets.symmetric(horizontal: 10, vertical: 5),
            decoration: BoxDecoration(
              color: colorScheme.surfaceContainerHighest.withValues(alpha: 0.7),
              borderRadius: BorderRadius.circular(9),
            ),
            child: Text(
              'Fitness Pro 1.0.0',
              style: TextStyle(
                color: colorScheme.onSurfaceVariant,
                fontSize: 10.5,
                fontWeight: FontWeight.w600,
              ),
            ),
          ),
        ],
      ),
    );
  }
}
