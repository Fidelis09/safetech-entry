"""
Envio do status da catraca ao ESP32 pelo cabo USB.

A catraca de demonstração (pasta catraca_esp32/) pode receber o status
de dois jeitos: pelo Wi-Fi (ela pergunta ao painel web) ou por este
cabo USB. Aqui está o lado do cabo: uma thread que, de tempos em
tempos, escreve uma linha de texto na porta serial com a situação do
acesso. O ESP32 lê a linha e move a cancela, acende os LEDs, etc.

Por que uma linha de texto simples:

    ST|negado|1|2|Capacete;Oculos

    ST        -> marca o começo de uma mensagem válida
    negado    -> acesso: sem_pessoas, analisando, liberado, negado,
                 camera_off (câmera parada) ou vigilancia (modo
                 vigilância: a catraca fica desligada e fechada)
    1         -> quantas pessoas estão irregulares
    2         -> quantas pessoas há na imagem
    Capacete;Oculos -> o que falta (vazio se nada)

Qualquer lixo no cabo (ruído, mensagem cortada no meio) é ignorado
pelo ESP32, porque a linha não começa com "ST|" ou não tem os campos.

Este módulo SÓ ENVIA: não aceita comandos do ESP32. A leitura da
porta serve apenas para esvaziar as mensagens de depuração dele (se
ninguém lesse, o espaço do cabo encheria e travaria a placa).

Regra de segurança: se o programa fechar ou o cabo sair, o ESP32 para
de receber linhas e FECHA a cancela sozinho (na dúvida, nega).
"""

import threading
import time

from safetech import config
from safetech.nucleo import modos
from safetech.nucleo.epis import nome_do_epi
from safetech.nucleo.tipos import StatusAcesso, StatusPessoa


# Acesso enviado quando a câmera está parada. Não existe em StatusAcesso:
# é uma situação da câmera, não da catraca.
ACESSO_CAMERA_PARADA = "camera_off"

# Acesso enviado no modo vigilância. Lá não existe acesso a liberar: a
# catraca física fica desligada (fechada, LEDs apagados), qualquer que
# seja a situação das pessoas na área.
ACESSO_VIGILANCIA = "vigilancia"

# Quem fabrica o chip USB das placas ESP32 mais comuns: Silicon Labs
# (CP210x), WCH (CH340/CH9102), Espressif (USB nativo) e FTDI.
FABRICANTES_USB = (0x10C4, 0x1A86, 0x303A, 0x0403)


# ============================================================
# MONTAGEM DA LINHA (função pura: fácil de testar)
# ============================================================

def montar_linha(frame, estado) -> str:
    """
    Transforma o frame e o estado da cena na linha enviada ao ESP32.

    frame  -> o frame atual da câmera (None se a câmera está parada)
    estado -> EstadoCena do analisador

    A linha termina com "\\n" e usa só texto simples. Os nomes dos EPIs
    vão como o programa os mostra (com acento); o ESP32 tira os acentos
    porque a fonte da tela não os tem.
    """

    if modos.eh_vigilancia(estado.modo):
        acesso = ACESSO_VIGILANCIA
    elif frame is None:
        acesso = ACESSO_CAMERA_PARADA
    else:
        acesso = estado.acesso.value

    negadas = [pessoa for pessoa in estado.pessoas if pessoa.status is StatusPessoa.NEGADO]

    # Cada EPI uma vez só, mesmo faltando em várias pessoas
    faltando = []

    for pessoa in negadas:

        for chave in pessoa.faltando:

            nome = nome_do_epi(chave)

            if nome not in faltando:
                faltando.append(nome)

    return f"ST|{acesso}|{len(negadas)}|{len(estado.pessoas)}|{';'.join(faltando)}\n"


def acessos_conhecidos() -> set:
    """Os valores de acesso que o ESP32 sabe tratar (para o teste de contrato)."""

    return {acesso.value for acesso in StatusAcesso} | {ACESSO_CAMERA_PARADA, ACESSO_VIGILANCIA}


# ============================================================
# PORTA SERIAL
# ============================================================

