"""
Configurações do SafeTech Entry.

Tudo o que pode ser ajustado no projeto fica neste arquivo: caminhos,
parâmetros do modelo, da câmera, da análise e do treinamento. Os outros
módulos apenas LEEM daqui, nenhum deles tem número "mágico" espalhado.
"""

from pathlib import Path


# ============================================================
# CAMINHOS DO PROJETO
# ============================================================
#
# RAIZ é a pasta do projeto (um nível acima da pasta "safetech").
# Todos os outros caminhos partem dela, então o projeto funciona
# independente da pasta de onde o Python for executado.
# ============================================================

RAIZ = Path(__file__).resolve().parent.parent

# Modelos (gerados pelo treinar.py ou baixados)
PASTA_MODELOS = RAIZ / "modelos"

# Modelo POR EPI: uma resposta independente para cada equipamento.
# epis.json guarda quais EPIs o modelo conhece, na ordem das saídas.
ARQUIVO_MODELO_EPIS = PASTA_MODELOS / "modelo_epis.keras"
ARQUIVO_EPIS = PASTA_MODELOS / "epis.json"

# Modelo ANTIGO (só "com_epi" / "sem_epi" para o conjunto todo). É
# usado apenas enquanto o modelo por EPI ainda não foi treinado.
ARQUIVO_MODELO_LEGADO = PASTA_MODELOS / "modelo_epi.keras"
ARQUIVO_CLASSES_LEGADO = PASTA_MODELOS / "classes.json"

ARQUIVO_MODELO_ROSTO = PASTA_MODELOS / "face_detection_yunet_2023mar.onnx"

# De onde baixar o detector de rosto, caso o arquivo esteja faltando
URL_MODELO_ROSTO = (
    "https://github.com/opencv/opencv_zoo/raw/main/models/"
    "face_detection_yunet/face_detection_yunet_2023mar.onnx"
)

# Detector de corpo inteiro (YOLOX), usado no modo "vigilancia". O arquivo
# tem cerca de 35 MB e não vai para o repositório: é baixado à parte.
# Sem ele o programa funciona normalmente, só com o modo "catraca".
ARQUIVO_MODELO_CORPO = PASTA_MODELOS / "object_detection_yolox_2022nov.onnx"

URL_MODELO_CORPO = (
    "https://github.com/opencv/opencv_zoo/raw/main/models/"
    "object_detection_yolox/object_detection_yolox_2022nov.onnx"
)

# Imagens de treino do modelo por EPI e a planilha de rótulos, que
# diz, para cada imagem, quais equipamentos a pessoa está usando.
PASTA_DATASET = RAIZ / "dataset"
PASTA_IMAGENS_DATASET = PASTA_DATASET / "epis"
ARQUIVO_ROTULOS = PASTA_DATASET / "rotulos.csv"

# Última seleção de setor/EPIs feita na tela (lembrada entre execuções)
ARQUIVO_PREFERENCIAS = RAIZ / "preferencias.json"

# Log de auditoria (CSV) e fotos de evidência
PASTA_AUDITORIA = RAIZ / "auditoria"
ARQUIVO_LOG_AUDITORIA = PASTA_AUDITORIA / "log_auditoria.csv"
PASTA_IMAGENS_AUDITORIA = PASTA_AUDITORIA / "imagens"

# Linhas excluídas da tabela de auditoria. Excluir não apaga: a linha
# vai para um CSV à parte (com a data da exclusão) e a foto vai junto,
# para a pasta de imagens dos excluídos.
PASTA_EXCLUIDOS = PASTA_AUDITORIA / "excluidos"

# Fotos tiradas pelo botão "Capturar foto" da câmera de uma área (a
# imagem do momento com as caixas e o carimbo de data, hora e área).
# Não fazem parte do log: são registros avulsos do operador.
PASTA_CAPTURAS = PASTA_AUDITORIA / "capturas"

