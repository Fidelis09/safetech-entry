"""
Leitura da lista de classes do modelo.

Fica num módulo separado (e sem TensorFlow) para que a interface possa
montar os botões de coleta na hora, antes de o modelo terminar de carregar.
"""

import json

from safetech import config


def carregar_classes(caminho=config.ARQUIVO_CLASSES) -> list[str]:
    """Nomes das classes, na ordem em que o modelo foi treinado."""

    with open(caminho, "r", encoding="utf-8") as arquivo:
        return json.load(arquivo)
