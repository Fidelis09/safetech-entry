"""
Estruturas de dados compartilhadas entre os módulos.

São objetos imutáveis (frozen): depois de criados não mudam. Isso é o
que permite passá-los com segurança da thread de análise para a thread
da interface, sem risco de um lado alterar o que o outro está lendo.
"""

from dataclasses import dataclass
from enum import Enum


# Caixa de uma pessoa na imagem: (x1, y1, x2, y2), em pixels do frame original
Caixa = tuple[int, int, int, int]


# ============================================================
# STATUS DE UMA PESSOA
# ============================================================

class StatusPessoa(Enum):

    # Ainda não há classificações suficientes para decidir
    ANALISANDO = "analisando"

    # Está com o EPI, com confiança acima do limiar
    LIBERADO = "liberado"

    # Está sem EPI, ou a confiança ficou abaixo do limiar
    NEGADO = "negado"


# ============================================================
# STATUS GERAL DA CATRACA
# ============================================================

class StatusAcesso(Enum):

    SEM_PESSOAS = "sem_pessoas"
    ANALISANDO = "analisando"
    LIBERADO = "liberado"
    NEGADO = "negado"


# ============================================================
# UMA PESSOA VISTA PELA CÂMERA
# ============================================================

@dataclass(frozen=True)
class PessoaObservada:

    # Número fixo da pessoa enquanto ela permanecer na imagem
    identificador: int

    caixa: Caixa

    status: StatusPessoa

    # Classe prevista (ex.: "com_epi"); None enquanto estiver analisando
    classe: str | None

    # Confiança média da classe prevista, de 0.0 a 1.0
    confianca: float


# ============================================================
# RETRATO DA CENA NUM INSTANTE
# ============================================================
#
# É o que a thread de análise publica e a interface lê para
# desenhar as caixas e o painel de status.
# ============================================================

@dataclass(frozen=True)
class EstadoCena:

    pessoas: tuple[PessoaObservada, ...] = ()

    acesso: StatusAcesso = StatusAcesso.SEM_PESSOAS

    # Quantas análises por segundo a linha de detecção está fazendo
    analises_por_segundo: float = 0.0


# ============================================================
# UMA LINHA DO LOG DE AUDITORIA
# ============================================================

@dataclass(frozen=True)
class RegistroAuditoria:

    timestamp: str

    # "ENTRADA" (primeira decisão da pessoa) ou "MUDANCA" (a decisão mudou)
    evento: str

    # Identificação da pessoa na sessão, ex.: "P003"
    pessoa: str

    classe: str

    # Confiança em porcentagem, já formatada (ex.: "93.50")
    confianca_percentual: str

    # "SIM" ou "NAO"
    liberado: str

    # Nome do arquivo da foto de evidência (dentro de auditoria/imagens)
    imagem: str

    def como_linha(self):
        """Valores na mesma ordem das colunas do CSV."""

        return [
            self.timestamp,
            self.evento,
            self.pessoa,
            self.classe,
            self.confianca_percentual,
            self.liberado,
            self.imagem,
        ]
