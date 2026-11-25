"""
Funções novas: indicadores e relatório em PDF, telão, modo calibração,
backup e restauração, assistente de configuração e o ícone do instalador.

Nenhuma janela aparece: o telão é escondido logo ao abrir, o assistente
é criado com mostrar=False e a janela de Indicadores nasce escondida.
"""

import json
import tkinter as tk
from dataclasses import replace
from datetime import date, timedelta
from pathlib import Path

import numpy as np
import pytest

from safetech import config
from safetech.nucleo import anotacao, horario
from safetech.nucleo.tipos import EstadoCena, PessoaObservada, RegistroAuditoria, ResultadoEPI, StatusAcesso, StatusPessoa
from safetech.servicos import backup, graficos, indicadores, preferencias, relatorio_pdf


def evento(dia, hora, liberado, faltando="", area="Portaria"):

    return RegistroAuditoria(
        timestamp=f"{dia}T{hora:02d}:00:00-03:00",
        evento="ENTRADA",
        pessoa="P001",
        setor="Canteiro de obras",
        exigidos="Capacete, Luvas",
        faltando=faltando,
        confiancas="",
        liberado="SIM" if liberado else "NAO",
        imagem="",
        modo=config.MODO_CATRACA,
        area=area,
    )


@pytest.fixture
def eventos():

    return [
        evento("2026-11-20", 8, True),
        evento("2026-11-20", 8, False, "Capacete, Luvas"),
        evento("2026-11-21", 14, False, "Luvas", area="Pátio"),
        evento("2026-11-21", 14, False, "Luvas"),
        # Formato antigo, sem fuso: também conta
        replace(evento("2026-11-22", 9, True, area="Pátio"), timestamp="2026-11-22 09:00:00"),
    ]


# ============================================================
# INDICADORES
# ============================================================

def test_indicadores_do_periodo(eventos):

    dados = indicadores.calcular(eventos, "2026-11-20", "2026-11-22")

    assert (dados.total, dados.conformes, dados.irregulares) == (5, 2, 3)
    assert dados.taxa == pytest.approx(0.4)

    # Luvas faltou 3 vezes, capacete 1
    assert dados.epi_que_mais_falta == ("Luvas", 3)
    assert dict(dados.faltas_por_epi) == {"Luvas": 3, "Capacete": 1}

    # 14h tem 2 irregulares: o horário crítico
    assert dados.hora_critica == 14

    assert dict((area, (total, ok)) for area, total, ok in dados.por_area) == {"Portaria": (3, 1), "Pátio": (2, 1)}

    # Um dia por posição, só dentro do período (dias sem eventos com zero)
    assert [dia for dia, _, _ in dados.por_dia] == ["2026-11-20", "2026-11-21", "2026-11-22"]


def test_indicadores_respeitam_o_periodo(eventos):

    dados = indicadores.calcular(eventos, "2026-11-21", "2026-11-21")

    assert dados.total == 2
    assert dados.hora_critica == 14


def test_sem_eventos(eventos):

    dados = indicadores.calcular(eventos, "2030-01-01", "2030-01-01")

    assert dados.total == 0
    assert dados.taxa is None
    assert dados.epi_que_mais_falta is None
    assert dados.hora_critica is None


def test_periodos_da_tela():

    hoje = date(2026, 11, 25)

    assert indicadores.periodo("Hoje", hoje) == ("2026-11-25", "2026-11-25")
    assert indicadores.periodo("Últimos 7 dias", hoje) == ("2026-11-19", "2026-11-25")
    assert indicadores.periodo("Todo o histórico", hoje) == (None, None)


def test_graficos_tem_o_tamanho_pedido(eventos):

    cores = {chave: "#ffffff" for chave in ("fundo", "texto", "texto_suave", "grade", "barra", "sucesso", "perigo")}

    imagens = graficos.graficos_dos_indicadores(indicadores.calcular(eventos), 400, 220, cores)

    assert set(imagens) == set(graficos.TITULOS_DOS_GRAFICOS)
    assert all(imagem.size == (400, 220) for imagem in imagens.values())


