"""
Ações sobre a auditoria (o painel da direita).

O PainelAuditoria só mostra e diz qual linha foi escolhida. Quem pede
confirmação, mexe nos arquivos e avisa o resultado é este controlador:

    receber          -> eventos novos das análises vão para a tabela
    alertar_negado   -> bipe de acesso negado (modo catraca)
    salvar_relatorio -> relatório HTML do momento de um evento
    exportar         -> planilha com o que está filtrado
    zerar            -> arquiva tudo e recomeça do zero (nada é apagado)
    excluir          -> tira uma linha do log (ela é guardada à parte)
"""

import logging
import webbrowser
from datetime import datetime
from tkinter import filedialog

from safetech import config
from safetech.interface import dialogos
from safetech.nucleo import horario, modos
from safetech.servicos import auditoria as modulo_auditoria
from safetech.servicos import relatorio


log = logging.getLogger(__name__)


class ControladorAuditoria:

    def __init__(self, janela, areas):
        """
        janela -> JanelaPrincipal (serviço de auditoria, painel, avisos)
        areas  -> ControladorAreas (as análises que geram os eventos)
        """

        self._janela = janela
        self._areas = areas

    # ============================================================
    # EVENTOS NOVOS
    # ============================================================

    def receber(self):
        """Passa para a tabela os eventos gravados pelas análises desde o último ciclo."""

        houve_negado_na_catraca = False

        for area in self._areas.lista:

            if area.analisador is None:
                continue

            fila = area.analisador.registros_novos

            while not fila.empty():

                registro = fila.get_nowait()

                self._janela.painel_auditoria.adicionar(registro)

                if registro.liberado == "NAO" and not modos.eh_vigilancia(registro.modo):
                    houve_negado_na_catraca = True

        # Um bipe só, mesmo que várias pessoas tenham sido negadas juntas
        if houve_negado_na_catraca:
            self.alertar_negado()

    def alertar_negado(self):
        """
        Bipe de "acesso negado" (config.ALERTA_SONORO_NEGADO).

        Usa o som de erro do Windows, que toca sem travar a tela; fora
        do Windows, o bipe simples do Tkinter.
        """

        if not config.ALERTA_SONORO_NEGADO:
            return

        try:
            import winsound

            winsound.MessageBeep(winsound.MB_ICONHAND)

        except (ImportError, RuntimeError):
            self._janela.raiz.bell()

    # ============================================================
    # RELATÓRIO DO MOMENTO
    # ============================================================

    def salvar_relatorio(self, registro):
        """
        Botão "Salvar relatório": grava um relatório completo do momento
        da linha selecionada e o abre no navegador.

        Além do evento escolhido, o relatório lista os outros eventos
        registrados no mesmo instante (mesmo segundo), de qualquer área,
        para mostrar o momento inteiro.
        """

        auditoria = self._janela.auditoria

        mesmo_momento = [
            outro
            for outro in auditoria.carregar_historico()
            if outro.timestamp == registro.timestamp and outro != registro
        ]

        try:
            pasta = relatorio.salvar(registro, auditoria.pasta_imagens, outros_do_momento=mesmo_momento)

        except OSError as erro:

            log.exception("Relatório não salvo")
            self._janela.avisar(f"Não foi possível salvar o relatório: {erro}", segundos=10)
            return

        self._janela.avisar(f"Relatório salvo em auditoria/relatorios/{pasta.name}.", segundos=8, tipo="sucesso")

        webbrowser.open((pasta / "relatorio.html").as_uri())

    # ============================================================
    # EXPORTAR (planilha)
    # ============================================================

    def exportar(self, registros):
        """
        Botão "Exportar CSV": grava numa planilha os eventos que estão
        filtrados na tela (área, período, resultado e busca).

        O log de auditoria não muda: a planilha é uma cópia legível,
        no formato que o Excel em português abre direto.
        """

        if not registros:
            self._janela.avisar("Nenhum evento para exportar com os filtros escolhidos.")
            return

        caminho = filedialog.asksaveasfilename(
            parent=self._janela.raiz,
            title="Exportar auditoria",
            defaultextension=".csv",
            initialfile=f"auditoria_safetech_{datetime.now().strftime('%Y-%m-%d_%H-%M')}.csv",
            filetypes=[("Planilha CSV", "*.csv"), ("Todos os arquivos", "*.*")],
        )

        if not caminho:
            return

        try:
            modulo_auditoria.exportar_csv(registros, caminho)

        except OSError as erro:

            # Ex.: um arquivo com esse nome está aberto no Excel
            self._janela.avisar(f"Não foi possível exportar: {erro}", segundos=10)
            return

        log.info("%d evento(s) exportados para %s", len(registros), caminho)

        quantidade = "1 evento exportado" if len(registros) == 1 else f"{len(registros)} eventos exportados"

        self._janela.avisar(f"{quantidade} para {caminho}.", segundos=8, tipo="sucesso")

    # ============================================================
    # ZERAR (arquiva, não apaga)
    # ============================================================

    def zerar(self):
        """
        Botão "Zerar": esvazia o log e as fotos de evidência e recomeça
        a contagem. Pede confirmação, porque é um registro de auditoria.
        """

        confirmou = dialogos.confirmar(
            self._janela.raiz,
            "Zerar a auditoria",
            "Zerar o log de auditoria e as fotos de evidência?\n\n"
            "A tela volta ao zero e as pessoas nas câmeras passam a contar "
            "como novas.\n\n"
            "Nada é apagado: os dados atuais vão para a pasta "
            "'auditoria/arquivados'.",
            texto_confirmar="Zerar auditoria",
            perigoso=True,
        )

        if not confirmou:
            return

        try:
            destino, eventos, fotos = self._janela.auditoria.zerar()

        except OSError as erro:

            # Ex.: o CSV ou uma foto está aberto em outro programa
            self._janela.avisar(f"Não foi possível zerar: {erro}", segundos=10)
            return

        self._janela.painel_auditoria.esvaziar()

        for area in self._areas.lista:

            if area.analisador is None:
                continue

            # Eventos que a análise gravou e a tela ainda não mostrou
            # pertencem ao log antigo: não devem reaparecer na tabela.
            fila = area.analisador.registros_novos

            while not fila.empty():
                fila.get_nowait()

            # Quem está na câmera volta a gerar um evento de entrada
            area.analisador.reiniciar_pessoas()

        if destino is None:
            self._janela.avisar("A auditoria já estava vazia.")
            return

        log.info("Auditoria zerada: %d evento(s) e %d foto(s) arquivados em %s", eventos, fotos, destino)

        self._janela.avisar(
            f"Auditoria zerada: {eventos} evento(s) e {fotos} foto(s) "
            f"arquivados em auditoria/arquivados/{destino.name}.",
            segundos=8,
            tipo="sucesso",
        )

    # ============================================================
    # EXCLUIR UMA LINHA (guardada à parte, não apagada)
    # ============================================================

    def excluir(self, registro):
        """
        Botão "Excluir": tira um evento da tabela e do log.

        Pede confirmação. Nada é apagado: a linha e a foto vão para
        'auditoria/excluidos' (o serviço de auditoria cuida disso).
        """

        resultado = modos.resultado(registro.modo, registro.liberado == "SIM").lower()

        confirmou = dialogos.confirmar(
            self._janela.raiz,
            "Excluir evento",
            f"Excluir o evento de {registro.pessoa} ({resultado}, área {registro.area}) "
            f"de {horario.para_exibir(registro.timestamp)}?\n\n"
            "Ele sai da tabela, do log e do painel web.\n\n"
            "Nada é apagado: a linha e a foto vão para a pasta "
            "'auditoria/excluidos'.",
            texto_confirmar="Excluir evento",
            perigoso=True,
        )

        if not confirmou:
            return

        try:
            excluido = self._janela.auditoria.excluir(registro)

        except OSError as erro:

            # Ex.: o CSV está aberto no Excel
            self._janela.avisar(f"Não foi possível excluir: {erro}", segundos=10)
            return

        # Some da tela de qualquer jeito: se não estava mais no log
        # (ex.: a auditoria foi zerada), também não deve aparecer.
        self._janela.painel_auditoria.remover(registro)

        if excluido:

            log.info("Evento excluído (guardado em auditoria/excluidos): %s %s %s", registro.timestamp, registro.pessoa, registro.area)

            self._janela.avisar(f"Evento de {registro.pessoa} excluído e guardado em auditoria/excluidos.", tipo="sucesso")

        else:
            self._janela.avisar("Esse evento não estava mais no log.")
