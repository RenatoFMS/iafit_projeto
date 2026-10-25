import 'package:flutter/material.dart';

import '../../models/exercise_catalog.dart';
import '../../widgets/exercise_thumbnail.dart';
import '../../widgets/premium_components.dart';
import '../../theme/app_theme.dart';
import 'exercise_detail_screen.dart';

class ExercisesScreen extends StatefulWidget {
  const ExercisesScreen({super.key});
  @override
  State<ExercisesScreen> createState() => _ExercisesScreenState();
}

class _ExercisesScreenState extends State<ExercisesScreen> {
  final _search = TextEditingController();
  String _category = 'Todos';
  @override
  void dispose() {
    _search.dispose();
    super.dispose();
  }

  @override
  Widget build(BuildContext context) {
    final categories = [
      'Todos',
      ...ExerciseCatalog.exercises.map((e) => e.category).toSet(),
    ];
    final query = _search.text.trim().toLowerCase();
    final exercises = ExerciseCatalog.exercises
        .where(
          (e) =>
              (_category == 'Todos' || e.category == _category) &&
              ('${e.name} ${e.category}').toLowerCase().contains(query),
        )
        .toList();
    return Scaffold(
      appBar: AppBar(title: const Text('Biblioteca de exercícios')),
      body: CustomScrollView(
        slivers: [
          SliverPadding(
            padding: const EdgeInsets.fromLTRB(20, 8, 20, 20),
            sliver: SliverToBoxAdapter(
              child: Entrance(
                child: Column(
                  crossAxisAlignment: CrossAxisAlignment.start,
                  children: [
                    const Text(
                      'DOMINE O MOVIMENTO',
                      style: TextStyle(
                        color: AppColors.sky,
                        fontSize: 10,
                        letterSpacing: 2,
                        fontWeight: FontWeight.w700,
                      ),
                    ),
                    const SizedBox(height: 8),
                    Text(
                      'Técnica primeiro.\nEvolução sempre.',
                      style: Theme.of(context).textTheme.headlineLarge,
                    ),
                    const SizedBox(height: 20),
                    TextField(
                      controller: _search,
                      onChanged: (_) => setState(() {}),
                      decoration: InputDecoration(
                        hintText: 'Buscar exercício ou músculo',
                        prefixIcon: const Icon(Icons.search_rounded),
                        suffixIcon: _search.text.isEmpty
                            ? null
                            : IconButton(
                                tooltip: 'Limpar busca',
                                icon: const Icon(Icons.close),
                                onPressed: () {
                                  _search.clear();
                                  setState(() {});
                                },
                              ),
                      ),
                    ),
                  ],
                ),
              ),
            ),
          ),
          SliverToBoxAdapter(
            child: SizedBox(
              height: 52,
              child: ListView.separated(
                padding: const EdgeInsets.symmetric(horizontal: 20),
                scrollDirection: Axis.horizontal,
                itemCount: categories.length,
                separatorBuilder: (_, _) => const SizedBox(width: 8),
                itemBuilder: (context, i) => ChoiceChip(
                  label: Text(categories[i]),
                  selected: _category == categories[i],
                  showCheckmark: false,
                  labelStyle: TextStyle(
                    color: _category == categories[i]
                        ? Colors.white
                        : Theme.of(context).colorScheme.onSurface,
                  ),
                  onSelected: (_) => setState(() => _category = categories[i]),
                ),
              ),
            ),
          ),
          SliverPadding(
            padding: const EdgeInsets.fromLTRB(20, 16, 20, 12),
            sliver: SliverToBoxAdapter(
              child: Text(
                '${exercises.length} movimentos · demonstrações em vídeo',
              ),
            ),
          ),
          if (exercises.isEmpty)
            const SliverFillRemaining(
              hasScrollBody: false,
              child: Center(
                child: Text('Nenhum exercício encontrado. Tente outra busca.'),
              ),
            )
          else
            SliverPadding(
              padding: const EdgeInsets.fromLTRB(20, 0, 20, 28),
              sliver: SliverLayoutBuilder(
                builder: (context, constraints) {
                  final columns = constraints.crossAxisExtent >= 700
                      ? 3
                      : constraints.crossAxisExtent >= 370
                      ? 2
                      : 1;
                  return SliverGrid.builder(
                    itemCount: exercises.length,
                    gridDelegate: SliverGridDelegateWithFixedCrossAxisCount(
                      crossAxisCount: columns,
                      mainAxisSpacing: 14,
                      crossAxisSpacing: 14,
                      mainAxisExtent:
                          252 +
                          (MediaQuery.textScalerOf(context).scale(14) - 14) * 4,
                    ),
                    itemBuilder: (context, i) {
                      final exercise = exercises[i];
                      return Material(
                        color: Theme.of(context).cardColor,
                        clipBehavior: Clip.antiAlias,
                        borderRadius: BorderRadius.circular(22),
                        child: InkWell(
                          onTap: () => Navigator.push(
                            context,
                            MaterialPageRoute(
                              builder: (_) => ExerciseDetailScreen(
                                name: exercise.name,
                                category: exercise.category,
                                description: exercise.description,
                                videoUrl: exercise.videoUrl,
                              ),
                            ),
                          ),
                          child: Column(
                            crossAxisAlignment: CrossAxisAlignment.start,
                            children: [
                              ExerciseThumbnail(
                                videoId: exercise.videoId,
                                height: 146,
                              ),
                              Padding(
                                padding: const EdgeInsets.all(14),
                                child: Column(
                                  crossAxisAlignment: CrossAxisAlignment.start,
                                  children: [
                                    Text(
                                      exercise.category.toUpperCase(),
                                      style: TextStyle(
                                        color: Theme.of(context)
                                            .colorScheme
                                            .primary,
                                        fontSize: 10,
                                        letterSpacing: 1,
                                        fontWeight: FontWeight.w700,
                                      ),
                                    ),
                                    const SizedBox(height: 5),
                                    Text(
                                      exercise.name,
                                      maxLines: 2,
                                      overflow: TextOverflow.ellipsis,
                                      style: Theme.of(context)
                                          .textTheme
                                          .titleMedium,
                                    ),
                                    const SizedBox(height: 4),
                                    const Text(
                                      'Ver técnica e vídeo',
                                      style: TextStyle(fontSize: 11),
                                    ),
                                  ],
                                ),
                              ),
                            ],
                          ),
                        ),
                      );
                    },
                  );
                },
              ),
            ),
        ],
      ),
    );
  }
}