# Relatórios do botão "Salvar relatório" da auditoria: uma pasta por
# relatório, com o relatório em HTML e a cópia da foto do evento.
PASTA_RELATORIOS = PASTA_AUDITORIA / "relatorios"

# Registro de erros e acontecimentos (logs/safetech.log). Quando o
# arquivo passa do tamanho máximo, vira safetech.log.1 e um novo começa;
# ficam guardados os últimos QUANTIDADE_LOGS_GUARDADOS.
PASTA_LOGS = RAIZ / "logs"
NOME_ARQUIVO_LOG = "safetech.log"
TAMANHO_MAXIMO_LOG_BYTES = 1_000_000
QUANTIDADE_LOGS_GUARDADOS = 5

# O que vai para o arquivo: "INFO" (acontecimentos e erros) ou
# "DEBUG" (muito mais detalhe, para investigar um problema).
NIVEL_LOG = "INFO"

# Largura máxima (em pixels) da página e da foto no relatório HTML.
# A foto em tamanho real fica na pasta; isto só limita a exibição.
LARGURA_FOTO_RELATORIO = 960


# ============================================================
# EQUIPAMENTOS (EPIs) E SETORES
# ============================================================
#
# EPIS: os equipamentos que o sistema fiscaliza.
#   chave -> nome mostrado na tela
# A chave (sem acento e sem espaço) é usada nos arquivos e nos
# rótulos desenhados no vídeo.
#
# ATENÇÃO: o modelo aprende exatamente esta lista. Se você acrescentar
# ou remover um EPI, é preciso coletar imagens rotuladas de novo e
# rodar o treinar.py.
# ============================================================

EPIS = {
    "capacete": "Capacete",
    "oculos": "Óculos",
    "colete": "Colete",
    "luvas": "Luvas",
}

# SETORES: perfis prontos de fiscalização.
#   nome do setor -> EPIs obrigatórios nele
# Escolher um setor na tela marca esses EPIs de uma vez; depois ainda
# dá para ajustar marcando ou desmarcando cada um.
SETORES = {
    "Acesso geral": ["capacete", "oculos", "colete", "luvas"],
    "Canteiro de obras": ["capacete", "colete"],
    "Laboratório": ["oculos", "luvas"],
    "Manuseio de materiais": ["luvas"],
    "Área de circulação": ["colete"],
}

# Setor selecionado na primeira vez que o programa abre
SETOR_PADRAO = "Acesso geral"

# Nome mostrado quando os EPIs marcados não batem com nenhum setor
SETOR_PERSONALIZADO = "Personalizado"


# ============================================================
# MODELO DE EPI
# ============================================================

# Tamanho de entrada da MobileNetV2 (largura, altura)
TAMANHO_IMAGEM = (224, 224)

# --- Modo de compatibilidade (modelo antigo) ------------------
#
# O modelo antigo não distingue os equipamentos: ele só sabe dizer se
# a pessoa está com o conjunto completo. Nesse modo o sistema trabalha
# com um único "EPI" fictício, representado pela chave abaixo.
EPI_CONJUNTO = "conjunto"
NOME_EPI_CONJUNTO = "EPI completo"

# Classe do modelo antigo (em classes.json) que significa "com EPI"
CLASSE_LIBERA_ACESSO = "com_epi"


# ============================================================
# CÂMERA
# ============================================================

# Câmera usada na primeira abertura (0 = webcam padrão do computador).
# Depois disso vale a câmera escolhida na caixa de seleção da tela,
# que fica salva em preferencias.json.
INDICE_CAMERA = 1

# Quantos índices (0, 1, 2...) o programa testa ao procurar câmeras para
# a caixa de seleção. Aumente se você tiver muitas câmeras conectadas;
# diminuir deixa a busca inicial mais rápida.
MAXIMO_CAMERAS_PROCURADAS = 5

# No Windows o backend DirectShow abre a webcam bem mais rápido
# que o backend padrão (MSMF).
USAR_DIRECTSHOW = True

