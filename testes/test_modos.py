"""
Modos de operação: CATRACA e VIGILÂNCIA.

    catraca    -> "Liberado" / "Negado"; a catraca física obedece.
    vigilancia -> "Conforme" / "Não conforme"; a catraca física fica
                  desligada (fechada), e tudo é registrado igual.

A regra de decisão é a mesma: estes testes conferem que o MODO chega a
todos os lugares (estado da cena, auditoria, tela, relatório, painel
web, cabo da catraca) e que cada um mostra o texto certo.
"""

import csv
import json
import socket
import base64
import urllib.request
from pathlib import Path

import numpy as np
import pytest

from safetech import config
from safetech.nucleo import anotacao, modos
from safetech.nucleo.tipos import (
    EstadoCena,
    PessoaObservada,
    ResultadoEPI,
    StatusAcesso,
    StatusPessoa,
)
from safetech.servicos import preferencias, relatorio
from safetech.servicos.analisador import Analisador, ParametrosAnalise
from safetech.servicos.auditoria import COLUNAS, COLUNAS_EXCLUIDOS, COLUNAS_SEM_MODO, ServicoAuditoria
from safetech.servicos.catraca_serial import montar_linha
from testes.falsos import CameraFalsa, ClassificadorFalso, DetectorFalso, esperar


FIRMWARE = Path(__file__).resolve().parent.parent / "catraca_esp32" / "catraca_esp32.ino"


def pessoa(identificador, status, faltando=()):

    return PessoaObservada(
        identificador=identificador,
        caixa=(10, 10, 60, 60),
        status=status,
        itens=(ResultadoEPI("capacete", status is StatusPessoa.LIBERADO, 0.9),),
        faltando=faltando,
    )


def registrar(auditoria, numero, liberado, modo):

    return auditoria.registrar(
        evento="ENTRADA",
        identificador_pessoa=numero,
        setor="Canteiro de obras",
        exigidos=("capacete",),
        itens=(ResultadoEPI("capacete", liberado, 0.9 if liberado else 0.1),),
        faltando=() if liberado else ("capacete",),
        liberado=liberado,
        imagem_bgr=np.zeros((40, 40, 3), np.uint8),
        modo=modo,
    )


# ============================================================
# TEXTOS DE CADA MODO
# ============================================================

@pytest.mark.parametrize(
    "modo, ok, irregular",
    [
        (config.MODO_CATRACA, "Liberado", "Negado"),
        (config.MODO_VIGILANCIA, "Conforme", "Não conforme"),
    ],
)
def test_resultado_em_cada_modo(modo, ok, irregular):

    assert modos.resultado(modo, True) == ok
    assert modos.resultado(modo, False) == irregular


def test_nomes_antigos_e_vazio_viram_modos_atuais():

    assert modos.modo_valido("rosto") == config.MODO_CATRACA
    assert modos.modo_valido("corpo") == config.MODO_VIGILANCIA

    # Registro de antes da vigilância existir: era catraca
    assert modos.modo_valido("") == config.MODO_CATRACA
    assert modos.modo_valido("qualquer") == config.MODO_CATRACA


def test_palavra_no_video_depende_do_modo():

    negada = pessoa(1, StatusPessoa.NEGADO, ("capacete",))

    assert anotacao.texto_da_pessoa(negada, config.MODO_CATRACA) == "NEGADO"
    assert anotacao.texto_da_pessoa(negada, config.MODO_VIGILANCIA) == "SEM EPI"
    assert anotacao.texto_da_pessoa(pessoa(2, StatusPessoa.LIBERADO), config.MODO_VIGILANCIA) == "OK"
    assert anotacao.texto_da_pessoa(pessoa(3, StatusPessoa.ANALISANDO), config.MODO_VIGILANCIA) == "..."


# ============================================================
# PREFERÊNCIAS: "rosto" e "corpo" salvos por versões anteriores
# ============================================================

@pytest.mark.parametrize("antigo, atual", [("rosto", config.MODO_CATRACA), ("corpo", config.MODO_VIGILANCIA)])
def test_preferencia_antiga_e_convertida(tmp_path, antigo, atual):

    arquivo = tmp_path / "preferencias.json"
    arquivo.write_text(json.dumps({"modo_deteccao": antigo}), encoding="utf-8")

    assert preferencias.carregar(arquivo)[2] == atual


# ============================================================
# AUDITORIA: coluna "modo"
# ============================================================

def test_auditoria_grava_o_modo(auditoria):

    registrar(auditoria, 1, False, config.MODO_VIGILANCIA)
    registrar(auditoria, 2, True, config.MODO_CATRACA)

    assert [r.modo for r in auditoria.carregar_historico()] == ["vigilancia", "catraca"]


