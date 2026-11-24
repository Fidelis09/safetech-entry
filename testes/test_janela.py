"""
Janela principal (safetech/interface/janela_principal.py), sempre
ESCONDIDA e com câmera falsa: nenhuma janela aparece e a webcam não liga.

Testa os botões que mexem em arquivos: excluir linha, salvar relatório
e adicionar/remover câmera IP, e a janela de Configurações (que também
fica escondida: os testes só mexem nos controles dela, sem mostrá-la).
As caixas de confirmação e o navegador são trocados por versões falsas
que respondem sozinhas.
"""

import tkinter as tk
import webbrowser
from tkinter import messagebox

import numpy as np
import pytest

from safetech import config
from safetech.interface import janela_principal
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

    # Alguns testes já fecham a janela (para conferir o que acontece ao fechar)
    try:
        tela._ao_fechar()
    except tk.TclError:
        pass


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


def test_lista_de_cameras_fica_nas_configuracoes(janela):

    configuracoes = janela._configuracoes

    assert configuracoes._caixa_camera["values"] == ("Câmera 0",)

    # Webcam não se remove
    assert configuracoes._botao_remover_ip.instate(["disabled"])

    # O painel principal não tem mais a lista de câmeras
    assert not hasattr(janela._painel_monitoramento, "_caixa_camera")


def test_adicionar_camera_ip(janela, monkeypatch):

    preferencias.salvar_cameras_ip([])

    monkeypatch.setattr(janela_principal, "pedir_camera_ip", lambda pai, sugerido: ("Portaria", ENDERECO))

    janela._adicionar_camera_ip()

    painel = janela._configuracoes

    assert janela._camera.fonte == ENDERECO
    assert preferencias.carregar_cameras_ip() == [("Portaria", ENDERECO)]
    assert preferencias.carregar_areas()[0].fonte == ENDERECO
    assert painel._nome_da_camera.get() == "Portaria (IP)"

    # A senha nunca aparece na tela
    assert "segredo" not in " ".join(painel._caixa_camera["values"])
    assert "segredo" not in janela._rotulo_aviso.cget("text")

    # Câmera IP selecionada: agora dá para remover
    assert not painel._botao_remover_ip.instate(["disabled"])


def test_remover_camera_ip_volta_para_a_webcam(janela, monkeypatch):

    preferencias.salvar_cameras_ip([])

    monkeypatch.setattr(janela_principal, "pedir_camera_ip", lambda pai, sugerido: ("Portaria", ENDERECO))

    janela._adicionar_camera_ip()
    janela._remover_camera_ip(ENDERECO)

    assert preferencias.carregar_cameras_ip() == []
    assert janela._camera.fonte == 0  # a webcam que estava em uso antes
    assert "Portaria (IP)" not in janela._configuracoes._caixa_camera["values"]
    assert janela._configuracoes._botao_remover_ip.instate(["disabled"])


# ============================================================
# JANELA DE CONFIGURAÇÕES
# ============================================================

def test_configuracoes_comecam_escondidas(janela):

    assert janela._configuracoes.state() == "withdrawn"


def test_mudar_confianca_e_intervalo_vale_na_hora_e_fica_salvo(janela):

    configuracoes = janela._configuracoes

    configuracoes._limiar.set(65)
    configuracoes._intervalo.set(2.5)
    configuracoes._ao_mover_deslizante()

    # Vale na hora para o analisador
    assert janela._parametros.limiar_confianca == pytest.approx(0.65)
    assert janela._parametros.intervalo_classificacao == pytest.approx(2.5)

    # A gravação espera o controle parar; ao fechar, o pendente é gravado
    janela._ao_fechar()

    assert preferencias.carregar_ajustes() == (pytest.approx(0.65), pytest.approx(2.5))


def test_voltar_aos_padroes(janela):

    configuracoes = janela._configuracoes

    configuracoes._limiar.set(55)
    configuracoes._ao_mover_deslizante()

    configuracoes._restaurar_padroes()

    assert janela._parametros.limiar_confianca == pytest.approx(config.LIMIAR_CONFIANCA_PADRAO)
    assert janela._parametros.intervalo_classificacao == pytest.approx(config.INTERVALO_CLASSIFICACAO_PADRAO_SEG)


