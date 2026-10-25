# Integração IAFit, câmera e vídeos — 1.0.2

Referência técnica: `C:\Users\pepic\Downloads\IAFit (2).zip`, SHA-256 `076F799AE768BE39DB0619D907204B81FF991DAF35FB304BF76268EF80A71F21`.

## O que havia no ZIP

Foram lidos integralmente `main.py`, `utils.py` e o arquivo de comandos. Cópias de referência estão em `docs/iafit_reference`; elas não são executadas nem empacotadas como assets do aplicativo.

- Python + OpenCV: acesso à webcam, desenho e janela do computador.
- Ultralytics YOLO11 Pose: `yolo11n-pose.pt`, aproximadamente 6 MB, produz os 17 pontos COCO. O código utiliza principalmente ombro, cotovelo, punho, quadril, joelho e tornozelo esquerdos.
- NumPy: diferença de `atan2` entre os vetores da articulação, valor absoluto e redução dos ângulos acima de 180°.
- Máquina de estados: um limiar arma a contagem; o outro registra uma repetição e muda a fase, impedindo incrementos repetidos enquanto o corpo permanece na mesma posição.
- Feedback: faixas do mesmo ângulo, sem análise adicional de alinhamento. Há cinco regras e descanso automático de 120 segundos depois de 20 contagens.

## Portabilidade e correções dos algoritmos

Os cálculos, transições e limiares foram portados para `movement_analyzer.dart`. A contagem permanece na chegada à fase alvo, como no Python; ela não representa uma verificação completa de toda a técnica.

| Movimento | Pontos utilizados | Preparação | Evento de contagem |
|---|---|---|---|
| Agachamento | Quadril–joelho–tornozelo | Joelho >160° | Joelho <90° |
| Rosca | Ombro–cotovelo–punho | Cotovelo >160° | Cotovelo <50° |
| Desenvolvimento | Quadril–ombro–cotovelo | Ombro >160° | Retorno abaixo de 80° |
| Abdominal dinâmico | Ombro–quadril–joelho | Quadril >160° | Quadril <100° |
| Elevação lateral | Quadril–ombro–cotovelo | Ombro <40° | Ombro >90° |

Mudanças deliberadas, em vez de copiar os defeitos do original:

1. A elevação lateral media o **cotovelo**. Um braço reto teria aproximadamente 180° mesmo sem ser elevado. Agora mede o ombro; os limiares de 40°/90° foram preservados.
2. O desenvolvimento chamava >160° de “braço baixo”, embora corresponda ao braço elevado em relação ao tronco. Os nomes e orientações foram corrigidos; a transição de contagem continua igual.
3. “Execução OK”, “fase ideal” e “descida muito profunda” eram conclusões gerais baseadas em um único ângulo. A interface agora descreve a medida e a fase como estimativas, sem afirmar postura correta ou diagnóstico.
4. Exigem-se três observações consecutivas nos extremos, confiança mínima de 0,75 nas articulações medidas, coordenadas finitas e vetores não degenerados. A perda de rastreamento exige nova posição inicial; contagens já registradas são preservadas.
5. Uma excursão intermediária sustentada que retorna ao início sem chegar ao alvo é sinalizada como **possível movimento incompleto**. Isso é uma regra geométrica adicional, não avaliação médica.
6. O detector pode usar o lado direito quando o esquerdo não está suficientemente visível. A troca de lado reinicia a preparação para evitar misturar fases de braços/pernas diferentes.
7. Não foram importadas a meta fixa de 20 repetições nem a substituição automática do descanso por 120 segundos. Séries, repetições e descanso continuam pertencendo ao treino existente.

O catálogo atual tem regras para agachamento livre, rosca direta, desenvolvimento e elevação lateral. A regra abdominal foi portada para abdominais **dinâmicos** explicitamente identificados. Prancha, supino, puxada e tríceps não recebem uma contagem ou avaliação inventada: exibem os pontos detectados e informam que não há regra disponível.

## Detector local e transformação da câmera

Foi mantido o detector nativo Google ML Kit já presente no projeto. Os 17 pontos relevantes do YOLO são mapeados para os nomes equivalentes dos 33 pontos do ML Kit. Os pesos PyTorch `.pt`, o loop OpenCV, a janela e o acesso `VideoCapture(0)` não executam diretamente no Flutter. Usar ML Kit evita embutir Python ou depender de uma API/computador ligado. **O modelo neural não é o YOLO do ZIP**; as regras geométricas e de contagem são as do IAFit, com as correções documentadas acima. Os detectores podem produzir estimativas diferentes da posição das articulações.

