# PROGRESSO — SafeTech Entry

Última atualização: 25/11/2026. Tudo commitado (o último commit traz a seção 2.19).

Este arquivo descreve **onde o trabalho parou**. Para entender o projeto em si (instalação, uso, arquitetura completa), leia o `README.md`. Para regras permanentes de trabalho no projeto, leia o `CLAUDE.md`.

---

## 1. Objetivo atual

O SafeTech Entry é um projeto acadêmico (desafio de segurança do trabalho): um sistema de visão computacional que verifica, pela câmera, se cada pessoa está usando os EPIs exigidos (capacete, óculos, colete, luvas) e libera ou nega o acesso, com log de auditoria e foto de evidência.

O foco das últimas rodadas foi fazer o sistema funcionar numa **câmera geral de obra** (várias pessoas pequenas, de costas, se movimentando e se cruzando), e não só numa catraca com uma pessoa de frente. O usuário testa com um **vídeo emulado** de canteiro de obras como câmera (`INDICE_CAMERA = 1`).

Estado: as funcionalidades pedidas estão implementadas e commitadas. O que falta agora é sobretudo **qualidade do modelo de EPI** (dataset pequeno e desbalanceado) e **publicar no GitHub**.

---

## 2. O que já foi feito nesta sessão

A sessão foi longa e passou por várias fases. Em ordem:

### 2.1 Primeira versão (substituída)
- App em Streamlit (`app.py`) com webcam, status, captura para dataset e auditoria em CSV. **Abandonado**: a câmera travava (ver seção 5).
- Reescrito em Tkinter, depois com detector de rosto, várias pessoas e tema escuro.
- Todo esse código antigo está em `_versao_anterior/` (fora do git).

### 2.2 Reescrita completa (commits `4fbf205` a `8dcba2e`, 05/10)
- Arquitetura em pacote `safetech/` com camadas `nucleo/`, `servicos/`, `interface/`, `web/`, `treino/`; configuração única em `safetech/config.py`.
- Três threads (câmera, analisador, interface); inferência em lote com `tf.function` (~24 ms contra ~224 ms do `predict`).
- Modelos movidos para `modelos/`. `README.md` completo criado.

### 2.3 Painel web do gerente (commit `0dfa1bf`)
- `safetech/web/servidor.py` e `safetech/web/painel.html`; `painel_web.py` na raiz (modo só histórico).
- Somente leitura (só GET; POST/PUT/DELETE → 405), login Basic Auth, proteção contra path traversal nas imagens.

### 2.4 Repositório git (05/10)
- `git init`, `.gitignore` (exclui fotos do dataset, auditoria, `_versao_anterior/`, `preferencias.json`, modelo YOLOX).
- **Não publicado no GitHub**: o `gh` (GitHub CLI) não está instalado (ver seção 4).

### 2.5 EPIs separados e fiscalização por setor (commits `e642eb9` a `a084f23`, 07/10)
- Classificador **multirrótulo** (uma saída sigmoid por EPI): `safetech/treino/treinador.py`, `safetech/nucleo/classificador.py`.
- Lista de EPIs e setores em `config.EPIS` e `config.SETORES`; regra em `safetech/nucleo/decisao.py`.
- Coleta rotulada na tela (`safetech/servicos/dataset.py`): imagens em `dataset/epis/`, rótulos em `dataset/rotulos.csv`.
- Seleção de setor salva em `preferencias.json` (`safetech/servicos/preferencias.py`).
- Modo de compatibilidade: sem `modelo_epis.keras`, usa o modelo antigo (`modelo_epi.keras`, só "com/sem EPI").
- Auditoria passou a registrar setor, EPIs exigidos, o que faltava e confiança de cada EPI.