def test_setor_escolhido_marca_os_epis_na_propria_aba(janela):

    painel = janela._painel_monitoramento

    painel._setor.set("Laboratório")
    painel._ao_escolher_setor_na_lista()

    esperado = tuple(c for c in config.SETORES["Laboratório"] if c in janela._epis_do_modelo)

    assert janela._parametros.setor == "Laboratório"
    assert janela._parametros.exigidos == esperado
    assert painel._exigidos() == esperado

    # E fica salvo na área
    assert preferencias.carregar_areas()[0].setor == "Laboratório"


def test_marcar_epi_na_tela_principal_vira_personalizado(janela):

    painel = janela._painel_monitoramento

    # Uma combinação que não é de nenhum setor pronto
    for chave, variavel in painel._exigir.items():
        variavel.set(chave in ("capacete", "luvas"))

    painel._ao_marcar_exigido()

    assert janela._parametros.setor == config.SETOR_PERSONALIZADO
    assert painel._setor.get() == config.SETOR_PERSONALIZADO
    assert set(janela._parametros.exigidos) == {"capacete", "luvas"}


def test_coleta_usa_os_rotulos_marcados_nas_configuracoes(janela, monkeypatch):

    salvos = []
    monkeypatch.setattr(janela, "_salvar_imagem", salvos.append)

    configuracoes = janela._configuracoes
    configuracoes._ao_salvar_imagem = janela._salvar_imagem

    configuracoes._usando["capacete"].set(True)
    configuracoes.salvar_imagem()

    assert salvos == [{"capacete"}]


def test_painel_principal_tem_so_a_fiscalizacao_da_area(janela):
    """Setor, modo, EPIs exigidos e câmera na aba; o resto foi para as Configurações."""

    painel = janela._painel_monitoramento

    for removido in ("_limiar", "_intervalo", "_usando", "_caixa_camera"):
        assert not hasattr(painel, removido)

    for mantido in ("_caixa_setor", "_modo", "_exigir", "_botao_camera"):
        assert hasattr(painel, mantido)

    # A fiscalização saiu das Configurações
    assert "fiscalizacao" not in janela._configuracoes._abas


# ============================================================
# VÁRIAS ÁREAS (uma aba por câmera)
# ============================================================

@pytest.fixture
def criar_area(janela, monkeypatch):
    """Cria uma área nova respondendo sozinho à janela "Nova área"."""

    def criar(nome, fonte=0):

        monkeypatch.setattr(
            janela_principal, "pedir_area", lambda *args, **kwargs: (nome, fonte)
        )

        janela._nova_area()

        return janela._area_atual

    return criar


def test_comeca_com_uma_area_que_comanda_a_catraca(janela):

    assert [area.nome for area in janela._areas] == [config.NOME_AREA_PADRAO]
    assert janela._area_da_catraca() is janela._areas[0]

    # Aba da área (com a marca da catraca) e a aba "+ Nova área"
    abas = [janela._caderno.tab(aba, "text") for aba in janela._caderno.tabs()]

    assert abas[0].startswith(config.NOME_AREA_PADRAO) and "catraca" in abas[0]
    assert "Nova área" in abas[-1]


def test_nova_area_ganha_aba_e_fiscalizacao_propria(janela, criar_area):

    principal = janela._areas[0]

    nova = criar_area("Laboratório", fonte=2)

    assert len(janela._areas) == 2
    assert janela._area_atual is nova
    assert nova.camera.fonte == 2

    # A nova aba fica antes de "+ Nova área"
    abas = janela._caderno.tabs()

    assert abas[1] == str(nova.painel)
    assert abas[-1] == str(janela._aba_nova)

    # Fiscalização independente: mudar uma não muda a outra
    nova.painel._setor.set("Laboratório")
    nova.painel._ao_escolher_setor_na_lista()

    assert nova.parametros.setor == "Laboratório"
    assert principal.parametros.setor != "Laboratório"

    # Cada análise grava eventos com o nome da sua área
    assert nova.parametros.area == "Laboratório"

    # Tudo fica salvo
    salvas = preferencias.carregar_areas()

    assert [a.nome for a in salvas] == [config.NOME_AREA_PADRAO, "Laboratório"]
    assert salvas[1].setor == "Laboratório" and salvas[1].fonte == 2


