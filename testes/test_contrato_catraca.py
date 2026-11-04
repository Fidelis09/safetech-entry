"""
Contrato entre o programa e a catraca de demonstração (catraca_esp32/).

A catraca lê /api/ao-vivo e depende de alguns campos com nomes e
valores exatos. Se alguém mudar esse formato no servidor, este teste
falha AQUI, antes de a catraca parar de funcionar numa apresentação.

Campos usados pela catraca (veja consultarSafeTech() no .ino):

    camera_ativa          -> true / false
    acesso                -> "sem_pessoas" | "analisando" | "liberado" | "negado"
    pessoas[].status      -> "negado" para quem está irregular
    pessoas[].faltando    -> nomes dos EPIs que faltam
"""

import base64
import json
import socket
import urllib.request

import numpy as np
import pytest

from safetech import config
from safetech.nucleo.tipos import (
    EstadoCena,
    PessoaObservada,
    ResultadoEPI,
    StatusAcesso,
    StatusPessoa,
)
from safetech.web.servidor import ServidorWeb


# Os valores que a catraca conhece. Mudou aqui, muda no .ino também.
VALORES_DE_ACESSO_DA_CATRACA = {"sem_pessoas", "analisando", "liberado", "negado"}


def porta_livre():

    with socket.socket() as teste:
        teste.bind(("127.0.0.1", 0))
        return teste.getsockname()[1]


def ler_ao_vivo(estado, frame=np.zeros((10, 10, 3), np.uint8), auditoria=None):
    """Sobe o painel com um estado combinado e lê /api/ao-vivo como a catraca lê."""

    porta = porta_livre()

    servidor = ServidorWeb(auditoria, lambda: (frame, estado), host="127.0.0.1", porta=porta)
    servidor.iniciar()

    try:

        # 127.0.0.1, e não "localhost": no Windows, "localhost" tenta
        # primeiro o IPv6 e perde uns 2 segundos em cada pedido.
        pedido = urllib.request.Request(f"http://127.0.0.1:{porta}/api/ao-vivo")

        # Mesmo login que a catraca usa (Basic Auth)
        credenciais = f"{config.PAINEL_WEB_USUARIO}:{config.PAINEL_WEB_SENHA}"
        pedido.add_header("Authorization", "Basic " + base64.b64encode(credenciais.encode()).decode())

        with urllib.request.urlopen(pedido, timeout=5) as resposta:

            assert resposta.status == 200

            return json.loads(resposta.read())

    finally:
        servidor.parar()


def pessoa(identificador, status, faltando=()):

    return PessoaObservada(
        identificador=identificador,
        caixa=(0, 0, 5, 5),
        status=status,
        itens=(ResultadoEPI("capacete", status is StatusPessoa.LIBERADO, 0.9),),
        faltando=faltando,
    )


def test_todos_os_valores_de_acesso_sao_conhecidos_pela_catraca():
    """Se surgir um status novo, a catraca precisa aprender a tratá-lo."""

    assert {status.value for status in StatusAcesso} == VALORES_DE_ACESSO_DA_CATRACA


def test_negado_informa_quem_e_o_que_falta(auditoria):

    estado = EstadoCena(
        pessoas=(
            pessoa(1, StatusPessoa.LIBERADO),
            pessoa(2, StatusPessoa.NEGADO, ("capacete", "oculos")),
        ),
        acesso=StatusAcesso.NEGADO,
        setor="Canteiro de obras",
        exigidos=("capacete", "oculos"),
    )

    dados = ler_ao_vivo(estado, auditoria=auditoria)

    assert dados["camera_ativa"] is True
    assert dados["acesso"] == "negado"
    assert [p["status"] for p in dados["pessoas"]] == ["liberado", "negado"]

    # Nomes legíveis, com acento: a catraca tira os acentos para a tela
    assert dados["pessoas"][1]["faltando"] == ["Capacete", "Óculos"]


@pytest.mark.parametrize(
    "acesso, esperado",
    [
        (StatusAcesso.LIBERADO, "liberado"),
        (StatusAcesso.ANALISANDO, "analisando"),
        (StatusAcesso.SEM_PESSOAS, "sem_pessoas"),
    ],
)
def test_outros_status(auditoria, acesso, esperado):

    dados = ler_ao_vivo(EstadoCena(acesso=acesso), auditoria=auditoria)

    assert dados["acesso"] == esperado
    assert dados["camera_ativa"] is True


def test_camera_desligada(auditoria):
    """Sem frame, a catraca mostra "CAMERA OFF" e fica fechada."""

    dados = ler_ao_vivo(EstadoCena(), frame=None, auditoria=auditoria)

    assert dados["camera_ativa"] is False
