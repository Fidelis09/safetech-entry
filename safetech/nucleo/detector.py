"""
Detector de pessoas.

O modelo de EPI só sabe dizer "esta imagem é com_epi ou sem_epi"; ele
não sabe ONDE estão as pessoas. Quem resolve isso é este módulo: ele
usa o detector de rosto YuNet (rede neural leve que já vem suportada
pelo OpenCV) para achar cada rosto e, a partir dele, monta uma caixa
maior cobrindo cabeça e tronco, que é a região onde ficam o capacete,
os óculos e o colete.
"""

import cv2

from safetech import config
from safetech.nucleo.tipos import Caixa


class DetectorPessoas:

    def __init__(
        self,
        caminho_modelo=config.ARQUIVO_MODELO_ROSTO,
        largura_deteccao=config.LARGURA_DETECCAO,
        confianca_minima=config.CONFIANCA_MINIMA_ROSTO,
    ):

        self._largura_deteccao = largura_deteccao
        self._tamanho_entrada = None
        self._detector = None

        # Sem o arquivo do modelo o programa continua funcionando,
        # mas em "modo cena inteira" (veja o método detectar).
        if caminho_modelo.exists():

            self._detector = cv2.FaceDetectorYN_create(
                str(caminho_modelo),
                "",
                (320, 320),
                score_threshold=confianca_minima,
                nms_threshold=0.3,
                top_k=50,
            )

    @property
    def disponivel(self):
        """True se o detector de rosto foi carregado."""

        return self._detector is not None

    # ============================================================
    # DETECÇÃO
    # ============================================================

    def detectar(self, frame_bgr) -> list[Caixa]:
        """
        Devolve uma caixa (x1, y1, x2, y2) para cada pessoa do frame,
        em coordenadas do frame ORIGINAL.

        Sem o detector de rosto, devolve uma única caixa cobrindo o
        frame inteiro: a cena toda é tratada como "uma pessoa".
        """

        altura, largura = frame_bgr.shape[:2]

        if self._detector is None:
            return [(0, 0, largura, altura)]

        # ------------------------------------------------------
        # 1) Reduz o frame: detectar rosto em imagem pequena é
        #    várias vezes mais rápido e quase tão preciso.
        # ------------------------------------------------------

        escala = min(1.0, self._largura_deteccao / largura)

        if escala < 1.0:

            imagem = cv2.resize(
                frame_bgr,
                (int(largura * escala), int(altura * escala)),
                interpolation=cv2.INTER_LINEAR,
            )

        else:
            imagem = frame_bgr

        # ------------------------------------------------------
        # 2) O YuNet precisa saber o tamanho da imagem de entrada.
        #    Só avisa de novo quando o tamanho muda.
        # ------------------------------------------------------

        tamanho = (imagem.shape[1], imagem.shape[0])

        if tamanho != self._tamanho_entrada:
            self._detector.setInputSize(tamanho)
            self._tamanho_entrada = tamanho

        _, rostos = self._detector.detect(imagem)

        if rostos is None:
            return []

        # ------------------------------------------------------
        # 3) Converte cada rosto numa caixa de cabeça + tronco,
        #    já na escala do frame original.
        # ------------------------------------------------------

        caixas = []

        for rosto in rostos:

            x, y, largura_rosto, altura_rosto = (float(v) / escala for v in rosto[:4])

            caixa = self._expandir_rosto(
                x, y, largura_rosto, altura_rosto, largura, altura
            )

            if caixa is not None:
                caixas.append(caixa)

        return caixas

    @staticmethod
    def _expandir_rosto(x, y, largura_rosto, altura_rosto, largura_frame, altura_frame):
        """Aumenta a caixa do rosto e a mantém dentro dos limites do frame."""

        x1 = int(max(0, x - largura_rosto * config.MARGEM_LATERAL_ROSTO))
        y1 = int(max(0, y - altura_rosto * config.MARGEM_SUPERIOR_ROSTO))

        x2 = int(min(largura_frame, x + largura_rosto * (1 + config.MARGEM_LATERAL_ROSTO)))
        y2 = int(min(altura_frame, y + altura_rosto * (1 + config.MARGEM_INFERIOR_ROSTO)))

        # Descarta caixas degeneradas (rosto cortado na borda da imagem)
        if x2 - x1 < 8 or y2 - y1 < 8:
            return None

        return (x1, y1, x2, y2)