def test_trocar_de_aba_muda_a_area_das_configuracoes(janela, criar_area):

    nova = criar_area("Pátio", fonte=3)

    assert janela._configuracoes._nome_da_area.get() == "Pátio"

    janela._selecionar_area(janela._areas[0])

    assert janela._configuracoes._nome_da_area.get() == config.NOME_AREA_PADRAO
    assert janela._configuracoes._nome_da_camera.get() == "Câmera 0"


def test_so_uma_area_comanda_a_catraca(janela, criar_area):

    principal = janela._areas[0]
    nova = criar_area("Portaria", fonte=2)

    # A área aberta (nova) passa a comandar: a outra é desmarcada
    janela._mudar_controle_catraca(True)

    assert nova.dados.controla_catraca and not principal.dados.controla_catraca
    assert janela._area_da_catraca() is nova
    assert "catraca" in janela._caderno.tab(nova.painel, "text")
    assert "catraca" not in janela._caderno.tab(principal.painel, "text")

    # Sem nenhuma marcada, a catraca recebe "vigilância" (fica fechada)
    janela._mudar_controle_catraca(False)

    _, estado = janela._ler_para_catraca()

    assert estado.modo == config.MODO_VIGILANCIA


def test_renomear_area(janela, monkeypatch):

    monkeypatch.setattr(janela_principal, "pedir_area", lambda *args, **kwargs: ("Entrada", None))

    janela._renomear_area()

    area = janela._areas[0]

    assert area.nome == "Entrada"
    assert area.parametros.area == "Entrada"
    assert janela._caderno.tab(area.painel, "text").startswith("Entrada")
    assert preferencias.carregar_areas()[0].nome == "Entrada"


def test_remover_area_nao_remove_a_ultima(janela, criar_area):

    # Com uma área só, nada acontece
    janela._remover_area()

    assert len(janela._areas) == 1

    criar_area("Pátio", fonte=3)

    janela._remover_area()   # confirmação respondida "sim" pela fixture

    assert [area.nome for area in janela._areas] == [config.NOME_AREA_PADRAO]
    assert janela._area_atual is janela._areas[0]
    assert len(janela._caderno.tabs()) == 2   # a área e "+ Nova área"
    assert [a.nome for a in preferencias.carregar_areas()] == [config.NOME_AREA_PADRAO]


def test_limite_de_areas(janela, criar_area, monkeypatch):

    monkeypatch.setattr(config, "MAXIMO_AREAS", 2)

    criar_area("Segunda", fonte=2)
    criar_area("Terceira", fonte=3)

    assert len(janela._areas) == 2
    assert "Limite" in janela._rotulo_aviso.cget("text")


def test_confianca_vale_para_todas_as_areas(janela, criar_area):

    nova = criar_area("Pátio", fonte=3)

    janela._configuracoes._limiar.set(70)
    janela._configuracoes._ao_mover_deslizante()

    for area in janela._areas:
        assert area.parametros.limiar_confianca == pytest.approx(0.70)

    assert nova.parametros.limiar_confianca == pytest.approx(0.70)


def test_areas_salvas_voltam_ao_abrir(raiz, sem_ia, monkeypatch):

    preferencias.salvar_areas([
        preferencias.DadosArea("Portaria", 0, "Canteiro de obras", ["capacete"], config.MODO_CATRACA, True),
        preferencias.DadosArea("Pátio", 3, "Área de circulação", ["colete"], config.MODO_CATRACA, False),
    ])

    tela = janela_principal.JanelaPrincipal(raiz, 1.0, camera=CameraParada())

    try:

        assert [area.nome for area in tela._areas] == ["Portaria", "Pátio"]
        assert tela._areas[1].parametros.setor == "Área de circulação"
        assert tela._area_da_catraca().nome == "Portaria"

        # A câmera das outras áreas é criada mas NÃO é ligada
        assert tela._areas[1].camera.estado.value == "parada"

    finally:
        tela._ao_fechar()



# ============================================================
# CABEÇALHO, LEGENDAS E VISÃO GERAL
# ============================================================

def test_selo_da_ia_mostra_que_esta_carregando(janela):

    # A fixture sem_ia impede a carga: a IA fica "carregando"
    assert "carregando" in janela._selo_ia.rotulo.cget("text")


