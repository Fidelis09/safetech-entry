"""
Acesso ao painel web ajustado na tela (safetech/servicos/acesso_web.py).

    - a senha vira hash (nunca é guardada como texto);
    - a validação dos campos da aba Configurações > Painel web;
    - os ajustes salvos em preferencias.json;
    - o servidor aceitando a senha nova e recusando a antiga;
    - o botão "Aplicar" da janela reiniciando o painel.

O painel de teste sobe só em 127.0.0.1 (nada de acesso pela rede, que
faria o firewall do Windows perguntar).
"""

import base64
import json
import socket
import tkinter as tk
import urllib.error
import urllib.request

import pytest

from safetech import config
from safetech.servicos import acesso_web, preferencias
from safetech.servicos.acesso_web import AjustesPainelWeb, montar_ajustes
from safetech.web.servidor import ServidorWeb


def porta_livre():

    with socket.socket() as teste:
        teste.bind(("127.0.0.1", 0))
        return teste.getsockname()[1]


def ajustes(porta=8080, senha="segredo123", **outros):

    valores = dict(
        ativo=True,
        na_rede=False,
        porta=porta,
        usuario="gerente",
        hash_senha=acesso_web.gerar_hash(senha) if senha else "",
    )
    valores.update(outros)

    return AjustesPainelWeb(**valores)


def pedir(porta, usuario=None, senha=None, caminho="/api/historico"):
    """Pedido ao painel em 127.0.0.1; devolve o código HTTP."""

    pedido = urllib.request.Request(f"http://127.0.0.1:{porta}{caminho}")

    if usuario is not None:
        credenciais = base64.b64encode(f"{usuario}:{senha}".encode()).decode()
        pedido.add_header("Authorization", "Basic " + credenciais)

    try:
        with urllib.request.urlopen(pedido, timeout=5) as resposta:
            return resposta.status

    except urllib.error.HTTPError as erro:
        return erro.code


# ============================================================
# HASH DA SENHA
# ============================================================

def test_hash_confere_so_a_senha_certa():

    guardado = acesso_web.gerar_hash("minha senha")

    assert "minha senha" not in guardado
    assert acesso_web.senha_confere("minha senha", guardado)
    assert not acesso_web.senha_confere("minha senhA", guardado)
    assert not acesso_web.senha_confere("", guardado)


def test_mesma_senha_gera_hashes_diferentes():
    """O sal aleatório: quem vê dois hashes não descobre que as senhas são iguais."""

    assert acesso_web.gerar_hash("igual") != acesso_web.gerar_hash("igual")


@pytest.mark.parametrize("estragado", ["", "texto qualquer", "md5$1$abc$def", "pbkdf2_sha256$x$y$z"])
def test_hash_estragado_nunca_confere(estragado):

    assert not acesso_web.senha_confere("qualquer", estragado)


# ============================================================
# VALIDAÇÃO DOS CAMPOS DA TELA
# ============================================================

def campos(**trocas):

    valores = dict(
        ativo=True,
        na_rede=False,
        porta="8090",
        exigir_login=True,
        usuario="gerente",
        nova_senha="",
        confirmacao="",
    )
    valores.update(trocas)

    return valores


def test_senha_em_branco_mantem_a_atual():

    atuais = ajustes()

    novos, erro = montar_ajustes(atuais, **campos(porta="9000"))

    assert erro is None
    assert novos.porta == 9000
    assert novos.hash_senha == atuais.hash_senha


def test_senha_nova_vira_hash():

    novos, erro = montar_ajustes(ajustes(), **campos(nova_senha="outra-senha", confirmacao="outra-senha"))

    assert erro is None
    assert acesso_web.senha_confere("outra-senha", novos.hash_senha)


@pytest.mark.parametrize(
    "trocas, trecho_do_erro",
    [
        ({"porta": "abc"}, "número"),
        ({"porta": "80"}, "entre"),
        ({"porta": "70000"}, "entre"),
        ({"usuario": "  "}, "usuário"),
        ({"usuario": "a:b"}, ":"),
        ({"nova_senha": "abcdefg", "confirmacao": "abcdefh"}, "diferentes"),
        ({"nova_senha": "abc", "confirmacao": "abc"}, "pelo menos"),
    ],
)
def test_campos_errados_explicam_o_problema(trocas, trecho_do_erro):

    novos, erro = montar_ajustes(ajustes(), **campos(**trocas))

    assert novos is None
    assert trecho_do_erro in erro


def test_exigir_login_sem_nenhuma_senha_definida():

    _, erro = montar_ajustes(ajustes(senha=None), **campos())

    assert "defina uma senha" in erro


def test_sem_login_apaga_o_hash():

    novos, erro = montar_ajustes(ajustes(), **campos(exigir_login=False))

    assert erro is None
    assert not novos.exige_login


# ============================================================
# AJUSTES SALVOS
# ============================================================

def test_ajustes_salvos_sem_a_senha_em_texto(tmp_path):

    arquivo = tmp_path / "preferencias.json"

    guardados = ajustes(porta=9123, senha="nao-pode-aparecer")

    preferencias.salvar_painel_web(guardados, arquivo)

    assert "nao-pode-aparecer" not in arquivo.read_text(encoding="utf-8")
    assert preferencias.carregar_painel_web(arquivo) == guardados


