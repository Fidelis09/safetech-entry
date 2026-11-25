"""
Registro de erros e acontecimentos em arquivo: logs/safetech.log.

Antes, um erro numa thread (a análise de uma câmera, a catraca, o
painel web) aparecia na tela e se perdia quando o programa fechava.
Agora tudo vai também para um arquivo de texto, com data, hora e de
qual parte do programa veio. É o primeiro lugar a olhar quando algo deu
errado na apresentação e ninguém viu a mensagem.

Como usar em qualquer módulo:

    import logging
    log = logging.getLogger(__name__)

    log.info("Câmera aberta")
    log.warning("Porta 8080 em uso")
    log.exception("Erro na análise")   # dentro de um except: guarda o erro completo

O arquivo não cresce sem fim: passou de config.TAMANHO_MAXIMO_LOG_BYTES,
ele vira safetech.log.1 (o .1 vira .2, e assim por diante) e o mais
antigo, além de config.QUANTIDADE_LOGS_GUARDADOS, é descartado.

Só o app.py liga a gravação (configurar()). Os testes não ligam: os
registros deles ficam só na memória do pytest, sem criar arquivos.
"""

import logging
import platform
import sys
import threading
from logging.handlers import RotatingFileHandler

from safetech import config


# Cada linha: data e hora, gravidade, thread, módulo e a mensagem, ex.:
# 2026-11-25 10:03:12 WARNING [analisador] safetech.servicos.analisador: ...
FORMATO = "%(asctime)s %(levelname)-7s [%(threadName)s] %(name)s: %(message)s"
FORMATO_DATA = "%Y-%m-%d %H:%M:%S"

# Nome do "registrador" do projeto: todos os módulos (safetech.xxx) são
# filhos dele e herdam o arquivo de destino
NOME_RAIZ = "safetech"

log = logging.getLogger(__name__)


def configurar(pasta=None):
    """
    Liga a gravação em arquivo. Devolve o caminho do arquivo de log.

    Chamar mais de uma vez não duplica as linhas: a segunda chamada só
    devolve o caminho.
    """

    pasta = pasta or config.PASTA_LOGS
    pasta.mkdir(parents=True, exist_ok=True)

    caminho = pasta / config.NOME_ARQUIVO_LOG

    registrador = logging.getLogger(NOME_RAIZ)

    if any(isinstance(saida, RotatingFileHandler) for saida in registrador.handlers):
        return caminho

    arquivo = RotatingFileHandler(
        caminho,
        maxBytes=config.TAMANHO_MAXIMO_LOG_BYTES,
        backupCount=config.QUANTIDADE_LOGS_GUARDADOS,
        encoding="utf-8",
    )
    arquivo.setFormatter(logging.Formatter(FORMATO, FORMATO_DATA))

    registrador.addHandler(arquivo)
    registrador.setLevel(config.NIVEL_LOG)

    _capturar_erros_nao_tratados()

    log.info(
        "SafeTech Entry iniciado (Python %s, %s)",
        platform.python_version(),
        platform.platform(),
    )

    return caminho


def _capturar_erros_nao_tratados():
    """
    Erros que ninguém tratou também vão para o arquivo.

    Sem isto, um erro que derruba uma thread só seria impresso no
    terminal (que nem existe quando o programa é aberto com dois cliques).
    """

    anterior_principal = sys.excepthook
    anterior_threads = threading.excepthook

    def no_programa(tipo, erro, rastro):

        logging.getLogger(NOME_RAIZ).critical("Erro não tratado", exc_info=(tipo, erro, rastro))

        anterior_principal(tipo, erro, rastro)

    def nas_threads(argumentos):

        logging.getLogger(NOME_RAIZ).error(
            "Erro não tratado na thread %s",
            argumentos.thread.name if argumentos.thread else "?",
            exc_info=(argumentos.exc_type, argumentos.exc_value, argumentos.exc_traceback),
        )

        anterior_threads(argumentos)

    sys.excepthook = no_programa
    threading.excepthook = nas_threads
