"""
Tema visual do SafeTech Entry.

Centraliza cores, fontes e estilos dos componentes. Para mudar a
aparência do programa inteiro, basta alterar este arquivo.
"""

import tkinter as tk
from tkinter import ttk

from PIL import Image, ImageDraw


# ============================================================
# PALETAS: TEMA ESCURO E TEMA CLARO
# ============================================================
#
# As duas paletas têm as MESMAS chaves. O resto do programa só usa as
# chaves (CORES["cartao"], CORES["texto"]...), nunca a cor escrita: é
# isso que permite trocar o tema com o programa aberto.
#
# Regra para quem mexer aqui: duas chaves com a mesma cor numa paleta
# precisam ter a mesma cor na outra também (o teste test_temas.py
# confere). A troca descobre de qual chave veio cada cor pela própria
# cor; se duas chaves tivessem a mesma cor só num dos temas, a troca
# não saberia qual das duas usar.
#
# As cores de status (sucesso, perigo, alerta) são as mesmas nos dois
# temas: verde é liberado e vermelho é negado em qualquer um deles.
# ============================================================

PALETAS = {
    "escuro": {
        # Superfícies, da mais funda para a mais elevada
        "fundo": "#0f1318",
        "painel": "#171c23",
        "cartao": "#1f262f",
        "cartao_hover": "#28313c",
        "borda": "#2c3642",

        # Botão secundário com o mouse em cima; botão desativado
        "realce": "#3a4655",
        "desativado": "#2a3340",

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
        "alerta_texto": "#fcd34d",
        "neutro": "#475569",

        # Fundo atrás do vídeo (faixas quando a proporção não bate), o
        # fundo escuro das legendas sobre ele e o texto delas. As
        # legendas ficam escuras nos dois temas: estão sobre a imagem.
        "video": "#07090c",
        "legenda_video": "#0b0f14",
        "texto_legenda": "#f1f5f9",

        # Linhas alternadas da tabela (listras), para o olho seguir a linha
        "linha_par": "#1f262f",
        "linha_impar": "#232b35",
    },

    "claro": {
        "fundo": "#eef1f5",
        "painel": "#f8f9fb",
        "cartao": "#ffffff",
        "cartao_hover": "#eef2f7",
        "borda": "#d5dbe3",

        "realce": "#c3ccd8",
        "desativado": "#e3e7ed",

        "texto": "#111827",
        "texto_suave": "#5b6676",

        "destaque": "#2563eb",
        "destaque_hover": "#1d4ed8",
        "sucesso": "#16a34a",
        "sucesso_texto": "#15803d",
        "sucesso_fundo": "#dcfce7",
        "perigo": "#dc2626",
        "perigo_hover": "#b91c1c",
        "perigo_texto": "#c0262d",
        "perigo_fundo": "#fde8e8",
        "alerta": "#d97706",
        "alerta_texto": "#b45309",
        "neutro": "#64748b",

        "video": "#dfe4ea",
        "legenda_video": "#0b0f14",
        "texto_legenda": "#f1f5f9",

        "linha_par": "#ffffff",
        "linha_impar": "#f4f6f9",
    },
}

# Nome mostrado de cada tema
NOMES_DOS_TEMAS = {"escuro": "Escuro", "claro": "Claro"}

TEMA_PADRAO = "escuro"

# As cores EM USO. É sempre o MESMO dicionário (os outros arquivos o
# importam uma vez): trocar o tema troca o conteúdo dele, não o objeto.
CORES = dict(PALETAS[TEMA_PADRAO])

_tema_atual = TEMA_PADRAO


def tema_atual() -> str:
    """ "escuro" ou "claro"."""

    return _tema_atual


