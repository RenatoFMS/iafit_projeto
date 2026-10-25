# Correções Android 1.0.3 — erros das capturas

Esta revisão mantém as regras IAFit, a identidade azul e os IDs existentes. A correção do player é compartilhada por todos os exercícios, não apenas pelo supino mostrado na captura.

## Falha da análise corporal

A captura informa `InputImageConverterError` com `NullPointerException` e o identificador de mapa R8 `4a14aaba139595811c9a825482de3fc78c1427dfe6dea942328cd8b458d47e86`. Esse identificador corresponde ao APK 1.0.2 entregue.

O rastreamento foi desobfuscado com o mapa daquela compilação:

- `ln2` é `com.google.android.gms.internal.mlkit_vision_common.zzmj`.
- O construtor contém uma chamada a `SharedPrefManager.getClass()`; a dependência `SharedPrefManager` chegou nula.
- `usage.txt` da compilação anterior apontava a remoção dos construtores públicos de `CommonComponentRegistrar` e `VisionCommonRegistrar`. O mapa anterior preservado também não contém esses construtores.
- Esses registradores são descobertos pela infraestrutura Firebase/ML Kit a partir dos metadados do manifesto e instanciados por reflexão. O modo completo do R8 preservou os nomes das classes, mas removeu os construtores. A descoberta dos componentes falha, embora a câmera e os bytes NV21 existam.

Foi acrescentada uma regra de preservação **somente dos construtores públicos** das implementações de `ComponentRegistrar`. A otimização do APK continua habilitada; a regra anterior para o construtor Room/WorkManager também foi mantida.

Evidências: `artifacts/android-runtime-fix/mapping-1.0.2.txt`, `registrars-before.json`, `registrars-after.json` e `zzmj-bytecode.txt`. O mapa anterior mostra os dois construtores ausentes; o mapa posterior os mostra preservados. O teste Android release também conseguiu passar um quadro NV21 real da câmera emulada ao detector nativo sem a exceção. A cena emulada não contém uma pessoa: o resultado de zero poses não é apresentado como validação de contagens humanas.

## Código 2 do YouTube

