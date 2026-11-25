"""
Caixas de diálogo com o visual do programa (no lugar das do Windows).

As caixas do Windows (tkinter.messagebox) saem brancas mesmo no tema
escuro e não deixam o botão perigoso em vermelho. Estas seguem o tema:

    confirmar      -> pergunta Sim/Não. Com perigoso=True, o ícone é de
                      atenção, o botão de confirmar é vermelho e o
                      destacado (o do Enter) é o "Cancelar"
    informar       -> só um aviso com "OK"
    pedir_intervalo-> duas datas (de / até) para um período personalizado

Todas são MODAIS: a janela de trás espera a resposta (como as do Windows).
"""

import tkinter as tk
from tkinter import ttk

from safetech.interface.tema import CORES, FONTES
from safetech.nucleo import horario


# Largura do texto da mensagem, em pixels a 100% de escala
LARGURA_TEXTO = 420

ICONE_PERIGO = "⚠"      # ⚠
ICONE_INFORMACAO = "ℹ"  # ℹ


class _Dialogo(tk.Toplevel):
    """Base das caixas: ícone, título, mensagem e uma fileira de botões."""

    def __init__(self, pai, titulo, mensagem, icone, cor_icone):

        super().__init__(pai)

        self.withdraw()

        self.title(titulo)
        self.configure(bg=CORES["painel"])
        self.resizable(False, False)

        if pai is not None and pai.winfo_viewable():
            self.transient(pai)

        self.resposta = None

        corpo = ttk.Frame(self, style="Painel.TFrame", padding=(22, 20, 22, 16))
        corpo.pack(fill="both", expand=True)

        corpo.columnconfigure(1, weight=1)

        tk.Label(corpo, text=icone, bg=CORES["painel"], fg=cor_icone, font=FONTES["status_icone"]).grid(
            row=0, column=0, rowspan=2, sticky="n", padx=(0, 16)
        )

        ttk.Label(corpo, text=titulo, style="Titulo.Painel.TLabel").grid(row=0, column=1, sticky="w")

        ttk.Label(corpo, text=mensagem, style="Painel.TLabel", wraplength=LARGURA_TEXTO, justify="left").grid(
            row=1, column=1, sticky="w", pady=(6, 0)
        )

        # Espaço para campos extras (ex.: as datas do período personalizado)
        self.campos = ttk.Frame(corpo, style="Painel.TFrame")
        self.campos.grid(row=2, column=1, sticky="w")

        self.botoes = ttk.Frame(corpo, style="Painel.TFrame")
        self.botoes.grid(row=3, column=0, columnspan=2, sticky="e", pady=(18, 0))

        self.protocol("WM_DELETE_WINDOW", self._cancelar)
        self.bind("<Escape>", lambda _evento: self._cancelar())

    def _responder(self, resposta):

        self.resposta = resposta
        self.destroy()

    def _cancelar(self):

        self._responder(None)

    def esperar(self, foco):
        """Mostra centralizado sobre a janela de trás e espera a resposta."""

        self.update_idletasks()

        pai = self.master

        if pai is not None and pai.winfo_viewable():
            x = pai.winfo_rootx() + (pai.winfo_width() - self.winfo_reqwidth()) // 2
            y = pai.winfo_rooty() + (pai.winfo_height() - self.winfo_reqheight()) // 3
            self.geometry(f"+{max(0, x)}+{max(0, y)}")

        self.deiconify()
        self.lift()

        foco.focus_set()

        # Modal: os cliques nas outras janelas esperam
        self.grab_set()
        self.wait_window()

        return self.resposta


