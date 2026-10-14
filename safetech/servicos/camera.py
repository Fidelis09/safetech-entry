"""
Captura da webcam em uma thread própria.

Ler um frame da webcam é uma operação que BLOQUEIA (o programa fica
parado esperando a câmera entregar a imagem), e abrir a câmera pode
levar alguns segundos. Se isso fosse feito na thread da interface, a
janela travaria.

Aqui a câmera roda sozinha em segundo plano e guarda sempre o frame
MAIS RECENTE. Quem precisa de imagem (a tela e o analisador) pega esse
frame na hora, sem esperar e sem acumular fila de frames atrasados.
"""

import threading
import time
from enum import Enum

import cv2

from safetech import config


class EstadoCamera(Enum):

    PARADA = "parada"
    ABRINDO = "abrindo"
    ATIVA = "ativa"
    ERRO = "erro"


class Camera:

    def __init__(self, indice=config.INDICE_CAMERA):

        self._indice = indice

        # A trava protege as variáveis lidas por outras threads
        self._trava = threading.Lock()

        self._frame = None
        self._numero_frame = 0
        self._estado = EstadoCamera.PARADA
        self._fps = 0.0

        self._parar = threading.Event()
        self._thread = None

    # ============================================================
    # CONTROLE
    # ============================================================

    def iniciar(self):
        """Liga a câmera. Retorna na hora; a abertura acontece em segundo plano."""

        if self._thread is not None and self._thread.is_alive():
            return

        self._parar.clear()

        with self._trava:
            self._estado = EstadoCamera.ABRINDO

        self._thread = threading.Thread(
            target=self._executar,
            name="camera",
            daemon=True,
        )

        self._thread.start()

    def parar(self):
        """Desliga a câmera e espera a thread terminar."""

        self._parar.set()

        if self._thread is not None:
            self._thread.join(timeout=3)
            self._thread = None

        with self._trava:
            self._frame = None
            self._fps = 0.0

            # Um erro continua visível até a próxima tentativa de ligar
            if self._estado is not EstadoCamera.ERRO:
                self._estado = EstadoCamera.PARADA

    @property
    def indice(self) -> int:

        return self._indice

    def trocar_indice(self, indice):
        """
        Passa a usar outra câmera. Se a atual estava ligada, desliga e
        liga a nova; se estava parada, só guarda a escolha.
        """

        if indice == self._indice:
            return

        estava_ligada = self._thread is not None and self._thread.is_alive()

        self.parar()

        self._indice = indice

        # Um erro da câmera antiga não vale para a nova
        with self._trava:
            self._estado = EstadoCamera.PARADA

        if estava_ligada:
            self.iniciar()

    # ============================================================
    # LEITURA (chamada por outras threads)
    # ============================================================

    def ler(self):
        """
        Devolve (frame, numero_do_frame) do frame mais recente.

        O número serve para quem lê saber se o frame é novo ou se é o
        mesmo da última leitura. Sem câmera ativa, o frame é None.

        O frame devolvido é compartilhado: quem o recebe NÃO deve
        desenhar nele; se precisar alterar, faça uma cópia.
        """

        with self._trava:
            return self._frame, self._numero_frame

    @property
    def estado(self) -> EstadoCamera:

        with self._trava:
            return self._estado

    @property
    def fps(self) -> float:

        with self._trava:
            return self._fps

    # ============================================================
    # THREAD DE CAPTURA
    # ============================================================

    def _executar(self):

        captura = self._abrir()

        if captura is None:

            with self._trava:
                self._estado = EstadoCamera.ERRO

            return

        with self._trava:
            self._estado = EstadoCamera.ATIVA

        frames_no_periodo = 0
        inicio_periodo = time.perf_counter()
        falhas_seguidas = 0

        try:

            while not self._parar.is_set():

                sucesso, frame = captura.read()

                if not sucesso:

                    # Uma falha isolada é normal; muitas seguidas
                    # significam que a câmera foi desconectada.
                    falhas_seguidas += 1

                    if falhas_seguidas > 30:

                        with self._trava:
                            self._estado = EstadoCamera.ERRO
                            self._frame = None

                        return

                    time.sleep(0.01)
                    continue

                falhas_seguidas = 0

                with self._trava:
                    self._frame = frame
                    self._numero_frame += 1

                # Mede o FPS real da câmera a cada meio segundo
                frames_no_periodo += 1
                decorrido = time.perf_counter() - inicio_periodo

                if decorrido >= 0.5:

                    with self._trava:
                        self._fps = frames_no_periodo / decorrido

                    frames_no_periodo = 0
                    inicio_periodo = time.perf_counter()

        finally:
            captura.release()

    def _abrir(self):
        """Abre a webcam já configurada; devolve None se não conseguir."""

        if config.USAR_DIRECTSHOW:
            captura = cv2.VideoCapture(self._indice, cv2.CAP_DSHOW)
        else:
            captura = cv2.VideoCapture(self._indice)

        if not captura.isOpened():
            captura.release()
            return None

        # Pede vídeo comprimido (MJPG). Sem isso, muitas webcams só
        # entregam poucos quadros por segundo em resoluções altas.
        # Câmeras que não suportam simplesmente ignoram o pedido.
        captura.set(cv2.CAP_PROP_FOURCC, cv2.VideoWriter_fourcc(*"MJPG"))

        captura.set(cv2.CAP_PROP_FRAME_WIDTH, config.LARGURA_CAPTURA)
        captura.set(cv2.CAP_PROP_FRAME_HEIGHT, config.ALTURA_CAPTURA)

        # Fila interna de 1 frame: sempre a imagem mais atual possível
        captura.set(cv2.CAP_PROP_BUFFERSIZE, 1)

        return captura
