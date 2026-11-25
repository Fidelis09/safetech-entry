"""
Pequenos componentes visuais reaproveitados pela interface.

    Selo       -> etiqueta de situação com um ponto colorido, usada no
                  cabeçalho ("● IA pronta", "● Catraca: COM3 conectada")
    BarraAreas -> navegação entre as áreas (câmeras), com a situação de
                  cada uma num ponto colorido
    Dica       -> frase que aparece ao parar o mouse em cima de um botão
    Avisos     -> avisos em cartões no canto da janela (toasts)
    PainelAtalhos -> cartão com as teclas de atalho (F1)
"""

import time
import tkinter as tk
from tkinter import ttk

from PIL import ImageTk

from safetech.interface.tema import CORES, FONTES, desenhar_ponto


# Diâmetro (px) do ponto de situação nas pílulas das áreas
TAMANHO_PONTO = 10


class Selo(tk.Frame):
    """
    Etiqueta com contorno: um ponto colorido e um texto.

    A cor do ponto diz a situação de relance (verde = ok, amarelo =
    esperando, vermelho = problema); o texto diz o que é. Selo com
    texto vazio some da tela (ex.: catraca desligada no config.py).
    """

    def __init__(self, pai, ao_clicar=None):

        super().__init__(
            pai,
            bg=CORES["painel"],
            padx=10,
            pady=4,
            highlightthickness=1,
            highlightbackground=CORES["borda"],
        )

        self._ponto = tk.Label(self, text="●", bg=CORES["painel"], fg=CORES["texto_suave"], font=FONTES["pequena"])
        self._ponto.pack(side="left", padx=(0, 6))

        # Público: os testes e a janela leem o texto daqui
        self.rotulo = tk.Label(self, text="", bg=CORES["painel"], fg=CORES["texto"], font=FONTES["pequena"])
        self.rotulo.pack(side="left")

        if ao_clicar is not None:

            # O selo inteiro é clicável e mostra a "mãozinha"
            for parte in (self, self._ponto, self.rotulo):
                parte.config(cursor="hand2")
                parte.bind("<Button-1>", lambda _evento: ao_clicar())

    def definir(self, texto, cor):
        """Troca o texto e a cor do ponto. Texto vazio esconde o selo."""

        if texto != self.rotulo.cget("text"):
            self.rotulo.config(text=texto)

        self._ponto.config(fg=cor)

        # O selo é posicionado com grid pela janela: grid_remove
        # esconde e lembra o lugar, para voltar ao mesmo ponto depois.
        if texto:
            self.grid()
        else:
            self.grid_remove()


# ============================================================
# BARRA DE NAVEGAÇÃO ENTRE AS ÁREAS
# ============================================================

