"""
Pequenos componentes visuais reaproveitados pela interface.

    Selo       -> etiqueta de situação com um ponto colorido, usada no
                  cabeçalho ("● IA pronta", "● Catraca: COM3 conectada")
    BarraAreas -> navegação entre as áreas (câmeras), com a situação de
                  cada uma num ponto colorido
"""

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
