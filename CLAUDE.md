# CLAUDE.md — SafeTech Entry

Regras permanentes para trabalhar neste projeto. O `README.md` explica o projeto para usuários (instalação, uso, arquitetura). O `PROGRESSO.md` diz onde o trabalho parou. Leia os dois antes de começar.

## O projeto

Projeto acadêmico de segurança do trabalho: visão computacional que verifica, pela câmera, se cada pessoa usa os EPIs exigidos no setor (capacete, óculos, colete, luvas), libera ou nega o acesso e registra auditoria com foto. Reconhecimento de voz é etapa futura: **não implementar sem pedido explícito**.

## Idioma e estilo

- O usuário escreve em **português do Brasil**; responder em português.
- Código em português: nomes de variáveis, funções, classes e comentários.
- Comentários em **blocos com cabeçalho** (`# ====...` / título / `# ====...`) e docstrings explicando o porquê, no mesmo estilo dos arquivos existentes. O projeto é didático: o código deve ser legível por um estudante.
- Nenhum número "mágico" nos módulos: todo ajuste fica em `safetech/config.py`, com comentário explicando o efeito.

## Ambiente

- Windows, Python 3.13 da Microsoft Store. Nos shells das ferramentas, `python` e `py` **não funcionam**; usar o caminho completo:
  `C:\Users\joaof\AppData\Local\Microsoft\WindowsApps\python3.13.exe`
- OpenCV **5.0**: não tem `CascadeClassifier` nem `HOGDescriptor`. Detecção de rosto só com `cv2.FaceDetectorYN`.
- O bash das ferramentas falha com heredoc contendo muitas aspas: para textos longos (ex.: mensagens de commit), gravar num arquivo e usar `git commit -F`.

## Como rodar

```
python app.py          # aplicativo (janela + painel web na porta 8080)
python treinar.py      # treina o modelo por EPI com dataset/epis + dataset/rotulos.csv
python reconhecer.py   # testa o modelo com uma foto
python painel_web.py   # painel web só com o histórico, sem câmera
python -m compileall -q app.py treinar.py reconhecer.py painel_web.py safetech   # checagem rápida de sintaxe
python -m pytest       # testes automatizados (pasta testes/, ~35 s)
```

## Arquitetura (resumo)

