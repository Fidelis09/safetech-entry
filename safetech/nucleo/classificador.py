"""
Classificador de EPI.

Carrega o modelo treinado pelo treinar.py e, para cada recorte de
pessoa, devolve a probabilidade de ela estar usando CADA equipamento.

Pontos importantes:
    - Quais EPIs o modelo conhece (e em que ordem) vem de epis.json,
      nunca do código.
    - O modelo espera imagem RGB 224x224 SEM normalização manual: o
      preprocess_input da MobileNetV2 já está embutido dentro dele.
    - Várias pessoas são classificadas numa ÚNICA chamada (lote), e a
      chamada é compilada em grafo (tf.function). Isso é bem mais rápido
      do que chamar modelo.predict() uma vez por pessoa.

Modo de compatibilidade: se o modelo por EPI ainda não foi treinado, o
modelo antigo (com_epi / sem_epi) é usado no lugar. Ele é apresentado
ao resto do sistema como um modelo de um único "EPI" (o conjunto
completo), então nenhum outro módulo precisa saber da diferença.
"""

import cv2
import numpy as np
import tensorflow as tf

from safetech import config
from safetech.nucleo import epis as modulo_epis


class ClassificadorEPI:

    def __init__(self, tamanho_imagem=config.TAMANHO_IMAGEM):

        self._tamanho_imagem = tamanho_imagem

        # ------------------------------------------------------
        # ESCOLHA DO MODELO
        # ------------------------------------------------------

        # True = modelo novo, que distingue os equipamentos
        self.por_epi = modulo_epis.modelo_por_epi_disponivel()

        # Chaves dos EPIs, na ordem das colunas devolvidas
        self.epis: list[str] = modulo_epis.epis_do_modelo()

        if self.por_epi:

            caminho_modelo = config.ARQUIVO_MODELO_EPIS

            # Não usado no modelo novo
            self._coluna_com_epi = None

        else:

            caminho_modelo = config.ARQUIVO_MODELO_LEGADO

            classes = modulo_epis.ler_lista(config.ARQUIVO_CLASSES_LEGADO)

            if config.CLASSE_LIBERA_ACESSO not in classes:

                raise ValueError(
                    f"A classe '{config.CLASSE_LIBERA_ACESSO}' não existe em "
                    f"classes.json (classes encontradas: {classes})."
                )

            # No modelo antigo, a probabilidade do "conjunto" é a
            # probabilidade da classe "com_epi".
            self._coluna_com_epi = classes.index(config.CLASSE_LIBERA_ACESSO)

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
        tamanho, e devolve uma matriz [recorte, epi]: a probabilidade
        (0 a 1) de a pessoa estar usando cada EPI, com as colunas na
        ordem de self.epis.
        """

        if not recortes_bgr:
            return np.zeros((0, len(self.epis)), dtype=np.float32)

        lote = np.stack([self._preparar(recorte) for recorte in recortes_bgr])

        saida = self._inferir(tf.convert_to_tensor(lote)).numpy()

        if self.por_epi:
            return saida

        # Modelo antigo: fica só com a coluna "com_epi", como uma
        # matriz de uma coluna (o "EPI" do conjunto).
        return saida[:, self._coluna_com_epi : self._coluna_com_epi + 1]

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