# Resolução pedida à webcam (ela usa a mais próxima que suportar).
# 640x480 mantém o vídeo fluido em qualquer webcam; resoluções
# maiores deixam a imagem mais nítida, mas podem derrubar o FPS.
#
# 1280x720 é o indicado para uma câmera geral (várias pessoas, cada
# uma pequena na imagem): sobra mais detalhe por pessoa para a IA
# avaliar os equipamentos. Se o vídeo ficar lento, use 640 e 480.
LARGURA_CAPTURA = 1280
ALTURA_CAPTURA = 720


# ============================================================
# CÂMERA IP (pela rede)
# ============================================================
#
# Além das webcams, o programa abre câmeras pela rede, adicionadas na
# tela ("Adicionar câmera IP..." na lista de câmeras). O endereço é
# do tipo rtsp://... (câmeras de segurança) ou http://... (câmeras
# simples e apps de celular como o "IP Webcam").
#
# A resolução de uma câmera IP é definida na própria câmera, não aqui.
# Prefira o "substream" (stream de qualidade menor): a IA não precisa
# de 4K e a análise fica mais rápida.
# ============================================================

# Tempo máximo esperando a câmera responder ao conectar. Sem limite,
# um endereço errado deixaria o programa "Conectando..." para sempre.
TEMPO_LIMITE_CONEXAO_IP_MS = 8000

# Tempo máximo esperando um frame depois de conectado. Passou disso,
# a conexão é considerada perdida e o programa tenta reconectar.
TEMPO_LIMITE_LEITURA_IP_MS = 5000

# Espera entre duas tentativas de reconexão quando a rede cai.
INTERVALO_RECONEXAO_IP_SEG = 3.0

# Webcam (USB) que para de responder (cabo frouxo, hub desligado):
# True = o programa tenta reabri-la sozinho, de tempos em tempos, como
# faz com a câmera IP. False = mostra o erro e espera o usuário clicar
# em "Tentar novamente".
RECONECTAR_WEBCAM = True

# Espera entre duas tentativas de reabrir a webcam
INTERVALO_RECONEXAO_WEBCAM_SEG = 2.0

# Vídeo RTSP por TCP em vez de UDP: um pouco mais de atraso, mas sem
# imagens cinzas ou borradas quando a rede perde pacotes (UDP não
# reenvia o que se perdeu).
RTSP_POR_TCP = True


# ============================================================
# CATRACA DE DEMONSTRAÇÃO (ESP32 pelo cabo USB)
# ============================================================
#
# A maquete de catraca (pasta catraca_esp32/) pode receber o status
# deste programa pelo cabo USB. O programa escreve uma linha de texto
# na porta serial algumas vezes por segundo; o ESP32 move a cancela.
#
# Também funciona pelo Wi-Fi (o ESP32 pergunta ao painel web). Os dois
# caminhos podem estar ligados ao mesmo tempo: o ESP32 usa o cabo
# enquanto ele estiver mandando dados e, se o cabo sair, tenta o Wi-Fi.
#
# Com a porta aberta aqui, a Arduino IDE não consegue gravar a placa
# nem abrir o Monitor Serial. Para gravar, feche o programa ou ponha
# CATRACA_SERIAL_ATIVA em False.
# ============================================================

# Liga ou desliga o envio pelo cabo. Sem ESP32 plugado não faz mal:
# o programa só fica procurando a placa em segundo plano.
CATRACA_SERIAL_ATIVA = True

# Porta do ESP32 (ex.: "COM3"). Vazio = procurar sozinho a primeira
# placa ESP32 encontrada no USB.
CATRACA_PORTA = ""

# Velocidade da comunicação. Precisa ser igual à do firmware
# (VELOCIDADE_SERIAL no config.h da catraca).
CATRACA_VELOCIDADE_SERIAL = 115200

