"""
Procura as câmeras conectadas ao computador.

O OpenCV não informa o nome das câmeras, só o índice (0, 1, 2...). Por
isso a busca tenta abrir cada índice e vê quais respondem. Abrir uma
câmera pode levar alguns segundos, então a busca roda em segundo plano
e entrega o resultado por uma função de retorno.
"""

import threading

import cv2

from safetech import config


def procurar_indices():
    """Devolve a lista de índices de câmeras que abriram, em ordem."""

    encontrados = []

    for indice in range(config.MAXIMO_CAMERAS_PROCURADAS):

        if config.USAR_DIRECTSHOW:
            captura = cv2.VideoCapture(indice, cv2.CAP_DSHOW)
        else:
            captura = cv2.VideoCapture(indice)

        if captura.isOpened():
            encontrados.append(indice)

        captura.release()

    return encontrados


def procurar_em_segundo_plano(ao_terminar):
    """Roda a busca numa thread e chama ao_terminar(indices) no fim (na thread da busca)."""

    def executar():

        try:
            indices = procurar_indices()
        except Exception:
            indices = []

        ao_terminar(indices)

    threading.Thread(target=executar, name="busca-cameras", daemon=True).start()