- `safetech/config.py` — toda a configuração.
- `safetech/nucleo/` — sem câmera e sem tela: detectores (`detector.py` escolhe entre `detector_rosto.py` e `detector_corpo.py`), `rastreador.py`, `classificador.py`, `decisao.py`, `anotacao.py`, `tipos.py`, `epis.py`, `modos.py` (textos de cada modo).
- `safetech/servicos/` — `camera.py` (thread; webcam por número ou câmera IP por endereço), `analisador.py` (thread: detectar → rastrear → classificar → decidir → auditar), `auditoria.py`, `dataset.py`, `importacao.py`, `preferencias.py`, `relatorio.py` (relatório HTML de uma linha da auditoria), `catraca_serial.py` (thread que envia o status ao ESP32 pelo cabo USB).
- `safetech/interface/` — Tkinter. Os painéis só exibem e chamam funções recebidas; não conhecem câmera nem modelo.
  - **Controladores**: a `janela_principal.py` só monta a tela (cabeçalho, divisor, rodapé), cuida de tema, atalhos, ciclo e avisos, e liga os controladores, um por assunto: `ia` (`controlador_ia.CargaIA`), `areas` (`controlador_areas`: áreas, barra, páginas, visão geral, fiscalização, confiança/intervalo), `cameras` (`controlador_cameras`), `eventos` (`controlador_auditoria`), `coleta` (`controlador_coleta`), `painel_web` (`controlador_painel_web`), `catraca` (`controlador_catraca`), `indicadores` (`controlador_indicadores`: janela de indicadores, PDF, relatório diário), `telao` (`controlador_telao`), `sistema` (`controlador_sistema`: assistente, backup, logs). Eles usam da janela só as propriedades públicas `raiz`, `escala`, `auditoria`, `configuracoes`, `painel_auditoria` e `avisar()`. Funcionalidade nova vai no controlador do assunto, não na janela.
  - **Várias áreas**: cada área (`area_monitorada.py`: dados + câmera + `ParametrosAnalise` + `Analisador` + aba) é uma aba do `ttk.Notebook` à esquerda; a última aba "+ Nova área" cria outra (`dialogo_area.py`). Só a área à vista é desenhada; todas analisam. `janela._camera`, `._parametros`, `._painel_monitoramento`, `._analisador` são da área à vista. A navegação é a `BarraAreas` (`componentes.py`: pílulas com ponto da situação, "Visão geral" e "+ Nova área"); o `ttk.Notebook` só guarda as páginas (estilo `SemAbas.TNotebook`, abas escondidas). Com 2+ áreas, "Visão geral" troca as páginas por `painel_visao_geral.py` (todas lado a lado; clique abre a área). A auditoria acompanha: área aberta = só os eventos dela (`PainelAuditoria.definir_area(nome)`); visão geral = todas (`definir_area(None)`).
  - **Temas escuro e claro**: `tema.PALETAS` (mesmas chaves nos dois; cores repetidas num tema também repetidas no outro, conferido em `test_temas.py`). Usar sempre `CORES["chave"]`, nunca cor escrita (exceto `"white"` sobre cores de status). `tema.trocar_tema` refaz os estilos e repinta os componentes tk trocando cor antiga pela nova; o que guarda cor por conta própria (tags da Treeview, imagens) precisa de um método para refazer (ex.: `PainelAuditoria.aplicar_cores`).
  - `painel_monitoramento.py` = a aba de uma área: vídeo, status, setor, modo, **EPIs exigidos** e botão da câmera.
  - `janela_configuracoes.py`: Toplevel criado uma vez, escondido, mostrado pelo botão "Configurações"; abas "Área e câmera" (da área aberta: nome, câmera, câmeras IP, comanda a catraca, nova/remover área), "Análise" (confiança e intervalo, globais, salvos) e "Coleta".
  - Áreas salvas em `preferencias.json` (`DadosArea`, `carregar_areas`/`salvar_areas`); sem "areas" no arquivo, monta a "Principal" com o setor/modo/câmera antigos.
  - O classificador é um só (`ClassificadorCompartilhado`, com trava); detectores são um por área (não são thread-safe).
  - A auditoria é uma só, com a coluna `area`. A catraca e o "ao vivo" do painel web seguem a área marcada para comandar a catraca.
- `safetech/web/` — painel do gerente. Ligar, porta, rede, usuário e senha são ajustados em Configurações > Painel web (`servicos/acesso_web.py`: `AjustesPainelWeb`, hash PBKDF2, `montar_ajustes` valida os campos) e salvos em `preferencias.json` (`painel_web`); o `config.py` só dá os valores iniciais. **Nunca guardar a senha em texto**, só o hash. "Aplicar" reinicia o servidor (`JanelaPrincipal._ligar_painel_web`).
- Indicadores e PDF: as contas em `servicos/indicadores.py`; os gráficos são imagens Pillow de `servicos/graficos.py`, os MESMOS na janela (nas cores do tema) e no PDF (`servicos/relatorio_pdf.py`, páginas desenhadas e salvas como PDF pela Pillow: sem biblioteca nova).
- Telão (`janela_telao.py`): o que mostrar vem de `situacao_do_telao(estado)` (testável sem tela); textos em `TEXTOS_POR_MODO["telao_*"]`; ícones dos EPIs desenhados em `nucleo/icones.py` (EPI sem desenho ganha a inicial; os mesmos nos chips, no evento selecionado e no relatório).
- **Peças de UI/UX** (usar em vez de criar outras): confirmações por `dialogos.confirmar(pai, titulo, mensagem, texto_confirmar, perigoso)` e `dialogos.informar` (nunca `tkinter.messagebox`, que sai branco no tema escuro; nos testes, trocar `dialogos.confirmar` por resposta pronta); avisos por `janela.avisar(texto, segundos, tipo)` (`info`/`sucesso`/`alerta`/`erro`; sem tipo, texto que começa com "Não foi possível"/"Erro" vira erro), mostrados em cartões (`componentes.Avisos`); dica de botão por `componentes.dica(botao, texto)`; atalho novo entra também em `janela_principal.ATALHOS` (lista do F1).
- Painel web: login por página própria (o JS manda o Basic em cada leitura com o cabeçalho `X-SafeTech-Painel`, e o servidor então responde 401 sem `WWW-Authenticate`). Só a página, o manifesto e os ícones são públicos (`ROTAS_PUBLICAS`); continua só GET.
- `instalador/`: `criar_atalho.py` (ícone + atalho com pythonw), `safetech.spec` e `gerar_exe.ps1` (PyInstaller, pasta onedir). O `.ico`, `build/` e `dist/` ficam fora do git.
- `catraca_esp32/` — firmware Arduino (C++) da catraca de demonstração. Recebe o status por dois caminhos: cabo USB (linhas `ST|acesso|negadas|total|faltando`, enviadas por `servicos/catraca_serial.py`) e Wi-Fi (lê `/api/ao-vivo`, só GET). O cabo tem prioridade. Ajustes ficam em `config.h` (fora do git; modelo em `config_exemplo.h`). Se mudar o formato da linha ou do `/api/ao-vivo`, atualizar o `.ino` e os testes `test_catraca_serial.py` / `test_contrato_catraca.py`.
- Compilar o firmware: a Arduino IDE traz o `arduino-cli` em `C:\Program Files\Arduino IDE\resources\app\lib\backend\resources\arduino-cli.exe` (placa `esp32:esp32`, FQBN `esp32:esp32:esp32`; a pasta do sketch é `catraca_esp32/` e compila com `.`). Gravar: `compile --upload -p COM3`. Com o SafeTech aberto a COM3 fica ocupada: fechar o app (ou `CATRACA_SERIAL_ATIVA = False`) antes de gravar.
- Dependências entre camadas têm direção única: interface → serviços → núcleo.

