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

import gc
import tempfile
import time
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
config.PASTA_CAPTURAS = config.PASTA_AUDITORIA / "capturas"
config.PASTA_LOGS = PASTA_TEMPORARIA / "logs"
config.PASTA_RELATORIOS_DIARIOS = config.PASTA_RELATORIOS / "diarios"
config.PASTA_IMAGENS_DATASET = PASTA_TEMPORARIA / "dataset" / "epis"
config.ARQUIVO_ROTULOS = PASTA_TEMPORARIA / "dataset" / "rotulos.csv"
config.ARQUIVO_PREFERENCIAS = PASTA_TEMPORARIA / "preferencias.json"

# O painel web só sobe quando um teste pede, e só para este computador
# (127.0.0.1): assim o firewall do Windows não pergunta nada.
config.PAINEL_WEB_ATIVO = False

# Os testes NUNCA abrem a porta USB de um ESP32 de verdade: a janela
# não deve sair procurando e tomando a porta da catraca do usuário.
config.CATRACA_SERIAL_ATIVA = False
config.PAINEL_WEB_HOST = "127.0.0.1"

# Sem bipes durante os testes (eles registram vários "negados")
config.ALERTA_SONORO_NEGADO = False

# Hash da senha do painel bem mais rápido nos testes (no programa de
# verdade ele é lento de propósito). O formato é o mesmo.
config.ITERACOES_HASH_SENHA = 1000

# Nada de gerar relatórios PDF sozinho, nem abrir o assistente de
# primeira execução, durante os testes
config.RELATORIO_DIARIO_AUTOMATICO = False
config.ASSISTENTE_NA_PRIMEIRA_EXECUCAO = False


# ============================================================
# FIXTURES (peças prontas que os testes pedem pelo nome)
# ============================================================

@pytest.fixture(autouse=True)
def preferencias_zeradas():
    """
    Cada teste começa sem preferências salvas.

    O arquivo é um só para todos os testes (os serviços leem o caminho
    na importação). Sem isto, as áreas e câmeras que um teste cria
    apareceriam no teste seguinte.
    """

    config.ARQUIVO_PREFERENCIAS.unlink(missing_ok=True)

    yield

    config.ARQUIVO_PREFERENCIAS.unlink(missing_ok=True)


@pytest.fixture
def auditoria(tmp_path):
    """Serviço de auditoria novo, vazio, numa pasta só deste teste."""

    from safetech.servicos.auditoria import ServicoAuditoria

    return ServicoAuditoria(
        arquivo_log=tmp_path / "log_auditoria.csv",
        pasta_imagens=tmp_path / "imagens",
        pasta_excluidos=tmp_path / "excluidos",
    )


def criar_janela_tk(tentativas=5):
    """
    Cria a janela do Tk, tentando de novo se ela falhar ao abrir.

    No Python da Microsoft Store, criar muitas janelas seguidas às vezes
    falha ao ler os arquivos do próprio Tk ("Can't find a usable
    init.tcl", "tk.tcl", "couldn't read file ... auto.tcl"). É uma falha passageira do
    Windows, não do programa: na tentativa seguinte, abre normalmente.
    """

    for tentativa in range(tentativas):

        try:
            return tk.Tk()

        except tk.TclError as erro:

            mensagem = str(erro)

            # Falha ao LER um arquivo .tcl do próprio Tk (init.tcl, tk.tcl, auto.tcl...)
            # (ou "invalid command name tcl_findLibrary", a mesma falha
            # aparecendo um passo depois)
            passageira = (
                ".tcl" in mensagem and ("usable" in mensagem or "couldn't read file" in mensagem)
            ) or "tcl_findLibrary" in mensagem

            if not passageira or tentativa == tentativas - 1:
                raise

            time.sleep(0.2)


@pytest.fixture
def raiz():
    """
    Janela raiz do Tkinter, ESCONDIDA (withdraw), com o tema aplicado.

    Fechada no fim do teste, se o próprio teste ainda não a fechou.
    """

    from safetech.interface import tema

    janela = criar_janela_tk()
    janela.withdraw()

    # Sempre começa no tema escuro: um teste que troca o tema não pode
    # deixar as cores trocadas para o teste seguinte
    tema.definir_paleta(tema.TEMA_PADRAO)

    tema.aplicar_tema(janela, 1.0)

    yield janela

    try:
        janela.destroy()
    except tk.TclError:
        pass  # o teste já fechou a janela

    # Recolhe agora, na thread principal, as variáveis do Tk que
    # sobraram da janela. Se ficassem para depois, poderiam ser
    # recolhidas por outra thread (a de uma análise), e o Tk reclama.
    gc.collect()


@pytest.fixture
def sem_ia(monkeypatch):
    """
    Impede a janela principal de carregar a IA (TensorFlow).

    Os testes de interface não precisam do modelo, e carregar o
    TensorFlow levaria vários segundos por teste.
    """

    from safetech.interface import controlador_ia

    monkeypatch.setattr(controlador_ia.CargaIA, "carregar", lambda self: None)
