"""
Tema visual do SafeTech Entry.

Centraliza cores, fontes e estilos dos componentes. Para mudar a
aparência do programa inteiro, basta alterar este arquivo.
"""

import tkinter as tk
from tkinter import ttk


# ============================================================
# PALETA
# ============================================================

CORES = {
    # Superfícies, da mais funda para a mais elevada
    "fundo": "#0f1318",
    "painel": "#171c23",
    "cartao": "#1f262f",
    "cartao_hover": "#28313c",
    "borda": "#2c3642",

    # Texto
    "texto": "#e8edf2",
    "texto_suave": "#8d9aab",

    # Cores de ação e de status
    "destaque": "#3b82f6",
    "destaque_hover": "#2563eb",
    "sucesso": "#16a34a",
    "sucesso_texto": "#86efac",
    "sucesso_fundo": "#12301f",
    "perigo": "#dc2626",
    "perigo_hover": "#b91c1c",
    "perigo_texto": "#fca5a5",
    "perigo_fundo": "#3a1717",
    "alerta": "#d97706",
    "neutro": "#334155",
}

FAMILIA = "Segoe UI"

FONTES = {
    "marca": (FAMILIA, 15, "bold"),
    "titulo": (FAMILIA, 13, "bold"),
    "texto": (FAMILIA, 10),
    "texto_negrito": (FAMILIA, 10, "bold"),
    "pequena": (FAMILIA, 9),
    "status_titulo": (FAMILIA, 17, "bold"),
    "status_detalhe": (FAMILIA, 10),
    "indicador_valor": (FAMILIA, 20, "bold"),
}


# ============================================================
# APLICAÇÃO DO TEMA
# ============================================================