## Erros e log

- Cada módulo usa `log = logging.getLogger(__name__)`; o `app.py` e o `painel_web.py` ligam o arquivo `logs/safetech.log` (`servicos/log_erros.configurar`, com rotação; ajustes `PASTA_LOGS`, `TAMANHO_MAXIMO_LOG_BYTES`...). Os testes não ligam o arquivo.
- `except` que engole um erro deve ao menos registrá-lo (`log.exception`). Erros de botões vão para o log e para o aviso (`report_callback_exception`); o ciclo da tela registra e segue.
- A análise de cada área se recupera sozinha (`Analisador._executar`: `ESPERA_REINICIO_ANALISE_SEG`, `MAXIMO_REINICIOS_ANALISE`); a faixa mostra "REINICIANDO A ANÁLISE".
- Títulos da faixa (liberado/negado/analisando/aguardando) só por `modos.titulo_da_situacao`, usado pela tela e pelo painel web.
- **Horário dos eventos**: gravar com `nucleo/horario.agora_iso()` (ISO 8601 com fuso) e ler/mostrar só pelas funções de `horario` (`para_exibir`, `fuso`, `data`, `hora`, `para_relatorio`): elas aceitam também o formato antigo sem fuso. Nunca fatiar o texto do timestamp na mão.
- Painel web: `ServidorWeb.verificar_login` aplica o limite de logins errados por endereço (`acesso_web.LimiteDeTentativas`, resposta 429). Pedido sem login não conta como erro.
- Sobrecarga: `area_monitorada.analise_lenta` / `AreaMonitorada.verificar_sobrecarga` (ajustes `SOBRECARGA_*`); o selo fica na janela (`_atualizar_selo_sobrecarga`).

## Regras do projeto (não quebrar)

- **Dois modos de operação** (`config.MODO_CATRACA` = detector de rosto, `config.MODO_VIGILANCIA` = detector de corpo). A decisão é a mesma; muda o texto ("Liberado/Negado" x "Conforme/Não conforme") e a catraca física só obedece no modo catraca. Textos só em `config.TEXTOS_POR_MODO`, lidos por `nucleo/modos.py`: nunca escrever "Liberado"/"Negado" fixo. O modo vai no `EstadoCena.modo` e na coluna `modo` da auditoria. Nomes antigos `"rosto"`/`"corpo"` são convertidos (`config.MODOS_ANTIGOS`).

