"""
Tema escuro e tema claro (safetech/interface/tema.py e a janela).

A troca de tema com o programa aberto descobre de qual chave da paleta
veio cada cor pela própria cor. Por isso as duas paletas precisam ter
as mesmas chaves e as mesmas "cores repetidas" — é o que o primeiro
teste confere. Os outros conferem a troca de verdade, com a janela
escondida.
"""

import itertools
import tkinter as tk

import pytest

from safetech import config
from safetech.interface import tema
from safetech.servicos import preferencias


# ============================================================
# PALETAS
# ============================================================

def test_paletas_tem_as_mesmas_chaves():

    escuro, claro = tema.PALETAS["escuro"], tema.PALETAS["claro"]

    assert set(escuro) == set(claro)
    assert set(tema.PALETAS) == set(config.TEMAS)


def test_cores_repetidas_se_repetem_nos_dois_temas():
    """Duas chaves com a mesma cor num tema precisam ter a mesma cor no outro."""

    escuro, claro = tema.PALETAS["escuro"], tema.PALETAS["claro"]

    for a, b in itertools.combinations(escuro, 2):

        iguais_no_escuro = escuro[a].lower() == escuro[b].lower()
        iguais_no_claro = claro[a].lower() == claro[b].lower()

        assert iguais_no_escuro == iguais_no_claro, (a, b)


def test_cores_de_status_sao_as_mesmas_nos_dois_temas():

    for chave in ("sucesso", "perigo", "alerta"):
        assert tema.PALETAS["escuro"][chave] == tema.PALETAS["claro"][chave]


# ============================================================
# TROCA COM O PROGRAMA ABERTO
# ============================================================

def test_trocar_tema_repinta_componentes_e_desenhos(raiz):

    rotulo = tk.Label(raiz, bg=tema.CORES["cartao"], fg=tema.CORES["texto"])
    fixo = tk.Label(raiz, bg=tema.CORES["perigo"], fg="white")

    tela = tk.Canvas(raiz, bg=tema.CORES["video"])
    texto = tela.create_text(10, 10, text="x", fill=tema.CORES["texto_suave"])

    tema.trocar_tema(raiz, "claro")

    assert tema.tema_atual() == "claro"

    assert rotulo.cget("bg") == tema.PALETAS["claro"]["cartao"]
    assert rotulo.cget("fg") == tema.PALETAS["claro"]["texto"]
    assert tela.cget("bg") == tema.PALETAS["claro"]["video"]
    assert tela.itemcget(texto, "fill") == tema.PALETAS["claro"]["texto_suave"]

    # Cores que não são da paleta (branco) e as de status não mudam
    assert fixo.cget("fg") == "white"
    assert fixo.cget("bg") == tema.PALETAS["claro"]["perigo"]

    # E volta
    tema.trocar_tema(raiz, "escuro")

    assert rotulo.cget("bg") == tema.PALETAS["escuro"]["cartao"]


def test_tema_desconhecido_vira_o_padrao():

    tema.definir_paleta("roxo")

    assert tema.tema_atual() == tema.TEMA_PADRAO


def test_preferencia_de_tema(tmp_path):

    arquivo = tmp_path / "preferencias.json"

    assert preferencias.carregar_tema(arquivo) == config.TEMA_PADRAO

    preferencias.salvar_tema("claro", arquivo)

    assert preferencias.carregar_tema(arquivo) == "claro"

    # Valor estranho no arquivo: volta ao padrão
    arquivo.write_text('{"tema": "neon"}', encoding="utf-8")

    assert preferencias.carregar_tema(arquivo) == config.TEMA_PADRAO


# ============================================================
# NA JANELA PRINCIPAL
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


def test_botao_do_tema_troca_e_salva(janela):

    assert "claro" in janela._botao_tema.cget("text").lower()

    janela._alternar_tema()

    assert tema.tema_atual() == "claro"
    assert preferencias.carregar_tema() == "claro"
    assert "escuro" in janela._botao_tema.cget("text").lower()

    # A janela e a tabela da auditoria seguem o tema novo
    assert janela._raiz.cget("bg") == tema.PALETAS["claro"]["fundo"]
    assert str(janela._painel_auditoria._tabela.tag_configure("impar", "background")) == tema.PALETAS["claro"]["linha_impar"]

    janela._alternar_tema()

    assert tema.tema_atual() == "escuro"


def test_janela_abre_no_tema_salvo(raiz, sem_ia):

    from safetech.interface import janela_principal
    from testes.falsos import CameraParada

    preferencias.salvar_tema("claro")

    tela = janela_principal.JanelaPrincipal(raiz, 1.0, camera=CameraParada())

    try:
        assert tema.tema_atual() == "claro"
        assert raiz.cget("bg") == tema.PALETAS["claro"]["fundo"]
    finally:
        tela._ao_fechar()
