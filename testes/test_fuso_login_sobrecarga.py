"""
Robustez, parte 2:

    - horário dos eventos no padrão ISO 8601, com o fuso (nucleo/horario.py),
      sem quebrar os logs antigos, gravados sem fuso;
    - limite de logins errados no painel web (acesso_web.LimiteDeTentativas);
    - aviso de sobrecarga quando a análise de uma área fica lenta.
"""

import base64
import re
import socket
import urllib.error
import urllib.request
from types import SimpleNamespace

import pytest

from safetech import config
from safetech.nucleo import horario
from safetech.nucleo.tipos import EstadoCena, ResultadoEPI
from safetech.servicos import acesso_web
from safetech.servicos.acesso_web import AjustesPainelWeb, LimiteDeTentativas
from safetech.servicos.auditoria import gerar_csv_exportacao
from safetech.servicos.camera import EstadoCamera
from safetech.web.servidor import ServidorWeb


# ============================================================
# HORÁRIO COM FUSO
# ============================================================

def test_agora_tem_o_fuso():

    texto = horario.agora_iso()

    # Ex.: 2026-11-25T09:18:51-03:00
    assert re.fullmatch(r"\d{4}-\d\d-\d\dT\d\d:\d\d:\d\d[+-]\d\d:\d\d", texto)


@pytest.mark.parametrize(
    "texto, exibir, fuso, data, hora",
    [
        ("2026-11-25T09:18:51-03:00", "2026-11-25 09:18:51", "-03:00", "2026-11-25", 9),
        ("2026-11-25T23:05:00+05:30", "2026-11-25 23:05:00", "+05:30", "2026-11-25", 23),
        # Formato antigo, sem fuso: continua funcionando
        ("2026-11-24 14:10:32", "2026-11-24 14:10:32", "", "2026-11-24", 14),
    ],
)
def test_ler_os_dois_formatos(texto, exibir, fuso, data, hora):

    assert horario.para_exibir(texto) == exibir
    assert horario.fuso(texto) == fuso
    assert horario.data(texto) == data
    assert horario.hora(texto) == hora


def test_texto_estranho_nao_quebra():

    assert horario.ler("ontem") is None
    assert horario.hora("ontem") is None
    assert horario.para_exibir("ontem") == "ontem"


def test_relatorio_mostra_o_fuso():

    assert horario.para_relatorio("2026-11-25T09:18:51-03:00") == "25/11/2026 09:18:51 (UTC-03:00)"
    assert horario.para_relatorio("2026-11-24 14:10:32") == "24/11/2026 14:10:32"


def registrar(auditoria):

    return auditoria.registrar(
        evento="ENTRADA",
        identificador_pessoa=1,
        setor="Canteiro de obras",
        exigidos=("capacete",),
        itens=(ResultadoEPI("capacete", True, 0.9),),
        faltando=(),
        liberado=True,
    )


def test_evento_novo_e_gravado_com_fuso(auditoria):

    registro = registrar(auditoria)

    assert horario.fuso(registro.timestamp) != ""

    # E volta igual do CSV
    assert auditoria.carregar_historico()[0].timestamp == registro.timestamp


def test_planilha_tem_data_legivel_e_coluna_do_fuso(auditoria):

    from dataclasses import replace

    novo = registrar(auditoria)
    antigo = replace(novo, timestamp="2026-11-24 14:10:32")

    linhas = gerar_csv_exportacao([novo, antigo]).splitlines()

    cabecalho = linhas[0].split(config.SEPARADOR_CSV_EXPORTACAO)

    assert cabecalho[-1] == "Fuso (UTC)"

    coluna_fuso = cabecalho.index("Fuso (UTC)")

    novo_valores = linhas[1].split(config.SEPARADOR_CSV_EXPORTACAO)
    antigo_valores = linhas[2].split(config.SEPARADOR_CSV_EXPORTACAO)

    # "Data e hora" sem o "T" (o Excel entende); o fuso na coluna dele
    assert "T" not in novo_valores[0]
    assert novo_valores[coluna_fuso] == horario.fuso(novo.timestamp)
    assert antigo_valores[coluna_fuso] == ""


def test_relatorio_de_evento_com_fuso(auditoria, tmp_path):

    from safetech.servicos import relatorio

    registro = registrar(auditoria)

    pasta = relatorio.salvar(registro, auditoria.pasta_imagens, pasta_relatorios=tmp_path)

    assert "(UTC" in (pasta / "relatorio.html").read_text(encoding="utf-8")


def test_painel_web_conta_eventos_de_hoje_por_hora(auditoria):

    registro = registrar(auditoria)

    dados = ServidorWeb(auditoria).dados_historico()

    assert dados["hoje"]["total"] == 1
    assert dados["por_hora"][horario.hora(registro.timestamp)]["liberados"] == 1

    evento = dados["eventos"][0]

    assert evento["horario"] == horario.para_exibir(registro.timestamp)
    assert evento["fuso"] == horario.fuso(registro.timestamp)


# ============================================================
# LIMITE DE LOGINS ERRADOS
# ============================================================

class RelogioFalso:
    """Tempo controlado pelo teste, para não esperar minutos de verdade."""

    def __init__(self):
        self.agora = 1000.0

    def __call__(self):
        return self.agora


def test_bloqueia_depois_de_erros_demais_e_libera_depois():

    relogio = RelogioFalso()

    limite = LimiteDeTentativas(maximo=3, janela_seg=60, bloqueio_seg=120, relogio=relogio)

    assert not limite.registrar_falha("10.0.0.5")
    assert not limite.registrar_falha("10.0.0.5")
    assert limite.registrar_falha("10.0.0.5")   # a 3ª bloqueia

    assert limite.bloqueado_por("10.0.0.5") == pytest.approx(120)

    # Outro aparelho não é afetado
    assert limite.bloqueado_por("10.0.0.9") == 0

    relogio.agora += 121

    assert limite.bloqueado_por("10.0.0.5") == 0


