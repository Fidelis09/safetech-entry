"""
Robustez: o programa continua de pé quando algo dá errado, e deixa rastro.

    - log_erros: erros e acontecimentos vão para um arquivo que não cresce
      sem fim;
    - Analisador: a análise que quebra recomeça sozinha (o "vigia") e só
      desiste depois de várias falhas seguidas;
    - janela: um erro num botão vai para o log e para o aviso do rodapé;
    - modos.titulo_da_situacao: o título da faixa num lugar só.
"""

import logging
import tkinter as tk
from logging.handlers import RotatingFileHandler

import numpy as np
import pytest

from safetech import config
from safetech.nucleo import modos
from safetech.nucleo.tipos import StatusAcesso
from safetech.servicos import log_erros
from safetech.servicos.analisador import Analisador, ParametrosAnalise
from testes.falsos import CameraFalsa, ClassificadorFalso, DetectorFalso, esperar


# ============================================================
# REGISTRO EM ARQUIVO
# ============================================================

@pytest.fixture
def log_em_arquivo(tmp_path, monkeypatch):
    """Liga o log num arquivo temporário e o desliga no fim do teste."""

    import sys
    import threading

    monkeypatch.setattr(config, "TAMANHO_MAXIMO_LOG_BYTES", 2000)
    monkeypatch.setattr(config, "QUANTIDADE_LOGS_GUARDADOS", 2)

    # configurar() troca os "ganchos" de erro do Python: voltam no fim
    monkeypatch.setattr(sys, "excepthook", sys.excepthook)
    monkeypatch.setattr(threading, "excepthook", threading.excepthook)

    caminho = log_erros.configurar(tmp_path)

    registrador = logging.getLogger(log_erros.NOME_RAIZ)

    yield caminho

    for saida in list(registrador.handlers):

        if isinstance(saida, RotatingFileHandler):
            registrador.removeHandler(saida)
            saida.close()


def test_log_grava_mensagens_dos_modulos(log_em_arquivo):

    logging.getLogger("safetech.servicos.camera").warning("Câmera 1 não respondeu")

    texto = log_em_arquivo.read_text(encoding="utf-8")

    assert "SafeTech Entry iniciado" in texto
    assert "WARNING" in texto and "Câmera 1 não respondeu" in texto
    assert "safetech.servicos.camera" in texto


def test_configurar_duas_vezes_nao_duplica_linhas(log_em_arquivo, tmp_path):

    log_erros.configurar(tmp_path)

    logging.getLogger("safetech").info("linha única")

    assert log_em_arquivo.read_text(encoding="utf-8").count("linha única") == 1


def test_log_nao_cresce_sem_fim(log_em_arquivo):

    for numero in range(200):
        logging.getLogger("safetech").info("mensagem comprida número %d %s", numero, "x" * 50)

    arquivos = sorted(log_em_arquivo.parent.glob(log_em_arquivo.name + "*"))

    # O atual e no máximo QUANTIDADE_LOGS_GUARDADOS antigos
    assert len(arquivos) <= 1 + config.QUANTIDADE_LOGS_GUARDADOS
    assert all(arquivo.stat().st_size <= config.TAMANHO_MAXIMO_LOG_BYTES + 500 for arquivo in arquivos)


# ============================================================
# VIGIA DA ANÁLISE
# ============================================================

class ClassificadorQueFalha(ClassificadorFalso):
    """Quebra nas primeiras 'falhas' chamadas; depois funciona."""

    def __init__(self, falhas):

        super().__init__([[0.9, 0.9, 0.9, 0.9]])

        self.falhas = falhas
        self.chamadas = 0

    def classificar_lote(self, recortes):

        self.chamadas += 1

        if self.chamadas <= self.falhas:
            raise RuntimeError(f"falha simulada {self.chamadas}")

        return super().classificar_lote(recortes)


def criar_analisador(auditoria, classificador):

    detectores = {modo: DetectorFalso([(100, 100, 300, 400)]) for modo in config.MODOS_DETECCAO}

    return Analisador(CameraFalsa(), detectores, classificador, auditoria, ParametrosAnalise(area="Portaria"))


