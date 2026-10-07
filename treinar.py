"""
SafeTech Entry - treinamento do modelo de EPI.

Para treinar (ou re-treinar depois de coletar mais imagens):

    python treinar.py

Lê as imagens de dataset/epis/ e os rótulos de dataset/rotulos.csv
(criados pela área "Coleta de imagens" do aplicativo) e gera, na pasta
"modelos":

    modelo_epis.keras -> o modelo, com uma resposta por equipamento
    epis.json         -> os EPIs que ele reconhece, na ordem das saídas

A lógica do treinamento está em safetech/treino/treinador.py.
"""

from safetech.treino.treinador import executar


if __name__ == "__main__":

    try:
        executar()

    except SystemExit as parada:

        # Erros de validação do dataset chegam aqui com a explicação
        print()
        print(parada)

    input("\nPressione ENTER para finalizar...")