def test_legenda_do_video_tem_area_resolucao_e_pessoas():

    from safetech.interface.area_monitorada import textos_da_legenda
    from safetech.nucleo.tipos import EstadoCena

    frame = np.zeros((720, 1280, 3), np.uint8)

    esquerda, direita = textos_da_legenda("Portaria", frame, 29.6, EstadoCena(analises_por_segundo=12.2))

    assert esquerda.startswith("AO VIVO") and "Portaria" in esquerda
    assert "1280\u00d7720" in direita and "30 fps" in direita and "0 pessoas" in direita


def test_visao_geral_so_com_duas_areas(janela, criar_area):

    # Com uma área só, o botão fica desativado
    assert janela._botao_visao_geral.instate(["disabled"])

    criar_area("Portaria", fonte=2)

    assert not janela._botao_visao_geral.instate(["disabled"])

    # Ligar mostra um quadro por área, no lugar das abas
    janela._visao_geral_ativa.set(True)
    janela._ao_alternar_visao_geral()
    janela._raiz.update()

    quadros = janela._visao_geral.quadros

    assert [quadro.area.nome for quadro in quadros] == [config.NOME_AREA_PADRAO, "Portaria"]
    assert not janela._caderno.winfo_ismapped()

    # Sem a IA carregada, cada quadro diz que está carregando
    janela._visao_geral.atualizar()

    assert quadros[0].etiqueta() == "CARREGANDO"

    # Clicar num quadro abre a aba daquela área e sai da visão geral
    janela._abrir_area_da_visao_geral(janela._areas[0])

    assert janela._area_atual is janela._areas[0]
    assert not janela._visao_geral_ativa.get()

    # Removendo a segunda área, a visão geral volta a ficar desativada
    janela._selecionar_area(janela._areas[1])
    janela._remover_area()

    assert janela._botao_visao_geral.instate(["disabled"])


def test_melhor_grade_aproveita_o_formato_do_painel():

    from safetech.interface.painel_visao_geral import melhor_grade

    # Painel alto: uma área em cima da outra; painel largo: lado a lado
    assert melhor_grade(2, 700, 800) == (1, 2)
    assert melhor_grade(2, 1600, 450) == (2, 1)

    # Quatro áreas num painel mais ou menos quadrado: 2 x 2
    assert melhor_grade(4, 1000, 700) == (2, 2)


# ============================================================
# AUDITORIA: PERÍODO, EXPORTAÇÃO E BIPE
# ============================================================

def test_periodo_filtra_tabela_e_cartoes(janela):

    from dataclasses import replace

    painel = janela._painel_auditoria

    hoje = registrar(janela, 1)

    # Um evento antigo, de 2020 (só na tela: não precisa estar no log)
    antigo = replace(hoje, timestamp="2020-01-01 10:00:00", pessoa="P099")

    painel.adicionar(antigo)

    assert len(painel._tabela.get_children()) == 2

    painel._periodo.set("Hoje")
    painel._ao_mudar_periodo(tk.Entry(janela._raiz))

    assert len(painel._tabela.get_children()) == 1
    assert painel._valor_total.cget("text") == "1"
    assert painel.registros_filtrados() == [hoje]

    # O filtro vale também para o que é exportado
    painel._periodo.set("Todo o histórico")
    painel._ao_mudar_periodo(tk.Entry(janela._raiz))

    assert painel._valor_total.cget("text") == "2"


def test_tabela_vazia_mostra_mensagem(janela):

    painel = janela._painel_auditoria

    janela._raiz.update()

    assert painel._rotulo_tabela_vazia.winfo_manager() == "place"

    registrar(janela, 1)

    assert painel._rotulo_tabela_vazia.winfo_manager() == ""


def test_exportar_grava_o_que_esta_filtrado(janela, monkeypatch, tmp_path):

    from tkinter import filedialog

    destino = tmp_path / "saida.csv"

    monkeypatch.setattr(filedialog, "asksaveasfilename", lambda **_kwargs: str(destino))

    registrar(janela, 1)
    registrar(janela, 2)

    # Só os irregulares (os dois registrados são "negado")
    janela._painel_auditoria._filtro_resultado.set("NAO")
    janela._painel_auditoria._exportar_filtrados()

    texto = destino.read_text(encoding="utf-8-sig")

    # Cabeçalho + os dois eventos
    assert len(texto.splitlines()) == 3
    assert ";P001;" in texto and ";P002;" in texto
    assert "exportados" in janela._rotulo_aviso.cget("text")