### 2.6 Adaptação para câmera geral (commit `b6498d5`, 08/10)
Arquivos: `safetech/config.py`, `safetech/nucleo/{detector.py, detector_rosto.py, detector_corpo.py, rastreador.py, decisao.py, anotacao.py, tipos.py}`, `safetech/servicos/{analisador.py, auditoria.py, camera.py, importacao.py, preferencias.py}`, `safetech/interface/{janela_principal.py, painel_monitoramento.py, painel_auditoria.py, tema.py}`, `reconhecer.py`, `README.md`, `.gitignore`.
- **Modo corpo** (YOLOX via `cv2.dnn`) além do modo rosto; seletor "Detectar por: Rosto | Corpo" na tela, troca imediata, escolha salva.
- **Bug corrigido** no detector de rosto: `top_k=50` fazia achar só parte das pessoas (13 de 24); agora 5000.
- Modo rosto em **duas escalas** (640 e 320 px).
- Rastreador **lembra quem sumiu** por 8 s e tem **previsão de movimento**.
- Decisão pela **mediana** das últimas 5 classificações; mudança só vai para o log após **3 confirmações**.
- **Uma foto de evidência por pessoa**; outra só quando a situação muda de fato.
- Vídeo com contorno fino e **uma palavra** (OK / NEGADO / ...); o detalhe do que falta fica no log e no painel web.
- Botão **Zerar** na auditoria (arquiva em `auditoria/arquivados/<data>/`, não apaga).
- **Importação** de imagens para o dataset: botão "Enviar arquivo" e Ctrl+V.
- Câmera em 1280x720 com MJPG.

### 2.7 Modelo re-treinado pelo usuário (commits `8b34692`, `a56a179`, `3c1261d`)
- `modelos/modelo_epis.keras` + `modelos/epis.json` (`["capacete","oculos","colete","luvas"]`).
- Dataset atual: 49 linhas em `rotulos.csv` (usando: capacete 39, óculos 36, colete 33, luvas 30).

### 2.8 Excluir linha e relatório do momento (28/10)
- **Excluir linha** na auditoria (botão ou tecla Delete, com confirmação): a linha sai do log, da tabela e do painel web, mas vai para `auditoria/excluidos/log_excluidos.csv` (com a data da exclusão) e a foto para `auditoria/excluidos/imagens/`. Nada é apagado.
- **Salvar relatório** na auditoria (age sobre a linha selecionada): grava `auditoria/relatorios/<data do evento>_<pessoa>/` com `relatorio.html` (dados do evento, confiança de cada EPI, foto) e `evidencia.jpg` (cópia), mais os outros eventos do mesmo segundo em `outros/`; abre o HTML no navegador.
- Testado só com a janela oculta e câmera/detector/classificador falsos; falta conferir na tela real.

### 2.9 Câmera IP (28/10)
- A câmera aceita um número (webcam) ou um endereço `rtsp://` / `http://` (câmera IP, aberta pelo FFMPEG do OpenCV). Tempo limite de conexão/leitura e RTSP por TCP em `config.py`.
- Quando a rede cai, o estado vira `RECONECTANDO` e a câmera tenta voltar sozinha; endereço errado na primeira conexão vira `ERRO`.
- Na tela: item "+ Adicionar câmera IP..." na lista de câmeras abre `safetech/interface/dialogo_camera_ip.py` (nome, endereço, usuário, senha). Botão "Remover" aparece ao lado da lista quando a câmera em uso é IP.
- Câmeras salvas em `preferencias.json` (chave `cameras_ip`); o endereço pode conter a senha, então nunca é mostrado na tela (só o nome).
- Testado com um servidor MJPEG falso em 127.0.0.1 (conexão, queda, reconexão, endereço errado) e com a janela oculta. Falta testar com uma câmera IP real e ver o diálogo na tela.

### 2.10 Testes, README e GitHub Actions (30/10)
- Pasta `testes/` com 63 testes pytest (decisão, auditoria, relatório, preferências, câmera IP, analisador, painel web, janela). `testes/conftest.py` redireciona os dados para pasta temporária; `testes/falsos.py` tem as peças falsas.
- Os testes acharam um bug: "Zerar" duas vezes no mesmo segundo dava erro (pasta de arquivo com o mesmo nome). Corrigido em `auditoria.zerar()`, com teste.
- `requirements.txt` com versões fixas; `requirements-dev.txt` (pytest); `.github/workflows/testes.yml` roda os testes em Windows a cada push (sem TensorFlow).
- README: corrigidos os dois trechos que diziam que o repositório só trazia o modelo antigo; novas seções de câmera IP, relatório, excluir linha e testes.

