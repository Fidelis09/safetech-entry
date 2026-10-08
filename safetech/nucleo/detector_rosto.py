"""
Detector de pessoas pelo ROSTO (modo "rosto").

O modelo de EPI só sabe dizer quais equipamentos aparecem numa imagem;
ele não sabe ONDE estão as pessoas. Quem resolve isso é este módulo:
ele usa o detector de rosto YuNet (rede neural leve que já vem
suportada pelo OpenCV) para achar cada rosto e, a partir dele, monta
uma caixa maior cobrindo cabeça, tronco e mãos, que é onde ficam o
capacete, os óculos, o colete e as luvas.

DETECÇÃO EM DUAS ESCALAS

O YuNet enxerga bem rostos dentro de uma certa faixa de tamanho.
Medido neste projeto:

    imagem reduzida para 640 px -> acha rostos pequenos (câmera geral,
                                   várias pessoas ao longe), mas NÃO
                                   acha um rosto grande e próximo;
    imagem reduzida para 320 px -> acha o rosto próximo (catraca), mas
                                   perde os pequenos.

Por isso o frame é analisado nas duas escalas e os resultados são
unidos. Assim a mesma configuração serve tanto para a catraca quanto
para uma câmera geral.
"""

import cv2

from safetech import config
from safetech.nucleo.rastreador import calcular_iou
from safetech.nucleo.tipos import Caixa


class DetectorRosto:

    def __init__(
        self,
        caminho_modelo=config.ARQUIVO_MODELO_ROSTO,
        larguras_deteccao=config.LARGURAS_DETECCAO,
        confianca_minima=config.CONFIANCA_MINIMA_ROSTO,
    ):

        # Da maior para a menor: a escala maior localiza o rosto com
        # mais precisão, então tem preferência quando as duas o acham.
        self._larguras = sorted(larguras_deteccao, reverse=True)

        # Um detector por escala (cada um guarda o tamanho da própria
        # imagem de entrada). Sem o arquivo do modelo, fica vazio e o
        # programa funciona em "modo cena inteira" (veja detectar).
        self._detectores = {}
        self._tamanhos = {}

        if caminho_modelo.exists():

            for largura in self._larguras:

                self._detectores[largura] = cv2.FaceDetectorYN_create(
                    str(caminho_modelo),
                    "",
                    (320, 320),
                    score_threshold=confianca_minima,
                    nms_threshold=0.3,
                    # Candidatos mantidos ANTES de eliminar os repetidos.
                    # Cada rosto gera vários candidatos; se este número
                    # for baixo, poucos rostos nítidos ocupam todas as
                    # vagas e o restante das pessoas não é detectado.
                    top_k=config.MAXIMO_CANDIDATOS_ROSTO,
                )

    @property
    def disponivel(self):
        """True se o detector de rosto foi carregado."""

        return bool(self._detectores)

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

        if not self._detectores:
            return [(0, 0, largura, altura)]

        caixas = []

        for largura_deteccao in self._larguras:

            for caixa in self._detectar_na_escala(frame_bgr, largura_deteccao):

                # A mesma pessoa pode ser achada nas duas escalas. Se
                # esta caixa cobre alguém que já está na lista, é
                # repetição e fica de fora.
                repetida = any(
                    calcular_iou(caixa, existente) >= config.IOU_MESMA_PESSOA
                    for existente in caixas
                )

                if not repetida:
                    caixas.append(caixa)

        return caixas

    def _detectar_na_escala(self, frame_bgr, largura_deteccao) -> list[Caixa]:
        """Roda o detector numa cópia do frame com a largura pedida."""

        altura, largura = frame_bgr.shape[:2]

        # ------------------------------------------------------
        # 1) Reduz o frame (nunca amplia: não criaria detalhe novo)
        # ------------------------------------------------------

        escala = min(1.0, largura_deteccao / largura)

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

        detector = self._detectores[largura_deteccao]

        tamanho = (imagem.shape[1], imagem.shape[0])

        if tamanho != self._tamanhos.get(largura_deteccao):
            detector.setInputSize(tamanho)
            self._tamanhos[largura_deteccao] = tamanho

        _, rostos = detector.detect(imagem)

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
