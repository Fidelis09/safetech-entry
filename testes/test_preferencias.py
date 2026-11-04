"""
Preferências salvas entre execuções (safetech/servicos/preferencias.py).
"""

import json

from safetech import config
from safetech.servicos import preferencias


def test_sem_arquivo_usa_os_padroes(tmp_path):

    arquivo = tmp_path / "preferencias.json"

    setor, exigidos, modo = preferencias.carregar(arquivo)

    assert setor == config.SETOR_PADRAO
    assert exigidos == list(config.SETORES[config.SETOR_PADRAO])
    assert modo == config.MODO_DETECCAO_PADRAO
    assert preferencias.carregar_fonte_camera(arquivo) == config.INDICE_CAMERA


def test_arquivo_corrompido_nao_quebra(tmp_path):

    arquivo = tmp_path / "preferencias.json"
    arquivo.write_text("{ isto não é json", encoding="utf-8")

    assert preferencias.carregar(arquivo)[0] == config.SETOR_PADRAO


def test_salvar_e_carregar_fiscalizacao(tmp_path):

    arquivo = tmp_path / "preferencias.json"

    preferencias.salvar("Laboratório", ["oculos", "luvas"], config.MODO_VIGILANCIA, arquivo)

    assert preferencias.carregar(arquivo) == ("Laboratório", ["oculos", "luvas"], config.MODO_VIGILANCIA)


def test_epi_que_nao_existe_mais_e_descartado(tmp_path):

    arquivo = tmp_path / "preferencias.json"

    preferencias.salvar("X", ["capacete", "botas"], config.MODO_CATRACA, arquivo)

    assert preferencias.carregar(arquivo)[1] == ["capacete"]


def test_cada_item_salvo_preserva_os_outros(tmp_path):

    arquivo = tmp_path / "preferencias.json"

    preferencias.salvar_cameras_ip([("Portaria", "rtsp://1.2.3.4/s")], arquivo)
    preferencias.salvar("Laboratório", ["oculos"], config.MODO_CATRACA, arquivo)
    preferencias.salvar_fonte_camera(2, arquivo)

    dados = json.loads(arquivo.read_text(encoding="utf-8"))

    assert dados["setor"] == "Laboratório"
    assert dados["indice_camera"] == 2
    assert dados["cameras_ip"] == [{"nome": "Portaria", "endereco": "rtsp://1.2.3.4/s"}]


def test_camera_ip_escolhida_volta_ao_abrir(tmp_path):

    arquivo = tmp_path / "preferencias.json"
    endereco = "rtsp://admin:1234@192.168.0.50/stream"

    preferencias.salvar_cameras_ip([("Portaria", endereco)], arquivo)
    preferencias.salvar_fonte_camera(endereco, arquivo)

    assert preferencias.carregar_fonte_camera(arquivo) == endereco
    assert preferencias.carregar_cameras_ip(arquivo) == [("Portaria", endereco)]


def test_camera_ip_removida_volta_para_a_webcam_padrao(tmp_path):

    arquivo = tmp_path / "preferencias.json"

    preferencias.salvar_fonte_camera("rtsp://192.168.0.50/stream", arquivo)

    # Não está na lista de câmeras cadastradas
    assert preferencias.carregar_fonte_camera(arquivo) == config.INDICE_CAMERA


def test_indice_invalido_e_ignorado(tmp_path):

    arquivo = tmp_path / "preferencias.json"

    for invalido in (-1, True, 2.5, None):

        preferencias.salvar_fonte_camera(invalido, arquivo)

        assert preferencias.carregar_fonte_camera(arquivo) == config.INDICE_CAMERA
