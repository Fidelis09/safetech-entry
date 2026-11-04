"""
Linha de análise (safetech/servicos/analisador.py), de ponta a ponta:
detectar -> rastrear -> classificar -> decidir -> auditar.

Câmera, detector e classificador são falsos, então o resultado é
conhecido de antemão: a pessoa 1 usa tudo; a pessoa 2 está sem capacete.
"""

import pytest

from safetech import config
from safetech.nucleo.tipos import StatusAcesso, StatusPessoa
from safetech.servicos.analisador import Analisador, ParametrosAnalise
from testes.falsos import CameraFalsa, ClassificadorFalso, DetectorFalso, esperar


#                 capacete oculos colete luvas
COM_TUDO =       [0.95,    0.95,  0.95,  0.95]
SEM_CAPACETE =   [0.05,    0.95,  0.95,  0.95]


@pytest.fixture
def analise(auditoria):
    """Analisador rodando com duas pessoas na imagem; parado no fim do teste."""

    parametros = ParametrosAnalise(
        setor="Canteiro de obras",
        exigidos=("capacete", "colete"),
        modo_deteccao=config.MODO_CATRACA,
        # Classifica bem rápido, para o teste não demorar
        intervalo_classificacao=0.05,
    )

    classificador = ClassificadorFalso([COM_TUDO, SEM_CAPACETE])

    analisador = Analisador(
        CameraFalsa(),
        {config.MODO_CATRACA: DetectorFalso([(50, 50, 200, 400), (300, 60, 450, 420)])},
        classificador,
        auditoria,
        parametros,
    )

    analisador.iniciar()

    yield analisador, parametros, classificador, auditoria

    analisador.parar()

    assert analisador.erro is None


def decidido(analisador):
    """True quando todas as pessoas já têm decisão."""

    pessoas = analisador.estado().pessoas

    return len(pessoas) == 2 and all(p.status is not StatusPessoa.ANALISANDO for p in pessoas)


def test_decide_cada_pessoa_e_a_catraca(analise):

    analisador, *_ = analise

    assert esperar(lambda: decidido(analisador), 10)

    estado = analisador.estado()
    pessoa1, pessoa2 = sorted(estado.pessoas, key=lambda p: p.identificador)

    assert pessoa1.status is StatusPessoa.LIBERADO
    assert pessoa2.status is StatusPessoa.NEGADO
    assert pessoa2.faltando == ("capacete",)

    # Uma pessoa irregular basta para negar a catraca
    assert estado.acesso is StatusAcesso.NEGADO


def test_uma_foto_por_pessoa_enquanto_nada_muda(analise):

    analisador, _, _, auditoria = analise

    assert esperar(lambda: len(auditoria.carregar_historico()) == 2, 10)

    # Continua analisando por mais um tempo: nada novo deve ser gravado
    esperar(lambda: False, 1.0)

    historico = auditoria.carregar_historico()

    assert len(historico) == 2
    assert {r.evento for r in historico} == {"ENTRADA"}
    assert len(list(auditoria.pasta_imagens.iterdir())) == 2


def test_trocar_o_setor_vale_na_hora_e_gera_evento_de_mudanca(analise):

    analisador, parametros, _, auditoria = analise

    assert esperar(lambda: len(auditoria.carregar_historico()) == 2, 10)

    # Setor que não exige capacete: a pessoa 2 passa a ser liberada
    parametros.setor = "Laboratório"
    parametros.exigidos = ("oculos", "luvas")

    assert esperar(lambda: analisador.estado().acesso is StatusAcesso.LIBERADO, 10)

    # A mudança só vai para o log depois de confirmada algumas vezes
    assert esperar(lambda: len(auditoria.carregar_historico()) == 3, 10)

    mudanca = auditoria.carregar_historico()[-1]

    assert mudanca.evento == "MUDANCA"
    assert mudanca.pessoa == "P002"
    assert mudanca.liberado == "SIM"
    assert mudanca.setor == "Laboratório"


def test_reiniciar_pessoas_recomeca_a_numeracao(analise):

    analisador, _, _, auditoria = analise

    assert esperar(lambda: len(auditoria.carregar_historico()) == 2, 10)

    auditoria.zerar()
    analisador.reiniciar_pessoas()

    # Quem está na imagem volta a contar como novo, de P001 em diante
    assert esperar(lambda: len(auditoria.carregar_historico()) == 2, 10)
    assert sorted(r.pessoa for r in auditoria.carregar_historico()) == ["P001", "P002"]
