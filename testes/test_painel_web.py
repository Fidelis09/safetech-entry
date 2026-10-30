"""
Painel web do gerente (safetech/web/servidor.py).

Regras testadas: exige login, é SOMENTE LEITURA (só GET) e não deixa
ler arquivos fora da pasta de fotos.
"""

import base64
import json
import socket
import urllib.error
import urllib.request

import numpy as np
import pytest

from safetech import config
from safetech.nucleo.tipos import ResultadoEPI
from safetech.web.servidor import ServidorWeb


def porta_livre():

    with socket.socket() as teste:
        teste.bind(("127.0.0.1", 0))
        return teste.getsockname()[1]


@pytest.fixture
def painel(auditoria):

    auditoria.registrar(
        evento="ENTRADA",
        identificador_pessoa=1,
        setor="Canteiro de obras",
        exigidos=("capacete",),
        itens=(ResultadoEPI("capacete", True, 0.9),),
        faltando=(),
        liberado=True,
        imagem_bgr=np.zeros((40, 40, 3), np.uint8),
    )

    servidor = ServidorWeb(auditoria, None, host="127.0.0.1", porta=porta_livre())
    servidor.iniciar()

    yield servidor

    servidor.parar()


def pedir(servidor, caminho, metodo="GET", login=True):
    """Faz um pedido ao painel; devolve (código HTTP, corpo)."""

    pedido = urllib.request.Request(servidor.endereco() + caminho, method=metodo)

    if login:

        credenciais = f"{config.PAINEL_WEB_USUARIO}:{config.PAINEL_WEB_SENHA}"

        pedido.add_header(
            "Authorization", "Basic " + base64.b64encode(credenciais.encode()).decode()
        )

    try:

        with urllib.request.urlopen(pedido, timeout=5) as resposta:
            return resposta.status, resposta.read()

    except urllib.error.HTTPError as erro:
        return erro.code, b""


def test_sem_login_pede_senha(painel):

    if not config.PAINEL_WEB_SENHA:
        pytest.skip("painel configurado sem senha")

    assert pedir(painel, "/", login=False)[0] == 401


def test_pagina_e_historico_com_login(painel):

    codigo, _ = pedir(painel, "/")

    assert codigo == 200

    codigo, corpo = pedir(painel, "/api/historico")

    assert codigo == 200
    assert "Canteiro de obras" in json.dumps(json.loads(corpo), ensure_ascii=False)


@pytest.mark.parametrize("metodo", ["POST", "PUT", "DELETE", "PATCH"])
def test_somente_leitura(painel, metodo):

    assert pedir(painel, "/api/historico", metodo=metodo)[0] == 405


@pytest.mark.parametrize(
    "caminho",
    ["/imagens/../../safetech/config.py", "/imagens/..%2F..%2Fsafetech%2Fconfig.py", "/imagens/nao_existe.jpg"],
)
def test_nao_sai_da_pasta_de_fotos(painel, caminho):

    assert pedir(painel, caminho)[0] == 404


def test_sem_camera_o_ao_vivo_avisa(painel):

    codigo, corpo = pedir(painel, "/api/ao-vivo")

    assert codigo == 200
    assert json.loads(corpo)["disponivel"] is False
