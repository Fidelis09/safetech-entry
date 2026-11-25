"""
Liga o telão (a tela do trabalhador) à área certa.

O telão segue a área que comanda a catraca física; sem nenhuma marcada,
segue a área aberta na janela principal. Botão "Telão" no topo do
monitoramento, ou tecla F2.
"""

import logging
import time

from safetech import config
from safetech.interface.janela_telao import JanelaTelao
from safetech.servicos.camera import EstadoCamera


log = logging.getLogger(__name__)


class ControladorTelao:

    def __init__(self, janela, areas):

        self._janela = janela
        self._areas = areas

        # None = telão fechado
        self.telao = None

        self._proximo_quadro = 0.0

    def alternar(self):
        """Abre o telão; se já estiver aberto, fecha."""

        if self.telao is not None:
            self.telao.fechar()
            return

        self.telao = JanelaTelao(self._janela.raiz, ao_fechar=self._ao_fechar_telao)

        log.info("Telão aberto")

        self._janela.avisar("Telão aberto: arraste-o para o monitor do trabalhador e aperte F11.", segundos=8)

        self.atualizar(forcar=True)

    def _ao_fechar_telao(self):

        self.telao = None

    def area_do_telao(self):
        """A área que comanda a catraca ou, sem nenhuma, a área aberta."""

        return self._areas.da_catraca() or self._areas.atual

    def atualizar(self, agora=None, forcar=False):
        """Chamado a cada ciclo: passa ao telão a situação da área (no ritmo de QUADROS_POR_SEGUNDO_TELAO)."""

        if self.telao is None:
            return

        agora = time.perf_counter() if agora is None else agora

        if not forcar and agora < self._proximo_quadro:
            return

        self._proximo_quadro = agora + 1.0 / config.QUADROS_POR_SEGUNDO_TELAO

        area = self.area_do_telao()

        if area is None:
            return

        frame, estado = area.ler_ao_vivo()

        ligada = area.camera.estado is EstadoCamera.ATIVA and area.analisador is not None

        self.telao.atualizar(area.nome, estado, frame, camera_ligada=ligada)

    def fechar(self):

        if self.telao is not None:
            self.telao.fechar()