# ============================================================
# RELATÓRIO EM PDF
# ============================================================

def test_pdf_tem_resumo_e_lista_de_irregulares(eventos, tmp_path, monkeypatch):

    import re

    monkeypatch.setattr(config, "LINHAS_POR_PAGINA_PDF", 2)

    caminho = relatorio_pdf.gerar(eventos, tmp_path / "relatorio.pdf", "2026-11-20", "2026-11-22")

    conteudo = caminho.read_bytes()

    assert conteudo.startswith(b"%PDF")

    # 1 página de resumo + 2 de irregulares (3 irregulares, 2 por página).
    # Cada página do PDF tem um "/Type /Page" (sem o "s" de "/Pages").
    assert len(re.findall(rb"/Type\s*/Page(?!s)", conteudo)) == 3


def test_pdf_de_uma_area_so(eventos, tmp_path):

    caminho = relatorio_pdf.gerar(eventos, tmp_path / "patio.pdf", area="Pátio")

    assert caminho.exists()


def test_relatorio_diario_so_com_eventos(eventos, tmp_path):

    assert relatorio_pdf.gerar_diario(eventos, dia="2026-11-21", pasta=tmp_path) == tmp_path / "2026-11-21.pdf"
    assert (tmp_path / "2026-11-21.pdf").exists()

    # Dia sem eventos: não gera um relatório vazio
    assert relatorio_pdf.gerar_diario(eventos, dia="2026-11-23", pasta=tmp_path) is None


# ============================================================
# TELÃO
# ============================================================

def estado_negado(*faltas_por_pessoa):

    pessoas = tuple(
        PessoaObservada(numero, (0, 0, 10, 10), StatusPessoa.NEGADO, faltando=faltando)
        for numero, faltando in enumerate(faltas_por_pessoa, start=1)
    )

    return EstadoCena(pessoas, StatusAcesso.NEGADO, "Canteiro", ("capacete", "colete", "luvas"), 10, config.MODO_CATRACA, "Portaria")


def test_telao_mostra_o_que_falta_de_todas_as_pessoas():

    from safetech.interface.janela_telao import situacao_do_telao

    titulo, mensagem, _, epis = situacao_do_telao(estado_negado(("luvas",), ("capacete", "luvas")))

    assert "ACESSO NEGADO" in titulo
    assert mensagem == config.TEXTOS_POR_MODO[config.MODO_CATRACA]["telao_irregular"]

    # Sem repetir e na ordem de config.EPIS
    assert epis == ("capacete", "luvas")


def test_telao_nos_outros_casos():

    from safetech.interface.janela_telao import situacao_do_telao

    liberado = EstadoCena((), StatusAcesso.LIBERADO, "Canteiro", ("capacete",), 0, config.MODO_CATRACA, "Portaria")

    assert situacao_do_telao(liberado)[1] == "Pode passar"
    assert situacao_do_telao(liberado)[3] == ("capacete",)

    vigilancia = replace(liberado, acesso=StatusAcesso.SEM_PESSOAS, modo=config.MODO_VIGILANCIA)

    assert situacao_do_telao(vigilancia)[1] == "Nenhuma pessoa na área"

    assert situacao_do_telao(liberado, camera_ligada=False)[0] == "FORA DE OPERAÇÃO"


def test_icones_dos_epis():

    from safetech.nucleo.icones import desenhar_icone_epi

    for chave in [*config.EPIS, "mascara"]:

        icone = desenhar_icone_epi(chave, 64)

        assert icone.size == (64, 64)

        # Algo foi desenhado (não é só transparente)
        assert icone.getextrema()[3][1] > 0