O código 2 significa **parâmetro inválido**, conforme a [API oficial do YouTube](https://developers.google.com/youtube/iframe_api_reference#onError). Não significa que o proprietário proibiu a incorporação, nem prova que o ID do vídeo esteja incorreto. Os oito IDs existentes já haviam sido verificados no navegador e foram mantidos.

Na biblioteca 6.0.2 em uso foram identificadas duas fragilidades na parametrização:

1. O template inicializa um player sem `videoId`, produzindo uma URL `/embed/` inicialmente vazia e dependendo de uma segunda chamada, depois de `onReady`, para selecionar o exercício.
2. Os métodos de fila enviam `startSeconds: null` e `endSeconds: null` quando não há recorte. O aplicativo não precisa enviar esses campos opcionais.

`ExerciseYoutubeController` mantém a biblioteca e seus controles, mas adapta esses pontos:

- O ID validado do exercício já vai no construtor JavaScript do player.
- A seleção inicial não depende mais da chamada posterior de fila. O carregamento termina ao receber a confirmação de que o player está pronto.
- Tempos opcionais ausentes são omitidos; zero continua sendo um valor válido de início. Tempos negativos, não finitos e intervalos inválidos são rejeitados antes de chegar ao player.
- A confirmação `Ready` envia um objeto vazio, suficiente para o protocolo do SDK, em vez de serializar o objeto de evento do player.
- O player não inicia reprodução automática ao abrir a página. A reprodução começa pelo controle do usuário.
- Continua sendo usada a identidade real do aplicativo no WebView, sem falsificar domínios externos ou contornar restrições.
- A identidade do widget acompanha a instância do controlador para evitar reutilizar um controlador descartado quando a fonte muda.

O adaptador usa o template incluído na dependência fixada em 6.0.2; há um teste carregando o template real para todos os IDs. Uma atualização futura incompatível desse template deve ser tratada explicitamente. Não foi editado o cache de pacotes nem o SDK Flutter.

**Limite de causalidade:** a captura do telefone comprova o código 2. O WebView 145 do emulador não reproduziu esse código de forma consistente com a versão anterior; houve buffering. Logo, não se afirma ter reproduzido no emulador exatamente a mesma rejeição da versão WebView do telefone. A parametrização foi corrigida e a validação Android posterior é registrada separadamente dos testes do aparelho físico.

## Mensagens e diagnóstico

A tela da câmera agora mostra uma mensagem curta com o código da falha. A exceção completa e seu rastreamento continuam acessíveis em **Detalhes técnicos**, sem ocupar toda a tela ou esconder os controles. Isso complementa a correção nativa; não substitui a falha por uma contagem simulada.

## Arquivos alterados

- `android/app/proguard-rules.pro`: construtores dos registradores carregados por reflexão.
- `lib/services/exercise_youtube_controller.dart`: inicialização e argumentos do player compartilhado.
- `lib/widgets/exercise_video_player.dart`: controlador adaptado, confirmação de carregamento e identidade do widget.
- `lib/services/video_service.dart`: descrição correta do erro 2.
- `lib/services/pose_tracking_service.dart`: mensagem curta e preservação dos detalhes técnicos.
- `lib/screens/workouts/movement_camera_screen.dart`: acesso aos detalhes da falha.
- `test/youtube_android_contract_test.dart`: contrato do template e argumentos opcionais para os oito vídeos.
- `test/pose_tracking_test.dart`: diagnóstico preservado sem despejar a exceção na mensagem principal.
- `test_support/android_runtime_probe.dart`: verificação manual dos plugins nativos em APK release. Esse ponto de entrada não é usado no APK do aplicativo, gerado a partir de `lib/main.dart`.
- `pubspec.yaml`, `pubspec.lock`, `README.md` e relatórios de validação: versão 1.0.3+10004 e instruções atualizadas.

## Validação

Os registros desta revisão ficam em `artifacts/android-runtime-fix/`. `flutter pub get` passou; a suíte completa aprovou **43 testes**; mais quatro verificações direcionadas do player passaram após os últimos ajustes; `flutter analyze --no-pub` terminou sem problemas. As compilações Android release universal e web release passaram. `native-probe-after.apk` é exclusivamente um artefato de teste; não é o APK entregue ao usuário.

`native-results.json` registra o teste em Android API 37, WebView 145.0.7632.218 e páginas de memória de 16 KB. Os **oito vídeos** chegaram ao estado `PLAYING`, todos com ID correspondente, erro zero e tempo avançando. O teste usa saída de áudio silenciada no emulador headless; não é teste de áudio em hardware. O detector recebeu um quadro real da câmera emulada, NV21 320×240, e retornou sem `InputImageConverterError`. Como a cena emulada não contém uma pessoa, retornou zero poses. Isso confirma a correção da cadeia nativa de conversão/inferência, não a precisão do acompanhamento de uma pessoa.

O teste foi repetido após encerrar as compilações concorrentes, com o emulador reiniciado e 2 GB de RAM: os oito vídeos e a conversão/inferência passaram novamente (`native-stable-results.json`). A regressão no Chrome também confirmou os oito vídeos, reprodução, pausa e ausência de exceções (`web-smoke-result.json`). Durante o boot da imagem emulada houve alertas de ANR de componentes do sistema: `com.android.systemui/.keyguard.KeyguardService` às 23:39:42 e serviços Google às 23:39:59, antes da execução do aplicativo de teste (câmera processada às 23:41:04). Os eventos estão em `system-anr-events.txt`; não foram atribuídos ao aplicativo. Portanto, esse ambiente confirma o funcionamento dos plugins/player, mas não deve ser usado como comprovação de desempenho ou estabilidade geral da interface em hardware.

O APK de entrega é `artifacts/releases/Fitness-Pro-1.0.3-universal.apk`, versão 1.0.3+10004, Android 7/API 24 ou superior, ARM32/ARM64/x86_64. A inspeção da assinatura, permissões e alinhamento está em `artifacts/apk-verification-1.0.3.json`. Mantém o certificado anterior e um código de versão superior, para atualização sem desinstalar.

O teste nativo é executado explicitamente em `emulator-5556`. Não houve conexão, instalação, captura ou alteração no M13. O processamento de movimentos de uma pessoa, a sobreposição sobre um corpo real e o funcionamento em versões WebView diferentes continuam exigindo validação física. As limitações das estimativas 2D e dos exercícios sem regra de avaliação permanecem documentadas em `IAFIT_ANDROID.md`.