def definir_paleta(nome):
    """
    Passa a usar a paleta do tema (só o dicionário CORES; não mexe na
    tela). Devolve o mapa {cor antiga: cor nova}, usado para repintar
    o que já está desenhado.
    """

    global _tema_atual

    if nome not in PALETAS:
        nome = TEMA_PADRAO

    antigas = dict(CORES)

    CORES.clear()
    CORES.update(PALETAS[nome])

    _tema_atual = nome

    return {antigas[chave].lower(): CORES[chave] for chave in CORES}


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
    "status_icone": (FAMILIA, 26, "bold"),
    "relogio": (FAMILIA, 11, "bold"),
    "legenda_video": (FAMILIA, 9, "bold"),
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
        background=[("disabled", CORES["desativado"]), ("active", CORES["destaque_hover"])],
        foreground=[("disabled", CORES["texto_suave"])],
    )

    # Botão secundário para usar DENTRO de um cartão (o botão padrão
    # tem a mesma cor do cartão e sumiria nele)
    estilo.configure("Secundario.TButton", background=CORES["borda"], foreground=CORES["texto"])

    estilo.map(
        "Secundario.TButton",
        background=[("disabled", CORES["desativado"]), ("active", CORES["realce"])],
        foreground=[("disabled", CORES["texto_suave"])],
    )

    estilo.configure("Perigo.TButton", background=CORES["perigo"], foreground="white")

    # Ação que apaga coisas da tela, do MESMO tamanho dos outros botões
    # (para a fileira ficar alinhada), mas em tom discreto: só fica
    # vermelho cheio quando o mouse passa por cima.
    estilo.configure("Suave.Perigo.TButton", background=CORES["perigo_fundo"], foreground=CORES["perigo_texto"])

    estilo.map(
        "Suave.Perigo.TButton",
        background=[("disabled", CORES["cartao"]), ("active", CORES["perigo"])],
        foreground=[("disabled", CORES["borda"]), ("active", "white")],
    )

    # Botão que liga e desliga uma visão (ex.: "Visão geral"): azul quando ligado
    estilo.configure(
        "Alternar.Toolbutton",
        background=CORES["borda"],
        foreground=CORES["texto"],
        font=FONTES["texto_negrito"],
        padding=(14, 9),
        relief="flat",
    )

    estilo.map(
        "Alternar.Toolbutton",
        background=[("disabled", CORES["cartao"]), ("selected", CORES["destaque"]), ("active", CORES["realce"])],
        foreground=[("disabled", CORES["texto_suave"]), ("selected", "white")],
    )

    # Versão pequena e discreta, para uma ação que apaga coisas da
    # tela: fica visível sem chamar mais atenção do que os botões do
    # dia a dia. Só fica vermelho cheio quando o mouse passa por cima.
    estilo.configure(
        "Pequeno.Perigo.TButton",
        background=CORES["perigo_fundo"],
        foreground=CORES["perigo_texto"],
        font=FONTES["pequena"],
        padding=(10, 5),
    )

    estilo.map(
        "Pequeno.Perigo.TButton",
        background=[("active", CORES["perigo"])],
        foreground=[("active", "white")],
    )

    estilo.map(
        "Perigo.TButton",
        background=[("disabled", CORES["desativado"]), ("active", CORES["perigo_hover"])],
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

    # Seletor do modo de detecção (Rosto / Corpo), dentro de um cartão
    estilo.configure(
        "Modo.Toolbutton",
        background=CORES["borda"],
        foreground=CORES["texto_suave"],
        font=FONTES["texto_negrito"],
        padding=(12, 5),
        relief="flat",
    )

    estilo.map(
        "Modo.Toolbutton",
        background=[
            ("disabled", CORES["cartao"]),
            ("selected", CORES["destaque"]),
            ("active", CORES["realce"]),
        ],
        foreground=[("disabled", CORES["borda"]), ("selected", "white")],
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

    # Campo desativado: fundo igual ao do cartão e texto apagado
    estilo.map(
        "TEntry",
        fieldbackground=[("disabled", CORES["cartao_hover"])],
        foreground=[("disabled", CORES["texto_suave"])],
        bordercolor=[("focus", CORES["destaque"])],
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
        # Desativada (ex.: opção que só vale com outra ligada): texto e
        # caixa apagados, mas ainda dá para ler e ver se está marcada
        foreground=[("disabled", CORES["texto_suave"])],
        indicatorbackground=[
            ("disabled", "selected", CORES["realce"]),
            ("disabled", CORES["cartao"]),
            ("selected", CORES["destaque"]),
        ],
        indicatorforeground=[("disabled", CORES["texto_suave"])],
        upperbordercolor=[("disabled", CORES["realce"]), ("selected", CORES["destaque"])],
        lowerbordercolor=[("disabled", CORES["realce"]), ("selected", CORES["destaque"])],
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

    # Lista de períodos e outras caixas de seleção pequenas
    estilo.configure("Pequena.TCombobox", padding=3)

    # ------------------------------------------------------
    # NAVEGAÇÃO ENTRE AS ÁREAS (pílulas no lugar das abas)
    # ------------------------------------------------------
    #
    # Cada área é uma "pílula" com um ponto colorido da situação dela;
    # a escolhida fica azul. As abas do ttk.Notebook ficam escondidas:
    # ele só guarda as páginas (veja SemAbas.TNotebook abaixo).

    for nome_estilo in ("Pilula.Toolbutton", "Pilula.TButton"):

        estilo.configure(
            nome_estilo,
            background=CORES["cartao"],
            foreground=CORES["texto"],
            font=FONTES["texto_negrito"],
            padding=(int(12 * escala), int(6 * escala)),
            relief="flat",
            borderwidth=0,
        )

        estilo.map(
            nome_estilo,
            background=[
                ("disabled", CORES["painel"]),
                ("selected", CORES["destaque"]),
                ("active", CORES["cartao_hover"]),
            ],
            foreground=[("disabled", CORES["texto_suave"]), ("selected", "white")],
        )

    # "+ Nova área": discreto, só o texto em azul
    estilo.configure("Nova.Pilula.TButton", foreground=CORES["destaque"])

    # Notebook sem a fileira de abas: só troca a página visível
    estilo.layout("SemAbas.TNotebook.Tab", [])
    estilo.layout("SemAbas.TNotebook", [("Notebook.client", {"sticky": "nswe"})])
    estilo.configure(
        "SemAbas.TNotebook",
        background=CORES["painel"],
        bordercolor=CORES["painel"],
        lightcolor=CORES["painel"],
        darkcolor=CORES["painel"],
        borderwidth=0,
        tabmargins=0,
    )

    # EPIs exigidos como "chips": azul = exigido, apagado = não exigido
    estilo.configure(
        "Chip.Toolbutton",
        background=CORES["cartao_hover"],
        foreground=CORES["texto_suave"],
        font=FONTES["texto_negrito"],
        padding=(int(12 * escala), int(5 * escala)),
        relief="flat",
    )

    estilo.map(
        "Chip.Toolbutton",
        background=[("disabled", CORES["cartao"]), ("selected", CORES["destaque"]), ("active", CORES["realce"])],
        foreground=[("disabled", CORES["borda"]), ("selected", "white"), ("active", CORES["texto"])],
    )

    # Botão pequeno do cabeçalho (ex.: trocar o tema)
    estilo.configure("Pequeno.TButton", font=FONTES["pequena"], padding=(int(10 * escala), int(4 * escala)))

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
        background=[("active", CORES["realce"])],
        lightcolor=[("active", CORES["realce"])],
        darkcolor=[("active", CORES["realce"])],
    )

    # ------------------------------------------------------
    # ABAS (janela de Configurações)
    # ------------------------------------------------------

    estilo.configure(
        "TNotebook",
        background=CORES["painel"],
        borderwidth=0,
        tabmargins=(0, 0, 0, 0),
    )

    estilo.configure(
        "TNotebook.Tab",
        background=CORES["cartao"],
        foreground=CORES["texto_suave"],
        bordercolor=CORES["borda"],
        lightcolor=CORES["cartao"],
        font=FONTES["texto"],
        padding=(int(16 * escala), int(7 * escala)),
    )

    # Aba escolhida em destaque; as outras mudam de cor ao passar o mouse
    estilo.map(
        "TNotebook.Tab",
        background=[("selected", CORES["destaque"]), ("active", CORES["cartao_hover"])],
        foreground=[("selected", "white"), ("active", CORES["texto"])],
        lightcolor=[("selected", CORES["destaque"])],
    )

    # ------------------------------------------------------
    # DIVISOR ARRASTÁVEL ENTRE OS PAINÉIS
    # ------------------------------------------------------

    estilo.configure("TPanedwindow", background=CORES["fundo"])
    estilo.configure("Sash", sashthickness=int(8 * escala), gripcount=0)

    return estilo


# ============================================================
# ÍCONE DO PROGRAMA (desenhado aqui, sem arquivo de imagem)
# ============================================================
#
# Um escudo azul com um "visto" branco: segurança + aprovado. É usado
# na barra de tarefas, no título da janela e no cabeçalho. Desenhado
# 4 vezes maior e depois reduzido, para as bordas ficarem suaves.
# ============================================================

def desenhar_icone(tamanho=64):
    """O escudo do SafeTech (imagem PIL RGBA) nas cores de destaque do tema."""

    from safetech.nucleo.icones import desenhar_escudo

    return desenhar_escudo(tamanho, CORES["destaque"], CORES["destaque_hover"])


# ============================================================
# TROCA DE TEMA COM O PROGRAMA ABERTO
# ============================================================
#
# Os componentes ttk seguem os estilos: basta refazer os estilos. Já os
# componentes tk (Frame, Label, Canvas...) guardam a cor escrita neles.
# Para esses, a troca percorre a janela inteira e substitui cada cor da
# paleta antiga pela cor da MESMA chave na paleta nova.
# ============================================================

# Opções de cor que um componente pode ter
OPCOES_DE_COR = (
    "background",
    "foreground",
    "highlightbackground",
    "highlightcolor",
    "activebackground",
    "activeforeground",
    "selectbackground",
    "selectforeground",
    "insertbackground",
    "disabledforeground",
    "troughcolor",
)


def trocar_tema(raiz, nome, escala=1.0):
    """
    Troca o tema com o programa aberto: estilos ttk e as cores escritas
    nos componentes tk (de todas as janelas, inclusive as escondidas).
    """

    mapa = definir_paleta(nome)

    aplicar_tema(raiz, escala)

    repintar(raiz, mapa)


def repintar(componente, mapa):
    """Troca, neste componente e em todos dentro dele, cada cor antiga pela nova."""

    for opcao in OPCOES_DE_COR:

        try:
            valor = str(componente.cget(opcao)).lower()
        except (tk.TclError, ValueError):
            continue  # este componente não tem essa opção

        if valor in mapa:

            try:
                componente.configure(**{opcao: mapa[valor]})
            except tk.TclError:
                pass

    # Desenhos de um Canvas (retângulos, textos...) têm cores próprias
    if isinstance(componente, tk.Canvas):

        for item in componente.find_all():

            for opcao in ("fill", "outline"):

                try:
                    valor = str(componente.itemcget(item, opcao)).lower()
                except tk.TclError:
                    continue

                if valor in mapa:
                    componente.itemconfigure(item, **{opcao: mapa[valor]})

    for filho in componente.winfo_children():
        repintar(filho, mapa)


# ============================================================
# PONTO COLORIDO (situação de cada área na navegação)
# ============================================================

def desenhar_ponto(cor, tamanho=10):
    """Círculo cheio na cor dada, com fundo transparente (imagem PIL)."""

    grande = tamanho * 4

    imagem = Image.new("RGBA", (grande, grande), (0, 0, 0, 0))

    ImageDraw.Draw(imagem).ellipse((2, 2, grande - 3, grande - 3), fill=cor)

    return imagem.resize((tamanho, tamanho), Image.LANCZOS)
