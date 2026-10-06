"""
Regras de decisão de acesso.

Este módulo transforma as probabilidades do modelo em decisões:

    1) por PESSOA: liberado, negado ou ainda analisando;
    2) da CATRACA: só libera se todas as pessoas na imagem estiverem
       liberadas.

São funções puras (sem estado, sem câmera, sem tela): recebem dados e
devolvem a decisão. As regras do negócio ficam todas num lugar só.
"""

import numpy as np

from safetech import config
from safetech.nucleo.tipos import StatusAcesso, StatusPessoa


# ============================================================
# DECISÃO DE UMA PESSOA
# ============================================================

def avaliar_pessoa(historico, classes, limiar_confianca):
    """
    Decide o status de uma pessoa a partir do histórico de classificações.

    historico         -> vetores de probabilidade das últimas classificações
    classes           -> nomes das classes, na ordem do modelo
    limiar_confianca  -> confiança mínima (0 a 1) para liberar

    Devolve (status, classe, confianca).
    """

    # Com poucas amostras ainda não dá para confiar no resultado
    if len(historico) < config.AMOSTRAS_MINIMAS_DECISAO:
        return StatusPessoa.ANALISANDO, None, 0.0

    # A MÉDIA das últimas classificações é bem mais estável do que a
    # última isolada: um frame borrado não derruba a decisão.
    probabilidades = np.mean(historico, axis=0)

    indice = int(np.argmax(probabilidades))

    classe = classes[indice]
    confianca = float(probabilidades[indice])

    liberado = (
        classe == config.CLASSE_LIBERA_ACESSO
        and confianca >= limiar_confianca
    )

    status = StatusPessoa.LIBERADO if liberado else StatusPessoa.NEGADO

    return status, classe, confianca


# ============================================================
# DECISÃO DA CATRACA
# ============================================================

def avaliar_acesso(status_das_pessoas) -> StatusAcesso:
    """
    Decide o status geral a partir do status de cada pessoa.

    Regra de segurança: basta UMA pessoa negada para a catraca negar.
    Enquanto houver alguém ainda em análise, ela também não libera.
    """

    status_das_pessoas = list(status_das_pessoas)

    if not status_das_pessoas:
        return StatusAcesso.SEM_PESSOAS

    if StatusPessoa.NEGADO in status_das_pessoas:
        return StatusAcesso.NEGADO

    if StatusPessoa.ANALISANDO in status_das_pessoas:
        return StatusAcesso.ANALISANDO

    return StatusAcesso.LIBERADO
