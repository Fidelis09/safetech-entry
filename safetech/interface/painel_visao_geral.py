"""
Visão geral: todas as áreas lado a lado, como num monitor de segurança.

Com uma área por aba, o operador só vê uma câmera por vez. A visão geral
mostra TODAS ao mesmo tempo, cada uma num quadro com:

    - o nome da área e o modo (catraca ou vigilância);
    - uma etiqueta colorida com a situação (liberado, negado, câmera
      desligada...), a mesma da faixa de status da aba;
    - o vídeo, pequeno, com as caixas das pessoas.

Clicar num quadro abre a página daquela área (e o botão "Visão geral"
da barra volta para cá). Passar o mouse destaca o quadro. Um quadro
com a câmera desligada tem o botão "Ligar câmera" no meio.

Desenhar várias imagens custa tempo da interface. Por isso os quadros
são redesenhados poucas vezes por segundo
(config.QUADROS_POR_SEGUNDO_VISAO_GERAL), e só enquanto a visão geral
está na tela.

Como os outros painéis, este só exibe e avisa: quem abre a aba da área
é a janela principal (função recebida em ao_abrir_area).
"""

import math
import time
import tkinter as tk
from tkinter import ttk

import cv2
from PIL import Image, ImageTk

from safetech import config
from safetech.interface.tema import CORES, FONTES
from safetech.nucleo import anotacao, modos
from safetech.servicos.camera import EstadoCamera


# Espaço (px) entre os quadros
ESPACO_ENTRE_QUADROS = 10

# Proporção do vídeo (largura / altura) usada para escolher a grade e
# altura aproximada do cabeçalho de cada quadro, em px
PROPORCAO_VIDEO = 16 / 9
ALTURA_CABECALHO_QUADRO = 34


def melhor_grade(quantidade, largura, altura):
    """
    (colunas, linhas) que deixam cada vídeo o MAIOR possível no espaço.

    Num painel largo, 2 áreas ficam lado a lado; num painel alto, uma
    em cima da outra. Testa todas as quantidades de colunas e fica com
    a que dá o vídeo mais largo (mantendo a proporção 16:9).
    """

    if quantidade <= 0:
        return 1, 1

    melhor = (1, quantidade)
    maior_largura = -1.0

    for colunas in range(1, quantidade + 1):

        linhas = math.ceil(quantidade / colunas)

        largura_quadro = (largura - ESPACO_ENTRE_QUADROS * (colunas - 1)) / colunas
        altura_video = (altura - ESPACO_ENTRE_QUADROS * (linhas - 1)) / linhas - ALTURA_CABECALHO_QUADRO

        # O vídeo é limitado pela largura OU pela altura do quadro
        largura_video = min(largura_quadro, altura_video * PROPORCAO_VIDEO)

        if largura_video > maior_largura:
            maior_largura = largura_video
            melhor = (colunas, linhas)

    return melhor


class PainelVisaoGeral(ttk.Frame):

    def __init__(self, pai, ao_abrir_area, ao_alternar_camera=None):
        """
        ao_abrir_area      -> chamado com a área do quadro clicado.
        ao_alternar_camera -> chamado com a área ao clicar em "Ligar câmera".
        """

        super().__init__(pai, style="Painel.TFrame")

        self._ao_abrir_area = ao_abrir_area
        self._ao_alternar_camera = ao_alternar_camera or (lambda _area: None)

        self._quadros = []

        # (colunas, linhas) em uso; refeita quando o painel muda de formato
        self._grade = None

        self._proximo_desenho = 0.0

        self.bind("<Configure>", lambda _evento: self._organizar())

    def definir_areas(self, areas):
        """Refaz a grade de quadros para estas áreas (ao abrir ou quando áreas entram e saem)."""

        for quadro in self._quadros:
            quadro.destroy()

        self._quadros = [QuadroArea(self, area, self._ao_abrir_area, self._ao_alternar_camera) for area in areas]

        self._grade = None
        self._organizar()

        self._proximo_desenho = 0.0

    def _organizar(self):
        """Distribui os quadros na grade que melhor aproveita o espaço atual."""

        if not self._quadros:
            return

        grade = melhor_grade(len(self._quadros), max(1, self.winfo_width()), max(1, self.winfo_height()))

        if grade == self._grade:
            return

        self._grade = grade

        colunas, linhas = grade

        # Limpa os pesos de uma grade anterior maior
        for indice in range(config.MAXIMO_AREAS):
            self.columnconfigure(indice, weight=0, uniform="")
            self.rowconfigure(indice, weight=0, uniform="")

        for indice in range(colunas):
            self.columnconfigure(indice, weight=1, uniform="colunas")

        for indice in range(linhas):
            self.rowconfigure(indice, weight=1, uniform="linhas")

        for posicao, quadro in enumerate(self._quadros):

            linha, coluna = divmod(posicao, colunas)

            quadro.grid(
                row=linha,
                column=coluna,
                sticky="nsew",
                padx=(0 if coluna == 0 else ESPACO_ENTRE_QUADROS, 0),
                pady=(0 if linha == 0 else ESPACO_ENTRE_QUADROS, 0),
            )

    def atualizar(self):
        """Chamado pelo ciclo da janela; redesenha os quadros no ritmo da configuração."""

        agora = time.perf_counter()

        if agora < self._proximo_desenho:
            return

        self._proximo_desenho = agora + 1.0 / config.QUADROS_POR_SEGUNDO_VISAO_GERAL

        for quadro in self._quadros:
            quadro.atualizar()

    @property
    def quadros(self):
        return list(self._quadros)

    def esquecer_desenho(self):
        """Redesenha todos os quadros na próxima atualização (ex.: depois de trocar o tema)."""

        for quadro in self._quadros:
            quadro.esquecer_desenho()

        self._proximo_desenho = 0.0


