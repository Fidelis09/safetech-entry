"""
Indicadores e relatórios em PDF.

    abrir           -> janela de Indicadores (botão na auditoria)
    salvar_pdf      -> relatório do período e da área escolhidos na janela
    atualizar       -> chamado a cada ciclo: redesenha a janela aberta de
                       tempos em tempos e, na virada do dia, gera o
                       relatório DIÁRIO do dia anterior (se ligado em
                       config.RELATORIO_DIARIO_AUTOMATICO)

O relatório diário é gerado numa thread à parte (leva um segundo ou
dois) e não mexe na tela: só grava o arquivo e registra no log.
"""

import logging
import threading
import time
import webbrowser
from datetime import date, timedelta
from tkinter import filedialog

from safetech import config
from safetech.interface.janela_indicadores import JanelaIndicadores
from safetech.servicos import relatorio_pdf


log = logging.getLogger(__name__)


class ControladorIndicadores:

    def __init__(self, janela, areas):
        """
        janela -> JanelaPrincipal (raiz, auditoria e avisos)
        areas  -> ControladorAreas (nomes das áreas para o filtro)
        """

        self._janela = janela
        self._areas = areas

        # Criada no primeiro "Indicadores" (não pesa na abertura do programa)
        self.janela_indicadores = None

        self._proxima_atualizacao = 0.0

        # Último dia em que o relatório diário foi conferido
        self._dia_conferido = None

    # ============================================================
    # JANELA DE INDICADORES
    # ============================================================

    def abrir(self):

        if self.janela_indicadores is None:

            self.janela_indicadores = JanelaIndicadores(
                self._janela.raiz,
                ler_registros=self._janela.auditoria.carregar_historico,
                nomes_das_areas=lambda: [area.nome for area in self._areas.lista],
                ao_salvar_pdf=self.salvar_pdf,
                escala=self._janela.escala,
            )

        self.janela_indicadores.mostrar()

    def salvar_pdf(self, inicio, fim, area):
        """Botão "Salvar PDF" da janela de Indicadores."""

        sugestao = f"relatorio_epi_{inicio or 'inicio'}_a_{fim or date.today().isoformat()}.pdf"

        caminho = filedialog.asksaveasfilename(
            parent=self.janela_indicadores or self._janela.raiz,
            title="Salvar relatório de indicadores",
            defaultextension=".pdf",
            initialfile=sugestao,
            filetypes=[("PDF", "*.pdf"), ("Todos os arquivos", "*.*")],
        )

        if not caminho:
            return

        from pathlib import Path

        try:
            relatorio_pdf.gerar(self._janela.auditoria.carregar_historico(), Path(caminho), inicio, fim, area)

        except OSError as erro:

            # Ex.: um PDF com esse nome está aberto no leitor
            log.exception("PDF não salvo")
            self._janela.avisar(f"Não foi possível salvar o PDF: {erro}", segundos=10)
            return

        self._janela.avisar(f"Relatório salvo em {caminho}.", segundos=8, tipo="sucesso")

        webbrowser.open(Path(caminho).resolve().as_uri())

    def ao_trocar_tema(self):
        """Os gráficos são imagens: precisam ser desenhados de novo nas cores do tema."""

        if self.janela_indicadores is not None:
            self.janela_indicadores.redesenhar()

    # ============================================================
    # A CADA CICLO
    # ============================================================

    def atualizar(self, agora=None):
        """Redesenha a janela aberta e confere o relatório diário (de tempos em tempos)."""

        agora = time.perf_counter() if agora is None else agora

        if agora < self._proxima_atualizacao:
            return

        self._proxima_atualizacao = agora + config.INTERVALO_ATUALIZAR_INDICADORES_SEG

        janela = self.janela_indicadores

        if janela is not None and janela.winfo_viewable():
            janela.redesenhar()

        self.conferir_relatorio_diario()

    def conferir_relatorio_diario(self, hoje=None):
        """
        Uma vez por dia (ao abrir o programa e na virada do dia): gera o
        relatório do dia ANTERIOR, se houve eventos e se ele ainda não existe.

        Devolve a thread que gera o relatório (ou None se não havia o que gerar).
        """

        if not config.RELATORIO_DIARIO_AUTOMATICO:
            return None

        hoje = hoje or date.today()

        if self._dia_conferido == hoje:
            return None

        self._dia_conferido = hoje

        ontem = (hoje - timedelta(days=1)).isoformat()

        if (config.PASTA_RELATORIOS_DIARIOS / f"{ontem}.pdf").exists():
            return None

        auditoria = self._janela.auditoria

        def gerar():

            try:
                caminho = relatorio_pdf.gerar_diario(auditoria.carregar_historico(), dia=ontem)

                if caminho:
                    log.info("Relatório diário de %s gerado em %s", ontem, caminho)

            except Exception:
                log.exception("Relatório diário de %s não foi gerado", ontem)

        thread = threading.Thread(target=gerar, name="relatorio-diario", daemon=True)
        thread.start()

        return thread
