"""
Melhorias de UI/UX: avisos em cartões, dicas, painel de atalhos (F1),
evento selecionado com barras e ícones, tabela (colunas, "mostrar mais",
período com datas) e os ícones dos EPIs no relatório.

As caixas de confirmação com o tema (interface/dialogos.py) são modais e
aparecem na tela: nos testes elas são trocadas por respostas prontas
(fixture janela), como antes eram as do Windows.
"""

import tkinter as tk
from dataclasses import replace

import numpy as np
import pytest

from safetech import config
from safetech.interface import dialogos
from safetech.nucleo import horario
from safetech.nucleo.epis import chave_do_epi, ler_confiancas
from safetech.nucleo.tipos import ResultadoEPI


@pytest.fixture
def janela(raiz, sem_ia, monkeypatch):

    from safetech.interface import janela_principal
    from testes.falsos import CameraParada

    monkeypatch.setattr(dialogos, "confirmar", lambda *a, **k: True)

    tela = janela_principal.JanelaPrincipal(raiz, 1.0, camera=CameraParada())

    tela._auditoria.zerar()
    tela._painel_auditoria.esvaziar()

    yield tela

    try:
        tela._ao_fechar()
    except tk.TclError:
        pass


def registrar(janela, pessoa, liberado=False, faltando=("capacete",)):

    registro = janela._auditoria.registrar(
        evento="ENTRADA",
        identificador_pessoa=pessoa,
        setor="Canteiro de obras",
        exigidos=("capacete", "luvas"),
        itens=(ResultadoEPI("capacete", liberado, 0.9 if liberado else 0.2), ResultadoEPI("luvas", True, 0.95)),
        faltando=() if liberado else faltando,
        liberado=liberado,
        imagem_bgr=np.zeros((40, 40, 3), np.uint8),
    )

    janela._painel_auditoria.adicionar(registro)

    return registro


# ============================================================
# AVISOS EM CARTÕES (toasts)
# ============================================================

def test_aviso_vira_cartao_e_fica_no_rodape(janela):

    janela.avisar("Relatório salvo.", tipo="sucesso")

    assert janela.avisos.textos() == ["Relatório salvo."]
    assert "Relatório salvo." in janela._rotulo_aviso.cget("text")


def test_aviso_de_erro_pelo_comeco_do_texto(janela, monkeypatch):

    tipos = []
    monkeypatch.setattr(janela.avisos, "mostrar", lambda texto, tipo, segundos: tipos.append(tipo))

    janela.avisar("Não foi possível exportar: arquivo aberto.")
    janela.avisar("Área criada.")

    assert tipos == ["erro", "info"]


def test_cartoes_somem_sozinhos_e_nao_passam_do_limite(janela):

    from safetech.interface import componentes

    for numero in range(componentes.MAXIMO_AVISOS_NA_TELA + 2):
        janela.avisar(f"aviso {numero}", segundos=0)

    # Os mais antigos saíram para os novos caberem
    assert len(janela.avisos.textos()) == componentes.MAXIMO_AVISOS_NA_TELA
    assert janela.avisos.textos()[-1] == f"aviso {componentes.MAXIMO_AVISOS_NA_TELA + 1}"

    # Vencidos (0 segundos): somem no próximo ciclo
    janela.avisos.atualizar()

    assert janela.avisos.textos() == []


# ============================================================
# ATALHOS (F1) E DICAS
# ============================================================

def test_painel_de_atalhos_abre_e_fecha_com_esc(janela):

    janela._atalhos.alternar()

    assert janela._atalhos.visivel

    janela._ao_apertar_esc()

    assert not janela._atalhos.visivel


def test_dica_nao_aparece_em_componente_escondido(raiz):

    from safetech.interface.componentes import Dica

    botao = tk.Button(raiz, text="X")

    dica = Dica(botao, "explica o botão")
    dica.mostrar()

    # A janela está escondida (teste): a dica não abre nada na tela
    assert dica._janela is None
    assert dica.texto == "explica o botão"


# ============================================================
# EVENTO SELECIONADO
# ============================================================

def test_ler_confiancas_e_chave_do_epi():

    assert ler_confiancas("Capacete 97%, Óculos 12%, lixo") == [("Capacete", 0.97), ("Óculos", 0.12)]
    assert chave_do_epi("óculos") == "oculos"
    assert chave_do_epi("Máscara") is None