### 2.11 Catraca de demonstração com ESP32 (30/10)
- Pasta `catraca_esp32/`: `catraca_esp32.ino`, `config_exemplo.h` (copiar para `config.h`, que fica fora do git) e `LEIA-ME.md` (peças, ligações, instalação, roteiro da apresentação, problemas comuns).
- O ESP32 lê `/api/ao-vivo` a cada 500 ms com o login do painel; servo (cancela), LEDs verde/amarelo/vermelho, buzzer ativo, OLED SSD1306 e relé (pulso ao abrir). Na dúvida, fecha: falha de rede, programa fechado ou status desconhecido mantêm a cancela fechada.
- `testes/test_contrato_catraca.py` garante os campos de que a catraca depende. Testes do painel passaram a usar 127.0.0.1 (no Windows, "localhost" perdia ~2 s por pedido): suíte caiu de 35 s para 16 s.
- **Não compilado**: não há Arduino IDE nem compilador neste computador. Falta compilar, gravar e montar.

### 2.12 Catraca pelo cabo USB, junto com o Wi-Fi (04/11)
- `safetech/servicos/catraca_serial.py`: thread que escreve `ST|acesso|negadas|total|faltando` na porta serial a cada 0,3 s. Acha o ESP32 sozinho (chips CP210x/CH340/Espressif/FTDI) e reconecta se o cabo sair; abre a porta com DTR/RTS desligados para não reiniciar a placa. Ajustes em `config.py` (`CATRACA_*`). A janela mostra "Catraca: COM3 conectada" no rodapé. `pyserial==3.5` entrou no `requirements.txt`.
- Firmware: aceita cabo e Wi-Fi juntos. Cabo tem prioridade; Wi-Fi só é consultado se `WIFI_ATIVO true` e o cabo não estiver mandando. `WIFI_ATIVO false` por enquanto (o Wi-Fi do dia da apresentação ainda não foi escolhido). Sem dados por 3 s ou "liberado" velho (1,5 s) fecha a cancela.
- Testado no ESP32 real (COM3): todas as situações, lixo no cabo ignorado, silêncio vai para OFFLINE, e o `CatracaSerial` real. Falta testar o conjunto com o SafeTech completo aberto (câmera + IA) e o Wi-Fi.
- Testes: 85 passam (`test_catraca_serial.py` novo; `conftest.py` desliga o envio nos testes).
- O Arduino IDE tem `arduino-cli` embutido: placa ESP32 e bibliotecas já instaladas; firmware gravado com ele.

### 2.13 Modos Catraca e Vigilância (04/11)
- Os modos "Rosto"/"Corpo" viraram **Catraca** (rosto; libera/nega; catraca física obedece) e **Vigilância** (corpo; só verifica conformidade e registra; catraca física desligada). Chaves `catraca`/`vigilancia` em `config.py`; `"rosto"`/`"corpo"` salvos antes são convertidos.
- Textos de cada modo em `config.TEXTOS_POR_MODO` e `safetech/nucleo/modos.py`. Faixa de status, palavra no vídeo, tabela de auditoria (nova coluna Modo; indicadores "Conformes/Irregulares/Conformidade"), relatório e painel web mostram o texto do modo.
- Auditoria ganhou a coluna `modo`. Log antigo é convertido (eventos viram `catraca`) e o original fica guardado como `_formato_antigo_`.
- Catraca: o programa envia `ST|vigilancia|...` pelo cabo e `"modo"` no `/api/ao-vivo`; o firmware tem a situação VIGILANCIA (fechada, LEDs apagados, tela "VIGILANCIA / Catraca desligada"). Gravado e testado no ESP32 real.
- Testes: 103 (novo `test_modos.py`). Uma vez o Tk falhou ao ler o `init.tcl` (instabilidade do Python da Store); nas rodadas seguintes passou.

### 2.14 Janela de Configurações e painel principal enxuto (04/11)
- Botão **Configurações** abre `safetech/interface/janela_configuracoes.py`: abas Câmera (lista, adicionar/remover IP), Análise (confiança e intervalo, com "Voltar aos valores padrão"), Fiscalização (setor e EPIs um por um) e Coleta de imagens. Criada uma vez, escondida; fechar só esconde.
- Painel principal ficou com vídeo, faixa de status e uma barra com Setor, Modo e botão da câmera.
- Confiança e intervalo agora ficam salvos (`preferencias.carregar_ajustes/salvar_ajustes`, gravação adiada `ESPERA_SALVAR_AJUSTES_MS`). Faixas dos controles em `config.py`. Estilo das abas no `tema.py`.
- Testes: 113. A nova tentativa de abrir o Tk nos testes cobre também a falha com `auto.tcl`.
- Falta: conferir o visual na tela real (os testes não mostram janelas).

