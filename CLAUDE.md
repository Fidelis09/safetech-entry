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
```

## Arquitetura (resumo)

- `safetech/config.py` — toda a configuração.
- `safetech/nucleo/` — sem câmera e sem tela: detectores (`detector.py` escolhe entre `detector_rosto.py` e `detector_corpo.py`), `rastreador.py`, `classificador.py`, `decisao.py`, `anotacao.py`, `tipos.py`, `epis.py`.
- `safetech/servicos/` — `camera.py` (thread; webcam por número ou câmera IP por endereço), `analisador.py` (thread: detectar → rastrear → classificar → decidir → auditar), `auditoria.py`, `dataset.py`, `importacao.py`, `preferencias.py`, `relatorio.py` (relatório HTML de uma linha da auditoria).
- `safetech/interface/` — Tkinter. Os painéis só exibem e chamam funções da `janela_principal.py`; não conhecem câmera nem modelo.
- `safetech/web/` — painel do gerente.
- Dependências entre camadas têm direção única: interface → serviços → núcleo.

## Regras do projeto (não quebrar)

- **Detectar separado de exigir**: o classificador avalia todos os EPIs; o setor só define quais contam. Não misturar regra de setor no classificador.
- **Nomes e ordem dos EPIs vêm de `modelos/epis.json`**, nunca fixos no código de inferência.
- **Painel web é somente leitura**: só GET. Não adicionar rotas que alterem configuração, câmera ou registros.
- **Auditoria nunca é apagada pelo programa**: logs de formato antigo são renomeados; o botão Zerar arquiva em `auditoria/arquivados/`; o botão Excluir linha move a linha e a foto para `auditoria/excluidos/`.
- O analisador recebe um dicionário `{modo: detector}`; os dois modos ficam carregados para a troca ser imediata.
- Objetos passados entre threads são imutáveis (`dataclass(frozen=True)` em `tipos.py`).

## Testes

- Não há pasta de testes no repositório ainda (ver `PROGRESSO.md`).
- Testes devem gravar só em **pastas temporárias**: alterar `config.PASTA_AUDITORIA`, `config.ARQUIVO_LOG_AUDITORIA`, `config.PASTA_IMAGENS_AUDITORIA`, `config.PASTA_IMAGENS_DATASET`, `config.ARQUIVO_ROTULOS`, `config.ARQUIVO_PREFERENCIAS`, `config.PASTA_EXCLUIDOS` e `config.PASTA_RELATORIOS` **antes** de importar os serviços (os padrões são lidos na importação).
- Para o painel web em teste: `config.PAINEL_WEB_HOST = "127.0.0.1"` e outra porta, para não acionar o firewall do Windows nem colidir com o app aberto.
- Câmera IP em teste: servir um MJPEG falso em `127.0.0.1` (`multipart/x-mixed-replace`) e abrir `http://127.0.0.1:<porta>/...`.
- **Não ligar a webcam do usuário** em testes: passar uma câmera falsa para `JanelaPrincipal(raiz, escala, camera=...)`.
- **Não mostrar a janela** em testes automáticos: o usuário fica no computador e fecha janelas que aparecem. Usar `raiz.withdraw()`.
- Para lógica do analisador, usar detector e classificador falsos (classes com `detectar()` e `classificar_lote()`).

## Git

- Repositório local, branch `main`, **sem remoto** por enquanto (ver `PROGRESSO.md`).
- Commits em português, com mensagem explicando o que mudou e por quê.
- Autor dos commits: passar `-c user.name="João Fidelis" -c user.email="jfidelis999@gmail.com"` no comando. **Não alterar o git config.**
- Commitar só quando o usuário pedir.
- Nunca versionar: fotos de pessoas (`dataset/*/*`), `auditoria/`, `preferencias.json`, `dataset/rotulos*.csv`, `_versao_anterior/`, o modelo YOLOX. O `.gitignore` já cobre isso; conferir `git status` antes de commitar.
- `_versao_anterior/` é o backup do código antigo (antes da reescrita). Não apagar sem o usuário pedir.
