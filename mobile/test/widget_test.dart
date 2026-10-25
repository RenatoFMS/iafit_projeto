import 'package:flutter_test/flutter_test.dart';
import 'package:flutter/widgets.dart';

import 'package:fitness_app/main.dart';

void main() {
  testWidgets('Fitness Pro inicia corretamente', (WidgetTester tester) async {
    await tester.pumpWidget(const FitnessApp());

    expect(find.text('Fitness Pro'), findsOneWidget);
    await tester.pumpWidget(const SizedBox.shrink());
    await tester.pump(const Duration(milliseconds: 1200));
  });
}