# De quanto em quanto tempo o status é enviado. 0,3 s deixa a cancela
# reagir rápido. O ESP32 considera o programa perdido se passar de
# TEMPO_SEM_RESPOSTA_MS (3 s no firmware) sem receber nada.
CATRACA_INTERVALO_ENVIO_SEG = 0.3

# Quanto tempo esperar antes de procurar o ESP32 de novo, quando ele
# não foi encontrado ou a porta estava ocupada.
CATRACA_INTERVALO_PROCURA_SEG = 2.0

# Tempo máximo para uma escrita no cabo. Passou disso, a porta é
# considerada com problema e o programa volta a procurá-la.
CATRACA_TEMPO_LIMITE_ESCRITA_SEG = 1.0


# ============================================================
# DETECÇÃO E RASTREAMENTO DE PESSOAS
# ============================================================

# O detector de rosto roda em cópias reduzidas do frame, em DUAS
# escalas, e junta os resultados. Cada escala enxerga uma faixa de
# tamanho de rosto (medido neste projeto):
#
#   640 px -> acha rostos pequenos de uma câmera geral (24 de 24
#             pessoas em 1280x720), mas não acha um rosto grande e
#             próximo;
#   320 px -> acha o rosto próximo (catraca), mas só 7 das 24 pequenas.
#
# Com as duas, a mesma configuração serve para os dois usos. Uma
# terceira escala maior (ex.: 960) acha rostos ainda menores, ao custo
# de mais tempo por frame.
LARGURAS_DETECCAO = (640, 320)

# Sobreposição (IoU) acima da qual duas caixas, achadas em escalas
# diferentes, são consideradas a mesma pessoa.
IOU_MESMA_PESSOA = 0.4

# Quantos candidatos a rosto o detector mantém antes de eliminar os
# repetidos. Precisa ser alto: com um valor baixo (era 50) o detector
# só encontrava parte das pessoas quando havia muita gente na imagem.
MAXIMO_CANDIDATOS_ROSTO = 5000

# Confiança mínima (0 a 1) para aceitar um rosto detectado
CONFIANCA_MINIMA_ROSTO = 0.7

# --- Modo de operação ------------------------------------------
#
# O sistema trabalha de dois jeitos. O usuário alterna na tela, e a
# escolha fica salva.
#
#   "catraca"    -> controle de ACESSO: uma pessoa por vez, perto da
#                   câmera e de frente. Acha a pessoa pelo ROSTO
#                   (rápido). A decisão é LIBERADO ou NEGADO, e a
#                   catraca física (ESP32) abre ou fica fechada.
#
#   "vigilancia" -> fiscalização de uma ÁREA: câmera geral, várias
#                   pessoas de costas, de lado, andando e se cruzando.
#                   Acha a pessoa pelo CORPO INTEIRO (mais lento). Não
#                   há acesso a liberar: só se verifica se cada pessoa
#                   está EM CONFORMIDADE (com os EPIs exigidos) e se
#                   registra. A catraca física fica desligada.
#
# A regra de decisão é a mesma nos dois (os EPIs exigidos no setor);
# muda o detector, o que se mostra e se a catraca obedece.
MODO_CATRACA = "catraca"
MODO_VIGILANCIA = "vigilancia"

# chave -> nome mostrado na tela
MODOS_DETECCAO = {
    MODO_CATRACA: "Catraca",
    MODO_VIGILANCIA: "Vigilância",
}

# Nomes usados por versões anteriores do programa (no preferencias.json),
# convertidos para os atuais ao carregar
MODOS_ANTIGOS = {
    "rosto": MODO_CATRACA,
    "corpo": MODO_VIGILANCIA,
}

# Modo usado na primeira vez que o programa abre
MODO_DETECCAO_PADRAO = MODO_CATRACA


# ============================================================
# ÁREAS (várias câmeras ao mesmo tempo)
# ============================================================
#
# Cada ÁREA é uma câmera com a sua própria fiscalização: nome, setor,
# EPIs exigidos e modo (catraca ou vigilância). Cada uma abre numa aba
# da tela principal e tem a sua própria linha de análise (thread).
#
# A auditoria é uma só para todas: cada evento guarda de qual área veio.
# ============================================================