def test_log_sem_modo_e_convertido_sem_perder_nada(tmp_path):
    """
    O log da versão anterior (sem a coluna "modo") continua aparecendo:
    os eventos são copiados com o modo "catraca", e o arquivo original
    fica guardado, intacto, com outro nome.
    """

    log = tmp_path / "log_auditoria.csv"

    with open(log, "w", newline="", encoding="utf-8") as arquivo:
        escritor = csv.writer(arquivo)
        escritor.writerow(COLUNAS_SEM_MODO)
        escritor.writerow(["2026-10-28 10:00:00", "ENTRADA", "P001", "Obra", "Capacete", "", "Capacete 90%", "SIM", "a.jpg"])
        escritor.writerow(["2026-10-28 10:00:05", "ENTRADA", "P002", "Obra", "Capacete", "Capacete", "Capacete 10%", "NAO", "b.jpg"])

    servico = ServicoAuditoria(log, tmp_path / "imagens", tmp_path / "excluidos")

    historico = servico.carregar_historico()

    assert [(r.pessoa, r.liberado, r.modo) for r in historico] == [("P001", "SIM", "catraca"), ("P002", "NAO", "catraca")]

    # O original foi guardado, com as colunas de antes
    guardados = list(tmp_path.glob("log_auditoria_formato_antigo_*.csv"))

    assert len(guardados) == 1
    assert guardados[0].read_text(encoding="utf-8").splitlines()[0] == ",".join(COLUNAS_SEM_MODO)

    # E o log novo já está no formato atual
    assert log.read_text(encoding="utf-8").splitlines()[0] == ",".join(COLUNAS)


def test_log_de_excluidos_antigo_e_guardado_a_parte(tmp_path):

    excluidos = tmp_path / "excluidos"
    excluidos.mkdir()

    antigo = excluidos / "log_excluidos.csv"
    antigo.write_text(",".join(COLUNAS_SEM_MODO + ["excluido_em"]) + "\n", encoding="utf-8")

    servico = ServicoAuditoria(tmp_path / "log_auditoria.csv", tmp_path / "imagens", excluidos)

    assert list(excluidos.glob("log_excluidos_formato_antigo_*.csv"))

    # Exclusão nova vai para um log no formato atual
    servico.excluir(registrar(servico, 1, True, config.MODO_VIGILANCIA))

    assert (excluidos / "log_excluidos.csv").read_text(encoding="utf-8").splitlines()[0] == ",".join(COLUNAS_EXCLUIDOS)


# ============================================================
# ANALISADOR: o modo chega ao estado e à auditoria
# ============================================================

@pytest.mark.parametrize("modo", [config.MODO_CATRACA, config.MODO_VIGILANCIA])
def test_analisador_publica_e_registra_o_modo(auditoria, modo):

    parametros = ParametrosAnalise(
        setor="Canteiro de obras",
        exigidos=("capacete",),
        modo_deteccao=modo,
        intervalo_classificacao=0.05,
    )

    analisador = Analisador(
        CameraFalsa(),
        {modo: DetectorFalso([(50, 50, 200, 400)])},
        ClassificadorFalso([[0.05, 0.9, 0.9, 0.9]]),
        auditoria,
        parametros,
    )

    analisador.iniciar()

    try:

        assert esperar(lambda: len(auditoria.carregar_historico()) == 1, 10)

        assert analisador.estado().modo == modo
        assert auditoria.carregar_historico()[0].modo == modo

    finally:
        analisador.parar()


# ============================================================
# TELA: faixa de status e tabela de auditoria
# ============================================================

def estado_com_uma_irregular(modo):

    return EstadoCena(
        pessoas=(pessoa(1, StatusPessoa.NEGADO, ("capacete",)),),
        acesso=StatusAcesso.NEGADO,
        setor="Canteiro de obras",
        exigidos=("capacete",),
        modo=modo,
    )


def test_faixa_de_status_em_cada_modo():

    from safetech.interface.area_monitorada import descrever_acesso

    titulo, detalhe, _ = descrever_acesso(estado_com_uma_irregular(config.MODO_CATRACA))

    assert titulo == "ACESSO NEGADO"

    titulo, detalhe, _ = descrever_acesso(estado_com_uma_irregular(config.MODO_VIGILANCIA))

    assert titulo == "NÃO CONFORME"
    assert "LIBERADO" not in titulo and "NEGADO" not in titulo

    titulo, detalhe, _ = descrever_acesso(
        EstadoCena(pessoas=(pessoa(1, StatusPessoa.LIBERADO),), acesso=StatusAcesso.LIBERADO, modo=config.MODO_VIGILANCIA)
    )

    assert titulo == "EM CONFORMIDADE"
    assert "na área" in detalhe


