"""
Várias áreas (câmeras) ao mesmo tempo, fora da tela:

    - áreas salvas nas preferências (e a conversão das versões antigas);
    - coluna "area" na auditoria (e a conversão do log antigo);
    - o modelo de EPI dividido entre as análises das áreas;
    - duas análises gravando na MESMA auditoria, cada uma com a sua área.

Os botões e abas das áreas são testados em test_janela.py.
"""

import csv
import json
import threading
import time

import pytest

from safetech import config
from safetech.servicos import preferencias
from safetech.servicos.analisador import Analisador, ClassificadorCompartilhado, ParametrosAnalise
from safetech.servicos.auditoria import COLUNAS, COLUNAS_SEM_AREA, ServicoAuditoria
from testes.falsos import CameraFalsa, ClassificadorFalso, DetectorFalso, esperar


# ============================================================
# ÁREAS NAS PREFERÊNCIAS
# ============================================================

def test_sem_areas_salvas_monta_a_principal_com_o_que_ja_havia(tmp_path):
    """Arquivo de versão anterior: setor, EPIs, modo e câmera viram a área "Principal"."""

    arquivo = tmp_path / "preferencias.json"

    preferencias.salvar("Laboratório", ["oculos", "luvas"], "corpo", arquivo)
    preferencias.salvar_fonte_camera(2, arquivo)

    areas = preferencias.carregar_areas(arquivo)

    assert len(areas) == 1

    area = areas[0]

    assert area.nome == config.NOME_AREA_PADRAO
    assert (area.setor, area.exigidos, area.modo, area.fonte) == ("Laboratório", ["oculos", "luvas"], config.MODO_VIGILANCIA, 2)

    # Sozinha, ela comanda a catraca (como antes de existirem áreas)
    assert area.controla_catraca


def test_salvar_e_carregar_areas(tmp_path):

    arquivo = tmp_path / "preferencias.json"

    salvas = [
        preferencias.DadosArea("Portaria", 0, "Canteiro de obras", ["capacete", "colete"], config.MODO_CATRACA, True),
        preferencias.DadosArea("Pátio", 1, "Área de circulação", ["colete"], config.MODO_VIGILANCIA, False),
    ]

    preferencias.salvar_areas(salvas, arquivo)

    assert preferencias.carregar_areas(arquivo) == salvas


def test_areas_estranhas_sao_descartadas_ou_corrigidas(tmp_path):

    arquivo = tmp_path / "preferencias.json"

    arquivo.write_text(json.dumps({
        "areas": [
            "não é uma área",
            {"nome": "", "fonte": 0},                                # sem nome
            {"nome": "A", "fonte": 0, "modo": "rosto", "controla_catraca": True,
             "exigidos": ["capacete", "botas"]},
            {"nome": "A", "fonte": 1},                               # nome repetido
            {"nome": "B", "fonte": "rtsp://removida/s", "controla_catraca": True},
        ],
    }), encoding="utf-8")

    areas = preferencias.carregar_areas(arquivo)

    assert [area.nome for area in areas] == ["A", "B"]

    a, b = areas

    assert a.modo == config.MODO_CATRACA            # "rosto" convertido
    assert a.exigidos == ["capacete"]               # EPI que não existe sai

    # Câmera IP que não está mais cadastrada volta para a webcam padrão
    assert b.fonte == config.INDICE_CAMERA

    # Só a primeira marcada comanda a catraca
    assert a.controla_catraca and not b.controla_catraca


def test_salvar_areas_preserva_o_resto(tmp_path):

    arquivo = tmp_path / "preferencias.json"

    preferencias.salvar_cameras_ip([("Portaria", "rtsp://1.2.3.4/s")], arquivo)
    preferencias.salvar_areas([preferencias.DadosArea("X", "rtsp://1.2.3.4/s", "Acesso geral")], arquivo)

    assert preferencias.carregar_cameras_ip(arquivo) == [("Portaria", "rtsp://1.2.3.4/s")]
    assert preferencias.carregar_areas(arquivo)[0].fonte == "rtsp://1.2.3.4/s"


