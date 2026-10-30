"""
Preparação comum a todos os testes.

O pytest lê este arquivo ANTES de qualquer teste. Ele é usado para
garantir duas regras:

    1) Testes nunca tocam nos dados reais. Todas as pastas e arquivos
       do programa (auditoria, dataset, preferências...) são apontados
       para uma pasta temporária. Isso precisa acontecer antes de os
       serviços serem importados, porque eles leem os caminhos do
       config.py no momento da importação.

    2) Testes nunca ligam a webcam nem mostram janelas: o usuário pode
       estar usando o computador enquanto os testes rodam.
"""

import tempfile
import tkinter as tk
from pathlib import Path

import pytest

from safetech import config


# ============================================================
# DADOS DO PROGRAMA EM UMA PASTA TEMPORÁRIA
# ============================================================

PASTA_TEMPORARIA = Path(tempfile.mkdtemp(prefix="safetech_testes_"))

config.PASTA_AUDITORIA = PASTA_TEMPORARIA / "auditoria"
config.ARQUIVO_LOG_AUDITORIA = config.PASTA_AUDITORIA / "log_auditoria.csv"
config.PASTA_IMAGENS_AUDITORIA = config.PASTA_AUDITORIA / "imagens"
config.PASTA_EXCLUIDOS = config.PASTA_AUDITORIA / "excluidos"
config.PASTA_RELATORIOS = config.PASTA_AUDITORIA / "relatorios"
config.PASTA_IMAGENS_DATASET = PASTA_TEMPORARIA / "dataset" / "epis"
config.ARQUIVO_ROTULOS = PASTA_TEMPORARIA / "dataset" / "rotulos.csv"
config.ARQUIVO_PREFERENCIAS = PASTA_TEMPORARIA / "preferencias.json"

# O painel web só sobe quando um teste pede, e só para este computador
# (127.0.0.1): assim o firewall do Windows não pergunta nada.
config.PAINEL_WEB_ATIVO = False
config.PAINEL_WEB_HOST = "127.0.0.1"


# ============================================================
# FIXTURES (peças prontas que os testes pedem pelo nome)
# ============================================================

@pytest.fixture
def auditoria(tmp_path):
    """Serviço de auditoria novo, vazio, numa pasta só deste teste."""

    from safetech.servicos.auditoria import ServicoAuditoria

    return ServicoAuditoria(
        arquivo_log=tmp_path / "log_auditoria.csv",
        pasta_imagens=tmp_path / "imagens",
        pasta_excluidos=tmp_path / "excluidos",
    )


@pytest.fixture
def raiz():
    """
    Janela raiz do Tkinter, ESCONDIDA (withdraw), com o tema aplicado.

    Fechada no fim do teste, se o próprio teste ainda não a fechou.
    """

    from safetech.interface import tema

    janela = tk.Tk()
    janela.withdraw()

    tema.aplicar_tema(janela, 1.0)

    yield janela

    try:
        janela.destroy()
    except tk.TclError:
        pass  # o teste já fechou a janela


@pytest.fixture
def sem_ia(monkeypatch):
    """
    Impede a janela principal de carregar a IA (TensorFlow).

    Os testes de interface não precisam do modelo, e carregar o
    TensorFlow levaria vários segundos por teste.
    """

    from safetech.interface import janela_principal

    monkeypatch.setattr(janela_principal.JanelaPrincipal, "_carregar_ia", lambda self: None)
