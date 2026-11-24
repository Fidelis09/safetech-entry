"""
SafeTech Entry - ponto de entrada do aplicativo.

Para abrir o programa:

    python app.py

Este arquivo só inicia a janela. O código está organizadco no pacote
"safetech" (veja o README.md para o mapa completo do projeto).
"""

from safetech.interface.janela_principal import executar


if __name__ == "__main__":
    executar()
