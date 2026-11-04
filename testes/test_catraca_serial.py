"""
Envio do status à catraca ESP32 pelo cabo USB
(safetech/servicos/catraca_serial.py).

Nenhum teste usa uma porta de verdade: a porta serial é trocada por
uma porta falsa que só guarda o que foi escrito nela.

Também é o "contrato" com o firmware (catraca_esp32/): o formato da
linha e os valores de acesso daqui precisam bater com o que o
processarLinhaSerial() do .ino entende.
"""

import re
from pathlib import Path

import pytest

from safetech import config
from safetech.nucleo.tipos import (
    EstadoCena,
    PessoaObservada,
    ResultadoEPI,
    StatusAcesso,
    StatusPessoa,
)
from safetech.servicos.catraca_serial import (
    ACESSO_CAMERA_PARADA,
    CatracaSerial,
    acessos_conhecidos,
    montar_linha,
)
from testes.falsos import esperar


FRAME = object()   # qualquer coisa que não seja None: "a câmera está ligada"

FIRMWARE = Path(__file__).resolve().parent.parent / "catraca_esp32" / "catraca_esp32.ino"


def pessoa(identificador, status, faltando=()):

    return PessoaObservada(
        identificador=identificador,
        caixa=(0, 0, 5, 5),
        status=status,
        itens=(ResultadoEPI("capacete", status is StatusPessoa.LIBERADO, 0.9),),
        faltando=faltando,
    )


# ============================================================
# FORMATO DA LINHA
# ============================================================

def test_negado_lista_o_que_falta_sem_repetir():

    estado = EstadoCena(
        pessoas=(
            pessoa(1, StatusPessoa.NEGADO, ("capacete", "oculos")),
            pessoa(2, StatusPessoa.LIBERADO),
            pessoa(3, StatusPessoa.NEGADO, ("oculos", "luvas")),
        ),
        acesso=StatusAcesso.NEGADO,
    )

    # 2 irregulares de 3 pessoas; "Óculos" aparece uma vez só
    assert montar_linha(FRAME, estado) == "ST|negado|2|3|Capacete;Óculos;Luvas\n"


@pytest.mark.parametrize(
    "acesso, esperado",
    [
        (StatusAcesso.LIBERADO, "ST|liberado|0|0|\n"),
        (StatusAcesso.ANALISANDO, "ST|analisando|0|0|\n"),
        (StatusAcesso.SEM_PESSOAS, "ST|sem_pessoas|0|0|\n"),
    ],
)
def test_outros_acessos(acesso, esperado):

    assert montar_linha(FRAME, EstadoCena(acesso=acesso)) == esperado


def test_camera_parada_manda_camera_off():
    """Sem frame, a câmera está parada, mesmo que o último estado fosse "liberado"."""

    estado = EstadoCena(acesso=StatusAcesso.LIBERADO)

    assert montar_linha(None, estado) == f"ST|{ACESSO_CAMERA_PARADA}|0|0|\n"


def test_linha_tem_uma_unica_quebra_de_linha_no_fim():
    """O firmware separa as mensagens pela quebra de linha."""

    linha = montar_linha(FRAME, EstadoCena(pessoas=(pessoa(1, StatusPessoa.NEGADO, ("capacete",)),)))

    assert linha.endswith("\n") and linha.count("\n") == 1


# ============================================================
# CONTRATO COM O FIRMWARE
# ============================================================

def test_firmware_entende_todos_os_acessos_enviados():
    """Se surgir um acesso novo aqui, o .ino precisa aprender a tratá-lo."""

    codigo = FIRMWARE.read_text(encoding="utf-8")

    entendidos = set(re.findall(r'acesso == "([a-z_]+)"', codigo))

    assert entendidos == acessos_conhecidos()


def test_firmware_usa_o_mesmo_prefixo_e_velocidade():

    codigo = FIRMWARE.read_text(encoding="utf-8")

    assert 'startsWith("ST|")' in codigo
    assert montar_linha(FRAME, EstadoCena()).startswith("ST|")

    # A velocidade padrão do firmware é a do programa
    assert f"#define VELOCIDADE_SERIAL 115200" in codigo
    assert config.CATRACA_VELOCIDADE_SERIAL == 115200


# ============================================================
# ENVIO PELA PORTA (porta falsa)
# ============================================================

class PortaFalsa:
    """Guarda o que foi escrito. Pode "perder o cabo" de repente."""

    def __init__(self):

        self.escrito = []
        self.fechada = False
        self.quebrada = False
        self.in_waiting = 0

    def write(self, dados):

        if self.quebrada:
            raise OSError("cabo desconectado")

        self.escrito.append(dados.decode("utf-8"))

    def read(self, _quantidade):
        return b""

    def close(self):
        self.fechada = True


