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
ARQUIVO_MODELO = PASTA_MODELOS / "modelo_epi.keras"
ARQUIVO_CLASSES = PASTA_MODELOS / "classes.json"
ARQUIVO_MODELO_ROSTO = PASTA_MODELOS / "face_detection_yunet_2023mar.onnx"

# De onde baixar o detector de rosto, caso o arquivo esteja faltando
URL_MODELO_ROSTO = (
    "https://github.com/opencv/opencv_zoo/raw/main/models/"
    "face_detection_yunet/face_detection_yunet_2023mar.onnx"
)

# Imagens de treino: uma subpasta por classe (dataset/com_epi, dataset/sem_epi)
PASTA_DATASET = RAIZ / "dataset"

# Log de auditoria (CSV) e fotos de evidência
PASTA_AUDITORIA = RAIZ / "auditoria"
ARQUIVO_LOG_AUDITORIA = PASTA_AUDITORIA / "log_auditoria.csv"
PASTA_IMAGENS_AUDITORIA = PASTA_AUDITORIA / "imagens"


# ============================================================
# MODELO DE EPI
# ============================================================

# Tamanho de entrada da MobileNetV2 (largura, altura)
TAMANHO_IMAGEM = (224, 224)

# Nome da classe (em classes.json) que libera o acesso. A inferência
# nunca depende da ORDEM das classes: ela lê a lista do arquivo e
# compara o NOME previsto com esta constante.
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

# A caixa do rosto é expandida para cobrir cabeça e tronco, que é
# onde ficam o capacete, os óculos e o colete. Os valores são
# múltiplos do tamanho do rosto.
MARGEM_LATERAL_ROSTO = 0.9
MARGEM_SUPERIOR_ROSTO = 0.7
MARGEM_INFERIOR_ROSTO = 2.2

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

# Confiança mínima (0 a 1) para liberar. Ajustável na tela.
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
TAMANHO_INICIAL_JANELA = "1360x820"
TAMANHO_MINIMO_JANELA = (1080, 680)

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
EPOCAS_TREINO = 10
FRACAO_VALIDACAO = 0.20
SEMENTE_TREINO = 123
TAXA_APRENDIZADO = 0.001
TAXA_DROPOUT = 0.20

EXTENSOES_IMAGEM = {".jpg", ".jpeg", ".png", ".bmp", ".gif"}

# Abaixo disso o treino funciona, mas o programa avisa que é pouco
MINIMO_IMAGENS_RECOMENDADO = 10
