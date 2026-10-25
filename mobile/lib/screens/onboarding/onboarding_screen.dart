import 'package:flutter/material.dart';

import '../../theme/app_theme.dart';
import '../../widgets/premium_components.dart';

import '../../models/user_model.dart';
import '../../models/weight_history_model.dart';
import '../../services/database_service.dart';
import '../../services/settings_service.dart';
import '../main_navigation.dart';

class OnboardingScreen extends StatefulWidget {
  const OnboardingScreen({super.key});

  @override
  State<OnboardingScreen> createState() => _OnboardingScreenState();
}

class _OnboardingScreenState extends State<OnboardingScreen> {
  final PageController _pageController = PageController();

  int _currentPage = 0;

  final TextEditingController _nameController = TextEditingController();

  final TextEditingController _weightController = TextEditingController();

  final TextEditingController _heightController = TextEditingController();

  String _selectedGoal = 'Ganhar massa muscular';

  bool _isSaving = false;

  final List<_OnboardingPageData> _pages = [
    _OnboardingPageData(
      icon: Icons.fitness_center,
      title: 'Seu treino,\nsua evolução.',
      description: 'Organize seus treinos e tenha tudo que você precisa para evoluir em um só lugar.',
    ),
    _OnboardingPageData(
      icon: Icons.play_circle_outline,
      title: 'Aprenda a\nexecutar melhor.',
      description: 'Encontre exercícios, instruções e vídeos para entender melhor cada movimento.',
    ),
    _OnboardingPageData(
      icon: Icons.bar_chart,
      title: 'Acompanhe\nseu progresso.',
      description: 'Registre seus treinos, acompanhe seu peso, conquiste XP e mantenha sua sequência.',
    ),
  ];

  @override
  void dispose() {
    _pageController.dispose();
    _nameController.dispose();
    _weightController.dispose();
    _heightController.dispose();

    super.dispose();
  }

  void _nextPage() {
    if (_currentPage < _pages.length - 1) {
      _pageController.nextPage(
        duration: const Duration(milliseconds: 350),
        curve: Curves.easeOut,
      );
    } else {
      _showProfileSetup();
    }
  }

  void _previousPage() {
    if (_currentPage > 0) {
      _pageController.previousPage(
        duration: const Duration(milliseconds: 350),
        curve: Curves.easeOut,
      );
    }
  }

  void _skip() {
    _showProfileSetup();
  }

  void _showProfileSetup() {
    showModalBottomSheet(
      context: context,
      isScrollControlled: true,
      backgroundColor: Colors.transparent,
      builder: (context) {
        return _ProfileSetupSheet(
          nameController: _nameController,
          weightController: _weightController,
          heightController: _heightController,
          selectedGoal: _selectedGoal,
          onGoalChanged: (goal) {
            setState(() {
              _selectedGoal = goal;
            });
          },
          onSave: _saveProfile,
        );
      },
    );
  }

  Future<void> _saveProfile() async {
    if (_isSaving) {
      return;
    }

    final name = _nameController.text.trim();

    final weight = double.tryParse(
      _weightController.text.trim().replaceAll(',', '.'),
    );

    final height = double.tryParse(
      _heightController.text.trim().replaceAll(',', '.'),
    );

    if (name.isEmpty ||
        weight == null ||
        height == null ||
        weight <= 0 ||
        height <= 0) {
      ScaffoldMessenger.of(context).showSnackBar(
        const SnackBar(content: Text('Preencha todos os dados corretamente.')),
      );

      return;
    }

    setState(() {
      _isSaving = true;
    });

    try {
      final database = DatabaseService.instance;

      final existingUser = await database.getUser();

      final user = UserModel(
        id: existingUser?.id,
        name: name,
        weight: weight,
        height: height,
        goal: _selectedGoal,
      );

      if (existingUser == null) {
        await database.insertUser(user);
      } else {
        await database.updateUser(user);
      }

      await database.insertWeight(
        WeightHistoryModel(
          weight: weight,
          date: DateTime.now().toIso8601String(),
        ),
      );

      await SettingsService.instance.completeOnboarding();

      if (!mounted) {
        return;
      }

      Navigator.pop(context);

      Navigator.of(context).pushReplacement(
        MaterialPageRoute(builder: (_) => const MainNavigation()),
      );
    } catch (error) {
      if (!mounted) {
        return;
      }

      setState(() {
        _isSaving = false;
      });

      ScaffoldMessenger.of(
        context,
      ).showSnackBar(SnackBar(content: Text('Erro ao salvar perfil: $error')));
    }
  }

