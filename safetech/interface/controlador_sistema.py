"""
Configurações > Sistema: assistente, backup e restauração, pasta de logs.

    abrir_assistente   -> passo a passo de configuração (abre sozinho na
                          primeira execução: conferir_primeira_execucao)
    salvar_backup      -> as configurações num arquivo só
    restaurar_backup   -> troca as configurações pelas de um backup (as de
                          antes são guardadas); valem ao reabrir o programa
    abrir_logs         -> abre a pasta logs/ no Explorador de Arquivos
"""

import logging
import os
from pathlib import Path
from tkinter import filedialog

from safetech import config
from safetech.interface import dialogos
from safetech.interface.assistente import Assistente
from safetech.nucleo import horario
from safetech.servicos import acesso_web, backup, preferencias


log = logging.getLogger(__name__)


class ControladorSistema:

    def __init__(self, janela, areas, cameras, painel_web, modos_disponiveis):

        self._janela = janela
        self._areas = areas
        self._cameras = cameras
        self._painel_web = painel_web
        self._modos_disponiveis = modos_disponiveis

        # O assistente aberto (None = fechado)
        self.assistente = None

    # ============================================================
    # ASSISTENTE
    # ============================================================

    def conferir_primeira_execucao(self):
        """Na primeira vez que o programa abre, o assistente aparece sozinho."""

        if config.ASSISTENTE_NA_PRIMEIRA_EXECUCAO and not preferencias.assistente_concluido():
            self.abrir_assistente()

    def abrir_assistente(self, mostrar=True):
        """Abre o assistente para a PRIMEIRA área (a principal)."""

        if self.assistente is not None and self.assistente.winfo_exists():
            self.assistente.lift()
            return self.assistente

        area = self._areas.lista[0]

        # O assistente configura a área principal: ela fica à vista
        self._areas.selecionar(area)

        configuracoes = self._janela.configuracoes

        self.assistente = Assistente(
            self._janela.raiz,
            opcoes_camera=configuracoes.opcoes_de_camera(),
            fonte_atual=area.dados.fonte,
            nome_area=area.nome,
            nomes_ocupados=[outra.nome for outra in self._areas.lista if outra is not area],
            setor=area.dados.setor,
            modo=area.dados.modo,
            modos_disponiveis=self._modos_disponiveis,
            painel_ativo=self._painel_web.ajustes.ativo,
            usa_senha_padrao=acesso_web.usa_senha_padrao(self._painel_web.ajustes),
            ao_testar_camera=lambda fonte: self._testar_camera(area, fonte),
            ler_previa=lambda: area.camera.ler()[0],
            ao_concluir=lambda respostas: self.aplicar_assistente(area, respostas),
            escala=self._janela.escala,
            mostrar=mostrar,
        )

        return self.assistente

    def _testar_camera(self, area, fonte):
        """Botão "Testar" do assistente: passa a usar a câmera e a liga."""

        if fonte != area.dados.fonte:
            self._cameras.escolher(fonte)

        area.camera.iniciar()

    def aplicar_assistente(self, area, respostas):
        """
        "Concluir" do assistente: aplica as respostas. Devolve (deu_certo, mensagem).

        O painel web vai primeiro: se a senha não servir, nada muda e o
        assistente mostra o motivo.
        """

        ajustes = self._painel_web.ajustes

        deu_certo, mensagem = self._painel_web.aplicar(
            ativo=respostas["painel_ativo"],
            na_rede=ajustes.na_rede,
            porta=ajustes.porta,
            exigir_login=True,
            usuario=ajustes.usuario or config.PAINEL_WEB_USUARIO,
            nova_senha=respostas["senha"],
            confirmacao=respostas["confirmacao"],
        )

        if not deu_certo:
            return False, mensagem

        if respostas["camera"] is not None and respostas["camera"] != area.dados.fonte:
            self._cameras.escolher(respostas["camera"])

        if respostas["nome_area"] != area.nome:
            self._areas.definir_nome(area, respostas["nome_area"])

        self._areas.escolher_setor(area, respostas["setor"])

        if respostas["modo"] != area.dados.modo:
            area.painel.definir_modo(respostas["modo"])
            self._areas.mudar_modo(area, respostas["modo"])

        preferencias.marcar_assistente_concluido()

        log.info("Assistente de configuração concluído")

        self._janela.avisar("Configuração concluída. Ligue a câmera (Espaço) para começar.", segundos=8, tipo="sucesso")

        return True, ""

    # ============================================================
    # BACKUP E RESTAURAÇÃO
    # ============================================================

    def salvar_backup(self):

        configuracoes = self._janela.configuracoes

        caminho = filedialog.asksaveasfilename(
            parent=configuracoes.pai_para_dialogos(self._janela.raiz),
            title="Salvar backup das configurações",
            defaultextension=".json",
            initialfile=f"safetech_backup_{horario.agora().strftime('%Y-%m-%d_%H-%M')}.json",
            filetypes=[("Backup do SafeTech", "*.json"), ("Todos os arquivos", "*.*")],
        )

        if not caminho:
            return

        try:
            backup.salvar(Path(caminho))

        except OSError as erro:
            self._janela.avisar(f"Não foi possível salvar o backup: {erro}", segundos=10)
            return

        self._janela.avisar(f"Backup das configurações salvo em {caminho}.", segundos=8, tipo="sucesso")

    def restaurar_backup(self):

        configuracoes = self._janela.configuracoes
        pai = configuracoes.pai_para_dialogos(self._janela.raiz)

        caminho = filedialog.askopenfilename(
            parent=pai,
            title="Restaurar backup das configurações",
            filetypes=[("Backup do SafeTech", "*.json"), ("Todos os arquivos", "*.*")],
        )

        if not caminho:
            return

        # Confere antes de perguntar: um arquivo errado nem chega à pergunta
        try:
            conteudo = backup.ler(Path(caminho))

        except backup.BackupInvalido as erro:
            self._janela.avisar(str(erro), segundos=10)
            return

        criado = horario.para_relatorio(conteudo.get("criado_em", "")) or "data desconhecida"

        confirmou = dialogos.confirmar(
            pai,
            "Restaurar backup",
            f"Trocar as configurações atuais pelas do backup de {criado}?\n\n"
            "As atuais não são perdidas: ficam guardadas numa cópia ao lado do "
            "preferencias.json. A auditoria e o dataset não mudam.\n\n"
            "O programa fecha em seguida; as configurações restauradas valem ao reabri-lo.",
            texto_confirmar="Restaurar e fechar",
            perigoso=True,
        )

        if not confirmou:
            return

        try:
            backup.restaurar(Path(caminho))

        except (backup.BackupInvalido, OSError) as erro:
            self._janela.avisar(f"Não foi possível restaurar: {erro}", segundos=10)
            return

        # Daqui em diante nada é gravado: o que está na memória (as
        # configurações de antes) não pode sobrescrever o que foi restaurado
        self._areas.nao_salvar_mais = True

        dialogos.informar(
            pai,
            "Backup restaurado",
            "Configurações restauradas. O programa vai fechar agora: abra-o de novo "
            "para usar as configurações do backup.",
        )

        self._janela.fechar()

    # ============================================================
    # LOGS
    # ============================================================

    def abrir_logs(self):

        config.PASTA_LOGS.mkdir(parents=True, exist_ok=True)

        os.startfile(config.PASTA_LOGS)
