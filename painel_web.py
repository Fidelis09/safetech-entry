"""
SafeTech Entry - painel web do gerente em modo histórico.

O painel web já sobe sozinho junto com o aplicativo (python app.py),
com imagem ao vivo. Use ESTE arquivo apenas quando quiser consultar o
histórico de auditoria sem abrir a catraca:

    python painel_web.py

Não abra os dois ao mesmo tempo: eles usam a mesma porta.
"""

import time
import webbrowser

from safetech import config
from safetech.servicos.auditoria import ServicoAuditoria
from safetech.web.servidor import ServidorWeb


def principal():

    # Sem fonte ao vivo: o painel mostra só indicadores, eventos e fotos
    servidor = ServidorWeb(ServicoAuditoria())

    try:
        servidor.iniciar()

    except OSError:
        print(f"A porta {config.PAINEL_WEB_PORTA} já está em uso.")
        print("Se o aplicativo estiver aberto, o painel já está no ar por ele.")
        return

    endereco = servidor.endereco()

    print("Painel web do gerente (somente leitura)")
    print("Endereço:", endereco)

    if config.PAINEL_WEB_SENHA:
        print("Usuário: ", config.PAINEL_WEB_USUARIO)

    print()
    print("Pressione Ctrl+C para encerrar.")

    webbrowser.open(endereco)

    try:

        while True:
            time.sleep(1)

    except KeyboardInterrupt:
        servidor.parar()


if __name__ == "__main__":
    principal()
