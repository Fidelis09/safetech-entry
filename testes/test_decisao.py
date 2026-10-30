"""
Regras de decisão (safetech/nucleo/decisao.py).

São as regras de negócio mais importantes do sistema: quem é liberado,
quem é negado e quando a catraca abre.
"""

import numpy as np

from safetech import config
from safetech.nucleo import decisao
from safetech.nucleo.tipos import StatusAcesso, StatusPessoa


EPIS = ["capacete", "oculos", "colete", "luvas"]


def historico(*vetores):
    return [np.array(vetor, dtype=float) for vetor in vetores]


# ============================================================
# DECISÃO DE UMA PESSOA
# ============================================================

def test_poucas_amostras_ainda_analisando():

    poucas = historico([0.9, 0.9, 0.9, 0.9])[: config.AMOSTRAS_MINIMAS_DECISAO - 1]

    status, itens, faltando = decisao.avaliar_pessoa(poucas, EPIS, ["capacete"], 0.8)

    assert status is StatusPessoa.ANALISANDO
    assert itens == () and faltando == ()


def test_libera_quem_usa_tudo_que_o_setor_exige():

    h = historico([0.95, 0.1, 0.9, 0.1], [0.92, 0.2, 0.85, 0.1])

    # Canteiro de obras: só capacete e colete. Óculos e luvas não contam.
    status, _, faltando = decisao.avaliar_pessoa(h, EPIS, ["capacete", "colete"], 0.8)

    assert status is StatusPessoa.LIBERADO
    assert faltando == ()


def test_nega_e_diz_o_que_falta():

    h = historico([0.95, 0.1, 0.9, 0.1], [0.92, 0.2, 0.85, 0.1])

    status, _, faltando = decisao.avaliar_pessoa(h, EPIS, ["capacete", "luvas"], 0.8)

    assert status is StatusPessoa.NEGADO
    assert faltando == ("luvas",)


def test_trocar_o_setor_muda_a_decisao_sem_reclassificar():
    """Detectar é separado de exigir: o mesmo histórico, setores diferentes."""

    h = historico([0.1, 0.9, 0.9, 0.9], [0.1, 0.9, 0.9, 0.9])

    assert decisao.avaliar_pessoa(h, EPIS, ["capacete"], 0.8)[0] is StatusPessoa.NEGADO
    assert decisao.avaliar_pessoa(h, EPIS, ["oculos", "luvas"], 0.8)[0] is StatusPessoa.LIBERADO


def test_sem_epi_exigido_libera():

    h = historico([0.0] * 4, [0.0] * 4)

    assert decisao.avaliar_pessoa(h, EPIS, [], 0.8)[0] is StatusPessoa.LIBERADO


def test_epi_que_o_modelo_nao_conhece_conta_como_faltando():
    """Regra de segurança: na dúvida, nega."""

    h = historico([0.99, 0.99], [0.99, 0.99])

    status, _, faltando = decisao.avaliar_pessoa(h, ["capacete", "colete"], ["capacete", "luvas"], 0.8)

    assert status is StatusPessoa.NEGADO
    assert faltando == ("luvas",)


def test_limiar_de_confianca():

    h = historico([0.75] * 4, [0.75] * 4)

    assert decisao.avaliar_pessoa(h, EPIS, ["capacete"], 0.70)[0] is StatusPessoa.LIBERADO
    assert decisao.avaliar_pessoa(h, EPIS, ["capacete"], 0.80)[0] is StatusPessoa.NEGADO


def test_mediana_ignora_uma_classificacao_errada_isolada():
    """
    Com a média, um único 0.0 derrubaria 0.9+0.9+0.0 para 0.6 (negado).
    A mediana fica em 0.9: um erro isolado não vira a decisão.
    """

    h = historico([0.9] * 4, [0.9] * 4, [0.0] * 4)

    status, itens, _ = decisao.avaliar_pessoa(h, EPIS, ["capacete"], 0.8)

    assert status is StatusPessoa.LIBERADO
    assert itens[0].confianca == 0.9


# ============================================================
# DECISÃO DA CATRACA
# ============================================================

def test_catraca_sem_pessoas():
    assert decisao.avaliar_acesso([]) is StatusAcesso.SEM_PESSOAS


def test_catraca_libera_so_se_todos_liberados():

    assert decisao.avaliar_acesso([StatusPessoa.LIBERADO] * 3) is StatusAcesso.LIBERADO


def test_catraca_nega_se_uma_pessoa_estiver_irregular():

    status = [StatusPessoa.LIBERADO, StatusPessoa.NEGADO, StatusPessoa.ANALISANDO]

    assert decisao.avaliar_acesso(status) is StatusAcesso.NEGADO


def test_catraca_espera_quem_ainda_esta_em_analise():

    status = [StatusPessoa.LIBERADO, StatusPessoa.ANALISANDO]

    assert decisao.avaliar_acesso(status) is StatusAcesso.ANALISANDO