O fluxo usa quadros reais da câmera: NV21 no Android, com conversão de YUV420 de três planos quando necessário, respeitando os strides. A rotação considera sensor, orientação do aparelho e lente. A sobreposição usa dimensões da imagem orientada, escala/centralização e espelhamento somente na lente frontal. O ângulo é calculado nas coordenadas da imagem antes da transformação visual. Pontos de baixa confiança não são desenhados.

Há no máximo uma inferência pendente e intervalo mínimo de 120 ms entre quadros aceitos. Quadros excedentes são descartados; não há fila crescente. A chamada nativa tem timeout e a câmera continua utilizável quando a análise falha. Nenhum vídeo ou quadro é gravado ou enviado para um servidor por essa funcionalidade.

ML Kit Pose Detection continua sendo uma API beta. Consulte a [documentação Android](https://developers.google.com/ml-kit/vision/pose-detection/android). A transformação de espelhamento segue o princípio do [exemplo oficial de sobreposição](https://github.com/googlesamples/mlkit/blob/master/android/vision-quickstart/app/src/main/java/com/google/mlkit/vision/demo/GraphicOverlay.java).

## Causas identificadas no player e na câmera

O player anterior usava `youtube_player_flutter` 10.0.1, que já envolvia `youtube_player_iframe` 6.0.2. A integração agora utiliza diretamente a mesma biblioteca subjacente; URLs, IDs e suporte MP4/HTTPS/assets foram preservados.

Defeitos verificáveis no código anterior:

- O player móvel não recebia a identidade do aplicativo; o HTML adotava o domínio padrão do provedor como base. Agora recebe `https://` seguido do **package ID real**, obtido por `package_info_plus`, para que o WebView carregue seu HTML com a identidade correta. É o mecanismo descrito nos [requisitos oficiais do YouTube](https://developers.google.com/youtube/terms/required-minimum-functionality).
- Erros distintos eram apresentados como bloqueio do proprietário. Agora há mensagens separadas para endereço inválido, HTML5/WebView, vídeo privado/removido, incorporação restrita e identidade do cliente. Um listener nativo preserva os códigos novos que o enum do SDK transforma em `unknown`, incluindo 153. A [referência oficial](https://developers.google.com/youtube/iframe_api_reference#onError) distingue esses erros.
- A reprodução externa pelo YouTube/navegador agora fica disponível independentemente do sucesso da incorporação. Há carregamento, timeout, repetir, reproduzir/pausar, controles nativos e tela cheia. O viewport tem pelo menos 200 px de altura nas larguras móveis usuais.
- A inicialização da câmera e o início da análise eram tratados como uma única operação: uma falha no fluxo de imagens podia descartar a prévia funcional. Agora são operações independentes.
- A tela reatribuía globalmente `CameraPlatform.instance` em cada abertura. Essa alteração foi removida; o registro automático seleciona `camera_android` corretamente.
- Falhas durante descarte/parada podiam interromper a cadeia de operações e prejudicar tentativas posteriores. As operações agora são serializadas com tratamento de erros e liberação protegida.

O manifesto principal **já tinha** INTERNET, CAMERA e aceleração de hardware. Não se atribuiu o problema a uma permissão ausente. Foi acrescentada a consulta/solicitação explícita da permissão em execução, distinguindo negação, bloqueio permanente e restrição. A tela permite configurações, nova tentativa, troca de lente e informa o código do erro. A prévia inicia antes de pedir que o usuário inicie a análise. Ao pausar, encerrar, trocar de câmera ou sair, os recursos são liberados ou suspensos conforme o caso.

**Limite do diagnóstico:** não foi coletado o código nativo do erro do aparelho nesta etapa, pois o usuário solicitou não realizar mais testes no M13. Portanto, a falta de identidade é uma falha concreta corrigida e uma explicação compatível com o relato de todos os vídeos falharem no Android; não se afirma que o erro físico observado era comprovadamente 153. O motivo nativo original da câmera também não foi capturado. Os defeitos acima foram identificados por inspeção e reproduzidos com testes controlados.

## Arquivos principais

- `lib/services/video_service.dart`: identidade, URL externa e diagnóstico do YouTube.
- `lib/widgets/exercise_video_player.dart`: integração direta, controles, carregamento, erro, fallback e descarte.
- `lib/services/camera_session_service.dart`: permissão, câmera, fluxo de imagens, lentes e ciclo de vida.
- `lib/services/pose_frame_converter.dart`: NV21/YUV/BGRA e rotação.
- `lib/services/pose_tracking_service.dart`: inferência nativa local e adaptação dos pontos às regras.
- `lib/services/movement_analyzer.dart`: regras portadas do IAFit.
- `lib/widgets/pose_skeleton_painter.dart`: esqueleto e ângulo sobre a imagem.
- `lib/screens/workouts/movement_camera_screen.dart`: interface azul, reconhecimento, iniciar/pausar/retomar/finalizar e resumo.
- `lib/screens/exercises/exercise_detail_screen.dart`: demonstração e câmera como ações distintas, com o exercício selecionado.
- `pubspec.yaml` e `pubspec.lock`: dependências e versão 1.0.2+10003. O build number supera os códigos dos APKs anteriores separados por ABI, permitindo atualizar pelo universal sem desinstalar os dados. `permission_handler` 12.0.1 foi selecionado por compatibilidade com a configuração Android atual; 13.0.2 exigia o target de SDK 37 que não era resolvido pelo ambiente. Não houve alteração no SDK Flutter.
- `test/android_media_services_test.dart`, `test/iafit_rules_test.dart`, `test/pose_tracking_test.dart` e os testes de câmera/analisador existentes: regressões e portabilidade.
- `artifacts/web-smoke.mjs`: auditoria de reprodução dos oito IDs no navegador real. Registros de plugins das plataformas desktop foram atualizados automaticamente pelo Flutter; houve apenas formatação automática em `settings_screen.dart` e `weekly_activity.dart`.

## Evidências e limites de validação

Os resultados finais dos comandos estão nos arquivos `artifacts/flutter-analyze-1.0.2.txt`, `artifacts/flutter-tests-1.0.2.txt`, `artifacts/android-build-1.0.2.txt` e `artifacts/apk-verification-1.0.2.json`.

Validação executada: `flutter pub get` passou; `flutter analyze --no-pub` sem problemas; `flutter test --no-pub --concurrency=1` com **41 testes aprovados**; compilação web release aprovada; compilação Android release universal aprovada. O número de versão foi elevado depois dos testes sem alterar o código funcional.

APK entregue: `artifacts/releases/Fitness-Pro-1.0.2-universal.apk`, 102.358.447 bytes (97,6 MiB), Android **7.0/API 24 ou superior**, ARM32/ARM64/x86_64, versão 1.0.2, código 10003. Assinatura e alinhamento ZIP de 16 KB verificados; os segmentos ELF das **10 bibliotecas de 64 bits** também atendem ao alinhamento de 16 KB (`artifacts/native-elf-alignment-1.0.2.json`). Isso verifica o requisito estrutural de alinhamento, não substitui execução em hardware de 16 KB. Foi confirmado o mesmo certificado dos APKs ARM32/ARM64 1.0.1 e código de versão superior a 1002/2002, evitando a necessidade de desinstalar por downgrade. SHA-256: `76149BFD989B673041F9C6F9CDB60D62BC2F00709BA8F74E2FE7221E987EF51A`.

`artifacts/youtube-audit-1.0.2.json`: os oito IDs responderam HTTP 200 no oEmbed e os títulos correspondem aos exercícios. `artifacts/web-smoke-result.json`: Chrome real, reprodução e pausa confirmadas, mais reprodução individual dos oito IDs, todos com estado PLAYING, tempo avançando e sem erro. Os links existentes foram mantidos; não foi encontrado bloqueio individual que justificasse substituí-los nesse ambiente. Essa auditoria não garante disponibilidade em todos os países, contas ou aparelhos.

Os testes de regras usam ângulos conhecidos e uma implementação de referência das transições do Python. Os testes do adaptador usam **fixtures sintéticas explicitamente identificadas nos testes**, não o modelo real no celular. Eles verificam transporte dos bytes/landmarks, confiança, fases, contagem, perda de pessoa, pausa e erro. Não medem acurácia do ML Kit nem precisão biomecânica. Os testes de câmera usam uma plataforma de teste para validar permissão, repetição, queda de resolução, troca de lente, descarte e o fluxo da interface em 320 px.

Continuam pendentes em aparelhos físicos representativos: reprodução incorporada no WebView, abertura externa efetiva, permissões reais, prévia nas duas lentes, calibração do esqueleto em retrato/paisagem e sensores diferentes, comparação com repetições anotadas em vídeos reais, desempenho, bateria, acesso concorrente à câmera e interrupções do sistema. Não foi feito teste em M13 nesta etapa, conforme solicitado. Não se declara compatibilidade com todo aparelho Android; o APK atende ao mínimo Android e ABIs registrados no relatório de inspeção.

A pasta gerada `build` está acessível no caminho habitual por uma junção para `D:\CodexBuilds\fitness-app-20261024`, criada quando C: estava sem espaço. Isso não altera o código do aplicativo. O APK mantém a assinatura de testes configurada no projeto; publicação na Play Store precisa de assinatura de produção.
