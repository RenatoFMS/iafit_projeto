import 'package:flutter/material.dart';

import 'home/home_screen.dart';
import 'workouts/workouts_screen.dart';
import 'profile/profile_screen.dart';
import 'progress/progress_screen.dart';
import '../widgets/bottom_navigation.dart';

class MainNavigation extends StatefulWidget {
  const MainNavigation({super.key});
  @override
  State<MainNavigation> createState() => _MainNavigationState();
}

class _MainNavigationState extends State<MainNavigation>
    with SingleTickerProviderStateMixin {
  int _currentIndex = 0;
  final List<Widget?> _pages = [const HomeScreen(), null, null, null];
  late final AnimationController _transition = AnimationController(
    vsync: this,
    duration: const Duration(milliseconds: 240),
    value: 1,
  );

  void _changePage(int index) {
    if (index == _currentIndex) return;
    setState(() {
      _currentIndex = index;
      _pages[index] = switch (index) {
        0 => HomeScreen(key: UniqueKey()),
        1 => const WorkoutsScreen(),
        2 => ProgressScreen(key: UniqueKey()),
        _ => ProfileScreen(key: UniqueKey()),
      };
    });
    if (!MediaQuery.disableAnimationsOf(context)) _transition.forward(from: 0);
  }

  @override
  void dispose() {
    _transition.dispose();
    super.dispose();
  }

  @override
  Widget build(BuildContext context) => Scaffold(
    body: FadeTransition(
      opacity: _transition,
      child: IndexedStack(
        index: _currentIndex,
        children: List.generate(
          4,
          (index) => TickerMode(
            enabled: _currentIndex == index,
            child: _pages[index] ?? const SizedBox.shrink(),
          ),
        ),
      ),
    ),
    bottomNavigationBar: BottomNavigation(
      currentIndex: _currentIndex,
      onTap: _changePage,
    ),
  );
}
