"""
Exportação da auditoria para planilha e o carimbo das fotos de evidência.

    - gerar_csv_exportacao / exportar_csv (safetech/servicos/auditoria.py):
      cabeçalhos por extenso, ";" como separador, resultado no texto do
      modo e codificação que o Excel em português abre com acentos;
    - carimbar / sem_acentos (safetech/nucleo/anotacao.py).
"""

import csv

import numpy as np

from safetech import config
from safetech.nucleo import anotacao
from safetech.nucleo.tipos import ResultadoEPI
from safetech.servicos.auditoria import exportar_csv, gerar_csv_exportacao


def registrar(auditoria, pessoa, liberado, modo, area="Portaria"):

    return auditoria.registrar(
        evento="ENTRADA",
        identificador_pessoa=pessoa,
        setor="Canteiro de obras",
        exigidos=("capacete", "colete"),
        itens=(ResultadoEPI("capacete", liberado, 0.9 if liberado else 0.1),),
        faltando=() if liberado else ("capacete",),
        liberado=liberado,
        modo=modo,
        area=area,
    )


def ler_planilha(texto):

    return list(csv.reader(texto.splitlines(), delimiter=config.SEPARADOR_CSV_EXPORTACAO))


# ============================================================
# PLANILHA
# ============================================================

def test_planilha_tem_cabecalho_por_extenso_e_resultado_do_modo(auditoria):

    registros = [
        registrar(auditoria, 1, True, config.MODO_CATRACA),
        registrar(auditoria, 2, False, config.MODO_VIGILANCIA, area="Pátio"),
    ]

    linhas = ler_planilha(gerar_csv_exportacao(registros))

    cabecalho = linhas[0]

    assert cabecalho[:3] == ["Data e hora", "Área", "Modo"]
    assert "Resultado" in cabecalho and "Faltando" in cabecalho

    resultado = cabecalho.index("Resultado")

    # Uma linha por registro, na ordem recebida
    assert len(linhas) == 3
    assert linhas[1][resultado] == "Liberado"
    assert linhas[2][resultado] == "Não conforme"

    # O modo e o evento saem por extenso, não como chaves internas
    assert linhas[2][cabecalho.index("Modo")] == "Vigilância"
    assert linhas[1][cabecalho.index("Evento")] == "Entrada"
    assert linhas[2][cabecalho.index("Área")] == "Pátio"
    assert linhas[2][cabecalho.index("Faltando")] == "Capacete"


def test_planilha_vazia_so_tem_o_cabecalho():

    linhas = ler_planilha(gerar_csv_exportacao([]))

    assert len(linhas) == 1


def test_exportar_grava_arquivo_que_o_excel_abre_com_acentos(auditoria, tmp_path):

    registros = [registrar(auditoria, 1, False, config.MODO_VIGILANCIA, area="Laboratório")]

    destino = tmp_path / "exportado.csv"

    exportar_csv(registros, destino)

    dados = destino.read_bytes()

    # Marca BOM do UTF-8 no começo: é ela que faz o Excel ler os acentos
    assert dados.startswith(b"\xef\xbb\xbf")

    texto = dados.decode("utf-8-sig")

    assert "Laboratório" in texto and "Não conforme" in texto

    # O log de auditoria original não muda com a exportação
    assert len(auditoria.carregar_historico()) == 1


# ============================================================
# CARIMBO DAS FOTOS DE EVIDÊNCIA
# ============================================================

def test_carimbo_escurece_so_a_faixa_de_baixo():

    imagem = np.full((480, 640, 3), 200, np.uint8)

    anotacao.carimbar(imagem, "SafeTech Entry | 2026-11-24 14:00:00 | Area: Portaria | P001 | Negado")

    # O alto da foto fica intacto
    assert (imagem[:400] == 200).all()

    # Na faixa de baixo há pixels escurecidos (fundo) e claros (texto)
    faixa = imagem[-12:]

    assert faixa.min() < 120
    assert faixa.max() > 200


def test_sem_acentos_para_a_fonte_do_opencv():

    assert anotacao.sem_acentos("Área Laboratório, Não conforme") == "Area Laboratorio, Nao conforme"


def test_analisador_carimba_a_foto_de_evidencia(auditoria, monkeypatch):
    """A foto gravada no evento traz a faixa do carimbo embaixo."""

    import cv2

    from safetech.servicos.analisador import Analisador, ParametrosAnalise
    from testes.falsos import CameraFalsa, ClassificadorFalso, DetectorFalso, esperar

    monkeypatch.setattr(config, "CARIMBAR_EVIDENCIA", True)

    camera = CameraFalsa()
    camera._frame[:] = 230

    detectores = {modo: DetectorFalso([(100, 100, 300, 400)]) for modo in config.MODOS_DETECCAO}

    analisador = Analisador(
        camera,
        detectores,
        ClassificadorFalso([[0.9, 0.9, 0.9, 0.9]]),
        auditoria,
        ParametrosAnalise(area="Portaria"),
    )

    analisador.iniciar()

    try:
        assert esperar(lambda: not analisador.registros_novos.empty(), 5)
    finally:
        analisador.parar()

    registro = analisador.registros_novos.get_nowait()

    foto = cv2.imread(str(auditoria.pasta_imagens / registro.imagem))

    # Rodapé escurecido pelo carimbo; o alto da foto continua claro
    assert foto[-6:, 20:200].mean() < 150
    assert foto[:60].mean() > 200