- **Detectar separado de exigir**: o classificador avalia todos os EPIs; o setor só define quais contam. Não misturar regra de setor no classificador.
- **Nomes e ordem dos EPIs vêm de `modelos/epis.json`**, nunca fixos no código de inferência.
- **Painel web é somente leitura**: só GET. Não adicionar rotas que alterem configuração, câmera ou registros.
- **Auditoria nunca é apagada pelo programa**: logs de formato antigo são renomeados; o botão Zerar arquiva em `auditoria/arquivados/`; o botão Excluir linha move a linha e a foto para `auditoria/excluidos/`.
- O analisador recebe um dicionário `{modo: detector}`; os dois modos ficam carregados para a troca ser imediata.
- Objetos passados entre threads são imutáveis (`dataclass(frozen=True)` em `tipos.py`).

## Testes

- Testes em `testes/` (pytest, configurado em `pytest.ini`). Rodar `python -m pytest` depois de qualquer mudança e manter todos passando; funcionalidade nova ganha teste novo.
- `testes/conftest.py` já redireciona os caminhos abaixo e oferece as fixtures `auditoria`, `raiz` (janela escondida) e `sem_ia` (troca `CargaIA.carregar`); `testes/falsos.py` tem câmera, detector, classificador e câmera IP falsos. Reaproveitar em vez de recriar.
- Os testes não podem depender do TensorFlow (o GitHub Actions não o instala).
- Os testes **nunca abrem a porta USB real** do ESP32: o `conftest.py` põe `CATRACA_SERIAL_ATIVA = False` e os testes do envio usam uma porta falsa.
- Testes devem gravar só em **pastas temporárias**: alterar `config.PASTA_AUDITORIA`, `config.ARQUIVO_LOG_AUDITORIA`, `config.PASTA_IMAGENS_AUDITORIA`, `config.PASTA_IMAGENS_DATASET`, `config.ARQUIVO_ROTULOS`, `config.ARQUIVO_PREFERENCIAS`, `config.PASTA_EXCLUIDOS`, `config.PASTA_RELATORIOS`, `config.PASTA_CAPTURAS`, `config.PASTA_LOGS` e `config.PASTA_RELATORIOS_DIARIOS` **antes** de importar os serviços (os padrões são lidos na importação).
- Para o painel web em teste: `config.PAINEL_WEB_HOST = "127.0.0.1"` (ou `na_rede=False` nos ajustes) e outra porta, para não acionar o firewall do Windows nem colidir com o app aberto. O `conftest.py` baixa `ITERACOES_HASH_SENHA` para 1000 (o hash de verdade é lento de propósito) e desliga `RELATORIO_DIARIO_AUTOMATICO` e `ASSISTENTE_NA_PRIMEIRA_EXECUCAO`.
- Janelas novas em teste: o telão é escondido (`withdraw`) logo depois de aberto; o assistente é criado com `mostrar=False`; a janela de Indicadores nasce escondida (não chamar `mostrar()`).
- Câmera IP em teste: servir um MJPEG falso em `127.0.0.1` (`multipart/x-mixed-replace`) e abrir `http://127.0.0.1:<porta>/...`.
- **Não ligar a webcam do usuário** em testes: passar uma câmera falsa para `JanelaPrincipal(raiz, escala, camera=...)`.
- **Não mostrar a janela** em testes automáticos: o usuário fica no computador e fecha janelas que aparecem. Usar `raiz.withdraw()`.
- Para lógica do analisador, usar detector e classificador falsos (classes com `detectar()` e `classificar_lote()`).

## Git

- Branch `main`, publicada em https://github.com/Fidelis09/safetech-entry (remoto `origin`). `git push` só quando o usuário pedir; o GitHub Actions roda os testes a cada envio.
- Commits em português, com mensagem explicando o que mudou e por quê.
- Autor dos commits: passar `-c user.name="João Fidelis" -c user.email="jfidelis999@gmail.com"` no comando. **Não alterar o git config.**
- Commitar só quando o usuário pedir.
- Nunca versionar: fotos de pessoas (`dataset/*/*`), `auditoria/`, `preferencias.json`, `dataset/rotulos*.csv`, `_versao_anterior/`, o modelo YOLOX. O `.gitignore` já cobre isso; conferir `git status` antes de commitar.
- `_versao_anterior/` é o backup do código antigo (antes da reescrita). Não apagar sem o usuário pedir.