# Nome da primeira área (e das gravadas antes de existirem áreas)
NOME_AREA_PADRAO = "Principal"

# Limite de áreas abertas ao mesmo tempo. Cada área é uma câmera e uma
# análise rodando juntas: com muitas, o computador não dá conta e todas
# ficam lentas.
MAXIMO_AREAS = 6

# Textos de cada modo. "ok" é quem está com todos os EPIs exigidos;
# "irregular" é quem não está.
#
#   resultado_*  -> tabela de auditoria, relatório e painel web
#   faixa_*      -> faixa de status grande da tela e painel web
#                   (ok, irregular, analisando e sem ninguém)
#   palavra_*    -> palavra desenhada no vídeo, junto da caixa (sem
#                   acento: a fonte do OpenCV não tem acentos)
TEXTOS_POR_MODO = {
    MODO_CATRACA: {
        "resultado_ok": "Liberado",
        "resultado_irregular": "Negado",
        "faixa_ok": "ACESSO LIBERADO",
        "faixa_irregular": "ACESSO NEGADO",
        "palavra_ok": "OK",
        "palavra_irregular": "NEGADO",
        "faixa_analisando": "ANALISANDO",
        "faixa_sem_pessoas": "AGUARDANDO",
        "lugar": "na frente da câmera",
    },
    MODO_VIGILANCIA: {
        "resultado_ok": "Conforme",
        "resultado_irregular": "Não conforme",
        "faixa_ok": "EM CONFORMIDADE",
        "faixa_irregular": "NÃO CONFORME",
        "palavra_ok": "OK",
        "palavra_irregular": "SEM EPI",
        "faixa_analisando": "ANALISANDO",
        "faixa_sem_pessoas": "AGUARDANDO",
        "lugar": "na área",
    },
}

# --- Detector de corpo -----------------------------------------

# Largura da cópia do frame analisada pelo detector de corpo. É o que
# mais pesa na velocidade (medido nesta máquina: ~150 ms com entrada
# quadrada de 640, ~70 ms com 416). Maior mantém o detalhe para pessoas
# pequenas ao fundo. 512 foi o melhor equilíbrio nas fotos reais da
# obra: achou as mesmas pessoas que 640, em ~77 ms contra ~113 ms.
LARGURA_DETECCAO_CORPO = 512

# Confiança mínima (0 a 1) para aceitar uma pessoa detectada
CONFIANCA_MINIMA_CORPO = 0.5

# Sobreposição (IoU) acima da qual duas caixas do detector de corpo
# são tratadas como a mesma pessoa. Mais alto = separa melhor pessoas
# coladas uma na outra, mas pode duplicar a mesma pessoa.
IOU_REPETICAO_CORPO = 0.5

# A caixa do rosto é expandida para cobrir cabeça, tronco e mãos: é
# onde ficam o capacete, os óculos, o colete e as luvas. Os valores
# são múltiplos do tamanho do rosto. A caixa é larga e comprida de
# propósito, para as mãos aparecerem (sem elas não há como ver luvas).
# Largura maior que esta faz a caixa invadir a pessoa ao lado na fila.
MARGEM_LATERAL_ROSTO = 1.2
MARGEM_SUPERIOR_ROSTO = 0.7
MARGEM_INFERIOR_ROSTO = 4.0

# Sobreposição mínima (IoU, de 0 a 1) para considerar que uma caixa
# detectada agora é a mesma pessoa do frame anterior.
IOU_MINIMO_RASTREIO = 0.2

# Por quanto tempo a caixa de uma pessoa continua NA TELA depois que
# o detector deixa de vê-la (falhou num frame, ela virou o rosto).
TEMPO_MAXIMO_AUSENTE_SEG = 1.0