def aplicar_tema(janela, escala=1.0):
    """
    Configura os estilos de todos os componentes ttk.

    escala -> fator de DPI do monitor (1.0 = 100%), usado nas medidas
              que o Tkinter não ajusta sozinho.
    """

    janela.configure(bg=CORES["fundo"])

    estilo = ttk.Style(janela)

    # O tema "clam" é o que mais respeita cores personalizadas
    try:
        estilo.theme_use("clam")
    except tk.TclError:
        pass

    estilo.configure(
        ".",
        background=CORES["fundo"],
        foreground=CORES["texto"],
        font=FONTES["texto"],
        borderwidth=0,
        focuscolor=CORES["painel"],
    )

    # ------------------------------------------------------
    # SUPERFÍCIES
    # ------------------------------------------------------

    estilo.configure("TFrame", background=CORES["fundo"])
    estilo.configure("Painel.TFrame", background=CORES["painel"])
    estilo.configure("Cartao.TFrame", background=CORES["cartao"])

    # ------------------------------------------------------
    # TEXTOS (um estilo por superfície, para o fundo combinar)
    # ------------------------------------------------------

    estilo.configure("TLabel", background=CORES["fundo"], foreground=CORES["texto"])

    estilo.configure("Marca.TLabel", font=FONTES["marca"])
    estilo.configure("Suave.TLabel", foreground=CORES["texto_suave"], font=FONTES["pequena"])

    estilo.configure("Painel.TLabel", background=CORES["painel"])
    estilo.configure("Titulo.Painel.TLabel", font=FONTES["titulo"])
    estilo.configure("Suave.Painel.TLabel", foreground=CORES["texto_suave"], font=FONTES["pequena"])

    estilo.configure("Cartao.TLabel", background=CORES["cartao"])
    estilo.configure("Suave.Cartao.TLabel", foreground=CORES["texto_suave"], font=FONTES["pequena"])
    estilo.configure("Valor.Cartao.TLabel", font=FONTES["indicador_valor"])

    # ------------------------------------------------------
    # BOTÕES
    # ------------------------------------------------------

    estilo.configure(
        "TButton",
        background=CORES["cartao"],
        foreground=CORES["texto"],
        font=FONTES["texto_negrito"],
        padding=(14, 9),
        relief="flat",
    )

    estilo.map(
        "TButton",
        background=[("disabled", CORES["cartao"]), ("active", CORES["cartao_hover"])],
        foreground=[("disabled", CORES["texto_suave"])],
    )

    estilo.configure("Primario.TButton", background=CORES["destaque"], foreground="white")

    estilo.map(
        "Primario.TButton",
        background=[("disabled", CORES["neutro"]), ("active", CORES["destaque_hover"])],
        foreground=[("disabled", CORES["texto_suave"])],
    )

    estilo.configure("Perigo.TButton", background=CORES["perigo"], foreground="white")

    estilo.map(
        "Perigo.TButton",
        background=[("disabled", CORES["neutro"]), ("active", CORES["perigo_hover"])],
    )

    # Botões do filtro (Todos / Liberados / Negados): parecem abas
    estilo.configure(
        "Filtro.Toolbutton",
        background=CORES["cartao"],
        foreground=CORES["texto_suave"],
        font=FONTES["texto_negrito"],
        padding=(12, 6),
        relief="flat",
    )

    estilo.map(
        "Filtro.Toolbutton",
        background=[("selected", CORES["destaque"]), ("active", CORES["cartao_hover"])],
        foreground=[("selected", "white")],
    )

    # ------------------------------------------------------
    # CONTROLES
    # ------------------------------------------------------

    # No controle deslizante, "background" é a cor do botão que se arrasta
    estilo.configure(
        "Horizontal.TScale",
        background=CORES["destaque"],
        troughcolor=CORES["borda"],
        bordercolor=CORES["cartao"],
        lightcolor=CORES["borda"],
        darkcolor=CORES["borda"],
        gripcount=0,
        sliderlength=int(18 * escala),
    )

    estilo.map("Horizontal.TScale", background=[("active", CORES["destaque_hover"])])

    estilo.configure(
        "TEntry",
        fieldbackground=CORES["cartao"],
        foreground=CORES["texto"],
        insertcolor=CORES["texto"],
        bordercolor=CORES["borda"],
        lightcolor=CORES["borda"],
        darkcolor=CORES["borda"],
        borderwidth=1,
        padding=6,
    )

    # Caixas de seleção (EPIs exigidos e rótulos da coleta)
    estilo.configure(
        "Cartao.TCheckbutton",
        background=CORES["cartao"],
        foreground=CORES["texto"],
        indicatorbackground=CORES["fundo"],
        indicatorforeground="white",
        upperbordercolor=CORES["texto_suave"],
        lowerbordercolor=CORES["texto_suave"],
        indicatorsize=int(15 * escala),
        padding=(2, 2),
    )

    estilo.map(
        "Cartao.TCheckbutton",
        background=[("active", CORES["cartao"])],
        foreground=[("disabled", CORES["borda"])],
        indicatorbackground=[
            ("disabled", CORES["cartao"]),
            ("selected", CORES["destaque"]),
        ],
        upperbordercolor=[("disabled", CORES["borda"]), ("selected", CORES["destaque"])],
        lowerbordercolor=[("disabled", CORES["borda"]), ("selected", CORES["destaque"])],
    )

    # Lista de escolha do setor
    estilo.configure(
        "TCombobox",
        fieldbackground=CORES["fundo"],
        background=CORES["borda"],
        foreground=CORES["texto"],
        arrowcolor=CORES["texto"],
        bordercolor=CORES["borda"],
        lightcolor=CORES["borda"],
        darkcolor=CORES["borda"],
        selectbackground=CORES["fundo"],
        selectforeground=CORES["texto"],
        padding=5,
    )

    estilo.map(
        "TCombobox",
        fieldbackground=[("disabled", CORES["cartao"]), ("readonly", CORES["fundo"])],
        foreground=[("disabled", CORES["borda"])],
        arrowcolor=[("disabled", CORES["borda"])],
        selectbackground=[("readonly", CORES["fundo"])],
    )

    # A lista que se abre ao clicar não é um componente ttk; suas
    # cores são definidas pelo banco de opções do Tkinter.
    janela.option_add("*TCombobox*Listbox.background", CORES["cartao"])
    janela.option_add("*TCombobox*Listbox.foreground", CORES["texto"])
    janela.option_add("*TCombobox*Listbox.selectBackground", CORES["destaque"])
    janela.option_add("*TCombobox*Listbox.selectForeground", "white")
    janela.option_add("*TCombobox*Listbox.font", FONTES["texto"])

    # ------------------------------------------------------
    # TABELA
    # ------------------------------------------------------

    estilo.configure(
        "Treeview",
        background=CORES["cartao"],
        fieldbackground=CORES["cartao"],
        foreground=CORES["texto"],
        rowheight=int(28 * escala),
        font=FONTES["texto"],
    )

    estilo.map(
        "Treeview",
        background=[("selected", CORES["destaque"])],
        foreground=[("selected", "white")],
    )

    estilo.configure(
        "Treeview.Heading",
        background=CORES["painel"],
        foreground=CORES["texto_suave"],
        font=FONTES["texto_negrito"],
        padding=(6, 8),
        relief="flat",
    )

    estilo.map("Treeview.Heading", background=[("active", CORES["cartao"])])

    # Remove a moldura clara que o tema desenha em volta da tabela
    estilo.layout("Treeview", [("Treeview.treearea", {"sticky": "nswe"})])

    estilo.configure(
        "Vertical.TScrollbar",
        background=CORES["borda"],
        troughcolor=CORES["cartao"],
        bordercolor=CORES["cartao"],
        lightcolor=CORES["borda"],
        darkcolor=CORES["borda"],
        arrowcolor=CORES["texto_suave"],
        gripcount=0,
        arrowsize=int(13 * escala),
        relief="flat",
    )

    estilo.map(
        "Vertical.TScrollbar",
        background=[("active", CORES["neutro"])],
        lightcolor=[("active", CORES["neutro"])],
        darkcolor=[("active", CORES["neutro"])],
    )

    # ------------------------------------------------------
    # DIVISOR ARRASTÁVEL ENTRE OS PAINÉIS
    # ------------------------------------------------------

    estilo.configure("TPanedwindow", background=CORES["fundo"])
    estilo.configure("Sash", sashthickness=int(8 * escala), gripcount=0)

    return estilo