def test_analise_que_quebra_recomeca_sozinha(auditoria, monkeypatch, caplog):

    monkeypatch.setattr(config, "ESPERA_REINICIO_ANALISE_SEG", 0.05)

    analisador = criar_analisador(auditoria, ClassificadorQueFalha(falhas=2))

    with caplog.at_level(logging.WARNING, logger="safetech"):

        analisador.iniciar()

        try:
            # Depois de duas quebras, volta a analisar e registra o evento
            assert esperar(lambda: not analisador.registros_novos.empty(), 10)
        finally:
            analisador.parar()

    assert analisador.reinicios == 2
    assert analisador.erro is None
    assert not analisador.reiniciando

    # As quebras e os reinícios ficaram registrados
    assert "falha simulada 1" in caplog.text
    assert "recomeçou" in caplog.text


def test_analise_desiste_depois_de_muitas_falhas_seguidas(auditoria, monkeypatch):

    monkeypatch.setattr(config, "ESPERA_REINICIO_ANALISE_SEG", 0.01)
    monkeypatch.setattr(config, "MAXIMO_REINICIOS_ANALISE", 3)

    analisador = criar_analisador(auditoria, ClassificadorQueFalha(falhas=10_000))

    analisador.iniciar()

    try:
        assert esperar(lambda: analisador.erro is not None and "parou" in analisador.erro, 10)
    finally:
        analisador.parar()

    assert analisador.reinicios == 3
    assert not analisador.reiniciando


def test_faixa_mostra_que_esta_reiniciando(auditoria):

    from safetech.interface.area_monitorada import AreaMonitorada
    from safetech.interface.tema import CORES

    analisador = criar_analisador(auditoria, ClassificadorFalso([[0.9, 0.9, 0.9, 0.9]]))
    analisador.erro = "RuntimeError: teste"
    analisador.reiniciando = True

    area = AreaMonitorada(dados=None, camera=CameraFalsa(), parametros=ParametrosAnalise(), painel=None)
    area.analisador = analisador

    titulo, detalhe, cor = area.resumo_status()

    assert titulo == "REINICIANDO A ANÁLISE"
    assert "RuntimeError: teste" in detalhe
    assert cor == CORES["alerta"]


# ============================================================
# ERRO NUM BOTÃO DA JANELA
# ============================================================

def test_erro_num_botao_vai_para_o_log_e_o_aviso(raiz, sem_ia, caplog):

    from safetech.interface import janela_principal
    from testes.falsos import CameraParada

    tela = janela_principal.JanelaPrincipal(raiz, 1.0, camera=CameraParada())

    try:

        def botao_com_defeito():
            raise ValueError("defeito de teste")

        with caplog.at_level(logging.ERROR, logger="safetech"):

            # O Tkinter chama report_callback_exception quando um
            # botão (ou atalho, ou temporizador) lança um erro
            raiz.after(0, botao_com_defeito)
            raiz.update()

        assert "defeito de teste" in caplog.text
        assert "defeito de teste" in tela._rotulo_aviso.cget("text")

    finally:
        tela._ao_fechar()


# ============================================================
# TÍTULO DA FAIXA (um lugar só para a tela e o painel web)
# ============================================================

@pytest.mark.parametrize(
    "modo, acesso, esperado",
    [
        (config.MODO_CATRACA, StatusAcesso.LIBERADO, "ACESSO LIBERADO"),
        (config.MODO_CATRACA, StatusAcesso.NEGADO, "ACESSO NEGADO"),
        (config.MODO_VIGILANCIA, StatusAcesso.LIBERADO, "EM CONFORMIDADE"),
        (config.MODO_VIGILANCIA, "negado", "NÃO CONFORME"),
        (config.MODO_VIGILANCIA, StatusAcesso.ANALISANDO, "ANALISANDO"),
        (config.MODO_CATRACA, "sem_pessoas", "AGUARDANDO"),
    ],
)
def test_titulo_da_situacao(modo, acesso, esperado):

    assert modos.titulo_da_situacao(modo, acesso) == esperado


def test_titulos_iguais_na_tela_e_no_painel_web(auditoria):
    """A faixa da tela e o /api/ao-vivo usam a mesma função: o mesmo texto."""

    from safetech.interface.area_monitorada import descrever_acesso
    from safetech.nucleo.tipos import EstadoCena
    from safetech.web.servidor import ServidorWeb

    estado = EstadoCena(acesso=StatusAcesso.SEM_PESSOAS, modo=config.MODO_VIGILANCIA)

    servidor = ServidorWeb(auditoria, lambda: (np.zeros((10, 10, 3), np.uint8), estado))

    assert servidor.dados_ao_vivo()["titulo"] == descrever_acesso(estado)[0] == "AGUARDANDO"