def procurar_porta():
    """
    Devolve o nome da porta (ex.: "COM3") do primeiro ESP32 encontrado,
    ou None. Só considera chips USB comuns de placa ESP32.
    """

    from serial.tools import list_ports

    for porta in list_ports.comports():

        if porta.vid in FABRICANTES_USB:
            return porta.device

    return None


def abrir_porta(nome):
    """
    Abre a porta serial SEM ligar os sinais DTR e RTS.

    Nas placas ESP32, esses dois sinais ligados ao abrir a porta
    REINICIAM a placa. Deixá-los desligados evita reiniciar a catraca
    toda vez que o programa abre.
    """

    import serial

    porta = serial.Serial()
    porta.port = nome
    porta.baudrate = config.CATRACA_VELOCIDADE_SERIAL
    porta.timeout = 0
    porta.write_timeout = config.CATRACA_TEMPO_LIMITE_ESCRITA_SEG
    porta.dtr = False
    porta.rts = False

    porta.open()

    return porta


# ============================================================
# THREAD DE ENVIO
# ============================================================

class CatracaSerial:

    def __init__(self, fonte_ao_vivo, abrir=abrir_porta, procurar=procurar_porta):
        """
        fonte_ao_vivo -> função que devolve (frame, EstadoCena) do momento
                         (a mesma que o painel web usa).
        abrir, procurar -> trocáveis nos testes, para não depender de
                           uma porta de verdade.
        """

        self._fonte_ao_vivo = fonte_ao_vivo
        self._abrir = abrir
        self._procurar = procurar

        self._parar = threading.Event()
        self._thread = None

        # Texto para a barra de status da janela (lido por outra thread;
        # trocar um texto inteiro de uma vez é seguro sem trava)
        self.situacao = "Catraca: procurando o cabo..."

        # Última linha enviada e quantas já foram (úteis nos testes)
        self.ultima_linha = ""
        self.total_enviado = 0

    # ============================================================
    # CONTROLE
    # ============================================================

    def iniciar(self):

        if self._thread is not None and self._thread.is_alive():
            return

        self._parar.clear()

        self._thread = threading.Thread(target=self._executar, name="catraca-serial", daemon=True)
        self._thread.start()

    def parar(self):

        self._parar.set()

        if self._thread is not None:
            self._thread.join(timeout=3)
            self._thread = None

    # ============================================================
    # LAÇO PRINCIPAL
    # ============================================================

    def _executar(self):

        while not self._parar.is_set():

            porta = self._conectar()

            if porta is None:

                # Sem cabo (ou porta ocupada): tenta de novo daqui a pouco
                self._parar.wait(config.CATRACA_INTERVALO_PROCURA_SEG)
                continue

            try:
                self._enviar_sem_parar(porta)

            except Exception:
                # Cabo puxado, porta tomada por outro programa...
                # volta a procurar
                self.situacao = "Catraca: cabo desconectado, procurando..."

            finally:

                try:
                    porta.close()
                except Exception:
                    pass

    def _conectar(self):
        """Acha a porta e a abre. Devolve a porta, ou None se não deu."""

        nome = config.CATRACA_PORTA or self._procurar()

        if nome is None:
            self.situacao = "Catraca: ESP32 nao encontrado no USB"
            return None

        try:
            porta = self._abrir(nome)

        except Exception:

            # Ex.: a porta está aberta na Arduino IDE ou em outro programa
            self.situacao = f"Catraca: {nome} ocupada ou indisponivel"
            return None

        self.situacao = f"Catraca: {nome} conectada"

        return porta

    def _enviar_sem_parar(self, porta):
        """Envia o status a cada CATRACA_INTERVALO_ENVIO_SEG, até pararem ou a porta falhar."""

        while not self._parar.is_set():

            frame, estado = self._fonte_ao_vivo()

            linha = montar_linha(frame, estado)

            porta.write(linha.encode("utf-8"))

            self.ultima_linha = linha
            self.total_enviado += 1

            # Esvazia o que o ESP32 escreveu (mensagens de depuração)
            if porta.in_waiting:
                porta.read(porta.in_waiting)

            self._parar.wait(config.CATRACA_INTERVALO_ENVIO_SEG)
