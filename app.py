"""
SafeTech Entry - ponto de entrada do aplicativo.

Para abrir o programa:

    python app.py

Este arquivo só inicia a janela. O código está organizado no pacote
"safetech" (veja o README.md para o mapa completo do projeto).
"""

from safetech.interface.janela_principal import executar
from safetech.servicos import log_erros


if __name__ == "__main__":

    # Erros e acontecimentos vão também para logs/safetech.log
    log_erros.configurar()

    executar()
