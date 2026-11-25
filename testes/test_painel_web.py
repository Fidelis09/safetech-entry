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

    porta = porta_livre()

    servidor = ServidorWeb(auditoria, None, host="127.0.0.1", porta=porta)
    servidor.iniciar()

    # 127.0.0.1, e não "localhost": no Windows, "localhost" tenta
    # primeiro o IPv6 e perde uns 2 segundos em cada pedido.
    servidor.endereco_de_teste = f"http://127.0.0.1:{porta}"

    yield servidor

    servidor.parar()


def pedir(servidor, caminho, metodo="GET", login=True):
    """Faz um pedido ao painel; devolve (código HTTP, corpo)."""

    pedido = urllib.request.Request(servidor.endereco_de_teste + caminho, method=metodo)

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

    # Os dados precisam de login...
    for rota in ("/api/historico", "/api/ao-vivo", "/api/areas", "/exportar.csv", "/ao-vivo.jpg", "/api/login"):
        assert pedir(painel, rota, login=False)[0] == 401

    # ...mas a página em si é pública: ela mostra a tela de login (sem dados)
    assert pedir(painel, "/", login=False)[0] == 200


def test_login_da_pagina_nao_abre_a_janela_do_navegador(painel):
    """Pedido da página (X-SafeTech-Painel): 401 sem WWW-Authenticate. Os outros continuam com."""

    if not config.PAINEL_WEB_SENHA:
        pytest.skip("painel configurado sem senha")

    def cabecalho_de_login(extras):

        pedido = urllib.request.Request(painel.endereco_de_teste + "/api/historico", headers=extras)

        try:
            urllib.request.urlopen(pedido, timeout=5)
        except urllib.error.HTTPError as erro:
            return erro.headers.get("WWW-Authenticate")

    assert cabecalho_de_login({"X-SafeTech-Painel": "1"}) is None
    assert cabecalho_de_login({}) is not None


def test_icones_e_manifesto_para_o_celular(painel):

    codigo, corpo = pedir(painel, "/manifest.webmanifest", login=False)

    assert codigo == 200
    assert json.loads(corpo)["icons"][0]["src"] == "/icone-192.png"

    codigo, corpo = pedir(painel, "/icone-192.png", login=False)

    assert codigo == 200
    assert corpo.startswith(b"\x89PNG")


def test_historico_filtrado_por_area_e_data(auditoria):

    from safetech.nucleo import horario

    servidor = ServidorWeb(auditoria)

    for area in ("Portaria", "Pátio", "Portaria"):
        auditoria.registrar(
            evento="ENTRADA", identificador_pessoa=1, setor="Canteiro", exigidos=(), itens=(),
            faltando=(), liberado=True, area=area,
        )

    hoje = horario.agora().date().isoformat()

    assert servidor.dados_historico(area="Portaria")["filtrados"] == 2
    assert servidor.dados_historico(de=hoje, ate=hoje)["filtrados"] == 3
    assert servidor.dados_historico(de="2000-01-01", ate="2000-01-02")["filtrados"] == 0

    dados = servidor.dados_historico(area="Pátio")

    assert [evento["area"] for evento in dados["eventos"]] == ["Pátio"]
    assert dados["areas"] == ["Portaria", "Pátio"]


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


# ============================================================
# VÁRIAS ÁREAS E EXPORTAÇÃO
# ============================================================

@pytest.fixture
def painel_com_areas(auditoria):
    """Painel com duas áreas: uma com câmera e uma pessoa negada, outra desligada."""

    from safetech.nucleo.tipos import EstadoCena, PessoaObservada, StatusAcesso, StatusPessoa

    negada = PessoaObservada(
        identificador=1,
        caixa=(10, 10, 60, 100),
        status=StatusPessoa.NEGADO,
        faltando=("capacete",),
    )

    estado_portaria = EstadoCena(
        pessoas=(negada,),
        acesso=StatusAcesso.NEGADO,
        setor="Canteiro de obras",
        exigidos=("capacete",),
        modo=config.MODO_CATRACA,
        area="Portaria",
    )

    areas = [
        ("Portaria", np.zeros((120, 160, 3), np.uint8), estado_portaria, True),
        ("Pátio", None, EstadoCena(modo=config.MODO_VIGILANCIA, area="Pátio"), False),
    ]

    porta = porta_livre()

    servidor = ServidorWeb(auditoria, None, host="127.0.0.1", porta=porta, fonte_areas=lambda: areas)
    servidor.iniciar()

    servidor.endereco_de_teste = f"http://127.0.0.1:{porta}"

    yield servidor

    servidor.parar()


def test_api_areas_resume_cada_area(painel_com_areas):

    codigo, corpo = pedir(painel_com_areas, "/api/areas")

    assert codigo == 200

    portaria, patio = json.loads(corpo)

    assert portaria["area"] == "Portaria"
    assert portaria["titulo"] == "ACESSO NEGADO"
    assert portaria["pessoas"] == 1 and portaria["irregulares"] == 1
    assert portaria["comanda_catraca"] is True

    assert patio["camera_ativa"] is False
    assert patio["acesso"] == "camera_desligada"
    assert patio["nome_modo"] == "Vigilância"


def test_imagem_de_cada_area(painel_com_areas):

    # Área com câmera: JPEG
    codigo, corpo = pedir(painel_com_areas, "/ao-vivo.jpg?area=0")

    assert codigo == 200
    assert corpo.startswith(b"\xff\xd8")   # início de todo arquivo JPEG

    # Câmera desligada, número fora da lista ou lixo: sem imagem, sem derrubar o servidor
    assert pedir(painel_com_areas, "/ao-vivo.jpg?area=1")[0] == 503
    assert pedir(painel_com_areas, "/ao-vivo.jpg?area=9")[0] == 503
    assert pedir(painel_com_areas, "/ao-vivo.jpg?area=abc")[0] == 503


def test_sem_aplicativo_a_lista_de_areas_vem_vazia(painel):

    codigo, corpo = pedir(painel, "/api/areas")

    assert codigo == 200
    assert json.loads(corpo) == []


def test_exportar_csv_baixa_o_historico(painel):

    pedido = urllib.request.Request(painel.endereco_de_teste + "/exportar.csv")

    credenciais = f"{config.PAINEL_WEB_USUARIO}:{config.PAINEL_WEB_SENHA}"
    pedido.add_header("Authorization", "Basic " + base64.b64encode(credenciais.encode()).decode())

    with urllib.request.urlopen(pedido, timeout=5) as resposta:

        assert resposta.status == 200
        assert "attachment" in resposta.headers["Content-Disposition"]

        texto = resposta.read().decode("utf-8-sig")

    assert texto.startswith("Data e hora;")
    assert "Canteiro de obras" in texto and "Liberado" in texto


def test_exportar_tambem_e_somente_leitura(painel):

    assert pedir(painel, "/exportar.csv", metodo="POST")[0] == 405
