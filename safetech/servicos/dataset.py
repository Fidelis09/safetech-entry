"""
Coleta de imagens para o dataset de treino.

Salva imagens direto em dataset/<classe>/, sem precisar copiar arquivos
manualmente.

Detalhe importante: o que é salvo é o RECORTE de cada pessoa (a mesma
caixa de cabeça + tronco que o modelo recebe durante o uso), e não o
frame inteiro. Treinar com o mesmo enquadramento que será usado na
inferência é o que mais melhora a precisão do modelo.
"""

from datetime import datetime

import cv2

from safetech import config


class ColetorDataset:

    def __init__(self, pasta_dataset=config.PASTA_DATASET):

        self._pasta_dataset = pasta_dataset

    def salvar(self, frame_bgr, caixas, nome_classe):
        """
        Salva um recorte por pessoa na pasta da classe.

        Sem nenhuma caixa (ninguém detectado), salva o frame inteiro.
        Devolve a lista dos arquivos criados.
        """

        pasta_classe = self._pasta_dataset / nome_classe
        pasta_classe.mkdir(parents=True, exist_ok=True)

        if caixas:
            imagens = [frame_bgr[y1:y2, x1:x2] for x1, y1, x2, y2 in caixas]
        else:
            imagens = [frame_bgr]

        momento = datetime.now().strftime("%Y%m%d_%H%M%S_%f")

        arquivos = []

        for indice, imagem in enumerate(imagens, start=1):

            if imagem.size == 0:
                continue

            caminho = pasta_classe / f"{nome_classe}_{momento}_{indice}.jpg"

            cv2.imwrite(str(caminho), imagem)

            arquivos.append(caminho)

        return arquivos

    def contar_imagens(self, nome_classe) -> int:
        """Quantas imagens de treino a classe já tem."""

        pasta_classe = self._pasta_dataset / nome_classe

        if not pasta_classe.exists():
            return 0

        return sum(
            1
            for arquivo in pasta_classe.iterdir()
            if arquivo.suffix.lower() in config.EXTENSOES_IMAGEM
        )
