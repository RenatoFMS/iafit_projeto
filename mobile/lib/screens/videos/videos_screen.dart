import 'package:flutter/material.dart';

import '../../models/exercise_catalog.dart';
import '../../widgets/exercise_thumbnail.dart';
import '../../widgets/premium_components.dart';
import 'video_detail_screen.dart';

class VideosScreen extends StatefulWidget {
  const VideosScreen({super.key});
  @override
  State<VideosScreen> createState() => _VideosScreenState();
}

class _VideosScreenState extends State<VideosScreen> {
  String _query = '';
  String _category = 'Todos';
  @override
  Widget build(BuildContext context) {
    final videos = ExerciseCatalog.exercises
        .where(
          (e) =>
              (_category == 'Todos' || e.category == _category) &&
              e.name.toLowerCase().contains(_query.toLowerCase()),
        )
        .toList();
    final categories = [
      'Todos',
      ...ExerciseCatalog.exercises.map((e) => e.category).toSet(),
    ];
    return Scaffold(
      appBar: AppBar(title: const Text('Movimento em foco')),
      body: CustomScrollView(
        slivers: [
          SliverPadding(
            padding: const EdgeInsets.all(20),
            sliver: SliverToBoxAdapter(
              child: Column(
                children: [
                  const SectionHeading(
                    'Sua videoteca',
                    eyebrow: 'APRENDA. PRATIQUE. EVOLUA.',
                  ),
                  const SizedBox(height: 18),
                  TextField(
                    onChanged: (value) => setState(() => _query = value),
                    decoration: const InputDecoration(
                      hintText: 'Buscar demonstração',
                      prefixIcon: Icon(Icons.search),
                    ),
                  ),
                  const SizedBox(height: 16),
                  SingleChildScrollView(
                    scrollDirection: Axis.horizontal,
                    child: Row(
                      children: categories
                          .map(
                            (category) => Padding(
                              padding: const EdgeInsets.only(right: 8),
                              child: ChoiceChip(
                                label: Text(category),
                                selected: category == _category,
                                showCheckmark: false,
                                labelStyle: TextStyle(
                                  color: category == _category
                                      ? Colors.white
                                      : Theme.of(context).colorScheme.onSurface,
                                ),
                                onSelected: (_) =>
                                    setState(() => _category = category),
                              ),
                            ),
                          )
                          .toList(),
                    ),
                  ),
                ],
              ),
            ),
          ),
          if (videos.isEmpty)
            const SliverFillRemaining(
              hasScrollBody: false,
              child: Center(child: Text('Nenhum vídeo encontrado.')),
            )
          else
            SliverPadding(
              padding: const EdgeInsets.fromLTRB(20, 0, 20, 24),
              sliver: SliverList.separated(
                itemCount: videos.length,
                separatorBuilder: (_, _) => const SizedBox(height: 16),
                itemBuilder: (context, i) {
                  final video = videos[i];
                  return Material(
                    color: Theme.of(context).cardColor,
                    borderRadius: BorderRadius.circular(24),
                    clipBehavior: Clip.antiAlias,
                    child: InkWell(
                      onTap: () => Navigator.push(
                        context,
                        MaterialPageRoute(
                          builder: (_) => VideoDetailScreen(
                            title: video.name,
                            category: video.category,
                            duration: '',
                            description: video.description,
                            videoId: video.videoId,
                          ),
                        ),
                      ),
                      child: Column(
                        crossAxisAlignment: CrossAxisAlignment.start,
                        children: [
                          ExerciseThumbnail(
                            videoId: video.videoId,
                            height: 190,
                          ),
                          Padding(
                            padding: const EdgeInsets.all(18),
                            child: Row(
                              children: [
                                Expanded(
                                  child: Column(
                                    crossAxisAlignment:
                                        CrossAxisAlignment.start,
                                    children: [
                                      Text(
                                        video.category,
                                        style: TextStyle(
                                          fontSize: 11,
                                          color: Theme.of(context)
                                              .colorScheme
                                              .primary,
                                        ),
                                      ),
                                      const SizedBox(height: 4),
                                      Text(
                                        video.name,
                                        style: Theme.of(context)
                                            .textTheme
                                            .titleLarge,
                                      ),
                                    ],
                                  ),
                                ),
                                const Icon(Icons.arrow_forward_rounded),
                              ],
                            ),
                          ),
                        ],
                      ),
                    ),
                  );
                },
              ),
            ),
        ],
      ),
    );
  }
}
