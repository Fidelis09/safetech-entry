"""
Peças falsas usadas nos testes, no lugar das reais.

Câmera, detector e classificador de verdade dependem de webcam e de
modelos de IA. As versões falsas abaixo têm a MESMA interface (os
mesmos métodos), mas devolvem dados combinados de antemão. Assim os
testes são rápidos, repetíveis e não precisam de hardware.
"""

import threading
import time
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer

import cv2
import numpy as np

from safetech.servicos.camera import EstadoCamera


# ============================================================
# CÂMERAS
# ============================================================

class CameraFalsa:
    """Entrega sempre a mesma imagem cinza, como se fosse um vídeo."""

    def __init__(self, largura=640, altura=480):

        self.fonte = 0
        self.estado = EstadoCamera.ATIVA
        self.fps = 30.0

        self._frame = np.full((altura, largura, 3), 90, np.uint8)
        self._numero = 0

    def ler(self):

        # Cada leitura conta como um frame novo
        self._numero += 1

        return self._frame, self._numero

    def iniciar(self):
        self.estado = EstadoCamera.ATIVA

    def parar(self):
        self.estado = EstadoCamera.PARADA

    def trocar_fonte(self, fonte):
        self.fonte = fonte


class CameraParada(CameraFalsa):
    """Câmera desligada: não entrega imagem nenhuma."""

    def __init__(self):

        super().__init__()

        self.estado = EstadoCamera.PARADA
        self.fps = 0.0

    def ler(self):
        return None, 0


# ============================================================
# DETECTOR E CLASSIFICADOR
# ============================================================

class DetectorFalso:
    """Sempre encontra as mesmas pessoas, nas caixas informadas."""

    disponivel = True

    def __init__(self, caixas):
        self.caixas = list(caixas)

    def detectar(self, _frame):
        return list(self.caixas)


class ClassificadorFalso:
    """
    Devolve, para a pessoa N da imagem, o vetor de probabilidades N.

    probabilidades -> uma lista por pessoa, na ordem de self.epis.
                      Pode ser trocada no meio do teste.
    """

    por_epi = True
    epis = ["capacete", "oculos", "colete", "luvas"]

    def __init__(self, probabilidades):
        self.probabilidades = probabilidades

    def classificar_lote(self, recortes):
        return [np.array(vetor, dtype=float) for vetor in self.probabilidades[: len(recortes)]]


# ============================================================
# CÂMERA IP FALSA (servidor de vídeo MJPEG em 127.0.0.1)
# ============================================================

class CameraIPFalsa:
    """
    Servidor HTTP que transmite um vídeo MJPEG, como uma câmera IP
    simples (ou o app "IP Webcam" do celular).

    Pode ser desligado e religado na mesma porta, para testar a
    reconexão automática.
    """

    def __init__(self):

        imagem = np.full((240, 320, 3), 120, np.uint8)

        self._jpeg = cv2.imencode(".jpg", imagem)[1].tobytes()
        self._parando = threading.Event()
        self._servidor = None

        self.porta = None

    @property
    def endereco(self):
        return f"http://127.0.0.1:{self.porta}/video"

    def ligar(self):

        jpeg = self._jpeg
        parando = self._parando

        class Tratador(BaseHTTPRequestHandler):

            def log_message(self, *_argumentos):
                pass  # sem mensagens no terminal

            def do_GET(self):

                self.send_response(200)
                self.send_header("Content-Type", "multipart/x-mixed-replace; boundary=quadro")
                self.end_headers()

                try:

                    while not parando.is_set():

                        self.wfile.write(
                            b"--quadro\r\nContent-Type: image/jpeg\r\n"
                            b"Content-Length: %d\r\n\r\n" % len(jpeg)
                        )
                        self.wfile.write(jpeg + b"\r\n")

                        time.sleep(0.05)

                except OSError:
                    pass  # o cliente desconectou

        self._parando.clear()

        # Porta 0 = o sistema escolhe uma livre; depois reaproveita a mesma
        self._servidor = ThreadingHTTPServer(("127.0.0.1", self.porta or 0), Tratador)
        self._servidor.daemon_threads = True

        self.porta = self._servidor.server_address[1]

        threading.Thread(target=self._servidor.serve_forever, daemon=True).start()

    def desligar(self):

        self._parando.set()

        if self._servidor is not None:
            self._servidor.shutdown()
            self._servidor.server_close()
            self._servidor = None


def esperar(condicao, limite_seg, passo=0.05):
    """Espera até condicao() ser verdadeira; devolve False se o tempo acabar."""

    fim = time.time() + limite_seg

    while time.time() < fim:

        if condicao():
            return True

        time.sleep(passo)

    return condicao()
