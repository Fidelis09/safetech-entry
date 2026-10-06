"""
SafeTech Entry - catraca inteligente com reconhecimento de EPI.

Organização do pacote:

    safetech/config.py   -> todas as configurações do projeto (caminhos e ajustes)
    safetech/nucleo/     -> a "inteligência": detecção, rastreamento, classificação e decisão
    safetech/servicos/   -> câmera, linha de análise, auditoria e coleta de dataset
    safetech/interface/  -> a janela (Tkinter) e seus painéis
    safetech/treino/     -> treinamento do modelo (transfer learning com MobileNetV2)
"""

import os

# ============================================================
# AJUSTES DO TENSORFLOW
# ============================================================
#
# Precisam ser definidos ANTES de qualquer "import tensorflow",
# por isso ficam aqui, no primeiro arquivo carregado do pacote.
#
#   TF_CPP_MIN_LOG_LEVEL=2  -> esconde os avisos informativos do TensorFlow
#   TF_ENABLE_ONEDNN_OPTS=0 -> resultados numéricos sempre iguais entre execuções
# ============================================================

os.environ.setdefault("TF_CPP_MIN_LOG_LEVEL", "2")
os.environ.setdefault("TF_ENABLE_ONEDNN_OPTS", "0")

__version__ = "2.0.0"
