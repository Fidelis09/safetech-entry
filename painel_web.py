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

from safetech.servicos import log_erros, preferencias
from safetech.servicos.auditoria import ServicoAuditoria
from safetech.web.servidor import ServidorWeb


def principal():

    # Erros e acontecimentos vão também para logs/safetech.log
    log_erros.configurar()

    # Porta, rede, usuário e senha: os mesmos escolhidos no aplicativo
    # (Configurações > Painel web). Aqui o painel sobe mesmo que lá esteja
    # desligado: rodar este arquivo já é pedir o painel.
    ajustes = preferencias.carregar_painel_web()

    # Sem fonte ao vivo: o painel mostra só indicadores, eventos e fotos
    servidor = ServidorWeb(ServicoAuditoria(), ajustes=ajustes)

    try:
        servidor.iniciar()

    except OSError:
        print(f"A porta {ajustes.porta} já está em uso.")
        print("Se o aplicativo estiver aberto, o painel já está no ar por ele.")
        return

    endereco = servidor.endereco()

    print("Painel web do gerente (somente leitura)")
    print("Endereço:", endereco)

    if ajustes.exige_login:
        print("Usuário: ", ajustes.usuario)

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
