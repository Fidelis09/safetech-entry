"""
Rastreador de pessoas.

O detector acha caixas a cada frame, mas não sabe que a caixa de agora
é a MESMA pessoa do frame anterior. O rastreador faz essa ligação e dá
a cada pessoa um número fixo enquanto ela estiver na imagem.

Isso é o que permite:
    - acumular um histórico de classificações por pessoa (decisão estável);
    - registrar na auditoria "a pessoa P003 mudou de negado para liberado";
    - não misturar os resultados quando há várias pessoas em fila.

O método é simples e suficiente para uma catraca: casa cada caixa nova
com o rastro existente de maior sobreposição (IoU).
"""

from collections import deque
from itertools import count

from safetech import config
from safetech.nucleo.tipos import Caixa


# ============================================================
# RASTRO: TUDO O QUE SE SABE SOBRE UMA PESSOA
# ============================================================

class Rastro:

    def __init__(self, identificador, caixa, agora):

        self.identificador = identificador

        # Guardada com casas decimais para a suavização não acumular
        # erro de arredondamento; use a propriedade "caixa" para ler.
        self._caixa = tuple(float(v) for v in caixa)

        self.ultimo_visto = agora

        # True quando o detector achou a pessoa no frame mais recente
        self.visivel = True

        # Últimas probabilidades devolvidas pelo modelo de EPI
        # (um vetor por classificação). A decisão usa a média delas.
        self.historico = deque(maxlen=config.TAMANHO_HISTORICO_DECISAO)

        # Última decisão gravada na auditoria (None = nenhuma ainda).
        # Serve para registrar apenas quando a decisão MUDA.
        self.decisao_registrada = None

    @property
    def caixa(self) -> Caixa:
        return tuple(int(round(v)) for v in self._caixa)

    def mover_para(self, nova_caixa, agora):
        """Atualiza a posição com suavização, para a caixa não tremer."""

        peso = config.SUAVIZACAO_CAIXA

        self._caixa = tuple(
            antigo + peso * (novo - antigo)
            for antigo, novo in zip(self._caixa, nova_caixa)
        )

        self.ultimo_visto = agora
        self.visivel = True


# ============================================================
# RASTREADOR
# ============================================================

class RastreadorPessoas:

    def __init__(self):

        self._rastros: list[Rastro] = []
        self._proximo_identificador = count(1)

    def limpar(self):
        """Esquece todas as pessoas (usado quando a câmera é desligada)."""

        self._rastros.clear()

    def atualizar(self, caixas: list[Caixa], agora: float) -> list[Rastro]:
        """
        Recebe as caixas detectadas no frame atual e devolve os rastros
        ativos, ordenados da esquerda para a direita.
        """

        for rastro in self._rastros:
            rastro.visivel = False

        # ------------------------------------------------------
        # 1) Calcula a sobreposição de cada caixa com cada rastro
        #    e ordena os pares do melhor para o pior.
        # ------------------------------------------------------

        pares = []

        for indice_rastro, rastro in enumerate(self._rastros):

            for indice_caixa, caixa in enumerate(caixas):

                sobreposicao = calcular_iou(rastro.caixa, caixa)

                if sobreposicao >= config.IOU_MINIMO_RASTREIO:
                    pares.append((sobreposicao, indice_rastro, indice_caixa))

        pares.sort(reverse=True)

        # ------------------------------------------------------
        # 2) Casa os pares em ordem: cada rastro e cada caixa só
        #    podem ser usados uma vez.
        # ------------------------------------------------------

        rastros_usados = set()
        caixas_usadas = set()

        for _, indice_rastro, indice_caixa in pares:

            if indice_rastro in rastros_usados or indice_caixa in caixas_usadas:
                continue

            self._rastros[indice_rastro].mover_para(caixas[indice_caixa], agora)

            rastros_usados.add(indice_rastro)
            caixas_usadas.add(indice_caixa)

        # ------------------------------------------------------
        # 3) Caixa que não casou com ninguém = pessoa nova.
        # ------------------------------------------------------

        for indice_caixa, caixa in enumerate(caixas):

            if indice_caixa not in caixas_usadas:

                self._rastros.append(
                    Rastro(next(self._proximo_identificador), caixa, agora)
                )

        # ------------------------------------------------------
        # 4) Esquece quem sumiu há tempo demais. Sumiços curtos são
        #    tolerados: a pessoa mantém o número e o histórico.
        # ------------------------------------------------------

        self._rastros = [
            rastro
            for rastro in self._rastros
            if agora - rastro.ultimo_visto <= config.TEMPO_MAXIMO_AUSENTE_SEG
        ]

        self._rastros.sort(key=lambda rastro: rastro.caixa[0])

        return list(self._rastros)


# ============================================================
# SOBREPOSIÇÃO ENTRE DUAS CAIXAS (IoU)
# ============================================================
#
# IoU = área da interseção / área da união.
# 0.0 = caixas não se tocam; 1.0 = caixas idênticas.
# ============================================================

def calcular_iou(caixa_a: Caixa, caixa_b: Caixa) -> float:

    largura = min(caixa_a[2], caixa_b[2]) - max(caixa_a[0], caixa_b[0])
    altura = min(caixa_a[3], caixa_b[3]) - max(caixa_a[1], caixa_b[1])

    if largura <= 0 or altura <= 0:
        return 0.0

    intersecao = largura * altura

    area_a = (caixa_a[2] - caixa_a[0]) * (caixa_a[3] - caixa_a[1])
    area_b = (caixa_b[2] - caixa_b[0]) * (caixa_b[3] - caixa_b[1])

    return intersecao / (area_a + area_b - intersecao)