# Por quanto tempo uma pessoa que sumiu continua LEMBRADA (número,
# histórico e decisão). Se ela reaparecer perto de onde estava dentro
# desse prazo, é reconhecida como a mesma pessoa, sem gerar um novo
# evento nem uma nova foto de evidência. Numa câmera geral, onde os
# rostos somem e voltam o tempo todo, é isso que evita as repetições.
TEMPO_MEMORIA_PESSOA_SEG = 8.0

# Distância máxima entre onde a pessoa estava e onde reapareceu para
# ser considerada a mesma, medida em "larguras da caixa" dela. O raio
# começa em BASE e cresce a cada segundo de sumiço (ela pode ter
# andado), até o limite MAXIMA.
DISTANCIA_BASE_RASTREIO = 0.5
DISTANCIA_POR_SEGUNDO_AUSENTE = 0.8
DISTANCIA_MAXIMA_RASTREIO = 2.5

# --- Previsão de movimento -------------------------------------
#
# O rastreador estima a velocidade de cada pessoa e a procura onde
# ela DEVE estar, não onde estava. Ajuda a acompanhar quem anda e a
# não trocar duas pessoas que se cruzam.

# Por quanto tempo (segundos) a previsão continua avançando depois
# que a pessoa deixa de ser detectada. 0 desliga a previsão.
TEMPO_MAXIMO_PREVISAO_SEG = 1.0

# Quanto a velocidade medida agora pesa sobre a estimada antes (0 a 1).
# Mais baixo = estimativa mais estável; mais alto = reage mais rápido.
SUAVIZACAO_VELOCIDADE = 0.4

# Suavização da posição da caixa (0 a 1). Mais alto = acompanha mais
# rápido; mais baixo = caixa mais estável, sem tremer.
SUAVIZACAO_CAIXA = 0.6

# Limite de análises por segundo da linha de detecção. Acima disso
# só se gasta processador, sem ganho visível.
TAXA_MAXIMA_ANALISE_HZ = 15


# ============================================================
# DECISÃO DE ACESSO
# ============================================================

# Confiança mínima (0 a 1) para considerar que a pessoa ESTÁ usando
# um equipamento. Ajustável em Configurações > Análise (o valor
# escolhido fica salvo). Mais alto = mais rigoroso.
LIMIAR_CONFIANCA_PADRAO = 0.80

# Faixa do controle deslizante da confiança (0 a 1). Abaixo de 50%,
# "usando" seria quase um chute; 99% é o máximo que ainda libera.
LIMIAR_CONFIANCA_MINIMO = 0.50
LIMIAR_CONFIANCA_MAXIMO = 0.99

# De quanto em quanto tempo (segundos) cada pessoa é reclassificada.
# Ajustável em Configurações > Análise (o valor fica salvo).
INTERVALO_CLASSIFICACAO_PADRAO_SEG = 1.0

# Faixa do controle deslizante do intervalo (segundos)
INTERVALO_CLASSIFICACAO_MINIMO_SEG = 0.3
INTERVALO_CLASSIFICACAO_MAXIMO_SEG = 5.0

# Depois de mexer num controle deslizante, espera este tempo parado
# antes de gravar o valor em preferencias.json. Sem isso, o arquivo
# seria regravado dezenas de vezes enquanto o controle é arrastado.
ESPERA_SALVAR_AJUSTES_MS = 600

# Quando aparece alguém novo, as primeiras classificações são feitas
# neste intervalo curto, para a decisão sair rápido.
INTERVALO_CLASSIFICACAO_RAPIDA_SEG = 0.25

# A decisão de cada pessoa usa a MEDIANA das últimas N classificações,
# não só a última. Isso evita o status "piscar" entre liberado e
# negado por causa de um único frame ruim.
TAMANHO_HISTORICO_DECISAO = 5

# Quantas classificações são necessárias antes da primeira decisão
AMOSTRAS_MINIMAS_DECISAO = 2