### 2.15 Várias áreas (câmeras) em abas e EPIs de volta na tela (04/11)
- Cada **área** é uma aba à esquerda (câmera, setor, modo, EPIs exigidos e análise próprios); aba "+ Nova área" cria outra; renomear/remover/trocar câmera/"comanda a catraca" em Configurações > Área e câmera. Limite `MAXIMO_AREAS` = 6.
- EPIs exigidos voltaram para a tela principal (na aba da área); a aba Fiscalização saiu das Configurações.
- Auditoria única com coluna `area` (log anterior convertido para "Principal", original guardado). Relatório e painel web mostram a área. A catraca e o "ao vivo" do painel web seguem a área marcada.
- Novos arquivos: `interface/area_monitorada.py`, `interface/dialogo_area.py`. `ClassificadorCompartilhado` em `servicos/analisador.py`.
- Testes: 130 (novo `test_areas.py`; `conftest.py` zera as preferências a cada teste e recolhe sobras do Tk na thread principal).
- Falta: ver na tela real e testar com duas câmeras de verdade ao mesmo tempo (desempenho).

### 2.16 Revisão de profissionalismo: visual, câmeras e funções (24/11)
- **Cabeçalho novo**: ícone (escudo desenhado em `tema.desenhar_icone`, também na barra de tarefas), nome, frase, **selos** com ponto colorido (IA, painel web, catraca; `interface/componentes.py`) e relógio. O rodapé ficou só com avisos e atalhos.
- **Vídeo**: legendas sobre a imagem ("● AO VIVO" piscando, área, data/hora; resolução real, fps, análises/s, pessoas), no lugar da linha de desempenho. Faixa de status com símbolo (✔ ✖ ◔ ●) e detalhe que quebra a linha. Palavra das caixas maior (`ESCALA_FONTE_ROTULO`).
- **Visão geral** (`interface/painel_visao_geral.py`): botão ao lado de Configurações, com 2+ áreas; quadros com a situação colorida, grade que se adapta ao formato do painel, redesenho a `QUADROS_POR_SEGUNDO_VISAO_GERAL`. Clique abre a aba.
- **Auditoria**: filtro de **período** (cartões, tabela e exportação o seguem), **Exportar CSV** (`auditoria.exportar_csv`, `;` + BOM para o Excel), listras na tabela, mensagem de tabela vazia, filete colorido nos cartões. Salvar relatório e Excluir foram para o cartão "Evento selecionado".
- **Fotos de evidência carimbadas** (`anotacao.carimbar`; `CARIMBAR_EVIDENCIA`).
- **Webcam reconecta sozinha** (`RECONECTAR_WEBCAM`, `INTERVALO_RECONEXAO_WEBCAM_SEG`).
- **Bipe** do Windows em acesso negado, só no modo catraca (`ALERTA_SONORO_NEGADO`; desligado nos testes).
- **F11** tela cheia; Esc sai.
- **Painel web**: logo e relógio, seção **Áreas** (`/api/areas`, `/ao-vivo.jpg?area=N`), **Exportar CSV** (`/exportar.csv`, GET), selo "AO VIVO", filetes nos cartões, listras e símbolos na faixa. `/api/ao-vivo` (contrato do ESP32) não mudou.
- Testes: 152 (novo `test_exportacao.py`; acréscimos em `test_janela.py`, `test_painel_web.py`, `test_camera.py`).
- Conferido por captura de tela com câmera/IA falsas e o painel web no navegador com dados falsos. Falta: ver com câmera e modelo reais, e ouvir o bipe.