def test_telao_abre_segue_a_area_e_fecha(raiz, sem_ia):

    from safetech.interface import janela_principal
    from testes.falsos import CameraParada

    tela = janela_principal.JanelaPrincipal(raiz, 1.0, camera=CameraParada())

    try:

        tela.telao.alternar()

        telao = tela.telao.telao
        telao.withdraw()   # não aparece na tela durante o teste

        assert tela.telao.area_do_telao() is tela.areas.lista[0]

        tela.telao.atualizar(forcar=True)

        # Câmera parada: fora de operação
        assert telao.situacao()[0] == "FORA DE OPERAÇÃO"

        tela.telao.alternar()

        assert tela.telao.telao is None

    finally:
        tela._ao_fechar()


# ============================================================
# MODO CALIBRAÇÃO
# ============================================================

def test_barras_de_confianca_desenhadas_embaixo_da_pessoa():

    imagem = np.full((480, 640, 3), 128, np.uint8)

    pessoa = PessoaObservada(
        1,
        (200, 100, 400, 250),
        StatusPessoa.NEGADO,
        itens=(ResultadoEPI("capacete", True, 0.95), ResultadoEPI("luvas", False, 0.2)),
        faltando=("luvas",),
    )

    anotacao.desenhar_confiancas(imagem, [pessoa], 1.0, 0.8, ("capacete", "luvas"))

    # Embaixo da caixa a imagem mudou; em cima, não
    assert (imagem[260:300, 200:400] != 128).any()
    assert (imagem[:90] == 128).all()


def test_pessoa_ainda_analisando_nao_tem_barras():

    imagem = np.full((200, 200, 3), 128, np.uint8)

    anotacao.desenhar_confiancas(imagem, [PessoaObservada(1, (10, 10, 50, 50), StatusPessoa.ANALISANDO)], 1.0, 0.8, ())

    assert (imagem == 128).all()


def test_sigla_do_epi():

    assert anotacao.sigla_do_epi("oculos") == "OCU"


def test_controle_da_calibracao_muda_a_confianca_de_todas_as_areas(raiz, sem_ia):

    from safetech.interface import janela_principal
    from testes.falsos import CameraParada

    tela = janela_principal.JanelaPrincipal(raiz, 1.0, camera=CameraParada())

    try:
        area = tela.areas.lista[0]

        area.painel._calibrando.set(True)
        area.painel._ao_clicar_calibrar()

        assert area.calibracao

        area.painel._limiar_calibracao.set(65)
        area.painel._ao_mover_limiar()

        assert area.parametros.limiar_confianca == pytest.approx(0.65)

        # O controle de Configurações > Análise acompanha
        assert tela.configuracoes._limiar.get() == pytest.approx(65)

    finally:
        tela._ao_fechar()


# ============================================================
# BACKUP E RESTAURAÇÃO
# ============================================================

def test_backup_salva_e_restaura_guardando_as_de_antes(tmp_path):

    preferencias_atuais = tmp_path / "preferencias.json"
    preferencias_atuais.write_text(json.dumps({"tema": "claro"}), encoding="utf-8")

    arquivo_backup = backup.salvar(tmp_path / "backup.json", preferencias_atuais)

    conteudo = backup.ler(arquivo_backup)

    assert conteudo["programa"] == backup.PROGRAMA
    assert conteudo["preferencias"] == {"tema": "claro"}

    # Mudou depois do backup...
    preferencias_atuais.write_text(json.dumps({"tema": "escuro"}), encoding="utf-8")

    # ...e restaurou: volta ao do backup, e o de antes fica guardado
    copia = backup.restaurar(arquivo_backup, preferencias_atuais)

    assert json.loads(preferencias_atuais.read_text(encoding="utf-8")) == {"tema": "claro"}
    assert json.loads(copia.read_text(encoding="utf-8")) == {"tema": "escuro"}


@pytest.mark.parametrize(
    "conteudo",
    [
        "isto nem é json",
        json.dumps({"qualquer": "coisa"}),
        json.dumps({"programa": "SafeTech Entry", "versao_formato": 1}),
        json.dumps({"programa": "SafeTech Entry", "versao_formato": 99, "preferencias": {}}),
    ],
)
def test_arquivo_que_nao_e_backup_e_recusado(tmp_path, conteudo):

    arquivo = tmp_path / "estranho.json"
    arquivo.write_text(conteudo, encoding="utf-8")

    preferencias_atuais = tmp_path / "preferencias.json"
    preferencias_atuais.write_text("{}", encoding="utf-8")

    with pytest.raises(backup.BackupInvalido):
        backup.restaurar(arquivo, preferencias_atuais)

    # Nada mudou
    assert preferencias_atuais.read_text(encoding="utf-8") == "{}"


