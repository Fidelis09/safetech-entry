"""
Coleta de imagens para treinar o modelo (Configurações > Coleta).

Três jeitos de pôr imagens no dataset, todos com os rótulos marcados
("a pessoa está usando: capacete, luvas..."):

    salvar_imagem   -> o frame da câmera da área à vista (botão ou tecla S)
    enviar_arquivos -> imagens que já estão no computador
    colar_imagem    -> uma imagem copiada (Ctrl+V)

Em todos, o que vai para o dataset é o RECORTE de cada pessoa, igual ao
que o modelo recebe na hora de analisar.
"""

import logging
from tkinter import filedialog

from safetech import config
from safetech.nucleo import detector, epis
from safetech.servicos import importacao
from safetech.servicos.dataset import ColetorDataset


log = logging.getLogger(__name__)


class ControladorColeta:

    def __init__(self, janela, areas):
        """
        janela -> JanelaPrincipal (Configurações e avisos)
        areas  -> ControladorAreas (a área à vista: câmera, pessoas e modo)
        """

        self._janela = janela
        self._areas = areas

        self.coletor = ColetorDataset()

        # Detectores usados só para importar imagens, um por modo (cada
        # um é criado no primeiro uso). O detector das análises roda em
        # outra thread e não pode ser usado por duas ao mesmo tempo.
        self._detectores_importacao = {}

    def salvar_imagem(self, usando):
        """
        Salva no dataset o recorte de cada pessoa do frame atual da área
        à vista, com os rótulos marcados (quais EPIs a pessoa está usando).
        """

        area = self._areas.atual

        frame, _ = area.camera.ler()

        if frame is None or area.analisador is None:
            self._janela.avisar(f"Ligue a câmera da área \"{area.nome}\" antes de salvar imagens.")
            return

        caixas = [pessoa.caixa for pessoa in area.analisador.estado().pessoas]

        arquivos = self.coletor.salvar(frame, caixas, usando)

        self.atualizar_resumo()

        descricao = "1 imagem salva" if len(arquivos) == 1 else f"{len(arquivos)} imagens salvas"

        if not caixas:
            descricao += " (ninguém detectado: frame inteiro)"

        # Repete os rótulos no aviso: é a chance de perceber um engano
        rotulos = epis.nomes_dos_epis(chave for chave in config.EPIS if chave in usando)

        self._janela.avisar(f"{descricao}, rotulada como usando: {rotulos or 'nenhum EPI'}.")

    def enviar_arquivos(self, usando):
        """Botão "Enviar arquivo": escolhe uma ou mais imagens do computador."""

        configuracoes = self._janela.configuracoes

        caminhos = filedialog.askopenfilenames(
            parent=configuracoes.pai_para_dialogos(self._janela.raiz),
            title="Escolha as imagens para o dataset",
            filetypes=[
                ("Imagens", importacao.EXTENSOES),
                ("Todos os arquivos", "*.*"),
            ],
        )

        if not caminhos:
            return

        imagens = [importacao.abrir_arquivo(caminho) for caminho in caminhos]

        lidas = [imagem for imagem in imagens if imagem is not None]

        self.importar(lidas, len(imagens) - len(lidas), usando)

    def colar_imagem(self):
        """Ctrl+V: importa a imagem (ou os arquivos de imagem) copiados."""

        imagens, falhas = importacao.ler_area_de_transferencia()

        if not imagens and not falhas:
            self._janela.avisar("Nada para colar: copie uma imagem (ou um arquivo de imagem) primeiro.")
            return

        self.importar(imagens, falhas, self._janela.configuracoes.rotulos_marcados())

    def importar(self, imagens, falhas, usando):
        """
        Grava no dataset imagens vindas de fora da câmera.

        Elas recebem o mesmo tratamento da captura: o detector acha as
        pessoas e o que é salvo é o recorte de cada uma (ou a imagem
        inteira, se ninguém for encontrado), com os rótulos marcados.
        """

        # Usa o MESMO modo da área à vista (rosto ou corpo): assim as
        # imagens importadas ficam com o mesmo enquadramento das
        # capturadas pela câmera naquele modo.
        modo = self._areas.atual.parametros.modo_deteccao

        if modo not in self._detectores_importacao:
            self._detectores_importacao[modo] = detector.criar_detector(modo)

        detector_importacao = self._detectores_importacao[modo]

        recortes = 0

        for imagem in imagens:

            caixas = detector_importacao.detectar(imagem)

            recortes += len(self.coletor.salvar(imagem, caixas, usando))

        self.atualizar_resumo()

        partes = []

        if imagens:

            rotulos = epis.nomes_dos_epis(chave for chave in config.EPIS if chave in usando)

            quantidade = "1 imagem importada" if len(imagens) == 1 else f"{len(imagens)} imagens importadas"

            partes.append(
                f"{quantidade} ({recortes} recorte(s) de pessoa), "
                f"rotulada(s) como usando: {rotulos or 'nenhum EPI'}."
            )

            log.info("%d imagem(ns) importada(s) para o dataset (%d recortes)", len(imagens), recortes)

        if falhas:
            partes.append(f"{falhas} arquivo(s) não são imagens legíveis e foram ignorados.")

        self._janela.avisar(" ".join(partes), segundos=7)

    def atualizar_resumo(self):
        """Quantas imagens rotuladas existem (mostrado em Configurações > Coleta)."""

        self._janela.configuracoes.definir_resumo_dataset(*self.coletor.resumo())
