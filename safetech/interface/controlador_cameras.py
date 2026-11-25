"""
Ações sobre as câmeras das áreas.

    alternar      -> liga ou desliga a câmera de uma área (botão ou Espaço)
    escolher      -> troca a câmera da área aberta (Configurações)
    trocar_da_area-> botão "Trocar câmera": abre as Configurações na área
    capturar_foto -> guarda o momento (com caixas e carimbo) em
                     auditoria/capturas, fora do log
    adicionar_ip  -> cadastra uma câmera IP e já a usa na área aberta
    remover_ip    -> tira uma câmera IP do cadastro

A senha de uma câmera IP pode estar no endereço: por isso os avisos
sempre usam o NOME da câmera, nunca o endereço.
"""

import logging

from safetech.interface import dialogos
from safetech.interface.dialogo_camera_ip import pedir_camera_ip
from safetech.servicos import capturas, preferencias
from safetech.servicos.camera import EstadoCamera


log = logging.getLogger(__name__)


class ControladorCameras:

    def __init__(self, janela, areas):
        """
        janela -> JanelaPrincipal (Configurações e avisos)
        areas  -> ControladorAreas (as áreas e a que está aberta)
        """

        self._janela = janela
        self._areas = areas

        # Índices das webcams achados pela busca (thread em segundo
        # plano); a interface os entrega à lista no ciclo seguinte.
        self._encontradas = None

        # Caminho da última foto capturada (usado nos testes)
        self.ultima_captura = None

    # ============================================================
    # LIGAR E DESLIGAR
    # ============================================================

    def alternar(self, area=None):
        """Botão da câmera de uma área (ou tecla Espaço, na área à vista)."""

        # Tecla Espaço na visão geral: não há UMA área à vista para ligar
        if area is None and self._areas.visao_geral_na_tela():
            return

        area = area or self._areas.atual

        # Antes de a IA carregar não há o que fazer com a câmera
        if area.analisador is None:
            return

        estado = area.camera.estado

        if estado in (EstadoCamera.PARADA, EstadoCamera.ERRO):
            area.camera.iniciar()

        elif estado in (EstadoCamera.ATIVA, EstadoCamera.RECONECTANDO):
            area.camera.parar()

    # ============================================================
    # LISTA DE WEBCAMS (busca em segundo plano)
    # ============================================================

    def guardar_encontradas(self, indices):
        """Chamado pela thread da busca; a lista é preenchida no próximo ciclo."""

        self._encontradas = indices

    def entregar_encontradas(self):
        """Chamado a cada ciclo: passa para as Configurações o que a busca achou."""

        if self._encontradas is not None:

            self._janela.configuracoes.definir_cameras(self._encontradas)
            self._encontradas = None

    # ============================================================
    # TROCAR A CÂMERA DE UMA ÁREA
    # ============================================================

    def escolher(self, fonte):
        """
        Configurações > Área e câmera: troca a câmera da área aberta.

        fonte -> número da webcam ou endereço da câmera IP.

        Se a câmera estava ligada, a nova liga sozinha; se estava
        parada, só fica escolhida para o próximo "Iniciar câmera".
        """

        area = self._areas.atual
        configuracoes = self._janela.configuracoes

        area.camera.trocar_fonte(fonte)
        area.dados.fonte = fonte

        area.painel.definir_camera(configuracoes.nome_camera(fonte), area.dados.controla_catraca)

        self._areas.salvar()

        # Faz o vídeo e o botão refletirem o novo estado da câmera
        area.esquecer_desenho()

        # Pelo nome, nunca pelo endereço (que pode ter a senha)
        self._janela.avisar(f"{configuracoes.nome_camera(fonte)} selecionada na área \"{area.nome}\".")

    def trocar_da_area(self, area):
        """Botão "Trocar câmera" de uma área: abre as Configurações já na aba dela."""

        if area is not self._areas.atual:
            self._areas.selecionar(area)

        self._janela.configuracoes.mostrar("area")

    # ============================================================
    # CAPTURAR FOTO
    # ============================================================

    def capturar_foto(self, area):
        """
        Botão "Foto": guarda a imagem do momento da área, com as
        caixas e o carimbo, em auditoria/capturas (fora do log).
        """

        frame, estado = area.ler_ao_vivo()

        if frame is None:
            self._janela.avisar(f"Ligue a câmera da área \"{area.nome}\" para capturar uma foto.")
            return

        try:
            caminho = capturas.salvar(frame, estado, area.nome)

        except OSError as erro:

            log.exception("Foto não capturada")
            self._janela.avisar(f"Não foi possível salvar a foto: {erro}", segundos=10)
            return

        self.ultima_captura = caminho

        self._janela.avisar(f"Foto da área \"{area.nome}\" salva em auditoria/capturas/{caminho.name}.", segundos=7, tipo="sucesso")

    # ============================================================
    # CÂMERAS IP: ADICIONAR E REMOVER
    # ============================================================

    def adicionar_ip(self):
        """
        "Adicionar câmera IP...": pede nome e endereço, salva a câmera e
        já passa a usá-la na área aberta.
        """

        configuracoes = self._janela.configuracoes

        cameras = preferencias.carregar_cameras_ip()

        resposta = pedir_camera_ip(configuracoes.pai_para_dialogos(self._janela.raiz), f"Câmera IP {len(cameras) + 1}")

        if resposta is None:
            return

        nome, endereco = resposta

        # O mesmo endereço não entra duas vezes: só é selecionado
        if endereco not in [existente for _, existente in cameras]:

            cameras.append((nome, endereco))

            preferencias.salvar_cameras_ip(cameras)

            log.info("Câmera IP adicionada: %s", nome)

        configuracoes.definir_cameras_ip(cameras, endereco)

        self.escolher(endereco)

        # Já liga a câmera nova, para o usuário ver na hora se conectou
        area = self._areas.atual

        if area.analisador is not None and area.camera.estado is EstadoCamera.PARADA:
            area.camera.iniciar()

    def remover_ip(self, endereco):
        """ "Remover câmera IP": tira a câmera do cadastro (as áreas que a usavam voltam para a webcam)."""

        configuracoes = self._janela.configuracoes

        nome = configuracoes.nome_camera(endereco)

        confirmou = dialogos.confirmar(
            configuracoes.pai_para_dialogos(self._janela.raiz),
            "Remover câmera IP",
            f"Remover {nome} da lista de câmeras?\n\n"
            "As áreas que usavam essa câmera voltam a usar a webcam.",
            texto_confirmar="Remover câmera",
            perigoso=True,
        )

        if not confirmou:
            return

        cameras = [
            (nome_camera, existente)
            for nome_camera, existente in preferencias.carregar_cameras_ip()
            if existente != endereco
        ]

        preferencias.salvar_cameras_ip(cameras)

        webcam = configuracoes.webcam_lembrada

        # Toda área que usava a câmera removida volta para a webcam
        for area in self._areas.lista:

            if area.dados.fonte == endereco:

                area.camera.trocar_fonte(webcam)
                area.dados.fonte = webcam
                area.esquecer_desenho()

                area.painel.definir_camera(configuracoes.nome_camera(webcam), area.dados.controla_catraca)

        self._areas.salvar()

        configuracoes.definir_cameras_ip(cameras, self._areas.atual.dados.fonte)

        log.info("Câmera IP removida: %s", nome)

        self._janela.avisar(f"{nome} removida.")
