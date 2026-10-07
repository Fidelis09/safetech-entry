# SafeTech Entry

Catraca inteligente com reconhecimento de EPI por visão computacional.

O programa usa a webcam para verificar, **equipamento por equipamento** (capacete, óculos, colete e luvas), o que cada pessoa na frente da câmera está usando. Você escolhe o setor que está sendo fiscalizado e o sistema cobra apenas os EPIs exigidos nele: num setor que só exige luvas, quem está de luvas passa. O acesso só é liberado quando todas as pessoas na imagem estão em conformidade, e cada decisão fica registrada em um log de auditoria, com foto de evidência.

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
- **EPIs reconhecidos separadamente**: o modelo dá uma resposta independente para cada equipamento.
- **Fiscalização por setor**: perfis prontos (cada setor com seus EPIs obrigatórios) e caixas de seleção para ajustar na hora. A última seleção é lembrada ao reabrir o programa.
- **Várias pessoas ao mesmo tempo** (fila): cada uma recebe uma caixa que a acompanha, com número e o que está faltando.
- **Decisão estável**: usa a média das últimas classificações de cada pessoa, então o status não fica piscando.
- **Status do acesso** em destaque: liberado (verde), negado (vermelho), analisando (laranja) ou aguardando.
- **Confiança mínima e intervalo de análise** ajustáveis na tela, com efeito imediato.
- **Auditoria na mesma tela**: indicadores, filtros, busca, ordenação por coluna e foto de evidência do evento selecionado. Cada evento guarda o setor, o que era exigido e o que faltava.
- **Coleta de dataset rotulada**: marque o que a pessoa está usando e salve, por botão ou atalho de teclado.
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

