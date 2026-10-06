# SafeTech Entry

Catraca inteligente com reconhecimento de EPI por visão computacional.

O programa usa a webcam para verificar se cada pessoa na frente da câmera está usando os equipamentos de proteção obrigatórios (capacete, colete e óculos). O acesso só é liberado quando todas as pessoas na imagem estão com EPI. Cada decisão fica registrada em um log de auditoria, com foto de evidência.

Projeto acadêmico (desafio de segurança do trabalho). Esta etapa cobre apenas a parte de visão computacional; a confirmação por voz da Ordem de Serviço fica para uma etapa futura.

---

## Sumário

1. [Funcionalidades](#funcionalidades)
2. [Instalação](#instalação)
3. [Como usar](#como-usar)
4. [Painel web do gerente](#painel-web-do-gerente)
5. [Como funciona](#como-funciona)
6. [Estrutura do projeto](#estrutura-do-projeto)
7. [Coleta de imagens e re-treino](#coleta-de-imagens-e-re-treino)
8. [Auditoria](#auditoria)
9. [Configuração](#configuração)
10. [Desempenho](#desempenho)
11. [Solução de problemas](#solução-de-problemas)
12. [Limitações e próximos passos](#limitações-e-próximos-passos)

---

## Funcionalidades

- **Vídeo ao vivo** da webcam, fluido e ajustado ao tamanho da janela.
- **Várias pessoas ao mesmo tempo** (fila): cada uma recebe uma caixa que a acompanha, com número, classe e confiança.
- **Decisão estável**: usa a média das últimas classificações de cada pessoa, então o status não fica piscando.
- **Status do acesso** em destaque: liberado (verde), negado (vermelho), analisando (laranja) ou aguardando.
- **Limiar de confiança e intervalo de análise** ajustáveis na tela, com efeito imediato.
- **Auditoria na mesma tela**: indicadores, filtros, busca, ordenação por coluna e foto de evidência do evento selecionado.
- **Coleta de dataset** por botão ou atalho de teclado, direto na pasta de treino.
- **Painel web do gerente**, somente leitura: status ao vivo, indicadores, gráfico e fotos pelo navegador, inclusive no celular.
- **Abertura imediata**: a janela aparece na hora e o modelo de IA carrega em segundo plano.

---

## Instalação

### Requisitos

- Windows 10 ou 11
- Python 3.10 ou superior (testado com 3.13)
- Webcam

### Passo a passo

1. Instale as dependências:

   ```bash
   pip install -r requirements.txt
   ```

2. Confira se a pasta `modelos/` tem estes três arquivos:

   | Arquivo | Origem |
   |---|---|
   | `modelo_epi.keras` | gerado pelo `treinar.py` |
   | `classes.json` | gerado pelo `treinar.py` |
   | `face_detection_yunet_2023mar.onnx` | detector de rosto, baixado uma vez |

   Se o detector de rosto estiver faltando, baixe com (PowerShell, na pasta do projeto):

   ```powershell
   Invoke-WebRequest -Uri "https://github.com/opencv/opencv_zoo/raw/main/models/face_detection_yunet/face_detection_yunet_2023mar.onnx" -OutFile "modelos/face_detection_yunet_2023mar.onnx"
   ```

3. Se ainda não houver modelo treinado, rode o treino (veja [Coleta de imagens e re-treino](#coleta-de-imagens-e-re-treino)).

---

## Como usar

### Abrir o programa

```bash
python app.py
```

A janela abre na hora, com a mensagem "Carregando o modelo de IA". Quando o botão mudar para **Iniciar câmera**, o programa está pronto.

### A tela

| Área | O que faz |
|---|---|
| **Vídeo** | Imagem da webcam com uma caixa por pessoa. Verde = com EPI, vermelho = sem EPI, cinza = ainda analisando. |
| **Faixa de status** | Decisão geral da catraca e quantas pessoas estão com e sem EPI. |
| **Limiar de confiança** | Confiança mínima para liberar. Mais alto = mais rigoroso. |
| **Intervalo de análise** | De quanto em quanto tempo cada pessoa é reclassificada. |
| **Coleta de imagens** | Salva o recorte de cada pessoa na pasta de treino da classe. O número entre parênteses é o total de imagens da classe. |
| **Auditoria** | Indicadores, filtros e tabela de eventos, atualizados ao vivo. Clique em um evento para ver a foto; duplo clique abre em tamanho real. Clique no título de uma coluna para ordenar. |

O divisor entre os dois painéis pode ser arrastado para dar mais espaço ao vídeo ou à auditoria.

### Atalhos de teclado

| Tecla | Ação |
|---|---|
| `Espaço` | Liga ou desliga a câmera |
| `1`, `2`, ... | Salva uma imagem na 1ª, 2ª... classe |
| `Esc` | Limpa a busca da auditoria |

Os atalhos ficam desativados enquanto você digita no campo de busca.

### Testar o modelo com uma foto

```bash
python reconhecer.py
```

Abre uma janela para escolher a imagem e mostra, para cada pessoa encontrada, a classe, a confiança e se o acesso seria liberado. Também aceita o caminho direto: `python reconhecer.py foto.jpg`.

---

## Painel web do gerente

Página de acompanhamento pelo navegador, **somente leitura**: o gerente vê os dados e as imagens, mas não consegue alterar nenhuma configuração, ligar ou desligar a câmera, nem apagar registros.

### Como acessar

1. Abra o aplicativo (`python app.py`). O painel web sobe junto.
2. O endereço aparece no canto inferior esquerdo da janela, por exemplo `Painel web: http://192.168.0.15:8080`. Clicar nele abre o navegador.
3. No computador do gerente (ou no celular), na **mesma rede**, digite esse endereço.
4. Informe o login: usuário `gerente`, senha definida em `safetech/config.py`.

Na primeira vez, o Windows pode perguntar se o Python pode aceitar conexões da rede. É preciso permitir para que outros aparelhos acessem.

### O que o painel mostra

| Área | Conteúdo |
|---|---|
| **Ao vivo** | Imagem atual da câmera com as caixas, status da catraca e a situação de cada pessoa. Atualiza a cada segundo. |
| **Hoje** | Eventos, liberados, negados e taxa de liberação do dia, com o total do histórico abaixo de cada número. |
| **Eventos por hora** | Gráfico de barras do dia. Passar o mouse numa hora mostra os números. |
| **Eventos de auditoria** | Os eventos mais recentes, com miniatura da foto, filtros e busca. Clicar numa linha abre a foto em tamanho grande. |

A página funciona em celular e não depende de internet (não carrega nada de fora).

### Só o histórico, sem abrir a catraca

```bash
python painel_web.py
```

Sobe o mesmo painel sem câmera: indicadores, gráfico, eventos e fotos. Não abra junto com o aplicativo, pois os dois usam a mesma porta.

### Segurança

- **Somente leitura de verdade**: o servidor só responde a pedidos de leitura (GET). Qualquer tentativa de envio ou alteração é recusada, e não existe rota que mude o sistema.
- **Login obrigatório**: o painel mostra fotos de pessoas, então pede usuário e senha. **Troque a senha padrão** (`PAINEL_WEB_SENHA`) antes de usar fora de testes.
- **Só as fotos de evidência são servidas**: pedidos que tentam alcançar outros arquivos do computador são recusados.
- **Limite conhecido**: a conexão é HTTP simples, sem criptografia. Use apenas em rede local de confiança, nunca exposto à internet.

Para restringir o painel a este computador, use `PAINEL_WEB_HOST = "127.0.0.1"`. Para desligar, `PAINEL_WEB_ATIVO = False`.

---

## Como funciona

### As duas redes neurais

O sistema combina dois modelos, cada um com uma função:

1. **Detector de rosto (YuNet)**: encontra ONDE estão as pessoas. A partir de cada rosto, o programa monta uma caixa maior cobrindo cabeça e tronco, que é onde ficam o capacete, os óculos e o colete.
2. **Classificador de EPI (MobileNetV2)**: recebe o recorte de cada pessoa e responde `com_epi` ou `sem_epi`, com uma confiança. Foi treinado por *transfer learning*: a MobileNetV2 já vem treinada com milhões de imagens e só a camada final foi treinada com as fotos do projeto.

### A linha de análise

Para cada frame da câmera:

```
 frame ──> DETECTAR ──> RASTREAR ──> CLASSIFICAR ──> DECIDIR ──> AUDITAR
           onde estão    quem é      com EPI ou      liberado    grava se a
           as pessoas    quem        sem EPI?        ou negado   decisão mudou
```

- **Detectar**: o YuNet roda numa cópia reduzida do frame (mais rápido).
- **Rastrear**: cada caixa é ligada à pessoa do frame anterior pela sobreposição entre as caixas (IoU). Assim cada pessoa mantém um número fixo (`#1`, `#2`...) e um histórico próprio, mesmo com várias pessoas em fila.
- **Classificar**: todas as pessoas são classificadas numa única chamada ao modelo. Isso acontece no intervalo configurado, e mais rápido quando aparece alguém novo.
- **Decidir**: a decisão de cada pessoa usa a **média** das últimas 5 classificações. A pessoa é liberada se a classe for `com_epi` e a confiança média passar do limiar.
- **Auditar**: um evento é gravado quando sai a primeira decisão de uma pessoa e sempre que essa decisão muda.

### Regra da catraca

| Situação | Status |
|---|---|
| Ninguém na imagem | Aguardando |
| Alguém ainda sem decisão | Analisando |
| Pelo menos uma pessoa sem EPI | **Acesso negado** |
| Todas as pessoas com EPI | **Acesso liberado** |

### Por que a tela não trava

O programa usa três threads, cada uma com um trabalho:

| Thread | Trabalho |
|---|---|
| **Câmera** | Captura os frames e guarda sempre o mais recente. |
| **Analisador** | Executa a linha de análise e publica o resultado. |
| **Interface** | Desenha a tela cerca de 30 vezes por segundo, usando o frame e o resultado mais recentes. |

A interface nunca espera pela câmera nem pela IA, então o vídeo continua fluido mesmo durante a análise.

---

## Estrutura do projeto

```
Tech_day_26.2/
├── app.py                  Abre o aplicativo
├── treinar.py              Treina o modelo
├── reconhecer.py           Testa o modelo com uma foto
├── painel_web.py           Painel web só com o histórico (sem abrir a catraca)
├── requirements.txt        Dependências
├── README.md
│
├── safetech/               Código do projeto
│   ├── config.py           Todas as configurações (caminhos e ajustes)
│   │
│   ├── nucleo/             A "inteligência" (sem tela e sem câmera)
│   │   ├── tipos.py            Estruturas de dados trocadas entre os módulos
│   │   ├── classes.py          Leitura do classes.json
│   │   ├── detector.py         Encontra as pessoas no frame (YuNet)
│   │   ├── rastreador.py       Mantém a identidade de cada pessoa
│   │   ├── classificador.py    Modelo de EPI (MobileNetV2)
│   │   ├── decisao.py          Regras de liberado / negado
│   │   └── anotacao.py         Desenha caixas e rótulos na imagem
│   │
│   ├── servicos/           O que acontece ao redor do núcleo
│   │   ├── camera.py           Captura da webcam em thread própria
│   │   ├── analisador.py       Linha de análise em thread própria
│   │   ├── auditoria.py        Log em CSV e fotos de evidência
│   │   └── dataset.py          Salva imagens de treino
│   │
│   ├── interface/          A janela (Tkinter)
│   │   ├── tema.py                  Cores, fontes e estilos
│   │   ├── painel_monitoramento.py  Vídeo, status, controles e coleta
│   │   ├── painel_auditoria.py      Indicadores, filtros, tabela e evidência
│   │   └── janela_principal.py      Monta a tela e liga tudo
│   │
│   ├── web/                Painel web do gerente (somente leitura)
│   │   ├── servidor.py         Servidor HTTP: página, dados e imagens
│   │   └── painel.html         A página do painel
│   │
│   └── treino/
│       └── treinador.py        Valida o dataset, monta a rede, treina e salva
│
├── modelos/                Modelos usados pelo programa
├── dataset/                Imagens de treino, uma pasta por classe
│   ├── com_epi/
│   └── sem_epi/
└── auditoria/              Gerada pelo programa
    ├── log_auditoria.csv
    └── imagens/            Fotos de evidência
```

### Princípios da organização

- **Camadas com direção única**: a interface usa os serviços, os serviços usam o núcleo. O núcleo não conhece ninguém acima dele, por isso pode ser testado sem câmera e sem janela.
- **Configuração em um lugar só**: nenhum módulo tem número fixo espalhado; tudo vem de `safetech/config.py`.
- **Classes vindas do arquivo**: os nomes e a ordem das classes são lidos de `classes.json`. O código só conhece o nome da classe que libera o acesso (`CLASSE_LIBERA_ACESSO`).
- **Painéis sem lógica**: os painéis apenas exibem dados e avisam a janela principal quando o usuário faz algo.

---

## Coleta de imagens e re-treino

A qualidade do reconhecimento depende diretamente do dataset. Para melhorar o modelo:

1. Abra o programa e ligue a câmera.
2. Fique na frente da câmera **com** os EPIs e pressione `1` várias vezes, variando posição, distância, ângulo e iluminação.
3. Faça o mesmo **sem** os EPIs (e com apenas parte deles), pressionando `2`.
4. Feche o programa e treine de novo:

   ```bash
   python treinar.py
   ```

5. Abra o programa novamente para usar o modelo novo.

Dicas:

- Mantenha as classes equilibradas (quantidade parecida de imagens em cada uma).
- Inclua casos difíceis em `sem_epi`: só capacete, só colete, boné no lugar do capacete, óculos de grau.
- Colete com pessoas, fundos e iluminações diferentes.

> **Importante:** a coleta salva o **recorte de cada pessoa** (cabeça e tronco), que é exatamente o que o modelo recebe durante o uso. As imagens coletadas por versões anteriores do programa eram o frame inteiro. O modelo atual funciona com os recortes, mas a precisão melhora ao coletar imagens novas nesta versão e treinar de novo.

### Sobre o treinamento

- Rede base: MobileNetV2 pré-treinada (ImageNet), congelada.
- Camada treinada: média global, dropout de 20% e uma camada densa com softmax.
- *Data augmentation*: espelhamento horizontal, rotação e zoom leves.
- 80% das imagens para treino e 20% para validação; 10 épocas; otimizador Adam.
- A normalização da MobileNetV2 fica dentro do modelo: quem usa o modelo entrega a imagem RGB 224x224 sem normalizar.

---

## Auditoria

O log fica em `auditoria/log_auditoria.csv`, e as fotos em `auditoria/imagens/`.

| Coluna | Conteúdo |
|---|---|
| `timestamp` | Data e hora do evento |
| `evento` | `ENTRADA` (primeira decisão da pessoa) ou `MUDANCA` (a decisão mudou) |
| `pessoa` | Identificação da pessoa na sessão, ex.: `P003` |
| `classe` | Classe prevista, ex.: `com_epi` |
| `confianca_percentual` | Confiança média da decisão |
| `liberado` | `SIM` ou `NAO` |
| `imagem` | Arquivo da foto de evidência |

Cada evento tem uma foto do frame inteiro, com a pessoa em questão destacada.

O número da pessoa (`P001`, `P002`...) vale enquanto ela permanece na imagem e recomeça a cada vez que o programa é aberto. Não é uma identificação de quem a pessoa é.

Logs de versões anteriores do programa, que tinham outras colunas, não são apagados: são renomeados para `log_auditoria_formato_antigo_<data>.csv`.

---

## Configuração

Os ajustes ficam em `safetech/config.py`. Os mais úteis:

| Constante | Padrão | Efeito |
|---|---|---|
| `CLASSE_LIBERA_ACESSO` | `"com_epi"` | Nome da classe que libera o acesso |
| `LIMIAR_CONFIANCA_PADRAO` | `0.80` | Confiança mínima para liberar (valor inicial do controle) |
| `INTERVALO_CLASSIFICACAO_PADRAO_SEG` | `1.0` | Intervalo de reclassificação (valor inicial do controle) |
| `TAMANHO_HISTORICO_DECISAO` | `5` | Quantas classificações entram na média da decisão |
| `AMOSTRAS_MINIMAS_DECISAO` | `2` | Classificações necessárias antes da primeira decisão |
| `INDICE_CAMERA` | `0` | Qual webcam usar |
| `LARGURA_CAPTURA` / `ALTURA_CAPTURA` | `640` / `480` | Resolução pedida à webcam |
| `LARGURA_DETECCAO` | `480` | Largura da cópia usada na detecção de rosto |
| `CONFIANCA_MINIMA_ROSTO` | `0.7` | Confiança mínima para aceitar um rosto |
| `MARGEM_*_ROSTO` | - | Quanto a caixa do rosto é expandida para cobrir o tronco |
| `TEMPO_MAXIMO_AUSENTE_SEG` | `1.0` | Tempo que uma pessoa pode sumir sem perder o número |
| `EPOCAS_TREINO` | `10` | Épocas do treinamento |
| `PAINEL_WEB_ATIVO` | `True` | Liga ou desliga o painel web |
| `PAINEL_WEB_HOST` | `"0.0.0.0"` | `"0.0.0.0"` = acessível na rede; `"127.0.0.1"` = só neste computador |
| `PAINEL_WEB_PORTA` | `8080` | Porta do painel web |
| `PAINEL_WEB_USUARIO` / `PAINEL_WEB_SENHA` | `gerente` / `safetech` | Login do painel. Troque a senha; senha vazia desliga o login |

---

## Desempenho

Medições feitas em CPU (sem placa de vídeo), no computador de desenvolvimento:

| Etapa | Tempo |
|---|---|
| Detecção de rosto por frame | cerca de 8 ms |
| Classificação de 1 pessoa | cerca de 24 ms |
| Classificação de 3 pessoas (uma chamada) | cerca de 50 ms |
| Mesma classificação com `modelo.predict()` | cerca de 224 ms |

O que deixa o programa rápido:

- captura, análise e tela em threads separadas;
- inferência compilada em grafo (`tf.function`) e em lote, no lugar de `modelo.predict()` por pessoa;
- detecção de rosto em imagem reduzida;
- classificação apenas no intervalo configurado, não a cada frame;
- tabela de auditoria atualizada por inserção, sem reler o CSV;
- a imagem do vídeo é reaproveitada entre os quadros, em vez de recriada.

O tempo de abertura do modelo depende do TensorFlow: alguns segundos normalmente, e mais de um minuto na primeira execução depois de ligar o computador. A janela fica utilizável durante esse tempo.

---

## Solução de problemas

| Problema | Solução |
|---|---|
| **"Modelo não encontrado em 'modelos/'"** | Rode `python treinar.py`. |
| **"Não foi possível acessar a webcam"** | Feche outros programas que usem a câmera (Teams, Zoom, navegador). Se houver mais de uma câmera, mude `INDICE_CAMERA`. |
| **Aviso "Detector de rosto não encontrado"** | Baixe o arquivo `.onnx` (veja [Instalação](#instalação)). Sem ele o programa funciona, mas trata a cena inteira como uma pessoa. |
| **Vídeo lento** | Mantenha `LARGURA_CAPTURA`/`ALTURA_CAPTURA` em 640x480 e aumente o intervalo de análise na tela. |
| **A caixa não aparece** | O detector precisa ver o rosto. Fique de frente para a câmera, com boa iluminação. |
| **Status errado com frequência** | O dataset é pequeno. Colete mais imagens e treine de novo. |
| **"Painel web indisponível (porta 8080 em uso)"** | Outro programa usa a porta, ou o `painel_web.py` está aberto. Feche-o ou mude `PAINEL_WEB_PORTA`. |
| **O painel web não abre em outro aparelho** | Os dois precisam estar na mesma rede, e o Windows precisa ter permitido o Python no firewall (redes privadas). |
| **`No module named 'tensorflow.python'`** ao instalar | Caminhos longos desativados no Windows. Em um PowerShell de administrador: `New-ItemProperty -Path "HKLM:\SYSTEM\CurrentControlSet\Control\FileSystem" -Name "LongPathsEnabled" -Value 1 -PropertyType DWORD -Force`, reinicie o computador e reinstale com `pip install --force-reinstall tensorflow`. |
| **`Could not find the DLL(s) 'msvcp140.dll'`** | Instale o Microsoft Visual C++ Redistributable: `winget install --id Microsoft.VCRedist.2015+.x64 -e`. |

---

## Limitações e próximos passos

Limitações conhecidas:

- **A pessoa é localizada pelo rosto.** De costas ou com o rosto muito coberto, ela pode não ser detectada.
- **O modelo responde apenas "com EPI" ou "sem EPI".** Ele não informa qual equipamento está faltando.
- **Dataset pequeno.** Com poucas dezenas de imagens por classe, o modelo pode errar em pessoas, fundos e iluminações que não viu no treino.
- **O número da pessoa não é identidade.** Quem sai da imagem e volta recebe um número novo.

Próximos passos possíveis:

- Confirmação por voz da Ordem de Serviço (etapa futura do desafio).
- Um classificador por equipamento (capacete, colete, óculos), para dizer o que falta.
- Detector de corpo inteiro, para não depender do rosto.
- Integração com uma catraca real (acionamento por relé ou porta serial).
- Exportação de relatórios da auditoria por período.