def confirmar(pai, titulo, mensagem, texto_confirmar="Confirmar", perigoso=False) -> bool:
    """
    Pergunta e devolve True (confirmou) ou False (cancelou ou fechou).

    perigoso -> ação que mexe em registros (zerar, excluir, remover):
                botão vermelho, e o Enter cai no "Cancelar"
    """

    dialogo = _Dialogo(
        pai,
        titulo,
        mensagem,
        ICONE_PERIGO if perigoso else ICONE_INFORMACAO,
        CORES["perigo_texto"] if perigoso else CORES["destaque"],
    )

    botao_confirmar = ttk.Button(
        dialogo.botoes,
        text=texto_confirmar,
        style="Perigo.TButton" if perigoso else "Primario.TButton",
        command=lambda: dialogo._responder(True),
    )
    botao_confirmar.pack(side="right")

    botao_cancelar = ttk.Button(dialogo.botoes, text="Cancelar", style="Secundario.TButton", command=dialogo._cancelar)
    botao_cancelar.pack(side="right", padx=(0, 8))

    # Enter aperta o botão que está em foco
    dialogo.bind("<Return>", lambda _evento: dialogo.focus_get().invoke() if hasattr(dialogo.focus_get(), "invoke") else None)

    return bool(dialogo.esperar(botao_cancelar if perigoso else botao_confirmar))


def informar(pai, titulo, mensagem):
    """Mostra um aviso com o botão "OK" e espera ele ser fechado."""

    dialogo = _Dialogo(pai, titulo, mensagem, ICONE_INFORMACAO, CORES["destaque"])

    botao = ttk.Button(dialogo.botoes, text="OK", style="Primario.TButton", command=lambda: dialogo._responder(True))
    botao.pack(side="right")

    dialogo.bind("<Return>", lambda _evento: botao.invoke())

    dialogo.esperar(botao)


def pedir_intervalo(pai, inicio=None, fim=None):
    """
    Pede um período personalizado (de / até, em dd/mm/aaaa).

    Devolve (inicio, fim) em "AAAA-MM-DD", ou None se cancelou.
    """

    dialogo = _Dialogo(
        pai,
        "Período personalizado",
        "Mostrar os eventos entre estas datas (as duas entram). Escreva no formato dia/mês/ano.",
        ICONE_INFORMACAO,
        CORES["destaque"],
    )

    def br(dia):
        return f"{dia[8:10]}/{dia[5:7]}/{dia[0:4]}" if dia else ""

    valor_inicio = tk.StringVar(value=br(inicio))
    valor_fim = tk.StringVar(value=br(fim))

    ttk.Label(dialogo.campos, text="De", style="Suave.Painel.TLabel").grid(row=0, column=0, sticky="w", pady=(12, 0), padx=(0, 8))
    campo_inicio = ttk.Entry(dialogo.campos, textvariable=valor_inicio, width=12)
    campo_inicio.grid(row=0, column=1, sticky="w", pady=(12, 0))

    ttk.Label(dialogo.campos, text="até", style="Suave.Painel.TLabel").grid(row=0, column=2, sticky="w", pady=(12, 0), padx=8)
    ttk.Entry(dialogo.campos, textvariable=valor_fim, width=12).grid(row=0, column=3, sticky="w", pady=(12, 0))

    erro = ttk.Label(dialogo.campos, text="", style="Painel.TLabel", foreground=CORES["perigo_texto"])
    erro.grid(row=1, column=0, columnspan=4, sticky="w", pady=(6, 0))

    def aplicar():

        de = horario.ler_data_digitada(valor_inicio.get())
        ate = horario.ler_data_digitada(valor_fim.get())

        if de is None or ate is None:
            erro.config(text="Use datas no formato dia/mês/ano, ex.: 25/11/2026.")
            return

        if de > ate:
            erro.config(text="A primeira data precisa ser antes da segunda.")
            return

        dialogo._responder((de, ate))

    botao = ttk.Button(dialogo.botoes, text="Aplicar", style="Primario.TButton", command=aplicar)
    botao.pack(side="right")

    ttk.Button(dialogo.botoes, text="Cancelar", style="Secundario.TButton", command=dialogo._cancelar).pack(side="right", padx=(0, 8))

    dialogo.bind("<Return>", lambda _evento: aplicar())

    return dialogo.esperar(campo_inicio)