### 2.17 Página da câmera redesenhada e temas claro/escuro (24/11)
- **Navegação por pílulas** (`componentes.BarraAreas`) no lugar das abas: "▦ Visão geral", uma pílula por área com ponto na cor da situação (atualizado 2x/s) e "+ Nova área". O Notebook continua guardando as páginas, com as abas escondidas (`SemAbas.TNotebook`), então os testes que leem o texto das abas seguem valendo.
- **Página da área** (`painel_monitoramento.py` reescrito): cabeçalho da câmera (nome da câmera, "comanda a catraca", **Trocar câmera** que abre Configurações na área, **Capturar foto**, **▶ Iniciar / ■ Parar**); **tela de espera** com ícone, título, explicação e botão de ligar no meio; faixa de status cheia só para liberado/negado/analisando (as outras viram cartão com filete); **EPIs como chips** (✓ quando exigido).
- **Capturar foto** (`servicos/capturas.py`, `config.PASTA_CAPTURAS` = `auditoria/capturas`): frame com caixas e carimbo, fora do log.
- **Visão geral**: clique abre a área (e a pílula volta), destaque ao passar o mouse com "Abrir ›", botão **Ligar câmera** no quadro desligado.
- **Temas escuro e claro** no programa: `tema.PALETAS`, `trocar_tema` (estilos + repintura de todos os componentes tk e desenhos de Canvas), botão no cabeçalho, salvo em `preferencias.json` (`tema`), aplicado antes de montar a tela. Chaves novas `realce`, `desativado`, `texto_legenda`.
- **Painel web**: variáveis CSS do tema claro, botão "Tema claro/escuro" (localStorage, com try/catch), sem escolha segue o sistema.
- **Auditoria por área**: com uma área aberta, a auditoria (cartões, tabela, exportação) mostra só os eventos dela, com o nome no título; na Visão geral, todos. `PainelAuditoria.definir_area`, chamado por `_selecionar_area` e pela visão geral. Renomear a área passa a mostrar os eventos do nome novo (os antigos ficam com o nome antigo no log).
- Testes: 169 (novo `test_temas.py`; mais testes de barra, tela de espera, chips e captura em `test_janela.py`). Conferido por captura de tela (PrintWindow, os dois temas e a troca ao vivo) e no navegador. Falta: ver com câmera real.

### 2.18 Painel web ajustado nas Configurações (24/11)
- Aba **Configurações > Painel web**: ligar, acesso pela rede ou só neste computador, porta, exigir login, usuário, nova senha + confirmação, "Mostrar senha", **Aplicar** (reinicia o servidor na hora e mostra o resultado, ex.: porta em uso), **Abrir no navegador**, aviso de senha padrão / sem senha, lembrete do `config.h` da catraca.
- `servicos/acesso_web.py`: `AjustesPainelWeb`, hash **PBKDF2-SHA256 com sal** (`ITERACOES_HASH_SENHA`), `senha_confere`, `montar_ajustes` (porta 1024–65535, usuário sem ":", senha mínima `PAINEL_WEB_SENHA_MINIMA`, confirmação, em branco mantém a atual). Salvo em `preferencias.json` (`painel_web`), nunca a senha em texto.
- Servidor (`ServidorWeb(ajustes=...)`) confere o login pelo hash e guarda os logins já aceitos (só o resumo do cabeçalho). `painel_web.py` usa os mesmos ajustes.
- Selo do cabeçalho: amarelo com senha padrão ou sem senha; "Painel web desligado" leva às Configurações.
- Isso resolve a pendência da senha padrão pública: basta trocar pela tela antes de publicar/usar. `config.h` da catraca (Wi-Fi) precisa ser atualizado à mão se mudar usuário/senha/porta.
- Testes: 195 (novo `test_acesso_web.py`). Conferido por captura de tela da aba nos dois temas.

### 2.19 Bloco 1 da revisão: controladores, log e análise que se recupera (25/11)
- **Janela principal dividida** (1.925 → ~660 linhas): a janela monta a tela e liga os controladores `ia`, `areas`, `cameras`, `eventos`, `coleta`, `painel_web` e `catraca` (arquivos `interface/controlador_*.py`). Comportamento igual; os testes foram migrados para os nomes novos (`janela.areas.lista`, `janela.areas.selecionar(...)`, `janela.cameras...`, `janela.eventos.receber()`, `janela.painel_web.servidor`, `janela.catraca.serial`; monkeypatch de `pedir_area` em `controlador_areas`, de `CatracaSerial` em `controlador_catraca`; `sem_ia` troca `CargaIA.carregar`).
- **Log em arquivo**: `servicos/log_erros.py` (`logs/safetech.log`, rotação por tamanho, erros não tratados de threads e do programa). Ligado no `app.py` e no `painel_web.py`. Registram: análise (erros e reinícios), IA, painel web, catraca, áreas, câmeras IP, zerar/excluir/exportar. Erro de botão vai para o log e para o aviso do rodapé; o ciclo da tela registra (sem repetir) e segue.
- **Vigia da análise** em `Analisador._executar`: erro → log, faixa "REINICIANDO A ANÁLISE", espera `ESPERA_REINICIO_ANALISE_SEG`, recomeça; desiste depois de `MAXIMO_REINICIOS_ANALISE` falhas seguidas (`TEMPO_ESTAVEL_ANALISE_SEG` zera a contagem).
- **Repetições**: título da faixa só em `modos.titulo_da_situacao` (chaves novas `faixa_analisando`/`faixa_sem_pessoas` em `TEXTOS_POR_MODO`), usado pela tela e pelo painel web. Erro de digitação no `app.py` corrigido. `logs/` no `.gitignore`.
- Testes: 209 (novo `test_robustez.py`). Tela conferida por captura (igual à de antes). Ficou para depois: juntar os `registrar(...)` repetidos nos testes num ajudante em `falsos.py`.

