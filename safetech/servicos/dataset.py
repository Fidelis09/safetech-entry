"""
Coleta de imagens rotuladas para o treino do modelo por EPI.

Para o modelo aprender a reconhecer cada equipamento separadamente,
cada imagem de treino precisa dizer QUAIS equipamentos a pessoa está
usando. Isso fica numa planilha:

    dataset/epis/           -> as imagens
    dataset/rotulos.csv     -> uma linha por imagem:
                               arquivo, capacete, oculos, colete, luvas
                               (1 = está usando, 0 = não está)

O que é salvo é o RECORTE de cada pessoa (a mesma caixa que o modelo
recebe durante o uso), e não o frame inteiro. Treinar com o mesmo
enquadramento da inferência é o que mais melhora a precisão.
"""

import csv
from datetime import datetime

import cv2

from safetech import config


class ColetorDataset:

    def __init__(
        self,
        pasta_imagens=config.PASTA_IMAGENS_DATASET,
        arquivo_rotulos=config.ARQUIVO_ROTULOS,
    ):

        self._pasta_imagens = pasta_imagens
        self._arquivo_rotulos = arquivo_rotulos

        # Cabeçalho da planilha: o nome do arquivo e uma coluna por EPI
        self._colunas = ["arquivo", *config.EPIS]

    # ============================================================
    # GRAVAÇÃO
    # ============================================================

    def salvar(self, frame_bgr, caixas, usando):
        """
        Salva um recorte por pessoa, com os rótulos informados.

        usando -> chaves dos EPIs que a pessoa ESTÁ usando na imagem.
                  Os demais EPIs são gravados como "não está usando".

        Todas as pessoas do frame recebem os mesmos rótulos, então o
        ideal é coletar com uma pessoa por vez. Sem nenhuma caixa
        (ninguém detectado), salva o frame inteiro.

        Devolve a lista dos arquivos criados.
        """

        self._preparar_planilha()

        if caixas:
            imagens = [frame_bgr[y1:y2, x1:x2] for x1, y1, x2, y2 in caixas]
        else:
            imagens = [frame_bgr]

        momento = datetime.now().strftime("%Y%m%d_%H%M%S_%f")

        rotulos = [1 if chave in usando else 0 for chave in config.EPIS]

        arquivos = []
        linhas = []

        for indice, imagem in enumerate(imagens, start=1):

            if imagem.size == 0:
                continue

            caminho = self._pasta_imagens / f"epi_{momento}_{indice}.jpg"

            cv2.imwrite(str(caminho), imagem)

            arquivos.append(caminho)
            linhas.append([caminho.name, *rotulos])

        with open(self._arquivo_rotulos, "a", newline="", encoding="utf-8") as arquivo:
            csv.writer(arquivo).writerows(linhas)

        return arquivos

    def _preparar_planilha(self):

        self._pasta_imagens.mkdir(parents=True, exist_ok=True)

        # Se a lista de EPIs em config.py mudou, a planilha antiga não
        # serve mais (as colunas não batem). Ela é RENOMEADA, nunca
        # apagada, e uma planilha nova é iniciada.
        if self._arquivo_rotulos.exists() and self._ler_cabecalho() != self._colunas:

            sufixo = datetime.now().strftime("%Y%m%d_%H%M%S")

            self._arquivo_rotulos.rename(
                self._arquivo_rotulos.with_name(f"rotulos_formato_antigo_{sufixo}.csv")
            )

        if not self._arquivo_rotulos.exists():

            with open(self._arquivo_rotulos, "w", newline="", encoding="utf-8") as arquivo:
                csv.writer(arquivo).writerow(self._colunas)

    def _ler_cabecalho(self):

        with open(self._arquivo_rotulos, "r", newline="", encoding="utf-8", errors="replace") as arquivo:
            return next(csv.reader(arquivo), None)

    # ============================================================
    # LEITURA
    # ============================================================

    def ler_rotulos(self):
        """
        Lê a planilha e devolve uma lista de (caminho_da_imagem, rotulos),
        onde rotulos é uma lista de 0/1 na ordem de config.EPIS.

        Linhas cuja imagem foi apagada, ou com valores inválidos, são
        ignoradas. Planilha de outro formato devolve lista vazia.
        """

        if not self._arquivo_rotulos.exists() or self._ler_cabecalho() != self._colunas:
            return []

        exemplos = []

        with open(self._arquivo_rotulos, "r", newline="", encoding="utf-8", errors="replace") as arquivo:

            leitor = csv.reader(arquivo)

            next(leitor, None)  # pula o cabeçalho

            for linha in leitor:

                if len(linha) != len(self._colunas):
                    continue

                caminho = self._pasta_imagens / linha[0]

                if not caminho.is_file() or any(valor not in ("0", "1") for valor in linha[1:]):
                    continue

                exemplos.append((caminho, [int(valor) for valor in linha[1:]]))

        return exemplos

    def resumo(self):
        """
        Situação do dataset: (total_de_imagens, {chave: quantas_usando}).

        Serve para a tela mostrar o que já foi coletado e o que falta.
        """

        exemplos = self.ler_rotulos()

        usando = {
            chave: sum(rotulos[posicao] for _, rotulos in exemplos)
            for posicao, chave in enumerate(config.EPIS)
        }

        return len(exemplos), usando