class BarraAreas(ttk.Frame):
    """
    Navegação das áreas no lugar das abas:

        [▦ Visão geral] | [● Principal · catraca] [● Portaria] ... [+ Nova área]

    Cada área é uma "pílula" com um ponto na cor da situação dela agora
    (verde, vermelho, amarelo, cinza): dá para ver de relance qual área
    precisa de atenção, mesmo sem abri-la. A escolhida fica azul.

    "Visão geral" (todas lado a lado) só funciona com duas áreas ou mais.
    """

    def __init__(self, pai, ao_escolher_area, ao_nova_area, ao_alternar_visao_geral):
        """
        ao_escolher_area        -> chamado com a chave da área clicada
        ao_nova_area            -> botão "+ Nova área"
        ao_alternar_visao_geral -> botão "Visão geral" (lê visao_geral_ativa)
        """

        super().__init__(pai, style="Painel.TFrame")

        self._ao_escolher_area = ao_escolher_area

        # Imagens dos pontos já desenhadas, uma por cor (o Tkinter apaga
        # a imagem que ninguém guarda)
        self._pontos = {}

        # chave da área -> pílula; e a cor que o ponto de cada uma mostra
        self._pilulas = {}
        self._cor_da_pilula = {}

        self.visao_geral_ativa = tk.BooleanVar(value=False)

        self.botao_visao_geral = ttk.Checkbutton(
            self,
            text="\u25a6  Visão geral",
            variable=self.visao_geral_ativa,
            style="Pilula.Toolbutton",
            command=ao_alternar_visao_geral,
            takefocus=False,
        )
        self.botao_visao_geral.pack(side="left", padx=(0, 6))

        Dica(self.botao_visao_geral, "Todas as câmeras lado a lado (com duas áreas ou mais)")

        # Separador fino entre a visão geral e as áreas
        self._separador = tk.Frame(self, bg=CORES["borda"], width=1)
        self._separador.pack(side="left", fill="y", padx=(2, 8), pady=4)

        # Área escolhida (chave); "" = nenhuma (visão geral na tela)
        self._escolhida = tk.StringVar(value="")

        self.botao_nova = ttk.Button(
            self,
            text="+  Nova área",
            style="Nova.Pilula.TButton",
            command=ao_nova_area,
            takefocus=False,
        )
        self.botao_nova.pack(side="left")

        Dica(self.botao_nova, "Cria outra área, com outra câmera e a sua própria fiscalização")

    def definir_areas(self, itens):
        """Refaz as pílulas: itens = lista de (chave, texto), na ordem."""

        for pilula in self._pilulas.values():
            pilula.destroy()

        self._pilulas = {}
        self._cor_da_pilula = {}

        # As pílulas entram antes do "+ Nova área", que fica por último
        self.botao_nova.pack_forget()

        for chave, texto in itens:

            pilula = ttk.Radiobutton(
                self,
                text=texto,
                value=chave,
                variable=self._escolhida,
                style="Pilula.Toolbutton",
                image=self._ponto(CORES["neutro"]),
                compound="left",
                command=lambda c=chave: self._ao_escolher_area(c),
                takefocus=False,
            )
            pilula.pack(side="left", padx=(0, 6))

            self._pilulas[chave] = pilula
            self._cor_da_pilula[chave] = CORES["neutro"]

        self.botao_nova.pack(side="left")

    def definir_texto(self, chave, texto):

        if chave in self._pilulas:
            self._pilulas[chave].config(text=texto)

    def selecionar(self, chave):
        """Marca a pílula da área (ou nenhuma, com chave "")."""

        self._escolhida.set(chave)

    def definir_cor(self, chave, cor):
        """Cor do ponto da área (a situação dela agora)."""

        if chave in self._pilulas and self._cor_da_pilula.get(chave) != cor:

            self._cor_da_pilula[chave] = cor

            # Espaço antes do texto: o ponto não encosta no nome
            self._pilulas[chave].config(image=self._ponto(cor))

    def cor(self, chave):
        """Cor que o ponto da área está mostrando (usado nos testes)."""

        return self._cor_da_pilula.get(chave)

    def esquecer_cores(self):
        """Depois de trocar o tema: os pontos são redesenhados na próxima atualização."""

        self._pontos = {}
        self._cor_da_pilula = {chave: None for chave in self._pilulas}

    def _ponto(self, cor):

        if cor not in self._pontos:
            self._pontos[cor] = ImageTk.PhotoImage(desenhar_ponto(cor, TAMANHO_PONTO))

        return self._pontos[cor]


# ============================================================
# DICA AO PASSAR O MOUSE (tooltip)
# ============================================================

# Espera (ms) com o mouse parado em cima antes de a dica aparecer
ESPERA_DICA_MS = 600


