"""
Janela principal (safetech/interface/janela_principal.py), sempre
ESCONDIDA e com câmera falsa: nenhuma janela aparece e a webcam não liga.

Testa os botões que mexem em arquivos: excluir linha, salvar relatório
e adicionar/remover câmera IP. As caixas de confirmação e o navegador
são trocados por versões falsas que respondem sozinhas.
"""

import webbrowser
from tkinter import messagebox

import numpy as np
import pytest

from safetech import config
from safetech.interface import janela_principal
from safetech.interface.painel_monitoramento import TEXTO_ADICIONAR_IP
from safetech.nucleo.tipos import ResultadoEPI
from safetech.servicos import preferencias
from testes.falsos import CameraParada


@pytest.fixture
def janela(raiz, sem_ia, monkeypatch):

    # Toda confirmação responde "sim"; o navegador só anota o endereço
    monkeypatch.setattr(messagebox, "askyesno", lambda *a, **k: True)

    abertos = []
    monkeypatch.setattr(webbrowser, "open", abertos.append)

    camera = CameraParada()

    tela = janela_principal.JanelaPrincipal(raiz, 1.0, camera=camera)
    tela.abertos_no_navegador = abertos

    # Começa cada teste com a auditoria vazia
    tela._auditoria.zerar()
    tela._painel_auditoria.esvaziar()

    raiz.update()

    yield tela

    tela._ao_fechar()


def registrar(janela, pessoa):

    registro = janela._auditoria.registrar(
        evento="ENTRADA",
        identificador_pessoa=pessoa,
        setor="Canteiro de obras",
        exigidos=("capacete",),
        itens=(ResultadoEPI("capacete", False, 0.1),),
        faltando=("capacete",),
        liberado=False,
        imagem_bgr=np.zeros((40, 40, 3), np.uint8),
    )

    janela._painel_auditoria.adicionar(registro)

    return registro


def selecionar_primeira_linha(janela):

    tabela = janela._painel_auditoria._tabela

    tabela.selection_set(tabela.get_children()[0])
    janela._raiz.update()


# ============================================================
# AUDITORIA
# ============================================================

def test_botoes_da_linha_so_funcionam_com_linha_selecionada(janela):

    painel = janela._painel_auditoria

    registrar(janela, 1)

    assert painel._botao_excluir.instate(["disabled"])
    assert painel._botao_relatorio.instate(["disabled"])

    selecionar_primeira_linha(janela)

    assert not painel._botao_excluir.instate(["disabled"])
    assert not painel._botao_relatorio.instate(["disabled"])


def test_excluir_linha_tira_da_tabela_e_do_log(janela):

    registrar(janela, 1)
    registrar(janela, 2)

    # A linha do topo é a mais recente (P002)
    selecionar_primeira_linha(janela)

    janela._painel_auditoria._excluir_selecionado()

    assert len(janela._painel_auditoria._tabela.get_children()) == 1
    assert [r.pessoa for r in janela._auditoria.carregar_historico()] == ["P001"]


def test_salvar_relatorio_da_linha_abre_no_navegador(janela):

    registrar(janela, 1)
    selecionar_primeira_linha(janela)

    janela._painel_auditoria._salvar_relatorio_selecionado()

    assert len(janela.abertos_no_navegador) == 1
    assert janela.abertos_no_navegador[0].endswith("relatorio.html")


# ============================================================
# CATRACA ESP32 (cabo USB)
# ============================================================

class CatracaFalsa:
    """No lugar do CatraciaSerial de verdade: não abre nenhuma porta."""

    def __init__(self, fonte_ao_vivo):

        self.situacao = "Catraca: COM3 conectada"
        self.iniciada = False
        self.parada = False

    def iniciar(self):
        self.iniciada = True

    def parar(self):
        self.parada = True


def test_catraca_aparece_na_barra_de_status_e_para_ao_fechar(raiz, sem_ia, monkeypatch):

    monkeypatch.setattr(config, "CATRACA_SERIAL_ATIVA", True)
    monkeypatch.setattr(janela_principal, "CatracaSerial", CatracaFalsa)

    tela = janela_principal.JanelaPrincipal(raiz, 1.0, camera=CameraParada())

    raiz.update()

    catraca = tela._catraca

    assert catraca.iniciada
    assert tela._rotulo_catraca.cget("text") == "Catraca: COM3 conectada"

    # O texto acompanha o que a catraca informa
    catraca.situacao = "Catraca: cabo desconectado, procurando..."

    tela._atualizar_catraca()

    assert tela._rotulo_catraca.cget("text") == "Catraca: cabo desconectado, procurando..."

    tela._ao_fechar()

    assert catraca.parada


def test_sem_catraca_ligada_nada_e_criado(janela):

    # No conftest, CATRACA_SERIAL_ATIVA é False
    assert janela._catraca is None


# ============================================================
# CÂMERA IP
# ============================================================

ENDERECO = "rtsp://admin:segredo@192.168.0.50:554/stream"


def test_lista_de_cameras_termina_com_adicionar(janela):

    valores = janela._painel_monitoramento._caixa_camera["values"]

    assert valores[-1] == TEXTO_ADICIONAR_IP


def test_adicionar_camera_ip(janela, monkeypatch):

    preferencias.salvar_cameras_ip([])

    monkeypatch.setattr(janela_principal, "pedir_camera_ip", lambda pai, sugerido: ("Portaria", ENDERECO))

    janela._adicionar_camera_ip()

    painel = janela._painel_monitoramento

    assert janela._camera.fonte == ENDERECO
    assert preferencias.carregar_cameras_ip() == [("Portaria", ENDERECO)]
    assert preferencias.carregar_fonte_camera() == ENDERECO
    assert painel._nome_da_camera.get() == "Portaria (IP)"

    # A senha nunca aparece na tela
    assert "segredo" not in " ".join(painel._caixa_camera["values"])
    assert "segredo" not in janela._rotulo_aviso.cget("text")


def test_remover_camera_ip_volta_para_a_webcam(janela, monkeypatch):

    preferencias.salvar_cameras_ip([])

    monkeypatch.setattr(janela_principal, "pedir_camera_ip", lambda pai, sugerido: ("Portaria", ENDERECO))

    janela._adicionar_camera_ip()
    janela._remover_camera_ip(ENDERECO)

    assert preferencias.carregar_cameras_ip() == []
    assert janela._camera.fonte == 0  # a webcam que estava em uso antes
    assert "Portaria (IP)" not in janela._painel_monitoramento._caixa_camera["values"]
