"""
Painel de monitoramento (lado esquerdo da janela).

Mostra o vídeo da webcam, a faixa de status do acesso e três cartões:

    Fiscalização -> qual setor está sendo fiscalizado e quais EPIs ele exige
    Ajustes      -> limiar de confiança, intervalo de análise e botão da câmera
    Coleta       -> salva imagens rotuladas para treinar o modelo

O painel só exibe e avisa: as ações de verdade (ligar câmera, salvar
imagem, mudar parâmetros) são funções recebidas da janela principal.
"""

import tkinter as tk
from tkinter import ttk

from safetech import config
from safetech.interface.tema import CORES, FONTES
from safetech.nucleo.epis import nome_do_epi


class PainelMonitoramento(ttk.Frame):

    def __init__(
        self,
        pai,
        epis_do_modelo,
        setor_inicial,
        exigidos_iniciais,
        limiar_inicial,
        intervalo_inicial,
        ao_alternar_camera,
        ao_salvar_imagem,
        ao_mudar_parametros,
        ao_mudar_fiscalizacao,
    ):
        """
        epis_do_modelo -> chaves dos EPIs que o modelo instalado reconhece.
                          Só eles podem ser exigidos (não dá para fiscalizar
                          o que o modelo não sabe ver).
        """

        super().__init__(pai, style="Painel.TFrame", padding=18)

        self._epis_do_modelo = set(epis_do_modelo)

        self._ao_salvar_imagem = ao_salvar_imagem
        self._ao_mudar_parametros = ao_mudar_parametros
        self._ao_mudar_fiscalizacao = ao_mudar_fiscalizacao

        # Variáveis ligadas aos controles deslizantes
        self._limiar = tk.DoubleVar(value=limiar_inicial * 100)
        self._intervalo = tk.DoubleVar(value=intervalo_inicial)

        # Fiscalização: setor escolhido e uma caixa de seleção por EPI
        self._setor = tk.StringVar(value=setor_inicial)

        self._exigir = {
            chave: tk.BooleanVar(value=chave in exigidos_iniciais and chave in self._epis_do_modelo)
            for chave in config.EPIS
        }

        # Coleta: o que a pessoa na câmera está usando (rótulos da imagem)
        self._usando = {chave: tk.BooleanVar(value=False) for chave in config.EPIS}

        # Referência à imagem em exibição (sem ela o Tkinter apaga a imagem)
        self._imagem_video = None

        # A coluna única e a linha do vídeo ocupam todo o espaço que
        # sobrar; as outras linhas ficam com a altura do conteúdo.
        self.columnconfigure(0, weight=1)
        self.rowconfigure(1, weight=1)

        self._montar_cabecalho()
        self._montar_video()
        self._montar_status()
        self._montar_fiscalizacao()
        self._montar_ajustes(ao_alternar_camera)
        self._montar_coleta()

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
            height=200,
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

        self._faixa_status = tk.Frame(self, bg=CORES["neutro"], padx=18, pady=10)
        self._faixa_status.grid(row=2, column=0, sticky="ew", pady=10)

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
            justify="left",
        )
        self._rotulo_detalhe.pack(fill="x")

    # ------------------------------------------------------
    # CARTÃO: FISCALIZAÇÃO (setor e EPIs exigidos)
    # ------------------------------------------------------

    def _montar_fiscalizacao(self):

        cartao = ttk.Frame(self, style="Cartao.TFrame", padding=(14, 10))
        cartao.grid(row=3, column=0, sticky="ew")

        linha = ttk.Frame(cartao, style="Cartao.TFrame")
        linha.pack(fill="x")

        ttk.Label(
            linha, text="Fiscalização", style="Cartao.TLabel", font=FONTES["texto_negrito"]
        ).pack(side="left")

        ttk.Label(linha, text="Setor", style="Suave.Cartao.TLabel").pack(side="left", padx=(16, 6))

        # Lista de setores prontos. "readonly": só dá para escolher da lista
        self._caixa_setor = ttk.Combobox(
            linha,
            textvariable=self._setor,
            values=list(config.SETORES),
            state="readonly",
            width=24,
            takefocus=False,
        )
        self._caixa_setor.pack(side="left")
        self._caixa_setor.bind("<<ComboboxSelected>>", self._ao_escolher_setor)

        # Os EPIs ficam numa segunda linha, para caberem mesmo com a
        # janela estreita (ou com mais equipamentos cadastrados)
        linha_epis = ttk.Frame(cartao, style="Cartao.TFrame")
        linha_epis.pack(fill="x", pady=(8, 0))

        ttk.Label(linha_epis, text="EPIs exigidos", style="Suave.Cartao.TLabel").pack(side="left")

        for chave in config.EPIS:

            caixa = ttk.Checkbutton(
                linha_epis,
                text=nome_do_epi(chave),
                variable=self._exigir[chave],
                style="Cartao.TCheckbutton",
                command=self._ao_marcar_exigido,
                takefocus=False,
            )
            caixa.pack(side="left", padx=(12, 0))

            # EPI que o modelo não reconhece não pode ser exigido
            if chave not in self._epis_do_modelo:
                caixa.state(["disabled"])

        # Aviso mostrado quando o modelo instalado não distingue os EPIs
        self._rotulo_aviso_modelo = ttk.Label(cartao, text="", style="Suave.Cartao.TLabel")

        if not self._epis_do_modelo & set(config.EPIS):

            self._caixa_setor.state(["disabled"])

            self._rotulo_aviso_modelo.config(
                text="O modelo instalado ainda não distingue os equipamentos. "
                     "Colete imagens rotuladas abaixo e rode o treinar.py para ativar."
            )
            self._rotulo_aviso_modelo.pack(anchor="w", pady=(6, 0))

    # ------------------------------------------------------
    # CARTÃO: AJUSTES (limiar, intervalo, câmera)
    # ------------------------------------------------------

    def _montar_ajustes(self, ao_alternar_camera):

        cartao = ttk.Frame(self, style="Cartao.TFrame", padding=(14, 10))
        cartao.grid(row=4, column=0, sticky="ew", pady=(10, 0))

        # Três colunas: dois controles deslizantes e o botão da câmera
        cartao.columnconfigure(0, weight=1, uniform="controles")
        cartao.columnconfigure(1, weight=1, uniform="controles")

        self._rotulo_limiar = self._criar_deslizante(
            cartao,
            coluna=0,
            titulo="Confiança mínima",
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
            width=15,
            state="disabled",
        )
        self._botao_camera.grid(row=0, column=2, rowspan=2, sticky="nsew", padx=(16, 0))

        self._atualizar_rotulos_parametros()

    def _criar_deslizante(self, pai, coluna, titulo, variavel, minimo, maximo):
        """Cria um controle deslizante com título e valor; devolve o rótulo do valor."""

        # Espaço entre os dois controles
        margem = (0, 20) if coluna == 0 else (0, 0)

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

    # ------------------------------------------------------
    # CARTÃO: COLETA DE IMAGENS ROTULADAS
    # ------------------------------------------------------

    def _montar_coleta(self):

        cartao = ttk.Frame(self, style="Cartao.TFrame", padding=(14, 10))
        cartao.grid(row=5, column=0, sticky="ew", pady=(10, 0))

        cartao.columnconfigure(0, weight=1)

        linha = ttk.Frame(cartao, style="Cartao.TFrame")
        linha.grid(row=0, column=0, sticky="ew")

        # O botão é posicionado primeiro (à direita) para nunca ser
        # cortado; se faltar espaço, quem encolhe é o resumo do dataset.
        ttk.Button(
            linha,
            text="Salvar imagem  [S]",
            style="Primario.TButton",
            command=self.salvar_imagem,
            takefocus=False,
        ).pack(side="right", padx=(12, 0))

        ttk.Label(
            linha, text="Coleta de imagens", style="Cartao.TLabel", font=FONTES["texto_negrito"]
        ).pack(side="left")

        # Situação do dataset (total e quantas imagens por EPI)
        self._rotulo_dataset = ttk.Label(linha, text="", style="Suave.Cartao.TLabel")
        self._rotulo_dataset.pack(side="left", padx=(16, 0))

        # Rótulos da próxima imagem: o que a pessoa está usando agora
        linha_epis = ttk.Frame(cartao, style="Cartao.TFrame")
        linha_epis.grid(row=1, column=0, sticky="ew", pady=(8, 0))

        ttk.Label(linha_epis, text="A pessoa está usando", style="Suave.Cartao.TLabel").pack(side="left")

        for chave in config.EPIS:

            ttk.Checkbutton(
                linha_epis,
                text=nome_do_epi(chave),
                variable=self._usando[chave],
                style="Cartao.TCheckbutton",
                takefocus=False,
            ).pack(side="left", padx=(12, 0))

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

    def _exigidos(self):
        """Chaves dos EPIs marcados como obrigatórios, na ordem de config.EPIS."""

        return tuple(chave for chave in config.EPIS if self._exigir[chave].get())

    def _ao_escolher_setor(self, _evento=None):
        """Escolher um setor pronto marca de uma vez os EPIs que ele exige."""

        # Tira a seleção azul do texto, que o Tkinter deixa na caixa
        self._caixa_setor.selection_clear()

        exigidos_do_setor = config.SETORES.get(self._setor.get(), [])

        for chave, variavel in self._exigir.items():
            variavel.set(chave in exigidos_do_setor and chave in self._epis_do_modelo)

        self._avisar_fiscalizacao()

    def _ao_marcar_exigido(self):
        """
        Marcar ou desmarcar um EPI à mão: se a combinação bater com um
        setor pronto, o nome dele aparece; senão, vira "Personalizado".
        """

        marcados = set(self._exigidos())

        setor = config.SETOR_PERSONALIZADO

        for nome, exigidos_do_setor in config.SETORES.items():

            if set(exigidos_do_setor) == marcados:
                setor = nome
                break

        self._setor.set(setor)

        self._avisar_fiscalizacao()

    def _avisar_fiscalizacao(self):

        self._ao_mudar_fiscalizacao(self._setor.get(), self._exigidos())

    # ============================================================
    # MÉTODOS USADOS PELA JANELA PRINCIPAL
    # ============================================================

    def salvar_imagem(self):
        """Pede à janela principal para salvar o frame com os rótulos marcados."""

        self._ao_salvar_imagem(
            {chave for chave, variavel in self._usando.items() if variavel.get()}
        )

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

    def definir_resumo_dataset(self, total, usando_por_epi):
        """Mostra quantas imagens rotuladas existem, no total e por EPI."""

        if total == 0:
            texto = "Nenhuma imagem rotulada ainda."

        else:

            # Ex.: "128 imagens: Capacete 60, Óculos 41, ..." (quantas
            # mostram a pessoa USANDO cada equipamento)
            partes = [
                f"{nome_do_epi(chave)} {quantidade}"
                for chave, quantidade in usando_por_epi.items()
            ]

            texto = f"{total} imagens: " + ", ".join(partes)

        self._rotulo_dataset.config(text=texto)