class Dica:
    """
    Uma frase curta que aparece quando o mouse para em cima de um botão.

        Dica(botao, "Abre a tela do trabalhador (F2)")

    Some quando o mouse sai ou quando o botão é clicado.
    """

    def __init__(self, componente, texto):

        self._componente = componente
        self.texto = texto

        self._agendada = None
        self._janela = None

        componente.bind("<Enter>", self._agendar, add="+")
        componente.bind("<Leave>", self._esconder, add="+")
        componente.bind("<ButtonPress>", self._esconder, add="+")

    def _agendar(self, _evento=None):

        self._cancelar()
        self._agendada = self._componente.after(ESPERA_DICA_MS, self.mostrar)

    def _cancelar(self):

        if self._agendada is not None:
            self._componente.after_cancel(self._agendada)
            self._agendada = None

    def mostrar(self):

        self._agendada = None

        if self._janela is not None or not self._componente.winfo_viewable():
            return

        # Janela sem borda, logo abaixo do componente
        self._janela = tk.Toplevel(self._componente)
        self._janela.wm_overrideredirect(True)

        x = self._componente.winfo_rootx()
        y = self._componente.winfo_rooty() + self._componente.winfo_height() + 6

        self._janela.wm_geometry(f"+{x}+{y}")

        # Cores invertidas (texto claro no escuro e vice-versa): destaca do resto
        tk.Label(
            self._janela,
            text=self.texto,
            bg=CORES["texto"],
            fg=CORES["fundo"],
            font=FONTES["pequena"],
            padx=8,
            pady=4,
            justify="left",
            wraplength=320,
        ).pack()

    def _esconder(self, _evento=None):

        self._cancelar()

        if self._janela is not None:
            self._janela.destroy()
            self._janela = None


def dica(componente, texto):
    """Atalho: põe uma dica no componente e o devolve (para usar em sequência)."""

    Dica(componente, texto)

    return componente


# ============================================================
# AVISOS EM CARTÕES (toasts)
# ============================================================
#
# Um aviso aparece num cartão no canto de baixo, à direita, com um ícone
# e uma faixa na cor do tipo (sucesso, erro, alerta ou informação), e
# some sozinho depois de alguns segundos (ou ao clicar no "×"). Vários
# avisos seguidos ficam empilhados; os mais antigos saem primeiro.
# ============================================================

ICONES_DOS_AVISOS = {
    "sucesso": "✔",   # ✔
    "erro": "✖",      # ✖
    "alerta": "⚠",    # ⚠
    "info": "ℹ",      # ℹ
}

# Quantos cartões cabem na pilha ao mesmo tempo
MAXIMO_AVISOS_NA_TELA = 4

# Distância (px) entre os cartões
ESPACO_AVISOS = 10