---

## 3. O que está pela metade

Nenhuma alteração de código ficou incompleta: tudo foi commitado. Estão pela metade:

1. ~~README desatualizado~~: corrigido em 30/10.
2. **Publicação no GitHub.** Repositório só local, sem remoto. Parou esperando o usuário instalar e autenticar o GitHub CLI. Decisões já tomadas: repositório **público**, autor "João Fidelis <jfidelis999@gmail.com>", **sem** fotos do dataset.
3. **Qualidade do modelo de EPI.** Ver seção 5. Parou em: o usuário treinou com 49 imagens; nos testes do sistema, quase todas as pessoas saem como "NEGADO".
4. ~~Testes fora do repositório~~: pasta `testes/` criada em 30/10. Depois de publicar no GitHub, acrescentar ao topo do README o selo do Actions (precisa da URL do repositório).

---

## 4. Próximos passos (em ordem)

1. **Corrigir os dois trechos desatualizados do README** (item 3.1).
2. **Publicar no GitHub.** O usuário roda, no terminal do VS Code:
   ```
   winget install --id GitHub.cli -e
   gh auth login --web --git-protocol https
   ```
   Depois: `gh repo create <nome> --public --source . --push`. Antes de publicar: confirmar com o usuário se o e-mail `jfidelis999@gmail.com` é o da conta GitHub dele, e lembrar que a senha padrão do painel web (`PAINEL_WEB_SENHA = "safetech"`) ficará pública.
3. **Melhorar o dataset e re-treinar** (é o que mais melhora o resultado):
   - coletar muito mais imagens **sem** cada EPI (hoje são só 10 a 19 por EPI);
   - variar combinações (só capacete, só luvas, tudo, nada);
   - coletar **no modo que será usado** (corpo, para a câmera geral), porque o recorte de cada modo é diferente;
   - depois: `python treinar.py` e conferir a taxa de acerto por EPI que ele imprime no fim.
4. **Trazer testes para o repositório** (pasta `testes/`). Os que existiam e o que verificavam:
   - regras de decisão (`decisao.avaliar_pessoa` com vários conjuntos de exigidos, limiar e mediana);
   - modo de compatibilidade (classificador antigo devolve matriz de 1 coluna);
   - coleta rotulada e treino com rótulos sintéticos em pasta temporária;
   - analisador com câmera/detector/classificador falsos: troca de setor muda a decisão; uma pessoa intermitente com classificação oscilando gera só 1 foto, e outra só quando a exigência muda;
   - simulação de rastreio (9 pessoas, detecção intermitente) contando identidades criadas;
   - detector de rosto em duas escalas (rosto grande + 24 rostos pequenos);
   - botão Zerar e seletor de modo com a janela **oculta** (`raiz.withdraw()`).
   Todos devem gravar em pastas temporárias, nunca em `auditoria/`, `dataset/` ou `preferencias.json` reais.
5. **Conferir visualmente** o seletor Rosto/Corpo e o botão Zerar na tela real (foram testados só com a janela oculta).
6. Opcionais, se o usuário pedir: limpar `dataset/com_epi`, `dataset/sem_epi` (obsoletos) e `_versao_anterior/`; detector de objetos por EPI; confirmação de voz da Ordem de Serviço (etapa futura do desafio, **não implementar sem pedido**).

---

## 5. Problemas conhecidos, bugs em aberto e o que não funcionou

