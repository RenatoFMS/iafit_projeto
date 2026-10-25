import 'package:flutter/material.dart';

class ArticleDetailScreen extends StatelessWidget {
  final String title;
  final String category;
  final String description;
  final String icon;

  const ArticleDetailScreen({
    super.key,
    required this.title,
    required this.category,
    required this.description,
    required this.icon,
  });

  @override
  Widget build(BuildContext context) {
    return Scaffold(
      appBar: AppBar(title: const Text('Conteúdo')),
      body: SingleChildScrollView(
        padding: const EdgeInsets.all(20),
        child: Column(
          crossAxisAlignment: CrossAxisAlignment.start,
          children: [
            Container(
              width: double.infinity,
              height: 180,
              decoration: BoxDecoration(
                color: const Color(0xFF172D50),
                borderRadius: BorderRadius.circular(25),
              ),
              child: Center(
                child: Text(icon, style: const TextStyle(fontSize: 70)),
              ),
            ),

            const SizedBox(height: 25),

            Text(
              category.toUpperCase(),
              style: const TextStyle(
                color: Color(0xFF2563EB),
                fontWeight: FontWeight.bold,
                letterSpacing: 1,
              ),
            ),

            const SizedBox(height: 8),

            Text(
              title,
              style: const TextStyle(fontSize: 27, fontWeight: FontWeight.bold),
            ),

            const SizedBox(height: 20),

            Text(
              description,
              style: const TextStyle(fontSize: 16, height: 1.6),
            ),

            const SizedBox(height: 30),

            const Text(
              'Principais informações',
              style: TextStyle(fontSize: 20, fontWeight: FontWeight.bold),
            ),

            const SizedBox(height: 15),

            _section(
              '1. Prepare o corpo',
              'Antes de iniciar atividades mais intensas, uma preparação adequada pode ajudar a deixar o corpo pronto para o esforço.',
            ),

            _section(
              '2. Priorize a execução',
              'A técnica correta deve ser uma prioridade durante os exercícios. Aumentar a carga não deve comprometer a execução.',
            ),

            _section(
              '3. Respeite seus limites',
              'A evolução no treinamento acontece de maneira progressiva. O corpo precisa de tempo para se adaptar.',
            ),

            _section(
              '4. Tenha consistência',
              'Resultados dependem de uma rotina consistente de treinamento, alimentação adequada e recuperação.',
            ),

            const SizedBox(height: 25),

            Container(
              padding: const EdgeInsets.all(16),
              decoration: BoxDecoration(
                color: Colors.orange.withValues(alpha: 0.1),
                borderRadius: BorderRadius.circular(15),
              ),
              child: const Row(
                crossAxisAlignment: CrossAxisAlignment.start,
                children: [
                  Icon(Icons.info_outline, color: Colors.orange),
                  SizedBox(width: 10),
                  Expanded(
                    child: Text(
                      'Este conteúdo possui finalidade educativa e não substitui orientação profissional.',
                      style: TextStyle(fontSize: 13, height: 1.4),
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

  Widget _section(String title, String text) {
    return Padding(
      padding: const EdgeInsets.only(bottom: 20),
      child: Column(
        crossAxisAlignment: CrossAxisAlignment.start,
        children: [
          Text(
            title,
            style: const TextStyle(fontSize: 16, fontWeight: FontWeight.bold),
          ),
          const SizedBox(height: 7),
          Text(text, style: const TextStyle(fontSize: 14, height: 1.5)),
        ],
      ),
    );
  }
}
