"""
Classificador de EPI.

Carrega o modelo treinado pelo treinar.py (MobileNetV2 + camada de
classificação) e classifica recortes de imagem.

Pontos importantes:
    - Os nomes e a ORDEM das classes vêm de classes.json, nunca do código.
    - O modelo espera imagem RGB 224x224 SEM normalização manual: o
      preprocess_input da MobileNetV2 já está embutido dentro dele.
    - Várias pessoas são classificadas numa ÚNICA chamada (lote), e a
      chamada é compilada em grafo (tf.function). Isso é bem mais rápido
      do que chamar modelo.predict() uma vez por pessoa.
"""

import cv2
import numpy as np
import tensorflow as tf

from safetech import config
from safetech.nucleo.classes import carregar_classes


class ClassificadorEPI:

    def __init__(
        self,
        caminho_modelo=config.ARQUIVO_MODELO,
        caminho_classes=config.ARQUIVO_CLASSES,
        tamanho_imagem=config.TAMANHO_IMAGEM,
    ):

        self._tamanho_imagem = tamanho_imagem

        # ------------------------------------------------------
        # CLASSES (na mesma ordem em que a rede foi treinada)
        # ------------------------------------------------------

        self.classes = carregar_classes(caminho_classes)

        # ------------------------------------------------------
        # MODELO
        # ------------------------------------------------------

        self._modelo = tf.keras.models.load_model(caminho_modelo, compile=False)

        largura, altura = tamanho_imagem

        # Compila a inferência em grafo. A assinatura fixa (lote de
        # tamanho livre, imagens 224x224x3) evita recompilar quando o
        # número de pessoas na imagem muda.
        self._inferir = tf.function(
            lambda lote: self._modelo(lote, training=False),
            input_signature=[
                tf.TensorSpec([None, altura, largura, 3], tf.float32)
            ],
        )

        # A primeira chamada de um modelo é sempre lenta (é quando o
        # grafo é montado). Fazendo ela aqui, com uma imagem vazia, a
        # primeira pessoa real já é classificada na velocidade normal.
        self._inferir(tf.zeros([1, altura, largura, 3], tf.float32))

    # ============================================================
    # CLASSIFICAÇÃO
    # ============================================================

    def classificar_lote(self, recortes_bgr) -> np.ndarray:
        """
        Classifica vários recortes de uma vez.

        Recebe uma lista de imagens BGR (formato do OpenCV), de qualquer
        tamanho, e devolve uma matriz [recorte, classe] de probabilidades,
        com as colunas na ordem de self.classes.
        """

        if not recortes_bgr:
            return np.zeros((0, len(self.classes)), dtype=np.float32)

        lote = np.stack([self._preparar(recorte) for recorte in recortes_bgr])

        return self._inferir(tf.convert_to_tensor(lote)).numpy()

    def classificar(self, imagem_bgr) -> np.ndarray:
        """Classifica uma única imagem; devolve o vetor de probabilidades."""

        return self.classificar_lote([imagem_bgr])[0]

    def _preparar(self, imagem_bgr) -> np.ndarray:
        """
        Deixa a imagem no formato que o modelo espera.

        O OpenCV trabalha em BGR e o modelo foi treinado em RGB, então
        a conversão de cores é obrigatória. A normalização NÃO é feita
        aqui porque já está dentro do modelo.
        """

        imagem_rgb = cv2.cvtColor(imagem_bgr, cv2.COLOR_BGR2RGB)

        imagem_rgb = cv2.resize(
            imagem_rgb,
            self._tamanho_imagem,
            interpolation=cv2.INTER_LINEAR,
        )

        return imagem_rgb.astype(np.float32)