### Em aberto
- **Modelo de EPI pouco confiável.** Dataset de 49 imagens e desbalanceado (poucas "sem usar"). Em testes, pessoas com capacete e colete saíram como "NEGADO", e num teste o capacete deu 100% para quem não usava. Não se sabe em qual modo (rosto ou corpo) as imagens atuais foram coletadas.
- **Recortes diferentes por modo.** Modo rosto entrega cabeça+tronco ao classificador; modo corpo entrega o corpo inteiro. Um modelo treinado num modo funciona mal no outro.
- **Troca de identidade em cruzamentos.** "Mesma pessoa" é decidida por posição e movimento, não por aparência. Na simulação mais difícil, ~12 de ~18 identidades acabaram misturando pessoas. Quem some por mais de 8 s volta como pessoa nova.
- **Modo corpo mais lento** (~8 análises/s contra ~12 do rosto) e não acha quem está quase todo encoberto.
- **`INDICE_CAMERA = 1`** está commitado; é específico do computador do usuário (vídeo emulado). Em máquina com uma webcam só, precisa ser `0`.
- **Senha padrão do painel web** (`safetech`) está no código, que será público. Conexão é HTTP sem criptografia (uso só em rede local).
- **Log antigo:** há arquivos `auditoria/log_auditoria_formato_antigo_*.csv` de versões anteriores (inofensivos).

### Tentativas que não funcionaram (não repetir)
- **Streamlit**: a câmera travava (o script inteiro reexecuta a cada frame). Trocado por Tkinter.
- **Haar Cascade e HOG do OpenCV**: não existem no OpenCV 5.0 instalado (`cv2.CascadeClassifier` e `cv2.HOGDescriptor` ausentes). Só `cv2.FaceDetectorYN` (YuNet) funciona.
- **`top_k=50` no YuNet**: perdia pessoas em multidões. Usar 5000.
- **Detecção de rosto numa escala só**: 640 px perde rosto grande e próximo; 320 px perde rostos pequenos. Por isso duas escalas.
- **Média das classificações**: uma única classificação errada virava a decisão por vários ciclos. Trocada pela mediana.
- **Rastreador que esquecia após 1 s**: gerava dezenas de "pessoas" e fotos repetidas (21 IDs em 10 s para ~9 pessoas).
- **Instalação do TensorFlow**: falhou por caminho longo do Windows e depois por falta do Visual C++ Redistributable (soluções estão na seção "Solução de problemas" do README).
- **Abrir a janela do app em testes automáticos**: o usuário fica no computador e fecha a janela; usar `raiz.withdraw()`.

---

## 6. Decisões importantes e motivo

| Decisão | Motivo |
|---|---|
| Interface em **Tkinter**, não Streamlit | Streamlit travava a câmera |
| **Três threads** (câmera, analisador, interface) | A janela nunca espera pela câmera nem pela IA |
| **Detectar separado de exigir**: o modelo avalia todos os EPIs; o setor só define quais contam | Trocar de setor vale na hora, sem reclassificar |
| Classificador **multirrótulo** (sigmoid por EPI) | Responder cada EPI independentemente; softmax obrigaria uma única resposta |
| Catraca **nega se uma pessoa estiver irregular**; EPI exigido que o modelo não conhece conta como faltando | Regra de segurança: na dúvida, nega |
| Lista de EPIs gravada em `modelos/epis.json` no treino | O app nunca troca um EPI por outro, mesmo se `config.EPIS` mudar |
| **Modo de compatibilidade** com o modelo antigo | O app continua funcionando antes do primeiro treino por EPI |
| Coleta salva o **recorte da pessoa**, não o frame | Treinar com o mesmo enquadramento da inferência |
| Auditoria por **evento** (ENTRADA / MUDANCA), com 1 foto | Log legível e fotos sem repetição |
| **Zerar arquiva**, não apaga | Registro de auditoria não deve sumir com um clique |
| Painel web **somente leitura** e com login | Pedido do usuário: o gerente vê, não altera; e mostra fotos de pessoas |
| Repositório **público**, **sem fotos** do dataset | Escolha do usuário; privacidade |
| Modelo YOLOX (35 MB) **fora do git** | Tamanho; comando de download no README |
| Rótulo de **uma palavra** no vídeo; detalhe no log | Pedido do usuário: com muita gente, rótulos longos cobriam pessoas |
| **Seletor manual** Rosto/Corpo (não automático) | Pedido do usuário; cada modo serve a um uso |
| Reconhecimento de **voz** fora do escopo | Etapa futura do desafio |
