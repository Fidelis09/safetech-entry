"""
Regras de decisão de acesso.

Este módulo transforma as probabilidades do modelo em decisões:

    1) por PESSOA: ela está usando todos os EPIs que o setor exige?
    2) da CATRACA: só libera se todas as pessoas na imagem estiverem
       liberadas.

O ponto central é a separação entre DETECTAR e EXIGIR: o modelo sempre
avalia todos os EPIs que conhece, mas só os EPIs exigidos no setor
selecionado contam para liberar ou negar. Um setor que só exige luvas
libera quem está de luvas, mesmo sem capacete.

São funções puras (sem estado, sem câmera, sem tela): recebem dados e
devolvem a decisão. As regras do negócio ficam todas num lugar só.
"""

import numpy as np

from safetech import config
from safetech.nucleo.tipos import ResultadoEPI, StatusAcesso, StatusPessoa


# ============================================================
# DECISÃO DE UMA PESSOA
# ============================================================

def avaliar_pessoa(historico, epis_do_modelo, exigidos, limiar_confianca):
    """
    Decide o status de uma pessoa a partir do histórico de classificações.

    historico         -> vetores de probabilidade das últimas classificações
    epis_do_modelo    -> chaves dos EPIs, na ordem das posições do vetor
    exigidos          -> chaves dos EPIs obrigatórios no setor
    limiar_confianca  -> confiança mínima (0 a 1) para considerar que a
                         pessoa está usando um EPI

    Devolve (status, itens, faltando):
        itens    -> um ResultadoEPI por EPI que o modelo conhece
        faltando -> chaves dos EPIs exigidos que a pessoa não está usando
    """

    # Com poucas amostras ainda não dá para confiar no resultado
    if len(historico) < config.AMOSTRAS_MINIMAS_DECISAO:
        return StatusPessoa.ANALISANDO, (), ()

    # A MÉDIA das últimas classificações é bem mais estável do que a
    # última isolada: um frame borrado não derruba a decisão.
    probabilidades = np.mean(historico, axis=0)

    itens = tuple(
        ResultadoEPI(
            chave=chave,
            presente=float(probabilidade) >= limiar_confianca,
            confianca=float(probabilidade),
        )
        for chave, probabilidade in zip(epis_do_modelo, probabilidades)
    )

    usando = {item.chave for item in itens if item.presente}

    # Um EPI exigido que o modelo não conhece conta como faltando: na
    # dúvida, o sistema nega (é uma regra de segurança).
    faltando = tuple(chave for chave in exigidos if chave not in usando)

    status = StatusPessoa.NEGADO if faltando else StatusPessoa.LIBERADO

    return status, itens, faltando


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
