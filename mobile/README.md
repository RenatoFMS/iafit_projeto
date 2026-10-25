# Fitness Pro — aplicativo mobile

Aplicativo Flutter de treinos, exercícios e acompanhamento de progresso, com banco local SQLite, temas claro/escuro e identidade azul. Inclui vídeos demonstrativos e análise experimental de amplitude pela câmera no Android/iPhone.

**Dart · Flutter · SQLite · Google ML Kit**

Projeto acadêmico de TCC desenvolvido por João Lucas, Raul Dias e Renato Silva. João Lucas atua principalmente no desenvolvimento do website, do aplicativo e da integração de visão computacional; Raul contribui com design e concepção, e Renato com pesquisa e contribuições para a IA.

## Funcionalidades

- Biblioteca de exercícios e vídeos demonstrativos.
- Organização de treinos e sessões com cronômetro.
- Perfil, histórico de treinos e acompanhamento de peso em SQLite.
- Temas claro e escuro.
- Detecção de pose e regras experimentais de amplitude e contagem em exercícios compatíveis.

## Capturas reais

As imagens foram publicadas no repositório do site institucional a partir do aplicativo em ambiente de testes. Os dados visíveis são ilustrativos.

<p>
<img src="https://raw.githubusercontent.com/jluuck4real/fitness-pro-website/main/public/institutional/screens/home.webp" alt="Tela inicial do Fitness Pro" width="240">
<img src="https://raw.githubusercontent.com/jluuck4real/fitness-pro-website/main/public/institutional/screens/exercises.webp" alt="Biblioteca de exercícios" width="240">
<img src="https://raw.githubusercontent.com/jluuck4real/fitness-pro-website/main/public/institutional/screens/progress.webp" alt="Histórico e progresso" width="240">
</p>

## Preparação

O projeto foi validado com Flutter 3.47.5 / Dart 3.13.4. O Android requer API 24 (Android 7) ou superior.

```sh
git clone https://github.com/jluuck4real/fitness-app.git
cd fitness-app
flutter pub get
```

## Executar no navegador

```sh
flutter run -d chrome
```

O aplicativo pode ser executado no Chrome/Edge; a análise pela câmera é exclusiva da versão móvel. Se o Windows pedir suporte a links simbólicos, ative o Modo de Desenvolvedor do Windows.

## Executar no Android

Conecte um celular com depuração USB habilitada, autorize o computador e execute:

```sh
flutter devices
flutter run -d ID_DO_APARELHO
```

Para gerar o APK universal, execute `flutter build apk --release`. O arquivo será criado em `build/app/outputs/flutter-apk/app-release.apk`. A configuração atual usa assinatura de testes. Builds, APKs, capturas e caches locais não são versionados.

## Estrutura

```text
lib/models/      Catálogo, perfil e históricos
lib/screens/     Telas de exercícios, treinos, progresso e câmera
lib/services/    SQLite, vídeos e análise de movimentos
lib/theme/       Identidade visual
lib/widgets/     Componentes reutilizáveis
test/            Testes Dart e Flutter
docs/            Referências, limites e registros de validação
```

## Vídeos e câmera

- Biblioteca, videoteca e sessão usam o mesmo catálogo de demonstrações em `lib/models/exercise_catalog.dart`.
- YouTube é reproduzido pelo player incorporado oficial; arquivos de vídeo HTTPS usam `video_player`.
- A permissão de internet está no manifesto Android principal, inclusive para produção.
- Na sessão, **VER DEMONSTRAÇÃO** pausa o cronômetro enquanto o usuário assiste ao vídeo; **VER MINHA EXECUÇÃO** abre a câmera.
- A biblioteca também oferece **ASSISTIR DEMONSTRAÇÃO** e **VER MINHA EXECUÇÃO** na página de cada exercício. O player mantém **Abrir no YouTube** quando a incorporação não está disponível.
- Agachamento, roscas, desenvolvimento e elevação lateral têm regras experimentais portadas do IAFit. A regra abdominal se aplica somente a abdominais dinâmicos identificados, não à prancha. Os demais exercícios informam que ainda não têm regra de avaliação. A análise pode ser iniciada, pausada, retomada e finalizada com resumo. O vídeo da câmera não é gravado.
- A análise usa ML Kit localmente; os limiares, cálculos e fases foram adaptados dos códigos Python enviados. A comparação com o ZIP, correções, arquivos e limites de validação estão em [docs/IAFIT_ANDROID.md](docs/IAFIT_ANDROID.md).
- A correção dos erros enviados nas capturas (conversão da imagem no APK otimizado e código 2 do player) está documentada em [docs/ANDROID_RUNTIME_FIX_1.0.3.md](docs/ANDROID_RUNTIME_FIX_1.0.3.md).

## Verificações

```sh
flutter analyze
flutter test --concurrency=1
flutter build apk --release
flutter build web --release
```

O resumo das verificações da versão 1.0.3 está em [docs/validation/1.0.3.json](docs/validation/1.0.3.json). Os relatórios técnicos estão na pasta [docs](docs). As referências a `artifacts/` nesses relatórios identificam arquivos de diagnóstico locais, que não fazem parte do repositório. O teste nativo usa uma cena de câmera emulada e não comprova a precisão de contagens com uma pessoa real; essa validação física continua pendente.

A fonte Manrope está incorporada localmente sob licença SIL Open Font License; consulte `assets/fonts/OFL.txt`.

## Disponibilidade

O código contém suporte a múltiplas plataformas. Não há publicação em lojas ou build iOS validado confirmado na documentação. A avaliação corporal permanece experimental e requer validação com pessoas reais; não é uma avaliação clínica nem um sistema de garantia de técnica.
