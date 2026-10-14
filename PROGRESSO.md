# PROGRESSO — SafeTech Entry

Última atualização: 14/10/2026. Último commit: `3c1261d`. Árvore de trabalho limpa (tudo commitado).

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

---

## 3. O que está pela metade

Nenhuma alteração de código ficou incompleta: tudo foi commitado. Estão pela metade:

1. **README desatualizado em dois trechos.** Ele ainda diz que o repositório traz só o modelo antigo (linhas ~70 e ~554 do `README.md`), mas desde o commit `8b34692` o `modelo_epis.keras` está versionado. Corrigir esses dois parágrafos.
2. **Publicação no GitHub.** Repositório só local, sem remoto. Parou esperando o usuário instalar e autenticar o GitHub CLI. Decisões já tomadas: repositório **público**, autor "João Fidelis <jfidelis999@gmail.com>", **sem** fotos do dataset.
3. **Qualidade do modelo de EPI.** Ver seção 5. Parou em: o usuário treinou com 49 imagens; nos testes do sistema, quase todas as pessoas saem como "NEGADO".
4. **Testes automatizados não estão no repositório.** Foram escritos durante a sessão numa pasta temporária, que se perde. Ver seção 4, passo 4.

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