  @override
  Widget build(BuildContext context) {
    final theme = Theme.of(context);

    return Scaffold(
      backgroundColor: theme.scaffoldBackgroundColor,
      body: SafeArea(
        child: Column(
          children: [
            Padding(
              padding: const EdgeInsets.symmetric(horizontal: 20, vertical: 12),
              child: Row(
                children: [
                  if (_currentPage > 0)
                    IconButton(
                      onPressed: _previousPage,
                      icon: const Icon(Icons.arrow_back),
                    )
                  else
                    const SizedBox(width: 48),
                  const Spacer(),
                  TextButton(
                    onPressed: _skip,
                    child: const Text(
                      'PULAR',
                      style: TextStyle(fontWeight: FontWeight.bold),
                    ),
                  ),
                ],
              ),
            ),

            Expanded(
              child: PageView.builder(
                controller: _pageController,
                itemCount: _pages.length,
                onPageChanged: (page) {
                  setState(() {
                    _currentPage = page;
                  });
                },
                itemBuilder: (context, index) {
                  final page = _pages[index];

                  return SingleChildScrollView(
                    padding: const EdgeInsets.symmetric(
                      horizontal: 28,
                      vertical: 24,
                    ),
                    child: Column(
                      mainAxisAlignment: MainAxisAlignment.center,
                      children: [
                        Entrance(
                          child: index == 0
                              ? const StrengthArtwork(size: 220)
                              : Container(
                                  width: 180,
                                  height: 180,
                                  decoration: BoxDecoration(
                                    gradient: AppColors.heroGradient,
                                    borderRadius: BorderRadius.circular(52),
                                    border: Border.all(
                                      color: AppColors.sky.withValues(
                                        alpha: .3,
                                      ),
                                    ),
                                  ),
                                  child: Icon(
                                    page.icon,
                                    size: 70,
                                    color: Colors.white,
                                  ),
                                ),
                        ),

                        const SizedBox(height: 45),

                        Text(
                          page.title,
                          textAlign: TextAlign.center,
                          style: const TextStyle(
                            fontSize: 34,
                            fontWeight: FontWeight.w800,
                            height: 1.05,
                          ),
                        ),

                        const SizedBox(height: 20),

                        Text(
                          page.description,
                          textAlign: TextAlign.center,
                          style: TextStyle(
                            fontSize: 16,
                            height: 1.5,
                            color: theme.colorScheme.onSurfaceVariant,
                          ),
                        ),
                      ],
                    ),
                  );
                },
              ),
            ),

            Padding(
              padding: const EdgeInsets.fromLTRB(24, 10, 24, 25),
              child: Column(
                children: [
                  Row(
                    mainAxisAlignment: MainAxisAlignment.center,
                    children: List.generate(_pages.length, (index) {
                      final selected = index == _currentPage;

                      return AnimatedContainer(
                        duration: const Duration(milliseconds: 250),
                        margin: const EdgeInsets.symmetric(horizontal: 4),
                        width: selected ? 28 : 8,
                        height: 8,
                        decoration: BoxDecoration(
                          color: selected
                              ? const Color(0xFF2563EB)
                              : Colors.grey.shade300,
                          borderRadius: BorderRadius.circular(20),
                        ),
                      );
                    }),
                  ),

                  const SizedBox(height: 25),

                  SizedBox(
                    width: double.infinity,
                    height: 56,
                    child: ElevatedButton(
                      onPressed: _nextPage,
                      style: ElevatedButton.styleFrom(
                        backgroundColor: const Color(0xFF2563EB),
                        foregroundColor: Colors.white,
                        shape: RoundedRectangleBorder(
                          borderRadius: BorderRadius.circular(18),
                        ),
                      ),
                      child: Text(
                        _currentPage == _pages.length - 1
                            ? 'COMEÇAR'
                            : 'CONTINUAR',
                        style: const TextStyle(
                          fontSize: 16,
                          fontWeight: FontWeight.bold,
                        ),
                      ),
                    ),
                  ),
                ],
              ),
            ),
          ],
        ),
      ),
    );
  }
}

class _OnboardingPageData {
  final IconData icon;
  final String title;
  final String description;

  _OnboardingPageData({
    required this.icon,
    required this.title,
    required this.description,
  });
}

class _ProfileSetupSheet extends StatefulWidget {
  final TextEditingController nameController;
  final TextEditingController weightController;
  final TextEditingController heightController;
  final String selectedGoal;
  final ValueChanged<String> onGoalChanged;
  final Future<void> Function() onSave;