# ============================================================
# AUDITORIA: coluna "area"
# ============================================================

def test_log_sem_area_e_convertido_para_a_area_principal(tmp_path):

    log = tmp_path / "log_auditoria.csv"

    with open(log, "w", newline="", encoding="utf-8") as arquivo:
        escritor = csv.writer(arquivo)
        escritor.writerow(COLUNAS_SEM_AREA)
        escritor.writerow(["2026-11-01 10:00:00", "ENTRADA", "P001", "Obra", "Capacete", "", "Capacete 90%", "SIM", "a.jpg", "vigilancia"])

    servico = ServicoAuditoria(log, tmp_path / "imagens", tmp_path / "excluidos")

    registro = servico.carregar_historico()[0]

    assert (registro.modo, registro.area) == ("vigilancia", config.NOME_AREA_PADRAO)
    assert log.read_text(encoding="utf-8").splitlines()[0] == ",".join(COLUNAS)

    # O original fica guardado
    assert list(tmp_path.glob("log_auditoria_formato_antigo_*.csv"))


def test_auditoria_grava_a_area(auditoria):

    registro = auditoria.registrar(
        evento="ENTRADA",
        identificador_pessoa=1,
        setor="Obra",
        exigidos=(),
        itens=(),
        faltando=(),
        liberado=True,
        area="Portaria",
    )

    assert registro.area == "Portaria"
    assert auditoria.carregar_historico()[0].area == "Portaria"


# ============================================================
# MODELO DIVIDIDO ENTRE AS ÁREAS
# ============================================================

class ClassificadorQueVigia:
    """Conta quantas threads estão dentro dele ao mesmo tempo."""

    por_epi = True
    epis = ["capacete"]

    def __init__(self):

        self.dentro = 0
        self.maximo_junto = 0
        self._trava = threading.Lock()

    def classificar_lote(self, recortes):

        with self._trava:
            self.dentro += 1
            self.maximo_junto = max(self.maximo_junto, self.dentro)

        time.sleep(0.01)

        with self._trava:
            self.dentro -= 1

        return [[0.9]] * len(recortes)


def test_classificador_compartilhado_atende_uma_thread_por_vez():

    original = ClassificadorQueVigia()
    compartilhado = ClassificadorCompartilhado(original)

    assert (compartilhado.por_epi, compartilhado.epis) == (True, ["capacete"])

    threads = [
        threading.Thread(target=lambda: [compartilhado.classificar_lote([1]) for _ in range(5)])
        for _ in range(4)
    ]

    for thread in threads:
        thread.start()

    for thread in threads:
        thread.join()

    assert original.maximo_junto == 1


# ============================================================
# DUAS ÁREAS, UMA AUDITORIA
# ============================================================

def test_duas_areas_gravam_na_mesma_auditoria(auditoria):

    classificador = ClassificadorCompartilhado(ClassificadorFalso([[0.05, 0.9, 0.9, 0.9]]))

    analisadores = []

    for nome in ("Portaria", "Pátio"):

        parametros = ParametrosAnalise(
            setor="Canteiro de obras",
            exigidos=("capacete",),
            modo_deteccao=config.MODO_CATRACA,
            intervalo_classificacao=0.05,
            area=nome,
        )

        analisador = Analisador(
            CameraFalsa(),
            {config.MODO_CATRACA: DetectorFalso([(50, 50, 200, 400)])},
            classificador,
            auditoria,
            parametros,
        )

        analisador.iniciar()
        analisadores.append(analisador)

    try:

        assert esperar(lambda: len(auditoria.carregar_historico()) == 2, 10)

        assert {registro.area for registro in auditoria.carregar_historico()} == {"Portaria", "Pátio"}

        # O estado de cada análise diz de qual área é
        assert {analisador.estado().area for analisador in analisadores} == {"Portaria", "Pátio"}

    finally:

        for analisador in analisadores:
            analisador.parar()
