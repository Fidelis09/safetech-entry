"""
Ligação entre a janela e a catraca de demonstração (ESP32 pelo cabo USB).

A catraca física segue UMA área: a marcada como "comanda a catraca"
(Configurações > Área e câmera). Este controlador:

    - liga a thread que envia o status pelo cabo (CatracaSerial);
    - diz a ela o que enviar (ler_para_catraca), a partir da área marcada;
    - mostra no selo do cabeçalho se a placa está conectada.

Sem ESP32 plugado não faz mal: a thread só fica procurando a placa.
"""

import logging

from safetech import config
from safetech.interface.tema import CORES
from safetech.nucleo.tipos import EstadoCena
from safetech.servicos.catraca_serial import CatracaSerial


log = logging.getLogger(__name__)


class ControladorCatraca:

    def __init__(self, areas):
        """areas -> ControladorAreas (para saber qual área comanda a catraca)."""

        self._areas = areas

        # Thread do envio pelo cabo (None = desligada no config ou sem pyserial)
        self.serial = None

        # Selo do cabeçalho; a janela entrega depois de montar a tela
        self.selo = None

    def iniciar(self):
        """
        Começa a enviar o status à catraca pelo cabo USB.

        Se a biblioteca pyserial não estiver instalada, o programa segue
        normalmente, só sem a catraca.
        """

        if not config.CATRACA_SERIAL_ATIVA:
            return

        try:
            import serial  # noqa: F401  (só para saber se está instalada)

        except ImportError:

            log.warning("pyserial não instalado: catraca pelo cabo desligada")
            self.selo.definir("Catraca: instale o pyserial (veja o README)", CORES["alerta"])
            return

        self.serial = CatracaSerial(self.ler_para_catraca)
        self.serial.iniciar()

    def ler_para_catraca(self):
        """
        O que a catraca física deve seguir: a área marcada para comandá-la.

        Chamado pela thread da catraca. Sem nenhuma área marcada, a
        catraca recebe "vigilância" e fica desligada (fechada): na
        dúvida, nega.
        """

        area = self._areas.da_catraca()

        if area is None:
            return None, EstadoCena(modo=config.MODO_VIGILANCIA)

        return area.ler_ao_vivo()

    def atualizar(self):
        """Mostra no selo se a catraca está conectada (chamado a cada ciclo)."""

        if self.serial is None:
            return

        texto = self.serial.situacao

        # Ponto verde só com a placa conectada; procurando = amarelo
        cor = CORES["sucesso"] if texto.endswith("conectada") else CORES["alerta"]

        # Só mexe no selo quando o texto muda (e registra a mudança)
        if texto != self.selo.rotulo.cget("text"):

            log.info(texto)

            self.selo.definir(texto, cor)

    def parar(self):

        if self.serial is not None:
            self.serial.parar()