2. Confira a pasta `modelos/`:

   | Arquivo | Para que serve | Origem |
   |---|---|---|
   | `face_detection_yunet_2023mar.onnx` | Localiza as pessoas | Baixado uma vez (já vem no repositório) |
   | `modelo_epis.keras` e `epis.json` | Modelo **por EPI** | Gerados pelo `treinar.py`, depois de você coletar imagens rotuladas |
   | `modelo_epi.keras` e `classes.json` | Modelo **antigo** (só "com EPI" / "sem EPI") | Já vêm no repositório |

   > **Importante:** o repositório vem só com o modelo antigo. Com ele o programa funciona, mas **não distingue os equipamentos** nem aplica a seleção por setor (a área de fiscalização fica desativada, com um aviso). Para ativar a fiscalização por EPI, siga [Coleta de imagens e re-treino](#coleta-de-imagens-e-re-treino). Depois de treinado, o modelo por EPI passa a ser usado automaticamente.

   Se o detector de rosto estiver faltando, baixe com (PowerShell, na pasta do projeto):

   ```powershell
   Invoke-WebRequest -Uri "https://github.com/opencv/opencv_zoo/raw/main/models/face_detection_yunet/face_detection_yunet_2023mar.onnx" -OutFile "modelos/face_detection_yunet_2023mar.onnx"
   ```

3. Para usar a fiscalização por EPI, colete imagens e treine (veja [Coleta de imagens e re-treino](#coleta-de-imagens-e-re-treino)).

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
| **Vídeo** | Imagem da webcam com uma caixa por pessoa. Verde = em conformidade (`#1 OK`), vermelho = falta algo (`#2 FALTA: CAPACETE, LUVAS`), cinza = ainda analisando. |
| **Faixa de status** | Decisão geral da catraca, quem está sem o quê e o que o setor exige. |
| **Fiscalização** | O setor em fiscalização e os EPIs obrigatórios nele (veja abaixo). |
| **Confiança mínima** | Confiança necessária para considerar que a pessoa está usando um EPI. Mais alto = mais rigoroso. |
| **Intervalo de análise** | De quanto em quanto tempo cada pessoa é reclassificada. |
| **Coleta de imagens** | Salva o recorte de cada pessoa, com os rótulos marcados, para treinar o modelo. |
| **Auditoria** | Indicadores, filtros e tabela de eventos, atualizados ao vivo. Clique em um evento para ver a foto, o que era exigido e a confiança de cada EPI; duplo clique abre a foto em tamanho real. Clique no título de uma coluna para ordenar. |

### Fiscalização por setor

Cada setor da empresa pode exigir EPIs diferentes. Na área **Fiscalização**:

1. Escolha o **setor** na lista. Os EPIs obrigatórios dele são marcados de uma vez.
2. Se precisar, **marque ou desmarque** cada EPI à mão. Se a combinação não corresponder a nenhum setor pronto, o setor aparece como "Personalizado".

A mudança vale na hora, sem reiniciar nada. O sistema continua enxergando todos os equipamentos; a seleção define apenas **quais deles contam** para liberar ou negar. A última seleção fica salva e é restaurada quando o programa é aberto de novo.

Os setores prontos ficam em `safetech/config.py`, no dicionário `SETORES`. Para criar o seu, acrescente uma linha:

```python
SETORES = {
    "Acesso geral": ["capacete", "oculos", "colete", "luvas"],
    "Manuseio de materiais": ["luvas"],
    "Almoxarifado": ["colete", "luvas"],   # setor novo
}
```

O divisor entre os dois painéis pode ser arrastado para dar mais espaço ao vídeo ou à auditoria.

### Atalhos de teclado

| Tecla | Ação |
|---|---|
| `Espaço` | Liga ou desliga a câmera |
| `S` | Salva uma imagem com os rótulos marcados na área de coleta |
| `Esc` | Limpa a busca da auditoria |

Os atalhos ficam desativados enquanto você digita no campo de busca.

### Testar o modelo com uma foto

```bash
python reconhecer.py
```

Abre uma janela para escolher a imagem e mostra, para cada pessoa encontrada, a confiança de cada EPI e se ele conta como "usando". Também aceita o caminho direto: `python reconhecer.py foto.jpg`.

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
| **Ao vivo** | Imagem atual da câmera com as caixas, o setor em fiscalização e o que ele exige, status da catraca e o que falta para cada pessoa. Atualiza a cada segundo. |
| **Hoje** | Eventos, liberados, negados e taxa de liberação do dia, com o total do histórico abaixo de cada número. |
| **Eventos por hora** | Gráfico de barras do dia. Passar o mouse numa hora mostra os números. |
| **Eventos de auditoria** | Os eventos mais recentes, com miniatura da foto, setor, EPIs exigidos e o que faltava, além de filtros e busca. Clicar numa linha abre a foto em tamanho grande. |

O gerente **vê** qual setor está sendo fiscalizado, mas não consegue mudá-lo: a escolha do setor é feita só no aplicativo.

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

1. **Detector de rosto (YuNet)**: encontra ONDE estão as pessoas. A partir de cada rosto, o programa monta uma caixa maior cobrindo cabeça, tronco e mãos, que é onde ficam o capacete, os óculos, o colete e as luvas.
2. **Classificador de EPI (MobileNetV2)**: recebe o recorte de cada pessoa e devolve **uma probabilidade por equipamento**, cada uma independente das outras:

   ```
   capacete 0.97    óculos 0.12    colete 0.88    luvas 0.05
   ```

   Isso se chama classificação *multirrótulo*: em vez de escolher uma classe entre várias, a rede responde várias perguntas de sim ou não. Por isso a camada final usa a função *sigmoid* (cada saída vai de 0 a 1 sozinha) em vez de *softmax* (que obrigaria as saídas a somarem 1). O treino é por *transfer learning*: a MobileNetV2 já vem treinada com milhões de imagens e só a camada final é treinada com as fotos do projeto.

### Detectar é diferente de exigir

Esta é a ideia central da fiscalização por setor. O modelo **sempre avalia todos os EPIs** que conhece. Quais deles são obrigatórios é uma decisão separada, tomada depois, com base no setor escolhido:

| A pessoa está usando | Setor exige | Resultado |
|---|---|---|
| Capacete, colete | Capacete, colete | Liberado |
| Capacete, colete | Luvas | Negado (falta: luvas) |
| Só luvas | Luvas | Liberado |
| Nada | Nenhum EPI | Liberado |

Como a classificação não depende do setor, trocar de setor tem efeito imediato: basta refazer a comparação, sem analisar a imagem de novo.

### A linha de análise

Para cada frame da câmera:

```
 frame ──> DETECTAR ──> RASTREAR ──> CLASSIFICAR ──> DECIDIR ──> AUDITAR
           onde estão    quem é      quais EPIs      compara com  grava se a
           as pessoas    quem        cada um usa?    o setor      decisão mudou
```

- **Detectar**: o YuNet roda numa cópia reduzida do frame (mais rápido).
- **Rastrear**: cada caixa é ligada à pessoa do frame anterior pela sobreposição entre as caixas (IoU). Assim cada pessoa mantém um número fixo (`#1`, `#2`...) e um histórico próprio, mesmo com várias pessoas em fila.
- **Classificar**: todas as pessoas são classificadas numa única chamada ao modelo. Isso acontece no intervalo configurado, e mais rápido quando aparece alguém novo.
- **Decidir**: para cada EPI, usa a **média** das últimas 5 classificações. O EPI conta como "usando" se a média passar da confiança mínima. A pessoa é liberada se estiver usando todos os EPIs exigidos no setor.
- **Auditar**: um evento é gravado quando sai a primeira decisão de uma pessoa e sempre que essa decisão muda (inclusive por troca de setor).

### Regra da catraca

| Situação | Status |
|---|---|
| Ninguém na imagem | Aguardando |
| Alguém ainda sem decisão | Analisando |
| Pelo menos uma pessoa sem algum EPI exigido | **Acesso negado** |
| Todas as pessoas com os EPIs exigidos | **Acesso liberado** |

Um EPI exigido que o modelo não sabe reconhecer conta como faltando: na dúvida, o sistema nega.

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
│   │   ├── epis.py             Quais EPIs o modelo instalado reconhece
│   │   ├── detector.py         Encontra as pessoas no frame (YuNet)
│   │   ├── rastreador.py       Mantém a identidade de cada pessoa
│   │   ├── classificador.py    Modelo de EPI: uma probabilidade por equipamento
│   │   ├── decisao.py          Compara o que a pessoa usa com o que o setor exige
│   │   └── anotacao.py         Desenha caixas e rótulos na imagem
│   │
│   ├── servicos/           O que acontece ao redor do núcleo
│   │   ├── camera.py           Captura da webcam em thread própria
│   │   ├── analisador.py       Linha de análise em thread própria
│   │   ├── auditoria.py        Log em CSV e fotos de evidência
│   │   ├── dataset.py          Salva imagens de treino com os rótulos
│   │   └── preferencias.py     Lembra o setor e os EPIs selecionados
│   │
│   ├── interface/          A janela (Tkinter)
│   │   ├── tema.py                  Cores, fontes e estilos
│   │   ├── painel_monitoramento.py  Vídeo, status, fiscalização, ajustes e coleta
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
├── dataset/                Dados de treino (não vão para o repositório)
│   ├── epis/               Imagens coletadas pelo aplicativo
│   └── rotulos.csv         Quais EPIs aparecem em cada imagem
├── preferencias.json       Última seleção de setor (gerado pelo programa)
└── auditoria/              Gerada pelo programa
    ├── log_auditoria.csv
    └── imagens/            Fotos de evidência
```

### Princípios da organização

- **Camadas com direção única**: a interface usa os serviços, os serviços usam o núcleo. O núcleo não conhece ninguém acima dele, por isso pode ser testado sem câmera e sem janela.
- **Configuração em um lugar só**: nenhum módulo tem número fixo espalhado; tudo vem de `safetech/config.py`.
- **EPIs vindos do arquivo**: quais EPIs o modelo reconhece, e em que ordem, é lido de `epis.json`, gravado junto com o modelo no treino. Assim o aplicativo nunca troca um equipamento por outro.
- **Detectar separado de exigir**: o classificador não sabe nada de setores, e a regra de decisão não sabe nada de imagens.
- **Painéis sem lógica**: os painéis apenas exibem dados e avisam a janela principal quando o usuário faz algo.

---

## Coleta de imagens e re-treino

Para o modelo reconhecer cada equipamento separadamente, ele precisa de imagens **rotuladas item a item**: para cada foto, quais EPIs a pessoa está usando. O próprio aplicativo faz isso.

### Passo a passo

1. Abra o programa e ligue a câmera.
2. Na área **Coleta de imagens**, marque o que a pessoa na câmera **está usando agora**. Por exemplo, se ela está só de capacete e luvas, marque `Capacete` e `Luvas`.
3. Pressione `S` (ou clique em **Salvar imagem**) várias vezes, variando posição, distância, ângulo e iluminação.
4. Troque os equipamentos, **atualize as caixas marcadas** e repita. O aviso no rodapé repete os rótulos de cada imagem salva: confira, porque um rótulo errado ensina o modelo errado.
5. Feche o programa e treine:

   ```bash
   python treinar.py
   ```

6. Abra o programa novamente. O modelo por EPI passa a ser usado automaticamente e a área de fiscalização é ativada.

### Como montar um bom dataset

- **Cada EPI precisa dos dois casos**: imagens com a pessoa usando e imagens sem usar. O treino se recusa a começar se algum EPI tiver só um dos casos.
- **Varie as combinações.** Se o capacete e o colete aparecem sempre juntos, o modelo não aprende a separá-los: ele aprende "capacete e colete" como uma coisa só. Colete também só capacete, só colete, só luvas, tudo junto e nada.
- **As mãos precisam aparecer** nas imagens com luvas (e nas sem luvas também). Mãos fora da imagem não ensinam nada sobre luvas.
- **Inclua casos que confundem**: boné no lugar do capacete, óculos de grau no lugar dos óculos de proteção, camiseta de cor forte no lugar do colete.
- **Varie pessoas, fundos e iluminação.**
- **Quantidade**: o treino exige pelo menos 20 imagens e avisa quando um EPI tem menos de 10 exemplos de cada caso. Para um resultado confiável, pense em 100 ou mais imagens de cada caso por EPI.
- Colete com **uma pessoa por vez**: todas as pessoas da imagem recebem os mesmos rótulos.

O resumo ao lado do título da coleta mostra o total de imagens e em quantas delas cada EPI aparece em uso.

### Onde os dados ficam

| Arquivo | Conteúdo |
|---|---|
| `dataset/epis/` | As imagens: o **recorte de cada pessoa**, que é exatamente o que o modelo recebe durante o uso |
| `dataset/rotulos.csv` | Uma linha por imagem: `arquivo, capacete, oculos, colete, luvas` (1 = usando, 0 = sem usar) |

A planilha pode ser aberta e corrigida em qualquer editor de planilhas. Se uma imagem for apagada, a linha dela é ignorada no treino.

Ao final, o treino mostra a **taxa de acerto de cada EPI** nas imagens de validação. É assim que se descobre qual equipamento precisa de mais imagens.

### Mudar a lista de EPIs

Os equipamentos fiscalizados ficam em `EPIS`, no `safetech/config.py`. O modelo aprende exatamente essa lista, então, ao acrescentar ou remover um EPI, é preciso **coletar as imagens de novo** (rotulando também o EPI novo) e treinar. A planilha antiga é renomeada, não apagada.

### Sobre o treinamento

- Rede base: MobileNetV2 pré-treinada (ImageNet), congelada.
- Camada treinada: média global, dropout de 20% e uma camada densa com uma saída *sigmoid* por EPI.
- Função de perda: *binary crossentropy*, que trata cada saída como uma pergunta de sim ou não separada.
- *Data augmentation*: espelhamento horizontal, rotação e zoom leves.
- 80% das imagens para treino e 20% para validação; 15 épocas; otimizador Adam.
- A normalização da MobileNetV2 fica dentro do modelo: quem usa o modelo entrega a imagem RGB 224x224 sem normalizar.

---

## Auditoria

O log fica em `auditoria/log_auditoria.csv`, e as fotos em `auditoria/imagens/`.

| Coluna | Conteúdo |
|---|---|
| `timestamp` | Data e hora do evento |
| `evento` | `ENTRADA` (primeira decisão da pessoa) ou `MUDANCA` (a decisão mudou) |
| `pessoa` | Identificação da pessoa na sessão, ex.: `P003` |
| `setor` | Setor que estava sendo fiscalizado |
| `exigidos` | EPIs obrigatórios naquele setor, ex.: `Capacete, Luvas` |
| `faltando` | EPIs exigidos que a pessoa não estava usando (vazio se nenhum) |
| `confiancas` | Confiança de cada EPI, ex.: `Capacete 97%, Luvas 12%` |
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
| `EPIS` | capacete, óculos, colete, luvas | Equipamentos fiscalizados. Mudar exige coletar e treinar de novo |
| `SETORES` | 5 setores de exemplo | Perfis prontos: nome do setor e os EPIs obrigatórios nele |
| `SETOR_PADRAO` | `"Acesso geral"` | Setor selecionado na primeira vez que o programa abre |
| `LIMIAR_CONFIANCA_PADRAO` | `0.80` | Confiança mínima para considerar que a pessoa usa um EPI (valor inicial do controle) |
| `INTERVALO_CLASSIFICACAO_PADRAO_SEG` | `1.0` | Intervalo de reclassificação (valor inicial do controle) |
| `TAMANHO_HISTORICO_DECISAO` | `5` | Quantas classificações entram na média da decisão |
| `AMOSTRAS_MINIMAS_DECISAO` | `2` | Classificações necessárias antes da primeira decisão |
| `INDICE_CAMERA` | `0` | Qual webcam usar |
| `LARGURA_CAPTURA` / `ALTURA_CAPTURA` | `640` / `480` | Resolução pedida à webcam |
| `LARGURA_DETECCAO` | `480` | Largura da cópia usada na detecção de rosto |
| `CONFIANCA_MINIMA_ROSTO` | `0.7` | Confiança mínima para aceitar um rosto |
| `MARGEM_*_ROSTO` | - | Quanto a caixa do rosto é expandida para cobrir tronco e mãos |
| `TEMPO_MAXIMO_AUSENTE_SEG` | `1.0` | Tempo que uma pessoa pode sumir sem perder o número |
| `EPOCAS_TREINO` | `15` | Épocas do treinamento |
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
| **"Nenhum modelo encontrado em 'modelos/'"** | Recupere os arquivos de `modelos/` do repositório, ou colete imagens e rode `python treinar.py`. |
| **A área de fiscalização está cinza** | O programa está usando o modelo antigo, que não distingue os EPIs. Colete imagens rotuladas e rode `python treinar.py`. |
| **Um EPI específico erra muito** | Veja a taxa de acerto dele no fim do treino e colete mais imagens desse EPI, nos dois casos (usando e sem usar) e em combinações variadas. |
| **O treino diz que falta um caso** | Algum EPI só tem imagens "usando" ou só "sem usar". Colete o caso que falta. |
| **Luvas nunca são reconhecidas** | As mãos precisam aparecer dentro da caixa da pessoa. Afaste-se um pouco da câmera ou aumente `MARGEM_INFERIOR_ROSTO`. |
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
- **O modelo por EPI precisa ser treinado por você.** O repositório traz só o modelo antigo; a fiscalização por equipamento depende de coletar imagens rotuladas e treinar.
- **O modelo olha o recorte inteiro da pessoa, reduzido para 224x224.** Itens pequenos, como óculos e luvas, são os mais difíceis e os que mais dependem de um dataset grande e variado.
- **As mãos precisam estar visíveis** para as luvas serem avaliadas. Mãos fora da imagem ou atrás do corpo contam como "sem luvas".
- **Pessoas muito próximas** podem ter as caixas sobrepostas, e o equipamento de uma influenciar o resultado da outra.
- **O número de imagens necessárias é alto.** Com poucas dezenas de imagens, o modelo erra em pessoas, fundos e iluminações que não viu no treino.
- **O número da pessoa não é identidade.** Quem sai da imagem e volta recebe um número novo.

Próximos passos possíveis:

- Confirmação por voz da Ordem de Serviço (etapa futura do desafio).
- Um detector de objetos (que localiza cada equipamento na imagem), mais preciso para itens pequenos como óculos e luvas.
- Detector de corpo inteiro, para não depender do rosto.
- Edição dos setores pela própria tela, sem mexer no `config.py`.
- Integração com uma catraca real (acionamento por relé ou porta serial).
- Exportação de relatórios da auditoria por período.
