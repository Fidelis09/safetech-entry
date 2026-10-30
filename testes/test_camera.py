"""
Câmera (safetech/servicos/camera.py), com foco na câmera IP.

Em vez de uma câmera de verdade, os testes sobem um servidor de vídeo
MJPEG em 127.0.0.1 (CameraIPFalsa). Ele pode ser desligado e religado
para simular uma queda de rede.
"""

import pytest

from safetech import config
from safetech.servicos.camera import (
    Camera,
    EstadoCamera,
    eh_endereco_ip,
    esconder_senha,
    montar_endereco,
)
from testes.falsos import CameraIPFalsa, esperar


# ============================================================
# ENDEREÇOS
# ============================================================

def test_numero_e_webcam_texto_e_camera_ip():

    assert not eh_endereco_ip(0)
    assert eh_endereco_ip("rtsp://192.168.0.50/stream")


def test_montar_endereco_com_usuario_e_senha():

    endereco = montar_endereco("rtsp://192.168.0.5:554/s?a=1", "admin", "1234")

    assert endereco == "rtsp://admin:1234@192.168.0.5:554/s?a=1"


def test_caracteres_especiais_da_senha_sao_codificados():
    """Um "@" ou ":" na senha confundiria o endereço se não fosse codificado."""

    endereco = montar_endereco("rtsp://192.168.0.5/s", "admin", "p@ss:1")

    assert endereco == "rtsp://admin:p%40ss%3A1@192.168.0.5/s"


def test_sem_usuario_o_endereco_nao_muda():

    assert montar_endereco("  http://192.168.0.20:8080/video ") == "http://192.168.0.20:8080/video"


def test_esconder_senha():

    assert esconder_senha("rtsp://admin:1234@192.168.0.5:554/s") == "rtsp://192.168.0.5:554/s"
    assert esconder_senha("http://192.168.0.5/video") == "http://192.168.0.5/video"


# ============================================================
# CONEXÃO COM A CÂMERA IP FALSA
# ============================================================

@pytest.fixture
def camera_ip(monkeypatch):
    """Servidor de vídeo ligado e tempos de rede curtos (testes rápidos)."""

    monkeypatch.setattr(config, "TEMPO_LIMITE_CONEXAO_IP_MS", 3000)
    monkeypatch.setattr(config, "TEMPO_LIMITE_LEITURA_IP_MS", 2000)
    monkeypatch.setattr(config, "INTERVALO_RECONEXAO_IP_SEG", 0.5)

    servidor = CameraIPFalsa()
    servidor.ligar()

    yield servidor

    servidor.desligar()


def test_conecta_e_recebe_frames(camera_ip):

    camera = Camera(camera_ip.endereco)

    camera.iniciar()

    try:

        assert esperar(lambda: camera.estado is EstadoCamera.ATIVA, 10)
        assert esperar(lambda: camera.ler()[1] > 5, 10)

        frame, _ = camera.ler()

        assert frame.shape == (240, 320, 3)

    finally:
        camera.parar()

    assert camera.estado is EstadoCamera.PARADA


def test_reconecta_sozinha_quando_a_rede_volta(camera_ip):

    camera = Camera(camera_ip.endereco)

    camera.iniciar()

    try:

        assert esperar(lambda: camera.estado is EstadoCamera.ATIVA, 10)

        camera_ip.desligar()

        assert esperar(lambda: camera.estado is EstadoCamera.RECONECTANDO, 10)
        assert camera.ler()[0] is None

        camera_ip.ligar()

        assert esperar(lambda: camera.estado is EstadoCamera.ATIVA, 15)

        _, antes = camera.ler()

        assert esperar(lambda: camera.ler()[1] > antes, 5)

    finally:
        camera.parar()


def test_endereco_errado_vira_erro(monkeypatch):

    monkeypatch.setattr(config, "TEMPO_LIMITE_CONEXAO_IP_MS", 2000)

    # Porta onde nada está escutando
    camera = Camera("http://127.0.0.1:9/nada")

    camera.iniciar()

    assert esperar(lambda: camera.estado is EstadoCamera.ERRO, 15)

    camera.parar()

    # O erro continua visível até a próxima tentativa
    assert camera.estado is EstadoCamera.ERRO


def test_trocar_fonte_parada_so_guarda_a_escolha():

    camera = Camera(0)

    camera.trocar_fonte("rtsp://192.168.0.50/stream")

    assert camera.fonte == "rtsp://192.168.0.50/stream"
    assert camera.e_camera_ip
    assert camera.estado is EstadoCamera.PARADA
