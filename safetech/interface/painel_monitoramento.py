"""
Painel de monitoramento (lado esquerdo da janela).

Mostra o vídeo da webcam, a faixa de status do acesso, os controles de
ajuste e os botões de coleta de imagens para o dataset.

O painel só exibe e avisa: as ações de verdade (ligar câmera, salvar
imagem, mudar parâmetros) são funções recebidas da janela principal.
"""

import tkinter as tk
from tkinter import ttk

from safetech.interface.tema import CORES, FONTES


class PainelMonitoramento(ttk.Frame):

    def __init__(
        self,
        pai,
        classes,
        limiar_inicial,
        intervalo_inicial,
        ao_alternar_camera,
        ao_capturar,
        ao_mudar_parametros,
    ):

        super().__init__(pai, style="Painel.TFrame", padding=18)

        self._ao_capturar = ao_capturar
        self._ao_mudar_parametros = ao_mudar_parametros

        # Variáveis ligadas aos controles deslizantes
        self._limiar = tk.DoubleVar(value=limiar_inicial * 100)
        self._intervalo = tk.DoubleVar(value=intervalo_inicial)

        # Referência à imagem em exibição (sem ela o Tkinter apaga a imagem)
        self._imagem_video = None

        self._botoes_captura = {}

        # A coluna única e a linha do vídeo ocupam todo o espaço que
        # sobrar; as outras linhas ficam com a altura do conteúdo.
        self.columnconfigure(0, weight=1)
        self.rowconfigure(1, weight=1)

        self._montar_cabecalho()
        self._montar_video()
        self._montar_status()
        self._montar_controles(ao_alternar_camera)
        self._montar_coleta(classes)

    # ============================================================
    # MONTAGEM
    # ============================================================

    def _montar_cabecalho(self):

        cabecalho = ttk.Frame(self, style="Painel.TFrame")
        cabecalho.grid(row=0, column=0, sticky="ew", pady=(0, 12))

        ttk.Label(
            cabecalho, text="Monitoramento", style="Titulo.Painel.TLabel"
        ).pack(side="left")

        # Indicadores de desempenho (câmera / análise), à direita
        self._rotulo_desempenho = ttk.Label(
            cabecalho, text="", style="Suave.Painel.TLabel"
        )
        self._rotulo_desempenho.pack(side="right")

    def _montar_video(self):

        # Canvas em vez de Label: permite centralizar a imagem e
        # escrever uma mensagem quando não há vídeo.
        self._tela = tk.Canvas(
            self,
            bg="#000000",
            highlightthickness=1,
            highlightbackground=CORES["borda"],
            width=320,
            height=240,
        )
        self._tela.grid(row=1, column=0, sticky="nsew")

        self._item_imagem = self._tela.create_image(0, 0, anchor="center")

        self._item_mensagem = self._tela.create_text(
            0,
            0,
            text="",
            fill=CORES["texto_suave"],
            font=FONTES["titulo"],
            justify="center",
        )

        # Mantém imagem e mensagem no centro quando o painel muda de tamanho
        self._tela.bind("<Configure>", self._ao_redimensionar_tela)

    def _montar_status(self):

        self._faixa_status = tk.Frame(self, bg=CORES["neutro"], padx=18, pady=12)
        self._faixa_status.grid(row=2, column=0, sticky="ew", pady=12)

        self._rotulo_status = tk.Label(
            self._faixa_status,
            text="",
            font=FONTES["status_titulo"],
            bg=CORES["neutro"],
            fg="white",
            anchor="w",
        )
        self._rotulo_status.pack(fill="x")

        self._rotulo_detalhe = tk.Label(
            self._faixa_status,
            text="",
            font=FONTES["status_detalhe"],
            bg=CORES["neutro"],
            fg="white",
            anchor="w",
        )
        self._rotulo_detalhe.pack(fill="x")

    def _montar_controles(self, ao_alternar_camera):

        cartao = ttk.Frame(self, style="Cartao.TFrame", padding=14)
        cartao.grid(row=3, column=0, sticky="ew")

        # Três colunas: dois controles deslizantes e o botão da câmera
        cartao.columnconfigure(0, weight=1, uniform="controles")
        cartao.columnconfigure(1, weight=1, uniform="controles")

        self._rotulo_limiar = self._criar_deslizante(
            cartao,
            coluna=0,
            titulo="Limiar de confiança",
            variavel=self._limiar,
            minimo=50,
            maximo=99,
        )

        self._rotulo_intervalo = self._criar_deslizante(
            cartao,
            coluna=1,
            titulo="Intervalo de análise",
            variavel=self._intervalo,
            minimo=0.3,
            maximo=5.0,
        )

        self._botao_camera = ttk.Button(
            cartao,
            text="Carregando...",
            style="Primario.TButton",
            command=ao_alternar_camera,
            takefocus=False,
            width=18,
            state="disabled",
        )
        self._botao_camera.grid(row=0, column=2, rowspan=2, sticky="nsew", padx=(16, 0))

        self._atualizar_rotulos_parametros()

    def _criar_deslizante(self, pai, coluna, titulo, variavel, minimo, maximo):
        """Cria um controle deslizante com título e valor; devolve o rótulo do valor."""

        # Espaço entre os dois controles
        margem = (0, 28) if coluna == 0 else (0, 0)

        linha_titulo = ttk.Frame(pai, style="Cartao.TFrame")
        linha_titulo.grid(row=0, column=coluna, sticky="ew", padx=margem)

        ttk.Label(linha_titulo, text=titulo, style="Suave.Cartao.TLabel").pack(side="left")

        rotulo_valor = ttk.Label(linha_titulo, text="", style="Cartao.TLabel", font=FONTES["texto_negrito"])
        rotulo_valor.pack(side="right")

        ttk.Scale(
            pai,
            from_=minimo,
            to=maximo,
            orient="horizontal",
            variable=variavel,
            command=self._ao_mover_deslizante,
            takefocus=False,
        ).grid(row=1, column=coluna, sticky="ew", padx=margem, pady=(6, 0))

        return rotulo_valor

    def _montar_coleta(self, classes):

        cartao = ttk.Frame(self, style="Cartao.TFrame", padding=14)
        cartao.grid(row=4, column=0, sticky="ew", pady=(12, 0))

        ttk.Label(
            cartao,
            text="Coleta de imagens para o dataset",
            style="Cartao.TLabel",
            font=FONTES["texto_negrito"],
        ).pack(anchor="w")

        ttk.Label(
            cartao,
            text="Salva o recorte de cada pessoa detectada direto na pasta de treino da classe.",
            style="Suave.Cartao.TLabel",
        ).pack(anchor="w", pady=(2, 10))

        linha_botoes = ttk.Frame(cartao, style="Cartao.TFrame")
        linha_botoes.pack(fill="x")

        for indice, nome_classe in enumerate(classes):

            linha_botoes.columnconfigure(indice, weight=1, uniform="captura")

            botao = ttk.Button(
                linha_botoes,
                style="Primario.TButton",
                command=lambda classe=nome_classe: self._ao_capturar(classe),
                takefocus=False,
            )

            botao.grid(
                row=0,
                column=indice,
                sticky="ew",
                padx=(0 if indice == 0 else 8, 0),
            )

            self._botoes_captura[nome_classe] = (botao, indice + 1)

    # ============================================================
    # EVENTOS INTERNOS
    # ============================================================

    def _ao_redimensionar_tela(self, evento):

        centro = (evento.width // 2, evento.height // 2)

        self._tela.coords(self._item_imagem, *centro)
        self._tela.coords(self._item_mensagem, *centro)

    def _ao_mover_deslizante(self, _valor=None):

        self._atualizar_rotulos_parametros()

        self._ao_mudar_parametros(
            self._limiar.get() / 100,
            self._intervalo.get(),
        )

    def _atualizar_rotulos_parametros(self):

        self._rotulo_limiar.config(text=f"{self._limiar.get():.0f}%")
        self._rotulo_intervalo.config(text=f"{self._intervalo.get():.1f} s")

    # ============================================================
    # MÉTODOS USADOS PELA JANELA PRINCIPAL
    # ============================================================

    def tamanho_do_video(self):
        """(largura, altura) em pixels do espaço disponível para o vídeo."""

        return self._tela.winfo_width(), self._tela.winfo_height()

    def mostrar_imagem(self, imagem_tk):
        """Exibe um frame já convertido para o formato do Tkinter."""

        self._imagem_video = imagem_tk

        self._tela.itemconfigure(self._item_imagem, image=imagem_tk)
        self._tela.itemconfigure(self._item_mensagem, text="")

    def mostrar_mensagem(self, texto):
        """Apaga o vídeo e escreve uma mensagem no lugar dele."""

        self._imagem_video = None

        self._tela.itemconfigure(self._item_imagem, image="")
        self._tela.itemconfigure(self._item_mensagem, text=texto)

    def definir_status(self, titulo, detalhe, cor):
        """Atualiza a faixa de status (texto grande, texto de apoio e cor)."""

        for componente in (self._faixa_status, self._rotulo_status, self._rotulo_detalhe):
            componente.config(bg=cor)

        self._rotulo_status.config(text=titulo)
        self._rotulo_detalhe.config(text=detalhe)

    def definir_botao_camera(self, texto, estilo, habilitado=True):

        self._botao_camera.config(
            text=texto,
            style=estilo,
            state="normal" if habilitado else "disabled",
        )

    def definir_desempenho(self, texto):

        self._rotulo_desempenho.config(text=texto)

    def definir_contagem(self, nome_classe, quantidade):
        """Atualiza o texto do botão de coleta com o total de imagens da classe."""

        botao, atalho = self._botoes_captura[nome_classe]

        botao.config(text=f"[{atalho}]  Salvar em {nome_classe}  ({quantidade})")