# ============================================================
# ASSISTENTE DE CONFIGURAÇÃO
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


def test_assistente_nao_abre_sozinho_nos_testes(janela):

    janela.raiz.update()

    assert janela.sistema.assistente is None


def test_assistente_aplica_area_setor_modo_e_senha(janela):

    assistente = janela.sistema.abrir_assistente(mostrar=False)

    # Passos: boas-vindas -> câmera -> área
    assistente._avancar()
    assistente._avancar()

    assert assistente.passo_atual() == "area"

    assistente._nome_area.set("Portaria")
    assistente._setor.set("Laboratório")

    assistente._avancar()

    # Painel web: senha nova (com confirmação errada não passa)
    assistente._painel_ativo.set(False)
    assistente._senha.set("nova-senha-forte")
    assistente._confirmacao.set("outra")

    assistente._avancar()

    assert assistente.passo_atual() == "painel"
    assert "diferentes" in assistente._rotulo_erro.cget("text")

    assistente._confirmacao.set("nova-senha-forte")
    assistente._avancar()

    assert assistente.passo_atual() == "pronto"

    assistente._avancar()   # Concluir

    area = janela.areas.lista[0]

    assert area.nome == "Portaria"
    assert area.parametros.setor == "Laboratório"
    assert preferencias.assistente_concluido()

    from safetech.servicos import acesso_web

    assert acesso_web.senha_confere("nova-senha-forte", preferencias.carregar_painel_web().hash_senha)


def test_assistente_nao_aceita_nome_repetido(janela):

    from testes.falsos import CameraParada

    dados = preferencias.DadosArea(nome="Pátio", fonte=4, setor=config.SETOR_PADRAO, exigidos=[], modo=config.MODO_CATRACA, controla_catraca=False)
    janela.areas.criar(dados, camera=CameraParada())

    assistente = janela.sistema.abrir_assistente(mostrar=False)

    assistente._avancar()
    assistente._avancar()

    assistente._nome_area.set("pátio")
    assistente._avancar()

    assert assistente.passo_atual() == "area"
    assert "outra área" in assistente._rotulo_erro.cget("text")


# ============================================================
# RELATÓRIO DIÁRIO AUTOMÁTICO E ÍCONE
# ============================================================

def test_relatorio_diario_automatico_do_dia_anterior(janela, monkeypatch, auditoria):

    monkeypatch.setattr(config, "RELATORIO_DIARIO_AUTOMATICO", True)

    ontem = (date.today() - timedelta(days=1)).isoformat()

    monkeypatch.setattr(janela.auditoria, "carregar_historico", lambda: [evento(ontem, 10, False, "Luvas")])

    thread = janela.indicadores.conferir_relatorio_diario()

    thread.join(timeout=30)

    assert (config.PASTA_RELATORIOS_DIARIOS / f"{ontem}.pdf").exists()

    # No mesmo dia, não confere de novo
    assert janela.indicadores.conferir_relatorio_diario() is None


def test_icone_do_instalador(tmp_path, monkeypatch):

    import importlib.util

    caminho = Path(__file__).resolve().parent.parent / "instalador" / "criar_atalho.py"

    especificacao = importlib.util.spec_from_file_location("criar_atalho", caminho)
    modulo = importlib.util.module_from_spec(especificacao)
    especificacao.loader.exec_module(modulo)

    monkeypatch.setattr(modulo, "ARQUIVO_ICONE", tmp_path / "safetech.ico")

    icone = modulo.gerar_icone()

    assert icone.read_bytes()[:4] == b"\x00\x00\x01\x00"   # cabeçalho de todo arquivo .ico