# --- Reinício automático da análise ------------------------------
#
# Se a análise de uma área quebrar (um erro inesperado no detector ou
# no modelo), ela não para de vez: espera um pouco e recomeça sozinha.
# Só desiste depois de várias falhas SEGUIDAS, para não ficar presa num
# erro que sempre se repete (aí o erro fica na tela e no log).

# Espera entre a falha e a nova tentativa
ESPERA_REINICIO_ANALISE_SEG = 3.0

# Falhas seguidas toleradas antes de desistir
MAXIMO_REINICIOS_ANALISE = 5

# Se a análise rodou bem por este tempo antes de falhar, a falha conta
# como nova (a contagem de falhas seguidas recomeça do zero)
TEMPO_ESTAVEL_ANALISE_SEG = 60.0

# Quantas classificações SEGUIDAS precisam discordar da decisão já
# registrada para a mudança ir para a auditoria (com foto nova). Evita
# registrar uma oscilação passageira como se a pessoa tivesse tirado
# ou colocado um equipamento.
CONFIRMACOES_PARA_MUDANCA = 3


# ============================================================
# INTERFACE
# ============================================================

TITULO_JANELA = "SafeTech Entry - Reconhecimento de EPI"

# Temas da tela: chave -> nome mostrado. O botão no cabeçalho alterna
# entre eles e a escolha fica salva. As cores de cada um ficam em
# safetech/interface/tema.py (PALETAS); o painel web tem o seu próprio
# botão de tema, guardado no navegador de cada gerente.
TEMAS = {"escuro": "Escuro", "claro": "Claro"}
TEMA_PADRAO = "escuro"

# Nome e frase de apresentação mostrados no cabeçalho da janela
NOME_PRODUTO = "SafeTech Entry"
SUBTITULO_PRODUTO = "Controle de acesso e fiscalização de EPI por visão computacional"
TAMANHO_INICIAL_JANELA = "1360x860"
TAMANHO_MINIMO_JANELA = (1080, 740)

# Tamanho da janela de Configurações (largura, altura), em pixels a
# 100% de escala do monitor
TAMANHO_JANELA_CONFIGURACOES = (720, 620)

# Intervalo (ms) do laço de atualização da tela. 33 ms = ~30 quadros/s
INTERVALO_TELA_MS = 33

# Máximo de linhas exibidas na tabela de auditoria (as mais recentes).
# Os totais dos cartões continuam contando o período inteiro.
MAXIMO_LINHAS_TABELA = 500

# Períodos da auditoria na tela: nome -> quantos dias para trás contam
# (0 = só hoje; None = todo o histórico). Os cartões de totais, a tabela
# e a exportação seguem o período escolhido.
PERIODOS_AUDITORIA = {
    "Hoje": 0,
    "Últimos 7 dias": 6,
    "Últimos 30 dias": 29,
    "Todo o histórico": None,
}

# Período escolhido quando o programa abre
PERIODO_AUDITORIA_PADRAO = "Todo o histórico"

# Exportação da auditoria (botão "Exportar CSV" e painel web). O Excel
# em português espera ";" como separador; a marca BOM ("utf-8-sig")
# faz ele mostrar os acentos certos ao abrir o arquivo com dois cliques.
SEPARADOR_CSV_EXPORTACAO = ";"
CODIFICACAO_CSV_EXPORTACAO = "utf-8-sig"

# Bipe do Windows quando alguém tem o acesso NEGADO numa área em modo
# catraca (como numa catraca de verdade). Na vigilância não toca: com
# muita gente seria um bipe atrás do outro.
ALERTA_SONORO_NEGADO = True

# Visão geral (todas as áreas lado a lado): quantas vezes por segundo
# cada quadro é redesenhado. Menos que o vídeo principal, porque são
# várias imagens ao mesmo tempo e a visão serve para acompanhar, não
# para analisar detalhes.
QUADROS_POR_SEGUNDO_VISAO_GERAL = 8

# --- Desenho sobre o vídeo e as fotos ---------------------------