class QuadroArea(tk.Frame):
    """O quadro de UMA área na visão geral: cabeçalho com a situação e o vídeo."""

    def __init__(self, pai, area, ao_abrir_area, ao_alternar_camera):

        super().__init__(pai, bg=CORES["cartao"], highlightthickness=2, highlightbackground=CORES["borda"], cursor="hand2")

        self.area = area

        self._foto = None
        self._ultimo_desenho = None
        self._ultima_situacao = None

        # Cor da borda pela situação; com o mouse em cima, fica azul
        self._cor_da_borda = CORES["borda"]
        self._mouse_em_cima = False

        self.columnconfigure(0, weight=1)
        self.rowconfigure(1, weight=1)

        # ---------------- cabeçalho: nome, modo e situação ----------------

        cabeca = tk.Frame(self, bg=CORES["cartao"], padx=10, pady=6)
        cabeca.grid(row=0, column=0, sticky="ew")

        self._rotulo_nome = tk.Label(cabeca, text="", bg=CORES["cartao"], fg=CORES["texto"], font=FONTES["texto_negrito"])
        self._rotulo_nome.pack(side="left")

        self._rotulo_modo = tk.Label(cabeca, text="", bg=CORES["cartao"], fg=CORES["texto_suave"], font=FONTES["pequena"])
        self._rotulo_modo.pack(side="left", padx=(8, 0))

        # Dica "Abrir ›", só com o mouse em cima
        self._rotulo_abrir = tk.Label(cabeca, text="Abrir \u203a", bg=CORES["cartao"], fg=CORES["destaque"], font=FONTES["pequena"])

        # Etiqueta colorida com a situação (a mesma da faixa de status)
        self._etiqueta = tk.Label(cabeca, text="", bg=CORES["neutro"], fg="white", font=FONTES["pequena"], padx=8, pady=1)
        self._etiqueta.pack(side="right")

        # ---------------- vídeo ----------------

        self._tela = tk.Canvas(self, bg=CORES["video"], highlightthickness=0, width=200, height=120, cursor="hand2")
        self._tela.grid(row=1, column=0, sticky="nsew")

        self._item_imagem = self._tela.create_image(0, 0, anchor="center")
        self._item_mensagem = self._tela.create_text(0, 0, text="", fill=CORES["texto_suave"], font=FONTES["texto"])

        # Ligar a câmera sem sair da visão geral
        self._botao_ligar = ttk.Button(
            self._tela,
            text="\u25b6  Ligar câmera",
            style="Primario.TButton",
            command=lambda: ao_alternar_camera(self.area),
            takefocus=False,
            cursor="hand2",
        )
        self._item_botao = self._tela.create_window(0, 0, window=self._botao_ligar, anchor="n", state="hidden")

        self._tela.bind("<Configure>", self._ao_redimensionar)

        # Clicar em qualquer parte do quadro abre a página da área; o
        # mouse em cima destaca o quadro e mostra "Abrir ›"
        for parte in (self, cabeca, self._rotulo_nome, self._rotulo_modo, self._etiqueta, self._rotulo_abrir, self._tela):
            parte.bind("<Button-1>", lambda _evento: ao_abrir_area(self.area))
            parte.bind("<Enter>", lambda _evento: self._destacar(True))
            parte.bind("<Leave>", lambda _evento: self._destacar(False))

    def _destacar(self, ligado):

        self._mouse_em_cima = ligado

        self.config(highlightbackground=CORES["destaque"] if ligado else self._cor_da_borda)

        if ligado:
            self._rotulo_abrir.pack(side="right", padx=(0, 8))
        else:
            self._rotulo_abrir.pack_forget()

    def esquecer_desenho(self):

        self._ultima_situacao = None
        self._ultimo_desenho = None

    def _ao_redimensionar(self, evento):

        centro = (evento.width // 2, evento.height // 2)

        self._tela.coords(self._item_imagem, *centro)
        self._tela.coords(self._item_mensagem, centro[0], centro[1] - 16)
        self._tela.coords(self._item_botao, centro[0], centro[1] + 4)

        self._ultimo_desenho = None

    # ============================================================
    # DESENHO
    # ============================================================

    def atualizar(self):

        area = self.area

        # ---------------- cabeçalho ----------------

        titulo, _, cor = area.resumo_status()

        situacao = (area.nome, modos.nome_do_modo(area.parametros.modo_deteccao), titulo, cor)

        if situacao != self._ultima_situacao:

            self._ultima_situacao = situacao

            self._rotulo_nome.config(text=area.nome)
            self._rotulo_modo.config(text=situacao[1])
            self._etiqueta.config(text=titulo, bg=cor)

            # Borda na cor da situação: o quadro com problema chama a atenção
            self._cor_da_borda = cor if cor != CORES["neutro"] else CORES["borda"]

            if not self._mouse_em_cima:
                self.config(highlightbackground=self._cor_da_borda)

        # ---------------- vídeo ----------------

        frame, numero_frame = area.camera.ler()

        if frame is None or area.analisador is None:

            # Câmera parada (ou com erro) e a IA pronta: dá para ligar daqui
            pode_ligar = area.analisador is not None and area.camera.estado in (EstadoCamera.PARADA, EstadoCamera.ERRO)

            situacao_sem_video = ("sem_video", pode_ligar)

            if self._ultimo_desenho != situacao_sem_video:

                self._ultimo_desenho = situacao_sem_video
                self._foto = None

                self._tela.itemconfigure(self._item_imagem, image="")
                self._tela.itemconfigure(self._item_mensagem, text="Câmera desligada" if pode_ligar else "Sem vídeo")
                self._tela.itemconfigure(self._item_botao, state="normal" if pode_ligar else "hidden")

            return

        self._tela.itemconfigure(self._item_botao, state="hidden")

        largura_tela = self._tela.winfo_width()
        altura_tela = self._tela.winfo_height()

        assinatura = (numero_frame, largura_tela, altura_tela)

        if assinatura == self._ultimo_desenho or largura_tela < 20 or altura_tela < 20:
            return

        self._ultimo_desenho = assinatura

        estado = area.analisador.estado()

        altura_frame, largura_frame = frame.shape[:2]

        escala = min(largura_tela / largura_frame, altura_tela / altura_frame)

        tamanho = (max(1, int(largura_frame * escala)), max(1, int(altura_frame * escala)))

        # Imagem NOVA (o frame é compartilhado com a análise: não desenhar nele)
        imagem = cv2.resize(frame, tamanho, interpolation=cv2.INTER_AREA)

        anotacao.desenhar_pessoas(imagem, estado.pessoas, escala, modo=estado.modo)

        imagem = Image.fromarray(cv2.cvtColor(imagem, cv2.COLOR_BGR2RGB))

        if self._foto is not None and (self._foto.width(), self._foto.height()) == tamanho:
            self._foto.paste(imagem)
        else:
            self._foto = ImageTk.PhotoImage(imagem)

        self._tela.itemconfigure(self._item_imagem, image=self._foto)
        self._tela.itemconfigure(self._item_mensagem, text="")

    def etiqueta(self):
        """Texto da etiqueta de situação (usado nos testes)."""

        return self._etiqueta.cget("text")
