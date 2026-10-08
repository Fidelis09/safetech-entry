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
        # (um vetor por classificação). A decisão usa a mediana delas.
        self.historico = deque(maxlen=config.TAMANHO_HISTORICO_DECISAO)

        # Última decisão gravada na auditoria (None = nenhuma ainda).
        # Serve para registrar apenas quando a decisão MUDA.
        self.decisao_registrada = None

        # Quantas classificações seguidas discordaram da decisão
        # registrada. A mudança só é gravada depois de confirmada.
        self.confirmacoes_de_mudanca = 0

        # Velocidade estimada do centro da caixa, em pixels por segundo
        self._velocidade = (0.0, 0.0)

    @property
    def caixa(self) -> Caixa:
        return tuple(int(round(v)) for v in self._caixa)

    def mover_para(self, nova_caixa, agora):
        """Atualiza a posição com suavização, para a caixa não tremer."""

        # Quem volta depois de um sumiço vai direto para a posição nova:
        # suavizar a partir de um lugar antigo deixaria a caixa para trás.
        intervalo = agora - self.ultimo_visto

        if intervalo > 0.3:
            peso = 1.0
        else:
            peso = config.SUAVIZACAO_CAIXA

        centro_antigo = self.centro()

        self._caixa = tuple(
            antigo + peso * (novo - antigo)
            for antigo, novo in zip(self._caixa, nova_caixa)
        )

        # Estima a velocidade (pixels por segundo) pelo quanto o centro
        # andou desde a última vez. O valor novo é misturado ao anterior
        # para o tremor da detecção não virar "movimento".
        if 0 < intervalo <= config.TEMPO_MAXIMO_PREVISAO_SEG:

            centro_novo = self.centro()
            mistura = config.SUAVIZACAO_VELOCIDADE

            self._velocidade = tuple(
                anterior + mistura * ((novo - antigo) / intervalo - anterior)
                for anterior, novo, antigo in zip(self._velocidade, centro_novo, centro_antigo)
            )

        self.ultimo_visto = agora
        self.visivel = True

    def centro(self):
        return (self._caixa[0] + self._caixa[2]) / 2, (self._caixa[1] + self._caixa[3]) / 2

    def centro_previsto(self, agora):
        """
        Onde a pessoa DEVE estar agora, supondo que continuou andando
        na mesma direção e velocidade desde a última vez em que foi
        vista.

        É o que permite acompanhar quem está em movimento e não trocar
        duas pessoas que se cruzam: cada uma é procurada onde estaria
        se seguisse seu caminho, e não onde estava.

        A previsão vale só por um tempo curto. Depois dele, ninguém
        garante que a pessoa manteve o rumo, então o ponto para de
        avançar.
        """

        decorrido = min(agora - self.ultimo_visto, config.TEMPO_MAXIMO_PREVISAO_SEG)

        x, y = self.centro()

        return x + self._velocidade[0] * decorrido, y + self._velocidade[1] * decorrido

    def largura(self):
        return max(1.0, self._caixa[2] - self._caixa[0])


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
        lembrados, ordenados da esquerda para a direita.

        A lista inclui pessoas que sumiram há pouco (rastro.visivel é
        False e rastro.ultimo_visto diz há quanto tempo); quem usa a
        lista decide se as mostra.
        """

        for rastro in self._rastros:
            rastro.visivel = False

        # ------------------------------------------------------
        # 1) Para cada caixa e cada rastro, decide se podem ser a
        #    mesma pessoa. Podem se:
        #      - as caixas se sobrepõem o bastante (IoU), ou
        #      - os centros estão próximos.
        #
        #    A distância é medida em "larguras de caixa", para valer
        #    igual para quem está perto ou longe da câmera. Quanto
        #    mais tempo a pessoa ficou sem ser detectada, mais longe
        #    ela pode ter ido, então o raio de busca cresce com o
        #    tempo de sumiço (até um limite).
        # ------------------------------------------------------

        pares = []

        for indice_rastro, rastro in enumerate(self._rastros):

            ausente = agora - rastro.ultimo_visto

            raio = min(
                config.DISTANCIA_MAXIMA_RASTREIO,
                config.DISTANCIA_BASE_RASTREIO + config.DISTANCIA_POR_SEGUNDO_AUSENTE * ausente,
            )

            # Procura a pessoa onde ela deve estar agora, não onde estava
            centro_x, centro_y = rastro.centro_previsto(agora)

            for indice_caixa, caixa in enumerate(caixas):

                distancia = (
                    ((caixa[0] + caixa[2]) / 2 - centro_x) ** 2
                    + ((caixa[1] + caixa[3]) / 2 - centro_y) ** 2
                ) ** 0.5 / rastro.largura()

                if (
                    distancia <= raio
                    or calcular_iou(rastro.caixa, caixa) >= config.IOU_MINIMO_RASTREIO
                ):
                    pares.append((distancia, indice_rastro, indice_caixa))

        # Do par mais próximo para o mais distante
        pares.sort()

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
        # 4) Esquece quem sumiu há tempo demais.
        #
        #    A pessoa que some por pouco tempo (virou o rosto, passou
        #    atrás de algo) continua LEMBRADA: mantém o número, o
        #    histórico e a decisão já registrada. Assim, quando ela
        #    reaparece, não vira "outra pessoa" nem gera um evento e
        #    uma foto de evidência repetidos.
        # ------------------------------------------------------

        self._rastros = [
            rastro
            for rastro in self._rastros
            if agora - rastro.ultimo_visto <= config.TEMPO_MEMORIA_PESSOA_SEG
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