def test_erros_antigos_e_login_certo_zeram_a_contagem():

    relogio = RelogioFalso()

    limite = LimiteDeTentativas(maximo=3, janela_seg=60, bloqueio_seg=120, relogio=relogio)

    limite.registrar_falha("10.0.0.5")
    limite.registrar_falha("10.0.0.5")

    # Fora da janela: os dois erros de antes não contam mais
    relogio.agora += 61

    assert not limite.registrar_falha("10.0.0.5")

    # Acertou: zera
    limite.registrar_sucesso("10.0.0.5")

    assert not limite.registrar_falha("10.0.0.5")
    assert not limite.registrar_falha("10.0.0.5")


def porta_livre():

    with socket.socket() as teste:
        teste.bind(("127.0.0.1", 0))
        return teste.getsockname()[1]


def pedir(porta, usuario=None, senha=None):
    """Devolve (código HTTP, cabeçalhos)."""

    pedido = urllib.request.Request(f"http://127.0.0.1:{porta}/api/historico")

    if usuario is not None:
        credenciais = base64.b64encode(f"{usuario}:{senha}".encode()).decode()
        pedido.add_header("Authorization", "Basic " + credenciais)

    try:
        with urllib.request.urlopen(pedido, timeout=5) as resposta:
            return resposta.status, resposta.headers

    except urllib.error.HTTPError as erro:
        return erro.code, erro.headers


@pytest.fixture
def painel(auditoria, monkeypatch):

    monkeypatch.setattr(config, "PAINEL_WEB_TENTATIVAS_MAXIMAS", 3)

    ajustes = AjustesPainelWeb(True, False, 8080, "gerente", acesso_web.gerar_hash("senha-certa"))

    porta = porta_livre()

    servidor = ServidorWeb(auditoria, host="127.0.0.1", porta=porta, ajustes=ajustes)
    servidor.iniciar()

    servidor.porta_de_teste = porta

    yield servidor

    servidor.parar()


def test_painel_bloqueia_quem_erra_a_senha_demais(painel):

    porta = painel.porta_de_teste

    assert pedir(porta, "gerente", "errada")[0] == 401
    assert pedir(porta, "gerente", "errada")[0] == 401

    codigo, cabecalhos = pedir(porta, "gerente", "errada")

    assert codigo == 429
    assert int(cabecalhos["Retry-After"]) > 0

    # Bloqueado: nem a senha certa entra até o tempo passar
    assert pedir(porta, "gerente", "senha-certa")[0] == 429


def test_pedido_sem_login_nao_conta_como_erro(painel):

    porta = painel.porta_de_teste

    # O navegador sempre pergunta sem login antes: isso não é tentativa errada
    for _ in range(10):
        assert pedir(porta)[0] == 401

    assert pedir(porta, "gerente", "senha-certa")[0] == 200


# ============================================================
# SOBRECARGA
# ============================================================

@pytest.mark.parametrize(
    "analises, fps, lenta",
    [
        (14, 30, False),   # em dia
        (3, 30, True),     # câmera dá 30, análise faz 3: lenta
        (5, 30, False),    # acima do mínimo absoluto (4)
        (3, 5, False),     # câmera IP de 5 fps: 3 é mais que a metade
        (2, 5, True),      # abaixo da metade do que a câmera permite
        (0, 0, False),     # câmera sem frames: não é sobrecarga
    ],
)
def test_analise_lenta(analises, fps, lenta):

    from safetech.interface.area_monitorada import analise_lenta

    assert analise_lenta(analises, fps) is lenta


def area_falsa(analises):

    from safetech.interface.area_monitorada import AreaMonitorada

    area = AreaMonitorada(dados=None, camera=SimpleNamespace(estado=EstadoCamera.ATIVA, fps=30.0), parametros=None, painel=None)

    estado = EstadoCena(analises_por_segundo=analises)

    area.analisador = SimpleNamespace(erro=None, estado=lambda: estado)

    return area


def test_sobrecarga_so_vale_se_durar(monkeypatch):

    monkeypatch.setattr(config, "TEMPO_SOBRECARGA_SEG", 5.0)

    area = area_falsa(analises=2)

    # Um pico curto não conta
    assert area.verificar_sobrecarga(100.0) is None
    assert area.verificar_sobrecarga(103.0) is None

    # Lenta por 5 s seguidos: sobrecarga
    assert area.verificar_sobrecarga(105.0) == 2

    # Normalizou: some, e a contagem recomeça
    area.analisador = SimpleNamespace(erro=None, estado=lambda: EstadoCena(analises_por_segundo=14))

    assert area.verificar_sobrecarga(106.0) is None


def test_selo_de_sobrecarga_aparece_e_some(raiz, sem_ia, monkeypatch):

    from safetech.interface import janela_principal
    from testes.falsos import CameraParada

    tela = janela_principal.JanelaPrincipal(raiz, 1.0, camera=CameraParada())

    try:

        area = tela.areas.lista[0]

        monkeypatch.setattr(tela.areas, "sobrecarregadas", lambda agora: [(area, 2.0)])

        tela._atualizar_selo_sobrecarga(agora=1e9)

        assert tela._selo_sobrecarga.rotulo.cget("text") == f"Sobrecarga: {area.nome} (2 análises/s)"

        monkeypatch.setattr(tela.areas, "sobrecarregadas", lambda agora: [])

        tela._atualizar_selo_sobrecarga(agora=2e9)

        assert tela._selo_sobrecarga.rotulo.cget("text") == ""

    finally:
        tela._ao_fechar()