@pytest.fixture
def ritmo_rapido(monkeypatch):
    """Envia e procura de novo bem rápido, para os testes não demorarem."""

    monkeypatch.setattr(config, "CATRACA_INTERVALO_ENVIO_SEG", 0.02)
    monkeypatch.setattr(config, "CATRACA_INTERVALO_PROCURA_SEG", 0.05)
    monkeypatch.setattr(config, "CATRACA_PORTA", "")


def test_envia_o_estado_atual_varias_vezes(ritmo_rapido):

    porta = PortaFalsa()
    estado = EstadoCena(pessoas=(pessoa(1, StatusPessoa.NEGADO, ("capacete",)),), acesso=StatusAcesso.NEGADO)

    catraca = CatracaSerial(lambda: (FRAME, estado), abrir=lambda nome: porta, procurar=lambda: "COM9")

    catraca.iniciar()

    try:

        assert esperar(lambda: len(porta.escrito) >= 3, 5)
        assert set(porta.escrito) == {"ST|negado|1|1|Capacete\n"}
        assert catraca.situacao == "Catraca: COM9 conectada"

    finally:
        catraca.parar()

    assert porta.fechada


def test_acompanha_as_mudancas_do_estado(ritmo_rapido):

    porta = PortaFalsa()
    atual = {"estado": EstadoCena(acesso=StatusAcesso.ANALISANDO)}

    catraca = CatracaSerial(lambda: (FRAME, atual["estado"]), abrir=lambda nome: porta, procurar=lambda: "COM9")

    catraca.iniciar()

    try:

        assert esperar(lambda: "ST|analisando|0|0|\n" in porta.escrito, 5)

        atual["estado"] = EstadoCena(acesso=StatusAcesso.LIBERADO)

        assert esperar(lambda: "ST|liberado|0|0|\n" in porta.escrito, 5)

    finally:
        catraca.parar()


def test_sem_esp32_fica_procurando_e_conecta_quando_ele_aparece(ritmo_rapido):

    porta = PortaFalsa()
    achada = {"nome": None}

    catraca = CatracaSerial(
        lambda: (FRAME, EstadoCena()),
        abrir=lambda nome: porta,
        procurar=lambda: achada["nome"],
    )

    catraca.iniciar()

    try:

        assert esperar(lambda: "nao encontrado" in catraca.situacao, 5)
        assert porta.escrito == []

        achada["nome"] = "COM3"

        assert esperar(lambda: len(porta.escrito) >= 1, 5)
        assert catraca.situacao == "Catraca: COM3 conectada"

    finally:
        catraca.parar()


def test_porta_ocupada_nao_derruba_o_programa(ritmo_rapido):

    tentativas = []

    def abrir_ocupada(nome):

        tentativas.append(nome)
        raise PermissionError("porta em uso na Arduino IDE")

    catraca = CatracaSerial(lambda: (FRAME, EstadoCena()), abrir=abrir_ocupada, procurar=lambda: "COM3")

    catraca.iniciar()

    try:

        # Continua tentando, sem travar nem lançar erro
        assert esperar(lambda: len(tentativas) >= 3, 5)
        assert "ocupada" in catraca.situacao

    finally:
        catraca.parar()


def test_cabo_puxado_volta_a_procurar_e_reconecta(ritmo_rapido):

    primeira, segunda = PortaFalsa(), PortaFalsa()
    portas = [primeira, segunda]

    catraca = CatracaSerial(
        lambda: (FRAME, EstadoCena()),
        abrir=lambda nome: portas.pop(0),
        procurar=lambda: "COM3",
    )

    catraca.iniciar()

    try:

        assert esperar(lambda: len(primeira.escrito) >= 2, 5)

        primeira.quebrada = True   # puxaram o cabo

        assert esperar(lambda: primeira.fechada, 5)
        assert esperar(lambda: len(segunda.escrito) >= 2, 5)

    finally:
        catraca.parar()


def test_porta_configurada_tem_prioridade_sobre_a_busca(ritmo_rapido, monkeypatch):

    monkeypatch.setattr(config, "CATRACA_PORTA", "COM7")

    abertas = []
    porta = PortaFalsa()

    def abrir(nome):

        abertas.append(nome)
        return porta

    def procurar():
        raise AssertionError("não deveria procurar quando a porta está configurada")

    catraca = CatracaSerial(lambda: (FRAME, EstadoCena()), abrir=abrir, procurar=procurar)

    catraca.iniciar()

    try:
        assert esperar(lambda: len(porta.escrito) >= 1, 5)
        assert abertas == ["COM7"]

    finally:
        catraca.parar()