class Avisos:

    def __init__(self, raiz, distancia_do_rodape=48):
        """distancia_do_rodape -> px acima da borda de baixo (para não cobrir o rodapé)."""

        self._raiz = raiz
        self._distancia_do_rodape = distancia_do_rodape

        # [cartão, momento em que some], do mais antigo ao mais novo
        self._cartoes = []

        self.ultimo_texto = ""

    def mostrar(self, texto, tipo="info", segundos=4):

        self.ultimo_texto = texto

        cor = {
            "sucesso": CORES["sucesso"],
            "erro": CORES["perigo"],
            "alerta": CORES["alerta"],
        }.get(tipo, CORES["destaque"])

        cartao = tk.Frame(self._raiz, bg=CORES["cartao"], highlightthickness=1, highlightbackground=CORES["borda"])

        tk.Frame(cartao, bg=cor, width=4).pack(side="left", fill="y")

        tk.Label(cartao, text=ICONES_DOS_AVISOS.get(tipo, ""), bg=CORES["cartao"], fg=cor, font=FONTES["titulo"]).pack(
            side="left", padx=(10, 6), pady=8
        )

        fechar = tk.Label(cartao, text="×", bg=CORES["cartao"], fg=CORES["texto_suave"], font=FONTES["titulo"], cursor="hand2")
        fechar.pack(side="right", padx=(6, 10))

        tk.Label(
            cartao, text=texto, bg=CORES["cartao"], fg=CORES["texto"], font=FONTES["texto"], justify="left", wraplength=380
        ).pack(side="left", pady=8)

        registro = [cartao, time.perf_counter() + segundos]

        fechar.bind("<Button-1>", lambda _evento: self._tirar(registro))

        self._cartoes.append(registro)

        # Pilha cheia: o mais antigo sai
        while len(self._cartoes) > MAXIMO_AVISOS_NA_TELA:
            self._tirar(self._cartoes[0])

        self._organizar()

    def atualizar(self):
        """Chamado a cada ciclo da janela: tira os cartões vencidos."""

        agora = time.perf_counter()

        for registro in list(self._cartoes):
            if agora >= registro[1]:
                self._tirar(registro)

    def textos(self):
        """Textos dos cartões na tela, do mais antigo ao mais novo (usado nos testes)."""

        textos = []

        for cartao, _ in self._cartoes:
            for filho in cartao.winfo_children():
                if isinstance(filho, tk.Label) and int(filho.cget("wraplength")):
                    textos.append(filho.cget("text"))

        return textos

    def _tirar(self, registro):

        if registro in self._cartoes:
            self._cartoes.remove(registro)
            registro[0].destroy()
            self._organizar()

    def _organizar(self):
        """Empilha de baixo para cima: o mais novo fica embaixo."""

        y = -self._distancia_do_rodape

        for cartao, _ in reversed(self._cartoes):

            cartao.place(relx=1.0, rely=1.0, x=-16, y=y, anchor="se")
            cartao.lift()

            cartao.update_idletasks()

            y -= cartao.winfo_reqheight() + ESPACO_AVISOS


# ============================================================
# PAINEL DE ATALHOS (F1)
# ============================================================

class PainelAtalhos(tk.Frame):
    """
    Cartão no meio da janela com todas as teclas de atalho. Aparece e
    some com F1 (ou Esc, ou o botão Fechar). Fica por cima da tela, sem
    abrir outra janela.
    """

    def __init__(self, raiz, atalhos):
        """atalhos -> lista de (tecla, o que faz)."""

        super().__init__(raiz, bg=CORES["cartao"], highlightthickness=1, highlightbackground=CORES["borda"], padx=24, pady=18)

        cabeca = tk.Frame(self, bg=CORES["cartao"])
        cabeca.pack(fill="x", pady=(0, 12))

        tk.Label(cabeca, text="Atalhos de teclado", bg=CORES["cartao"], fg=CORES["texto"], font=FONTES["titulo"]).pack(side="left")

        ttk.Button(cabeca, text="Fechar", style="Secundario.TButton", command=self.esconder, takefocus=False).pack(
            side="right", padx=(24, 0)
        )

        tabela = tk.Frame(self, bg=CORES["cartao"])
        tabela.pack(fill="x")

        for linha, (tecla, acao) in enumerate(atalhos):

            # A tecla num "botãozinho", como num teclado
            tk.Label(
                tabela, text=tecla, bg=CORES["cartao_hover"], fg=CORES["texto"], font=FONTES["texto_negrito"],
                padx=8, pady=2, highlightthickness=1, highlightbackground=CORES["borda"],
            ).grid(row=linha, column=0, sticky="w", pady=4)

            tk.Label(tabela, text=acao, bg=CORES["cartao"], fg=CORES["texto"], font=FONTES["texto"]).grid(
                row=linha, column=1, sticky="w", padx=(16, 0), pady=4
            )

        tk.Label(
            self, text="Os atalhos não disparam enquanto você digita na busca.",
            bg=CORES["cartao"], fg=CORES["texto_suave"], font=FONTES["pequena"],
        ).pack(anchor="w", pady=(12, 0))

        self.visivel = False

    def alternar(self):

        if self.visivel:
            self.esconder()
        else:
            self.place(relx=0.5, rely=0.45, anchor="center")
            self.lift()
            self.visivel = True

    def esconder(self):

        self.place_forget()
        self.visivel = False