def test_evento_selecionado_desenha_uma_barra_por_epi(janela):

    registrar(janela, 1)

    tabela = janela._painel_auditoria._tabela
    tabela.selection_set(tabela.get_children()[0])
    janela._raiz.update()

    painel = janela._painel_auditoria

    assert painel._registro_nas_barras is not None

    # Por EPI: ícone, nome, trilho, barra e o número (5 desenhos)
    assert len(painel._tela_confiancas.find_all()) == 2 * 5

    textos = [painel._tela_confiancas.itemcget(item, "text") for item in painel._tela_confiancas.find_all() if painel._tela_confiancas.type(item) == "text"]

    assert any("faltou" in texto for texto in textos)
    assert any(texto.startswith("95%") for texto in textos)


# ============================================================
# TABELA
# ============================================================

def test_escolher_colunas_fica_salvo(janela):

    from safetech.servicos import preferencias

    painel = janela._painel_auditoria

    painel._mostrar_coluna["setor"].set(False)
    painel._ao_mudar_coluna()

    assert "setor" not in painel._tabela.cget("displaycolumns")
    assert "setor" not in preferencias.carregar_colunas_auditoria()


def test_sempre_fica_uma_coluna(janela):

    painel = janela._painel_auditoria

    for variavel in painel._mostrar_coluna.values():
        variavel.set(False)

    painel._ao_mudar_coluna()

    assert painel.colunas_visiveis() == ["timestamp"]


def test_mostrar_mais_linhas(janela, monkeypatch):

    monkeypatch.setattr(config, "MAXIMO_LINHAS_TABELA", 2)

    painel = janela._painel_auditoria
    painel._limite_linhas = 2

    for pessoa in range(1, 6):
        registrar(janela, pessoa)

    painel._redesenhar_tabela()

    assert len(painel._tabela.get_children()) == 2
    assert "2 de 5" in painel._rotulo_quantas.cget("text")

    painel.mostrar_mais()

    assert len(painel._tabela.get_children()) == 4

    painel.mostrar_mais()

    assert len(painel._tabela.get_children()) == 5
    assert not painel._linha_mais.winfo_manager()


def test_periodo_com_datas_escolhidas(janela):

    painel = janela._painel_auditoria

    hoje = registrar(janela, 1)
    antigo = replace(hoje, timestamp="2020-03-10T10:00:00-03:00", pessoa="P099")

    painel.adicionar(antigo)

    painel.definir_intervalo("2020-03-01", "2020-03-31")

    assert painel.registros_filtrados() == [antigo]
    assert "a 31/03/2020" in painel._periodo.get()

    # Escolher um período pronto volta ao normal
    painel._periodo.set("Todo o histórico")
    painel._ao_mudar_periodo(tk.Entry(janela._raiz))

    assert len(painel.registros_filtrados()) == 2


@pytest.mark.parametrize(
    "texto, esperado",
    [("25/11/2026", "2026-11-25"), ("2026-11-25", "2026-11-25"), ("25-11-2026", "2026-11-25"), ("31/02/2026", None), ("ontem", None)],
)
def test_data_digitada(texto, esperado):

    assert horario.ler_data_digitada(texto) == esperado


# ============================================================
# ÍCONES DOS EPIs NOS CHIPS E NO RELATÓRIO
# ============================================================

def test_chips_tem_icone(janela):

    painel = janela._painel_monitoramento

    assert painel._chips["capacete"].cget("image")
    assert set(painel._icones_chips["capacete"]) == {"normal", "marcado", "desativado"}


def test_relatorio_tem_os_icones_dos_epis(janela, tmp_path):

    from safetech.servicos import relatorio

    registro = registrar(janela, 1)

    pasta = relatorio.salvar(registro, janela._auditoria.pasta_imagens, pasta_relatorios=tmp_path)

    assert "data:image/png;base64," in (pasta / "relatorio.html").read_text(encoding="utf-8")


def test_controladores_usam_os_dialogos_com_o_tema(janela, monkeypatch):
    """Zerar pergunta pelo diálogo novo, com o botão vermelho (perigoso)."""

    perguntas = []

    def responder(pai, titulo, mensagem, texto_confirmar="", perigoso=False):
        perguntas.append((titulo, perigoso))
        return False

    monkeypatch.setattr(dialogos, "confirmar", responder)

    janela.eventos.zerar()

    assert perguntas == [("Zerar a auditoria", True)]
