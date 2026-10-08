"""
Detector de pessoas pelo CORPO INTEIRO (modo "corpo").

Usa o YOLOX, uma rede de detecção de objetos treinada para reconhecer
80 tipos de coisa (base COCO); aqui só interessa a classe "pessoa".

Diferença para o modo rosto: a pessoa é encontrada em qualquer posição
(de costas, de lado, abaixada, com o rosto coberto). É o modo indicado
para uma câmera geral, com várias pessoas se movimentando e se
cruzando. O preço é a velocidade: a rede é bem mais pesada que o
detector de rosto.

COMO O YOLOX RESPONDE

A rede divide a imagem em grades de três tamanhos (células de 8, 16 e
32 pixels) e, para cada célula, devolve uma linha com 85 números:

    0-1   deslocamento do centro da caixa dentro da célula
    2-3   largura e altura da caixa (em escala logarítmica)
    4     confiança de haver um objeto ali
    5-84  confiança de cada uma das 80 classes (a primeira é "pessoa")

Este módulo converte essas linhas em caixas (x1, y1, x2, y2) no frame
original e elimina as repetidas.
"""

import cv2
import numpy as np

from safetech import config
from safetech.nucleo.tipos import Caixa


# Tamanho das células de cada grade do YOLOX (em pixels da imagem de entrada)
PASSOS = (8, 16, 32)

# Posição da classe "pessoa" entre as 80 classes da rede
CLASSE_PESSOA = 0

# Cor de preenchimento usada pelo YOLOX no treino para completar a imagem
COR_PREENCHIMENTO = 114


class DetectorCorpo:

    def __init__(
        self,
        caminho_modelo=config.ARQUIVO_MODELO_CORPO,
        largura_deteccao=config.LARGURA_DETECCAO_CORPO,
        confianca_minima=config.CONFIANCA_MINIMA_CORPO,
    ):

        self._largura_deteccao = largura_deteccao
        self._confianca_minima = confianca_minima

        # As grades dependem do tamanho da imagem de entrada; ficam
        # guardadas para não serem refeitas a cada frame.
        self._grades = {}

        self._rede = None

        if caminho_modelo.exists():
            self._rede = cv2.dnn.readNet(str(caminho_modelo))

    @property
    def disponivel(self):
        """True se o modelo de detecção de corpo foi carregado."""

        return self._rede is not None

    # ============================================================
    # DETECÇÃO
    # ============================================================

    def detectar(self, frame_bgr) -> list[Caixa]:
        """
        Devolve uma caixa (x1, y1, x2, y2) para cada pessoa do frame,
        em coordenadas do frame ORIGINAL. Sem o modelo, lista vazia.
        """

        if self._rede is None:
            return []

        altura, largura = frame_bgr.shape[:2]

        # ------------------------------------------------------
        # 1) Prepara a imagem de entrada
        # ------------------------------------------------------
        #
        # O frame é reduzido para a largura de detecção, mantendo a
        # proporção. A rede exige lados múltiplos de 32, então o que
        # faltar é completado com cinza (embaixo e à direita).
        #
        # A entrada acompanha o formato do vídeo (por exemplo 640x384
        # para um frame 16:9) em vez de ser um quadrado de 640x640: a
        # rede processa bem menos pixels, com o mesmo nível de detalhe.
        # ------------------------------------------------------

        escala = min(1.0, self._largura_deteccao / largura)

        largura_reduzida = max(32, int(largura * escala))
        altura_reduzida = max(32, int(altura * escala))

        largura_entrada = -(-largura_reduzida // 32) * 32  # arredonda para cima
        altura_entrada = -(-altura_reduzida // 32) * 32

        entrada = np.full(
            (altura_entrada, largura_entrada, 3), COR_PREENCHIMENTO, np.uint8
        )

        entrada[:altura_reduzida, :largura_reduzida] = cv2.resize(
            frame_bgr,
            (largura_reduzida, altura_reduzida),
            interpolation=cv2.INTER_LINEAR,
        )

        # swapRB: o OpenCV entrega BGR e a rede foi treinada em RGB.
        # Os valores ficam de 0 a 255, como a rede espera.
        self._rede.setInput(
            cv2.dnn.blobFromImage(entrada, 1.0, (largura_entrada, altura_entrada), swapRB=True)
        )

        saida = self._rede.forward()[0]

        # ------------------------------------------------------
        # 2) Fica só com as células que viram uma PESSOA
        # ------------------------------------------------------

        confiancas = saida[:, 4] * saida[:, 5 + CLASSE_PESSOA]

        selecionadas = confiancas >= self._confianca_minima

        if not selecionadas.any():
            return []

        grades, passos = self._grades_para(largura_entrada, altura_entrada)

        linhas = saida[selecionadas]
        confiancas = confiancas[selecionadas]

        # ------------------------------------------------------
        # 3) Converte a resposta da rede em caixas, no frame original
        # ------------------------------------------------------

        centros = (linhas[:, :2] + grades[selecionadas]) * passos[selecionadas]
        tamanhos = np.exp(linhas[:, 2:4]) * passos[selecionadas]

        # Formato (x, y, largura, altura), já desfazendo a redução
        retangulos = np.concatenate([centros - tamanhos / 2, tamanhos], axis=1) / escala

        # ------------------------------------------------------
        # 4) Elimina as repetições: várias células vizinhas costumam
        #    apontar para a mesma pessoa; fica a de maior confiança.
        # ------------------------------------------------------

        mantidas = cv2.dnn.NMSBoxes(
            retangulos.tolist(),
            confiancas.tolist(),
            self._confianca_minima,
            config.IOU_REPETICAO_CORPO,
        )

        caixas = []

        for indice in np.array(mantidas).flatten():

            x, y, largura_caixa, altura_caixa = retangulos[indice]

            x1 = int(max(0, x))
            y1 = int(max(0, y))
            x2 = int(min(largura, x + largura_caixa))
            y2 = int(min(altura, y + altura_caixa))

            # Descarta caixas degeneradas (pessoa quase toda fora da imagem)
            if x2 - x1 >= 8 and y2 - y1 >= 8:
                caixas.append((x1, y1, x2, y2))

        return caixas

    def _grades_para(self, largura_entrada, altura_entrada):
        """
        Posição (coluna, linha) e tamanho da célula de cada linha da
        saída da rede, para uma entrada deste tamanho.
        """

        chave = (largura_entrada, altura_entrada)

        if chave not in self._grades:

            posicoes = []
            passos = []

            for passo in PASSOS:

                colunas, linhas = np.meshgrid(
                    np.arange(largura_entrada // passo),
                    np.arange(altura_entrada // passo),
                )

                posicoes.append(np.stack([colunas, linhas], axis=2).reshape(-1, 2))
                passos.append(np.full((colunas.size, 1), passo))

            self._grades[chave] = (
                np.concatenate(posicoes).astype(np.float32),
                np.concatenate(passos).astype(np.float32),
            )

        return self._grades[chave]
