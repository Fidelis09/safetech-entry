"""
SafeTech Entry - treinamento do modelo de EPI.

Para treinar (ou re-treinar depois de coletar mais imagens):

    python treinar.py

Lê as imagens de dataset/<classe>/ e gera, na pasta "modelos":

    modelo_epi.keras  -> o modelo treinado
    classes.json      -> os nomes das classes, na ordem aprendida

A lógica do treinamento está em safetech/treino/treinador.py.
"""

from safetech.treino.treinador import executar


if __name__ == "__main__":

    executar()

    input("\nPressione ENTER para finalizar...")