  const _ProfileSetupSheet({
    required this.nameController,
    required this.weightController,
    required this.heightController,
    required this.selectedGoal,
    required this.onGoalChanged,
    required this.onSave,
  });

  @override
  State<_ProfileSetupSheet> createState() => _ProfileSetupSheetState();
}

class _ProfileSetupSheetState extends State<_ProfileSetupSheet> {
  late String _goal;

  @override
  void initState() {
    super.initState();

    _goal = widget.selectedGoal;
  }

  @override
  Widget build(BuildContext context) {
    final bottom = MediaQuery.of(context).viewInsets.bottom;

    return Container(
      padding: EdgeInsets.fromLTRB(24, 28, 24, 24 + bottom),
      decoration: BoxDecoration(
        color: Theme.of(context).scaffoldBackgroundColor,
        borderRadius: const BorderRadius.vertical(top: Radius.circular(30)),
      ),
      child: SingleChildScrollView(
        child: Column(
          crossAxisAlignment: CrossAxisAlignment.start,
          children: [
            Center(
              child: Container(
                width: 45,
                height: 5,
                decoration: BoxDecoration(
                  color: Colors.grey.shade400,
                  borderRadius: BorderRadius.circular(20),
                ),
              ),
            ),

            const SizedBox(height: 25),

            const Text(
              'Vamos configurar seu perfil',
              style: TextStyle(fontSize: 26, fontWeight: FontWeight.bold),
            ),

            const SizedBox(height: 8),

            Text(
              'Essas informações serão usadas '
              'para personalizar sua experiência.',
              style: TextStyle(color: Colors.grey.shade600, height: 1.4),
            ),

            const SizedBox(height: 25),

            TextField(
              controller: widget.nameController,
              textCapitalization: TextCapitalization.words,
              decoration: const InputDecoration(
                labelText: 'Seu nome',
                prefixIcon: Icon(Icons.person_outline),
              ),
            ),

            const SizedBox(height: 15),

            TextField(
              controller: widget.weightController,
              keyboardType: const TextInputType.numberWithOptions(
                decimal: true,
              ),
              decoration: const InputDecoration(
                labelText: 'Peso',
                hintText: 'Ex.: 60',
                suffixText: 'kg',
                prefixIcon: Icon(Icons.monitor_weight_outlined),
              ),
            ),

            const SizedBox(height: 15),

            TextField(
              controller: widget.heightController,
              keyboardType: const TextInputType.numberWithOptions(
                decimal: true,
              ),
              decoration: const InputDecoration(
                labelText: 'Altura',
                hintText: 'Ex.: 1.75',
                suffixText: 'm',
                prefixIcon: Icon(Icons.height),
              ),
            ),

            const SizedBox(height: 20),

            const Text(
              'Qual é o seu objetivo?',
              style: TextStyle(fontSize: 16, fontWeight: FontWeight.w600),
            ),

            const SizedBox(height: 10),

            DropdownButtonFormField<String>(
              initialValue: _goal,
              decoration: const InputDecoration(
                prefixIcon: Icon(Icons.flag_outlined),
              ),
              items: const [
                DropdownMenuItem(
                  value: 'Ganhar massa muscular',
                  child: Text('Ganhar massa muscular'),
                ),
                DropdownMenuItem(value: 'Emagrecer', child: Text('Emagrecer')),
                DropdownMenuItem(
                  value: 'Manter o peso',
                  child: Text('Manter o peso'),
                ),
                DropdownMenuItem(
                  value: 'Melhorar condicionamento',
                  child: Text('Melhorar condicionamento'),
                ),
                DropdownMenuItem(
                  value: 'Aumentar força',
                  child: Text('Aumentar força'),
                ),
              ],
              onChanged: (value) {
                if (value == null) {
                  return;
                }

                setState(() {
                  _goal = value;
                });

                widget.onGoalChanged(value);
              },
            ),

            const SizedBox(height: 25),

            SizedBox(
              width: double.infinity,
              height: 56,
              child: ElevatedButton.icon(
                onPressed: widget.onSave,
                icon: const Icon(Icons.check),
                label: const Text('CRIAR MEU PERFIL'),
                style: ElevatedButton.styleFrom(
                  backgroundColor: const Color(0xFF2563EB),
                  foregroundColor: Colors.white,
                  shape: RoundedRectangleBorder(
                    borderRadius: BorderRadius.circular(18),
                  ),
                ),
              ),
            ),
          ],
        ),
      ),
    );
  }
}