def test_tabela_mostra_o_resultado_no_texto_do_modo(raiz, sem_ia):

    from safetech.interface import janela_principal
    from testes.falsos import CameraParada

    tela = janela_principal.JanelaPrincipal(raiz, 1.0, camera=CameraParada())

    try:

        tela._auditoria.zerar()
        tela._painel_auditoria.esvaziar()

        tela._painel_auditoria.adicionar(registrar(tela._auditoria, 1, False, config.MODO_CATRACA))
        tela._painel_auditoria.adicionar(registrar(tela._auditoria, 2, False, config.MODO_VIGILANCIA))

        tabela = tela._painel_auditoria._tabela

        linhas = [tabela.item(linha, "values") for linha in tabela.get_children()]

        # Mais recente primeiro: a da vigilância (Área, Resultado)
        assert linhas[0][-2:] == (config.NOME_AREA_PADRAO, "Não conforme")
        assert linhas[1][-2:] == (config.NOME_AREA_PADRAO, "Negado")

    finally:
        tela._ao_fechar()


# ============================================================
# RELATÓRIO
# ============================================================

def test_relatorio_da_vigilancia_nao_fala_em_acesso(auditoria, tmp_path):

    registro = registrar(auditoria, 1, False, config.MODO_VIGILANCIA)

    pasta = relatorio.salvar(registro, auditoria.pasta_imagens, pasta_relatorios=tmp_path / "rel")

    pagina = (pasta / "relatorio.html").read_text(encoding="utf-8")

    assert "NÃO CONFORME - P001" in pagina
    assert "Vigilância" in pagina
    assert "ACESSO" not in pagina


# ============================================================
# CATRACA FÍSICA: desligada na vigilância
# ============================================================

def test_cabo_manda_vigilancia_qualquer_que_seja_a_situacao():

    estado = estado_com_uma_irregular(config.MODO_VIGILANCIA)

    assert montar_linha(object(), estado).startswith("ST|vigilancia|")

    # Mesmo com a câmera parada, o modo vale mais
    assert montar_linha(None, estado).startswith("ST|vigilancia|")


def test_cabo_no_modo_catraca_continua_igual():

    assert montar_linha(object(), estado_com_uma_irregular(config.MODO_CATRACA)) == "ST|negado|1|1|Capacete\n"


def test_firmware_trata_a_vigilancia_pelo_cabo_e_pelo_wifi():

    codigo = FIRMWARE.read_text(encoding="utf-8")

    assert 'acesso == "vigilancia"' in codigo   # cabo
    assert 'modo == "vigilancia"' in codigo     # Wi-Fi (campo "modo" do /api/ao-vivo)


# ============================================================
# PAINEL WEB
# ============================================================

def porta_livre():

    with socket.socket() as teste:
        teste.bind(("127.0.0.1", 0))
        return teste.getsockname()[1]


def pedir_json(porta, caminho):

    pedido = urllib.request.Request(f"http://127.0.0.1:{porta}{caminho}")

    credenciais = f"{config.PAINEL_WEB_USUARIO}:{config.PAINEL_WEB_SENHA}"
    pedido.add_header("Authorization", "Basic " + base64.b64encode(credenciais.encode()).decode())

    with urllib.request.urlopen(pedido, timeout=5) as resposta:
        return json.loads(resposta.read())


def test_painel_web_informa_o_modo_e_os_textos(auditoria):

    from safetech.web.servidor import ServidorWeb

    registrar(auditoria, 1, False, config.MODO_VIGILANCIA)

    estado = estado_com_uma_irregular(config.MODO_VIGILANCIA)
    porta = porta_livre()

    servidor = ServidorWeb(auditoria, lambda: (np.zeros((10, 10, 3), np.uint8), estado), host="127.0.0.1", porta=porta)
    servidor.iniciar()

    try:

        ao_vivo = pedir_json(porta, "/api/ao-vivo")

        assert ao_vivo["modo"] == "vigilancia"
        assert ao_vivo["titulo"] == "NÃO CONFORME"

        # O campo "acesso" continua o mesmo (a catraca pelo Wi-Fi depende dele)
        assert ao_vivo["acesso"] == "negado"

        evento = pedir_json(porta, "/api/historico")["eventos"][0]

        assert evento["resultado"] == "Não conforme"
        assert evento["nome_modo"] == "Vigilância"

    finally:
        servidor.parar()