def test_sem_nada_salvo_vale_o_config(tmp_path):

    lidos = preferencias.carregar_painel_web(tmp_path / "nao_existe.json")

    assert lidos.porta == config.PAINEL_WEB_PORTA
    assert lidos.usuario == config.PAINEL_WEB_USUARIO
    assert acesso_web.usa_senha_padrao(lidos)


def test_ajustes_estragados_voltam_ao_config(tmp_path):

    arquivo = tmp_path / "preferencias.json"
    arquivo.write_text(json.dumps({"painel_web": {"porta": "nada", "ativo": True}}), encoding="utf-8")

    assert preferencias.carregar_painel_web(arquivo).porta == config.PAINEL_WEB_PORTA


# ============================================================
# SERVIDOR COM OS AJUSTES
# ============================================================

def test_servidor_aceita_a_senha_nova_e_recusa_a_antiga(auditoria):

    porta = porta_livre()

    servidor = ServidorWeb(auditoria, host="127.0.0.1", porta=porta, ajustes=ajustes(senha="senha-nova"))
    servidor.iniciar()

    try:
        assert pedir(porta) == 401
        assert pedir(porta, "gerente", config.PAINEL_WEB_SENHA) == 401
        assert pedir(porta, "outro", "senha-nova") == 401
        assert pedir(porta, "gerente", "senha-nova") == 200

        # Segunda vez: vem do conjunto de logins já conferidos
        assert pedir(porta, "gerente", "senha-nova") == 200
    finally:
        servidor.parar()


def test_servidor_sem_login(auditoria):

    porta = porta_livre()

    servidor = ServidorWeb(auditoria, host="127.0.0.1", porta=porta, ajustes=ajustes(senha=None))
    servidor.iniciar()

    try:
        assert pedir(porta) == 200
    finally:
        servidor.parar()


# ============================================================
# ABA "PAINEL WEB" DAS CONFIGURAÇÕES
# ============================================================

@pytest.fixture
def janela(raiz, sem_ia):

    from safetech.interface import janela_principal
    from testes.falsos import CameraParada

    tela = janela_principal.JanelaPrincipal(raiz, 1.0, camera=CameraParada())

    yield tela

    try:
        tela._ao_fechar()
    except tk.TclError:
        pass


def preencher(configuracoes, **valores):

    configuracoes._web_ativo.set(valores.get("ativo", True))
    configuracoes._web_na_rede.set(False)
    configuracoes._web_porta.set(str(valores["porta"]))
    configuracoes._web_exigir_login.set(True)
    configuracoes._web_usuario.set(valores.get("usuario", "chefe"))
    configuracoes._web_senha.set(valores.get("senha", ""))
    configuracoes._web_confirmacao.set(valores.get("confirmacao", valores.get("senha", "")))


def test_aplicar_liga_o_painel_com_a_senha_nova(janela):

    configuracoes = janela._configuracoes

    # No conftest o painel começa desligado
    assert janela.painel_web.servidor is None
    assert "desligado" in janela._rotulo_painel_web.cget("text")

    porta = porta_livre()

    preencher(configuracoes, porta=porta, senha="senha-da-obra")
    configuracoes._aplicar_painel_web()

    assert "No ar" in configuracoes._rotulo_situacao_web.cget("text") or "no ar" in configuracoes.mensagem_painel_web()
    assert janela.painel_web.servidor is not None

    # A senha digitada some dos campos depois de aplicada
    assert configuracoes._web_senha.get() == ""

    assert pedir(porta, "chefe", "senha-da-obra") == 200
    assert pedir(porta, "gerente", config.PAINEL_WEB_SENHA) == 401

    # Salvo sem a senha em texto
    assert "senha-da-obra" not in config.ARQUIVO_PREFERENCIAS.read_text(encoding="utf-8")
    assert preferencias.carregar_painel_web().porta == porta

    # Desligar: o servidor sai do ar
    configuracoes._web_ativo.set(False)
    configuracoes._aplicar_painel_web()

    assert janela.painel_web.servidor is None
    assert "desligado" in configuracoes.mensagem_painel_web()


def test_aplicar_com_erro_nao_muda_nada(janela):

    configuracoes = janela._configuracoes

    preencher(configuracoes, porta=porta_livre(), senha="abc")
    configuracoes._aplicar_painel_web()

    assert "pelo menos" in configuracoes.mensagem_painel_web()
    assert janela.painel_web.servidor is None


def test_porta_ocupada_avisa(janela):

    with socket.socket() as ocupante:

        ocupante.bind(("127.0.0.1", 0))
        ocupante.listen()

        porta = ocupante.getsockname()[1]

        preencher(janela._configuracoes, porta=porta, senha="senha-boa")
        janela._configuracoes._aplicar_painel_web()

    assert "em uso" in janela._configuracoes.mensagem_painel_web()
    assert janela.painel_web.servidor is None


def test_aviso_da_senha_padrao(janela):

    from safetech.servicos.acesso_web import ajustes_padrao

    padrao = ajustes_padrao()

    janela._configuracoes.definir_painel_web(AjustesPainelWeb(True, False, 8080, "gerente", padrao.hash_senha), None, True)

    assert "senha padrão" in janela._configuracoes._rotulo_aviso_web.cget("text")