def test_exportar_sem_eventos_so_avisa(janela, monkeypatch):

    from tkinter import filedialog

    perguntou = []
    monkeypatch.setattr(filedialog, "asksaveasfilename", lambda **kwargs: perguntou.append(kwargs) or "")

    janela._painel_auditoria._exportar_filtrados()

    assert not perguntou
    assert "Nenhum evento" in janela._rotulo_aviso.cget("text")


def test_bipe_so_para_negado_no_modo_catraca(janela, monkeypatch):

    import queue
    from dataclasses import replace

    from safetech.servicos.analisador import Analisador

    bipes = []
    monkeypatch.setattr(janela, "_alertar_negado", lambda: bipes.append(1))

    area = janela._areas[0]
    area.analisador = Analisador.__new__(Analisador)
    area.analisador.registros_novos = queue.Queue()

    negado = registrar(janela, 1)

    # Negado na vigilância: registra, mas não bipa
    area.analisador.registros_novos.put(replace(negado, modo=config.MODO_VIGILANCIA))
    janela._receber_registros()

    assert bipes == []

    # Dois negados na catraca de uma vez: um bipe só
    area.analisador.registros_novos.put(negado)
    area.analisador.registros_novos.put(negado)
    janela._receber_registros()

    assert bipes == [1]

    area.analisador = None


# ============================================================
# BARRA DE ÁREAS, PÁGINA DA CÂMERA E CAPTURA DE FOTO
# ============================================================

def test_barra_tem_uma_pilula_por_area_e_abre_a_area(janela, criar_area):

    barra = janela._barra_areas

    nova = criar_area("Portaria", fonte=2)
    principal = janela._areas[0]

    assert list(barra._pilulas) == [str(principal.painel), str(nova.painel)]
    assert "Portaria" in barra._pilulas[str(nova.painel)].cget("text")

    # A área à vista fica marcada; clicar em outra pílula a abre
    assert barra._escolhida.get() == str(nova.painel)

    janela._ao_escolher_na_barra(str(principal.painel))

    assert janela._area_atual is principal
    assert barra._escolhida.get() == str(principal.painel)

    # Visão geral: nenhuma pílula marcada; voltar a uma área marca de novo
    janela._visao_geral_ativa.set(True)
    janela._ao_alternar_visao_geral()

    assert barra._escolhida.get() == ""

    janela._abrir_area_da_visao_geral(nova)

    assert barra._escolhida.get() == str(nova.painel)


def test_ponto_da_barra_mostra_a_situacao_da_area(janela):

    area = janela._areas[0]

    janela._proxima_conferencia_pontos = 0.0
    janela._atualizar_pontos_da_barra()

    # Sem a IA carregada (fixture sem_ia), a área está "carregando": cinza
    assert janela._barra_areas.cor(str(area.painel)) == area.resumo_status()[2]


def test_pagina_da_camera_mostra_a_camera_e_a_tela_de_espera(janela):

    painel = janela._painel_monitoramento

    assert painel._rotulo_camera.cget("text") == "Câmera 0"
    assert painel._rotulo_catraca.cget("text") == "comanda a catraca"

    painel.mostrar_mensagem("Câmera desligada\nLigue a câmera.", botao="Iniciar câmera")

    assert painel.mensagem() == ("Câmera desligada", "Ligue a câmera.")
    assert painel._tela.itemcget(painel._item_botao_espera, "state") == "normal"

    # Sem botão quando não há o que fazer (ex.: abrindo a câmera)
    painel.mostrar_mensagem("Abrindo a câmera...")

    assert painel._tela.itemcget(painel._item_botao_espera, "state") == "hidden"


def test_chips_dos_epis_marcam_o_exigido(janela):

    painel = janela._painel_monitoramento

    painel.mostrar_fiscalizacao("Laboratório", ("oculos", "luvas"))

    assert painel._chips["oculos"].cget("text").startswith("\u2713")
    assert not painel._chips["capacete"].cget("text").startswith("\u2713")