# Tamanho da palavra junto da caixa de cada pessoa ("OK", "NEGADO"),
# numa imagem de 800 px de largura (cresce junto com a imagem). Abaixo
# de ~0.45 a palavra fica difícil de ler no vídeo da tela.
ESCALA_FONTE_ROTULO = 0.5

# Carimbo nas fotos de evidência: data e hora, área, pessoa e resultado
# gravados NA PRÓPRIA FOTO, numa faixa embaixo. Assim a foto continua
# dizendo de quando e de onde é mesmo copiada para fora do sistema.
CARIMBAR_EVIDENCIA = True

# ============================================================
# PAINEL WEB DO GERENTE (somente leitura)
# ============================================================
#
# Página de acompanhamento acessível pelo navegador. Ela só MOSTRA
# dados (status ao vivo, eventos e fotos); não existe nenhuma rota
# que altere configurações ou apague registros.
#
# Ligar, porta, acesso pela rede, usuário e senha se ajustam na TELA
# (Configurações > Painel web) e ficam salvos em preferencias.json (fora
# do repositório; a senha só como hash). Os valores abaixo valem apenas
# até o primeiro "Aplicar" naquela aba.
# ============================================================

# False desliga o painel web por completo
PAINEL_WEB_ATIVO = True

# "0.0.0.0" = acessível por outros aparelhos da mesma rede (o
# computador do gerente, um celular). "127.0.0.1" = só neste computador.
PAINEL_WEB_HOST = "0.0.0.0"

PAINEL_WEB_PORTA = 8080

# Login pedido pelo navegador. O painel mostra fotos de pessoas, então
# não deve ficar aberto na rede: TROQUE A SENHA antes de usar de verdade.
# Senha vazia ("") desliga o login.
PAINEL_WEB_USUARIO = "gerente"
PAINEL_WEB_SENHA = "1234"

# Tamanho mínimo de uma senha nova definida na tela
PAINEL_WEB_SENHA_MINIMA = 6

# Portas aceitas na tela. Abaixo de 1024 o Windows reserva para
# serviços do sistema.
PAINEL_WEB_PORTA_MINIMA = 1024
PAINEL_WEB_PORTA_MAXIMA = 65535

# Quantas vezes o cálculo do hash da senha é repetido. Mais = mais
# lento para quem tenta adivinhar senhas (e um pouco mais lento para
# conferir o login, ~0,1 s; o servidor guarda os logins já conferidos).
ITERACOES_HASH_SENHA = 200_000

# Quantos eventos (os mais recentes) o painel web lista
PAINEL_WEB_MAXIMO_EVENTOS = 300


# ============================================================
# TREINAMENTO (usado pelo treinar.py)
# ============================================================

LOTE_TREINO = 32

# Máximo de épocas. O treino pode parar antes (ver PACIENCIA_TREINO):
# 15 épocas se mostraram poucas, o erro ainda estava caindo no fim.
EPOCAS_TREINO = 40

# Se o erro na validação não melhorar por este número de épocas seguidas,
# o treino para e o modelo volta ao melhor momento. Evita treinar além
# do ponto em que a rede começa a decorar as imagens.
PACIENCIA_TREINO = 8

# True = erros em "usando" e em "sem usar" pesam de forma equilibrada em
# cada EPI, mesmo que um dos casos tenha bem menos imagens. Sem isso, a
# rede aprende a apostar sempre no caso mais comum (ex.: "tem capacete").
BALANCEAR_CLASSES = True
FRACAO_VALIDACAO = 0.20
SEMENTE_TREINO = 123
TAXA_APRENDIZADO = 0.001
TAXA_DROPOUT = 0.20

# Mínimo de imagens rotuladas para o treino começar
MINIMO_IMAGENS_TREINO = 20

# Para cada EPI, o treino avisa se houver menos exemplos do que isto
# "usando" ou "não usando" (o modelo precisa ver os dois casos)
MINIMO_EXEMPLOS_POR_CASO = 10
