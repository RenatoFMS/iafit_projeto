import 'package:flutter/material.dart';

import 'article_detail_screen.dart';

class ContentScreen extends StatelessWidget {
  const ContentScreen({super.key});

  final List<Map<String, String>> articles = const [
    {
      'title': 'A importância do aquecimento',
      'category': 'Treinamento',
      'icon': '🔥',
      'description': 'Entenda por que preparar o corpo antes do exercício pode melhorar a qualidade do treino.',
    },
    {
      'title': 'Como melhorar a recuperação',
      'category': 'Recuperação',
      'icon': '😴',
      'description': 'Conheça hábitos que podem contribuir para uma recuperação adequada depois dos treinos.',
    },
    {
      'title': 'Hidratação durante o treino',
      'category': 'Saúde',
      'icon': '💧',
      'description': 'Entenda a importância da hidratação durante a prática de atividades físicas.',
    },
    {
      'title': 'A importância da técnica',
      'category': 'Treinamento',
      'icon': '🎯',
      'description': 'Aprenda por que executar corretamente um exercício é mais importante do que simplesmente aumentar a carga.',
    },
    {
      'title': 'Descanso e evolução',
      'category': 'Recuperação',
      'icon': '🛌',
      'description':
          'Veja como o descanso faz parte do processo de treinamento.',
    },
    {
      'title': 'Alongamento e mobilidade',
      'category': 'Mobilidade',
      'icon': '🤸',
      'description': 'Conheça conceitos básicos relacionados à mobilidade e preparação corporal.',
    },
  ];

  @override
  Widget build(BuildContext context) {
    return Scaffold(
      appBar: AppBar(
        title: const Text(
          'Conteúdos',
          style: TextStyle(fontWeight: FontWeight.bold),
        ),
      ),
      body: ListView.builder(
        padding: const EdgeInsets.all(20),
        itemCount: articles.length,
        itemBuilder: (context, index) {
          final article = articles[index];

          return GestureDetector(
            onTap: () {
              Navigator.push(
                context,
                MaterialPageRoute(
                  builder: (_) => ArticleDetailScreen(
                    title: article['title']!,
                    category: article['category']!,
                    description: article['description']!,
                    icon: article['icon']!,
                  ),
                ),
              );
            },
            child: Container(
              margin: const EdgeInsets.only(bottom: 16),
              padding: const EdgeInsets.all(18),
              decoration: BoxDecoration(
                color: Theme.of(context).cardColor,
                borderRadius: BorderRadius.circular(24),
                border: Border.all(
                  color: Theme.of(context).colorScheme.outline,
                ),
              ),
              child: Row(
                children: [
                  Container(
                    width: 58,
                    height: 58,
                    decoration: BoxDecoration(
                      color: const Color(0xFF172D50),
                      borderRadius: BorderRadius.circular(16),
                    ),
                    child: Center(
                      child: Text(
                        article['icon']!,
                        style: const TextStyle(fontSize: 28),
                      ),
                    ),
                  ),
                  const SizedBox(width: 15),
                  Expanded(
                    child: Column(
                      crossAxisAlignment: CrossAxisAlignment.start,
                      children: [
                        Text(
                          article['category']!,
                          style: const TextStyle(
                            color: Color(0xFF2563EB),
                            fontSize: 12,
                            fontWeight: FontWeight.bold,
                          ),
                        ),
                        const SizedBox(height: 5),
                        Text(
                          article['title']!,
                          style: const TextStyle(
                            fontWeight: FontWeight.bold,
                            fontSize: 16,
                          ),
                        ),
                        const SizedBox(height: 5),
                        Text(
                          article['description']!,
                          maxLines: 2,
                          overflow: TextOverflow.ellipsis,
                          style: const TextStyle(
                            color: Colors.grey,
                            fontSize: 13,
                          ),
                        ),
                      ],
                    ),
                  ),
                  const Icon(
                    Icons.arrow_forward_ios,
                    size: 16,
                    color: Colors.grey,
                  ),
                ],
              ),
            ),
          );
        },
      ),
    );
  }
}