def test_capturar_foto_sem_camera_so_avisa(janela):

    janela._capturar_foto(janela._areas[0])

    assert "Ligue a câmera" in janela._rotulo_aviso.cget("text")


def test_capturar_foto_salva_imagem_carimbada(janela):

    import cv2

    from testes.falsos import CameraFalsa

    dados = preferencias.DadosArea(
        nome="Pátio",
        fonte=5,
        setor=config.SETOR_PADRAO,
        exigidos=list(config.SETORES[config.SETOR_PADRAO]),
        modo=config.MODO_CATRACA,
        controla_catraca=False,
    )

    area = janela._criar_area(dados, camera=CameraFalsa())

    janela._capturar_foto(area)

    caminho = janela._ultima_captura

    assert caminho.parent == config.PASTA_CAPTURAS
    assert "Patio" in caminho.name

    imagem = cv2.imread(str(caminho))

    # Mesmo tamanho do frame, com a faixa do carimbo embaixo (mais escura)
    assert imagem.shape[:2] == (480, 640)
    assert imagem[-6:, 20:200].mean() < imagem[:60].mean()

    # A captura não entra no log de auditoria
    assert janela._auditoria.carregar_historico() == []


# ============================================================
# AUDITORIA ACOMPANHA A ÁREA ABERTA
# ============================================================

def registrar_na_area(janela, pessoa, area):

    registro = janela._auditoria.registrar(
        evento="ENTRADA",
        identificador_pessoa=pessoa,
        setor="Canteiro de obras",
        exigidos=("capacete",),
        itens=(ResultadoEPI("capacete", False, 0.1),),
        faltando=("capacete",),
        liberado=False,
        area=area,
    )

    janela._painel_auditoria.adicionar(registro)

    return registro


def linhas_da_tabela(janela):

    tabela = janela._painel_auditoria._tabela

    return [tabela.item(linha, "values")[1] for linha in tabela.get_children()]


def test_auditoria_mostra_so_a_area_aberta_e_tudo_na_visao_geral(janela, criar_area):

    principal = janela._areas[0]
    portaria = criar_area("Portaria", fonte=2)

    registrar_na_area(janela, 1, principal.nome)
    registrar_na_area(janela, 2, "Portaria")
    registrar_na_area(janela, 3, "Portaria")

    painel = janela._painel_auditoria

    # A nova área está aberta: só os eventos dela, nos cartões e na tabela
    assert painel.area == "Portaria"
    assert sorted(linhas_da_tabela(janela)) == ["P002", "P003"]
    assert painel._valor_total.cget("text") == "2"
    assert "Portaria" in painel._rotulo_area.cget("text")

    # Abrir a outra área troca os eventos
    janela._selecionar_area(principal)

    assert linhas_da_tabela(janela) == ["P001"]
    assert painel._valor_total.cget("text") == "1"

    # Evento novo de OUTRA área conta no histórico, mas não aparece aqui
    registrar_na_area(janela, 4, "Portaria")

    assert linhas_da_tabela(janela) == ["P001"]

    # Visão geral: todas as áreas
    janela._visao_geral_ativa.set(True)
    janela._ao_alternar_visao_geral()

    assert painel.area is None
    assert len(linhas_da_tabela(janela)) == 4
    assert painel._valor_total.cget("text") == "4"
    assert "Todas" in painel._rotulo_area.cget("text")

    # A exportação segue o que está na tela
    assert len(painel.registros_filtrados()) == 4

    # Clicar num quadro volta a filtrar pela área dele
    janela._abrir_area_da_visao_geral(portaria)

    assert painel.area == "Portaria"
    assert len(painel.registros_filtrados()) == 3


def test_area_sem_eventos_avisa_na_tabela(janela, criar_area):

    registrar_na_area(janela, 1, janela._areas[0].nome)

    criar_area("Pátio", fonte=3)

    janela._raiz.update()

    painel = janela._painel_auditoria

    assert painel._rotulo_tabela_vazia.winfo_manager() == "place"
    assert "nesta área" in painel._rotulo_tabela_vazia.cget("text")


def test_renomear_area_aberta_acompanha_na_auditoria(janela, monkeypatch):

    monkeypatch.setattr(janela_principal, "pedir_area", lambda *args, **kwargs: ("Entrada", None))

    janela._renomear_area()

    assert janela._painel_auditoria.area == "Entrada"
