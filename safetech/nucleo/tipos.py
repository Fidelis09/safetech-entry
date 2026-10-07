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

    # Está usando todos os EPIs exigidos no setor
    LIBERADO = "liberado"

    # Falta pelo menos um EPI exigido
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
# RESULTADO DE UM EPI PARA UMA PESSOA
# ============================================================

@dataclass(frozen=True)
class ResultadoEPI:

    # Chave do equipamento (ex.: "capacete"), como em config.EPIS
    chave: str

    # True se a confiança passou do limiar: a pessoa ESTÁ usando
    presente: bool

    # Confiança média de que a pessoa está usando, de 0.0 a 1.0
    confianca: float


# ============================================================
# UMA PESSOA VISTA PELA CÂMERA
# ============================================================

@dataclass(frozen=True)
class PessoaObservada:

    # Número fixo da pessoa enquanto ela permanecer na imagem
    identificador: int

    caixa: Caixa

    status: StatusPessoa

    # Resultado de cada EPI que o modelo conhece (vazio enquanto analisa)
    itens: tuple[ResultadoEPI, ...] = ()

    # Chaves dos EPIs exigidos no setor que a pessoa NÃO está usando
    faltando: tuple[str, ...] = ()


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

    # Setor em fiscalização e as chaves dos EPIs exigidos nele
    setor: str = ""
    exigidos: tuple[str, ...] = ()

    # Quantas análises por segundo a linha de detecção está fazendo
    analises_por_segundo: float = 0.0


# ============================================================
# UMA LINHA DO LOG DE AUDITORIA
# ============================================================
#
# Todos os campos são texto, exatamente como ficam no CSV.
# ============================================================

@dataclass(frozen=True)
class RegistroAuditoria:

    timestamp: str

    # "ENTRADA" (primeira decisão da pessoa) ou "MUDANCA" (a decisão mudou)
    evento: str

    # Identificação da pessoa na sessão, ex.: "P003"
    pessoa: str

    # Setor que estava sendo fiscalizado no momento
    setor: str

    # EPIs exigidos no setor, ex.: "Capacete, Luvas"
    exigidos: str

    # EPIs exigidos que a pessoa não estava usando ("" se nenhum)
    faltando: str

    # Confiança de cada EPI, ex.: "Capacete 97%, Luvas 12%"
    confiancas: str

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
            self.setor,
            self.exigidos,
            self.faltando,
            self.confiancas,
            self.liberado,
            self.imagem,
        ]
