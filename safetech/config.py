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

# 0 = webcam padrão do computador
INDICE_CAMERA = 0

# No Windows o backend DirectShow abre a webcam bem mais rápido
# que o backend padrão (MSMF).
USAR_DIRECTSHOW = True

# Resolução pedida à webcam (ela usa a mais próxima que suportar).
# 640x480 mantém o vídeo fluido em qualquer webcam; resoluções
# maiores deixam a imagem mais nítida, mas podem derrubar o FPS.
LARGURA_CAPTURA = 640
ALTURA_CAPTURA = 480


# ============================================================
# DETECÇÃO E RASTREAMENTO DE PESSOAS
# ============================================================

# O detector de rosto roda numa cópia reduzida do frame: é muito
# mais rápido e, para achar rostos, a precisão é praticamente a mesma.
LARGURA_DETECCAO = 480

# Confiança mínima (0 a 1) para aceitar um rosto detectado
CONFIANCA_MINIMA_ROSTO = 0.7

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

# Quanto tempo uma pessoa pode "sumir" (detector falhou, virou o
# rosto) antes de ser esquecida.
TEMPO_MAXIMO_AUSENTE_SEG = 1.0

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
# um equipamento. Ajustável na tela. Mais alto = mais rigoroso.
LIMIAR_CONFIANCA_PADRAO = 0.80

# De quanto em quanto tempo (segundos) cada pessoa é reclassificada.
# Ajustável na tela.
INTERVALO_CLASSIFICACAO_PADRAO_SEG = 1.0

# Quando aparece alguém novo, as primeiras classificações são feitas
# neste intervalo curto, para a decisão sair rápido.
INTERVALO_CLASSIFICACAO_RAPIDA_SEG = 0.25

# A decisão de cada pessoa usa a MÉDIA das últimas N classificações,
# não só a última. Isso evita o status "piscar" entre liberado e
# negado por causa de um único frame ruim.
TAMANHO_HISTORICO_DECISAO = 5

# Quantas classificações são necessárias antes da primeira decisão
AMOSTRAS_MINIMAS_DECISAO = 2


# ============================================================
# INTERFACE
# ============================================================

TITULO_JANELA = "SafeTech Entry - Reconhecimento de EPI"
TAMANHO_INICIAL_JANELA = "1360x860"
TAMANHO_MINIMO_JANELA = (1080, 740)

# Intervalo (ms) do laço de atualização da tela. 33 ms = ~30 quadros/s
INTERVALO_TELA_MS = 33

# Máximo de linhas exibidas na tabela de auditoria (as mais recentes).
# Os totais dos cartões continuam contando o histórico inteiro.
MAXIMO_LINHAS_TABELA = 500


# ============================================================
# PAINEL WEB DO GERENTE (somente leitura)
# ============================================================
#
# Página de acompanhamento acessível pelo navegador. Ela só MOSTRA
# dados (status ao vivo, eventos e fotos); não existe nenhuma rota
# que altere configurações ou apague registros.
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
PAINEL_WEB_SENHA = "safetech"

# Quantos eventos (os mais recentes) o painel web lista
PAINEL_WEB_MAXIMO_EVENTOS = 300


# ============================================================
# TREINAMENTO (usado pelo treinar.py)
# ============================================================

LOTE_TREINO = 32
EPOCAS_TREINO = 15
FRACAO_VALIDACAO = 0.20
SEMENTE_TREINO = 123
TAXA_APRENDIZADO = 0.001
TAXA_DROPOUT = 0.20

# Mínimo de imagens rotuladas para o treino começar
MINIMO_IMAGENS_TREINO = 20

# Para cada EPI, o treino avisa se houver menos exemplos do que isto
# "usando" ou "não usando" (o modelo precisa ver os dois casos)
MINIMO_EXEMPLOS_POR_CASO = 10
