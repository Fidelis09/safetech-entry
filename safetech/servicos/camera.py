"""
Captura da webcam em uma thread própria.

Ler um frame da webcam é uma operação que BLOQUEIA (o programa fica
parado esperando a câmera entregar a imagem), e abrir a câmera pode
levar alguns segundos. Se isso fosse feito na thread da interface, a
janela travaria.

Aqui a câmera roda sozinha em segundo plano e guarda sempre o frame
MAIS RECENTE. Quem precisa de imagem (a tela e o analisador) pega esse
frame na hora, sem esperar e sem acumular fila de frames atrasados.

A FONTE do vídeo pode ser:

    um número  (0, 1, 2...)      -> webcam ligada ao computador
    um texto   ("rtsp://...",    -> câmera IP, pela rede
                "http://...")

O resto do programa não precisa saber qual é: todos só pedem "o
frame mais recente" com ler().
"""

import os
import threading
import time
from enum import Enum

from safetech import config


# O FFMPEG (que o OpenCV usa para abrir câmeras IP) lê suas opções
# desta variável de ambiente no momento de abrir cada câmera.
# "setdefault" respeita um valor que o usuário já tenha definido.
if config.RTSP_POR_TCP:
    os.environ.setdefault("OPENCV_FFMPEG_CAPTURE_OPTIONS", "rtsp_transport;tcp")

import cv2  # noqa: E402  (importado depois da variável de ambiente, de propósito)


class EstadoCamera(Enum):

    PARADA = "parada"
    ABRINDO = "abrindo"
    ATIVA = "ativa"
    ERRO = "erro"

    # Câmera que parou de responder no meio do uso (rede da câmera IP,
    # cabo da webcam): o programa tenta de novo sozinho
    RECONECTANDO = "reconectando"


class Camera:

    def __init__(self, fonte=config.INDICE_CAMERA):
        """fonte -> índice da webcam (número) ou endereço de câmera IP (texto)."""

        self._fonte = fonte

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
    def fonte(self):
        """Índice da webcam (número) ou endereço da câmera IP (texto)."""

        return self._fonte

    @property
    def e_camera_ip(self) -> bool:

        return eh_endereco_ip(self._fonte)

    def trocar_fonte(self, fonte):
        """
        Passa a usar outra câmera. Se a atual estava ligada, desliga e
        liga a nova; se estava parada, só guarda a escolha.
        """

        if fonte == self._fonte:
            return

        estava_ligada = self._thread is not None and self._thread.is_alive()

        self.parar()

        self._fonte = fonte

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

        # Falhou já na primeira tentativa: endereço errado, câmera
        # desligada ou em uso. Mostra o erro e para por aqui.
        if captura is None:

            with self._trava:
                self._estado = EstadoCamera.ERRO

            return

        try:

            while not self._parar.is_set():

                with self._trava:
                    self._estado = EstadoCamera.ATIVA

                self._capturar(captura)

                captura.release()
                captura = None

                if self._parar.is_set():
                    return

                # A transmissão caiu no meio do caminho
                with self._trava:
                    self._frame = None
                    self._fps = 0.0

                # Webcam que parou de responder, com a reconexão
                # desligada: erro, o usuário decide o que fazer
                if not self.e_camera_ip and not config.RECONECTAR_WEBCAM:

                    with self._trava:
                        self._estado = EstadoCamera.ERRO

                    return

                # Quedas costumam ser passageiras (rede instável na câmera
                # IP, cabo USB frouxo na webcam), então o programa tenta
                # reabrir sozinho até conseguir (ou até o usuário parar).
                captura = self._reconectar()

        finally:

            if captura is not None:
                captura.release()

    def _capturar(self, captura):
        """Lê frames até a câmera parar de responder (ou até pedirem para parar)."""

        frames_no_periodo = 0
        inicio_periodo = time.perf_counter()
        falhas_seguidas = 0

        while not self._parar.is_set():

            sucesso, frame = captura.read()

            if not sucesso:

                # Uma falha isolada é normal; muitas seguidas
                # significam que a câmera foi desconectada.
                falhas_seguidas += 1

                if falhas_seguidas > 30:
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

    def _reconectar(self):
        """Tenta abrir a câmera de novo, de tempos em tempos. None se mandaram parar."""

        with self._trava:
            self._estado = EstadoCamera.RECONECTANDO

        if self.e_camera_ip:
            intervalo = config.INTERVALO_RECONEXAO_IP_SEG
        else:
            intervalo = config.INTERVALO_RECONEXAO_WEBCAM_SEG

        while not self._parar.wait(intervalo):

            captura = self._abrir()

            if captura is not None:
                return captura

        return None

    def _abrir(self):
        """Abre a câmera (webcam ou IP); devolve None se não conseguir."""

        if self.e_camera_ip:
            return self._abrir_camera_ip()

        if config.USAR_DIRECTSHOW:
            captura = cv2.VideoCapture(self._fonte, cv2.CAP_DSHOW)
        else:
            captura = cv2.VideoCapture(self._fonte)

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

    def _abrir_camera_ip(self):
        """
        Abre uma câmera pela rede, usando o FFMPEG.

        Os tempos limite evitam que o programa fique esperando para
        sempre por uma câmera que não responde. Resolução e formato
        não são pedidos: quem define isso é a própria câmera.
        """

        captura = cv2.VideoCapture(
            self._fonte,
            cv2.CAP_FFMPEG,
            [
                cv2.CAP_PROP_OPEN_TIMEOUT_MSEC, config.TEMPO_LIMITE_CONEXAO_IP_MS,
                cv2.CAP_PROP_READ_TIMEOUT_MSEC, config.TEMPO_LIMITE_LEITURA_IP_MS,
            ],
        )

        if not captura.isOpened():
            captura.release()
            return None

        return captura


# ============================================================
# FUNÇÕES AUXILIARES DE CÂMERA IP
# ============================================================

def eh_endereco_ip(fonte) -> bool:
    """True se a fonte é um endereço de rede (texto), e não o número de uma webcam."""

    return isinstance(fonte, str)


def esconder_senha(endereco) -> str:
    """
    Endereço sem usuário e senha, para mostrar na tela e nos avisos.

        rtsp://admin:1234@192.168.0.50:554/stream -> rtsp://192.168.0.50:554/stream
    """

    esquema, separador, resto = endereco.partition("://")

    if not separador:
        return endereco

    servidor, barra, caminho = resto.partition("/")

    # O que vem antes do último "@" é "usuario:senha"
    servidor = servidor.rpartition("@")[2]

    return f"{esquema}://{servidor}{barra}{caminho}"


def montar_endereco(endereco, usuario="", senha="") -> str:
    """
    Junta usuário e senha ao endereço, no formato que as câmeras esperam:

        rtsp://192.168.0.50:554/stream + admin + 1234
            -> rtsp://admin:1234@192.168.0.50:554/stream

    Caracteres especiais (como "@" ou ":" na senha) são codificados,
    para não confundirem o endereço. Sem usuário, nada muda.
    """

    from urllib.parse import quote

    endereco = endereco.strip()

    if not usuario:
        return endereco

    esquema, separador, resto = endereco.partition("://")

    if not separador:
        return endereco

    credenciais = quote(usuario, safe="")

    if senha:
        credenciais += ":" + quote(senha, safe="")

    return f"{esquema}://{credenciais}@{resto}"
