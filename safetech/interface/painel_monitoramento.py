"""
Painel de monitoramento de UMA área (a página de cada área à esquerda).

De cima para baixo, na ordem em que o operador usa:

    1) CABEÇALHO DA CÂMERA -> qual câmera é, se comanda a catraca, e os
                              botões: ligar/desligar, capturar foto e
                              trocar a câmera;
    2) VÍDEO               -> a imagem com as caixas e as legendas "ao
                              vivo". Sem vídeo, uma tela de espera com
                              ícone, explicação e o botão de ligar no meio;
    3) FAIXA DE STATUS     -> liberado / negado (cheia de cor, para ser
                              vista de longe) ou aguardando / câmera
                              desligada (discreta, num cartão);
    4) FISCALIZAÇÃO        -> setor, modo (catraca ou vigilância) e os
                              EPIs exigidos, como "chips" que se ligam e
                              desligam com um clique.

O painel só exibe e avisa: as ações de verdade (ligar câmera, mudar o
setor, o modo ou os EPIs, capturar a foto) são funções recebidas da
janela principal.
"""

import tkinter as tk
from tkinter import ttk

from safetech import config
from safetech.interface.componentes import dica
from safetech.interface.tema import CORES, FONTES
from safetech.nucleo.epis import nome_do_epi
from safetech.nucleo.icones import desenhar_icone_epi

from PIL import ImageTk


# Tamanho (px) do ícone dentro de cada botão de EPI exigido
TAMANHO_ICONE_CHIP = 16

# Distância (px) entre as legendas sobre o vídeo e a borda dele
MARGEM_LEGENDA = 10

# Situações "fortes" da faixa: ela fica cheia de cor (verde, vermelho,
# amarelo) com texto branco. As outras (aguardando, câmera desligada,
# carregando) ficam num cartão discreto, com um filete colorido.
CHAVES_DE_COR_FORTE = ("sucesso", "perigo", "alerta")


def icone_da_cor(cor) -> str:
    """
    Símbolo à esquerda da faixa, escolhido pela cor dela (cada cor já é
    uma situação). Repete a informação da cor para quem não distingue cores.
    """

    simbolos = {
        CORES["sucesso"]: "✔",   # ✔
        CORES["perigo"]: "✖",    # ✖
        CORES["alerta"]: "◔",    # ◔
    }

    return simbolos.get(cor, "●")   # ●


class PainelMonitoramento(ttk.Frame):

    def __init__(
        self,
        pai,
        epis_do_modelo,
        modos_disponiveis,
        modo_inicial,
        setor_inicial,
        exigidos_iniciais,
        ao_mudar_modo,
        ao_escolher_setor,
        ao_mudar_fiscalizacao,
        ao_alternar_camera,
        ao_capturar_foto=None,
        ao_trocar_camera=None,
        ao_alternar_calibracao=None,
        ao_mudar_limiar=None,
        limiar_inicial=config.LIMIAR_CONFIANCA_PADRAO,
    ):
        """
        epis_do_modelo        -> EPIs que o modelo reconhece: só eles podem
                                 ser exigidos. Sem nenhum (modelo antigo),
                                 a fiscalização fica desativada.
        modos_disponiveis     -> modos cujo detector está instalado.
        ao_mudar_modo         -> chamado com o modo escolhido.
        ao_escolher_setor     -> chamado com o nome do setor escolhido.
        ao_mudar_fiscalizacao -> chamado com (setor, exigidos) ao marcar
                                 ou desmarcar um EPI à mão.
        ao_alternar_camera    -> liga ou desliga a câmera da área.
        ao_capturar_foto      -> botão "Foto" (sem argumentos).
        ao_trocar_camera      -> botão "Trocar câmera" (abre as Configurações).
        ao_alternar_calibracao-> botão "Calibrar": chamado com True/False.
        ao_mudar_limiar       -> controle de confiança do modo calibração:
                                 chamado com o valor (0 a 1).
        """

        super().__init__(pai, style="Painel.TFrame", padding=(0, 8, 0, 0))

        self._epis_do_modelo = set(epis_do_modelo)
        self._modos_disponiveis = set(modos_disponiveis)

        self._ao_mudar_modo = ao_mudar_modo
        self._ao_escolher_setor = ao_escolher_setor
        self._ao_mudar_fiscalizacao = ao_mudar_fiscalizacao
        self._ao_alternar_camera = ao_alternar_camera
        self._ao_alternar_calibracao = ao_alternar_calibracao or (lambda _ligado: None)
        self._ao_mudar_limiar = ao_mudar_limiar or (lambda _valor: None)

        # Modo calibração: barras de confiança no vídeo e o controle do limiar
        self._calibrando = tk.BooleanVar(value=False)
        self._limiar_calibracao = tk.DoubleVar(value=limiar_inicial * 100)

        # Fiscalização da área: modo, setor e um "chip" por EPI
        self._modo = tk.StringVar(value=modo_inicial)
        self._setor = tk.StringVar(value=setor_inicial)

        self._exigir = {
            chave: tk.BooleanVar(value=chave in exigidos_iniciais and chave in self._epis_do_modelo)
            for chave in config.EPIS
        }

        self._chips = {}

        # Ícones dos chips: um por EPI e por estado (normal, marcado, desativado)
        self._icones_chips = {}

        # Referência à imagem em exibição (sem ela o Tkinter apaga a imagem)
        self._imagem_video = None

        # A coluna única e a linha do vídeo ocupam todo o espaço que
        # sobrar; as outras linhas ficam com a altura do conteúdo.
        self.columnconfigure(0, weight=1)
        self.rowconfigure(1, weight=1)

        self._montar_cabecalho(ao_capturar_foto, ao_trocar_camera)
        self._montar_video()
        self._montar_calibracao()
        self._montar_status()
        self._montar_controles()

    # ============================================================
    # MONTAGEM
    # ============================================================

    def _montar_cabecalho(self, ao_capturar_foto, ao_trocar_camera):
        """Qual câmera é, se comanda a catraca, e os botões da câmera."""

        cabeca = ttk.Frame(self, style="Painel.TFrame")
        cabeca.grid(row=0, column=0, sticky="ew", pady=(0, 8))

        # O botão principal vai primeiro (à direita) para nunca ser cortado
        self._botao_camera = ttk.Button(
            cabeca,
            text="Carregando...",
            style="Primario.TButton",
            command=self._ao_alternar_camera,
            takefocus=False,
            width=15,
            state="disabled",
        )
        self._botao_camera.pack(side="right")

        dica(self._botao_camera, "Liga ou desliga a câmera desta área (tecla Espaço)")

        # Guarda o momento (imagem com caixas e carimbo) fora do log
        self._botao_foto = ttk.Button(
            cabeca,
            text="Foto",
            style="Secundario.TButton",
            command=ao_capturar_foto or (lambda: None),
            takefocus=False,
            state="disabled",
        )
        self._botao_foto.pack(side="right", padx=(0, 8))

        dica(self._botao_foto, "Guarda a imagem de agora, com as caixas e a data, em auditoria/capturas (fora do log)")

        # Liga e desliga as barras de confiança sobre as pessoas
        botao_calibrar = ttk.Checkbutton(
            cabeca,
            text="Calibrar",
            variable=self._calibrando,
            style="Alternar.Toolbutton",
            command=self._ao_clicar_calibrar,
            takefocus=False,
        )
        botao_calibrar.pack(side="right", padx=(0, 8))

        dica(botao_calibrar, "Mostra a confiança de cada EPI sobre as pessoas, para ajustar a confiança mínima vendo o efeito")

        botao_trocar = ttk.Button(
            cabeca,
            text="Trocar câmera",
            style="Secundario.TButton",
            command=ao_trocar_camera or (lambda: None),
            takefocus=False,
        )
        botao_trocar.pack(side="right", padx=(0, 8))

        dica(botao_trocar, "Escolhe outra webcam ou uma câmera IP para esta área")

        # À esquerda: qual câmera esta área usa (webcam N ou o nome da
        # câmera IP; nunca o endereço, que pode ter a senha). Quem comanda
        # a catraca já aparece na barra de áreas ("· catraca").
        self._rotulo_camera = ttk.Label(cabeca, text="", style="Painel.TLabel", font=FONTES["texto_negrito"])
        self._rotulo_camera.pack(side="left")

        # Guardado, mas não mostrado aqui: o cabeçalho divide a linha com
        # quatro botões, e quem comanda a catraca já aparece na barra de
        # áreas ("· catraca")
        self._rotulo_catraca = ttk.Label(cabeca, text="", style="Suave.Painel.TLabel")

    def _montar_video(self):

        # Canvas em vez de Label: permite centralizar a imagem, desenhar
        # a tela de espera e pôr legendas por cima do vídeo.
        self._tela = tk.Canvas(
            self,
            bg=CORES["video"],
            highlightthickness=0,
            width=320,
            height=200,
        )
        self._tela.grid(row=1, column=0, sticky="nsew")

        self._item_imagem = self._tela.create_image(0, 0, anchor="center")

        # ------------------------------------------------------
        # TELA DE ESPERA (sem vídeo): ícone, título, detalhe e botão
        # ------------------------------------------------------

        cor_icone = CORES["texto_suave"]

        # Ícone de câmera: corpo, visor em cima e a lente redonda
        self._icone_espera = [
            self._tela.create_rectangle(0, 0, 0, 0, outline=cor_icone, width=3),
            self._tela.create_rectangle(0, 0, 0, 0, outline=cor_icone, width=3),
            self._tela.create_oval(0, 0, 0, 0, outline=cor_icone, width=3),
        ]

        self._item_mensagem = self._tela.create_text(
            0, 0, text="", fill=CORES["texto"], font=FONTES["titulo"], justify="center", anchor="n"
        )

        self._item_detalhe = self._tela.create_text(
            0, 0, text="", fill=CORES["texto_suave"], font=FONTES["texto"], justify="center", anchor="n"
        )

        # Botão no meio da tela de espera: o caminho mais curto para ligar
        self._botao_espera = ttk.Button(
            self._tela,
            text="",
            style="Primario.TButton",
            command=self._ao_alternar_camera,
            takefocus=False,
        )

        self._item_botao_espera = self._tela.create_window(0, 0, window=self._botao_espera, anchor="n", state="hidden")

        # ------------------------------------------------------
        # LEGENDAS SOBRE O VÍDEO (como num monitor de segurança)
        # ------------------------------------------------------
        #
        #   à esquerda -> ● AO VIVO, nome da área, data e hora
        #   à direita  -> resolução, quadros por segundo, análises e pessoas
        #
        # Cada legenda é um texto sobre um retângulo escuro, para ser
        # lida em cima de qualquer imagem. Ficam escondidas sem vídeo.

        self._legendas = {}

        for lado, ancora in (("esquerda", "nw"), ("direita", "ne")):

            fundo = self._tela.create_rectangle(0, 0, 0, 0, fill=CORES["legenda_video"], outline="", state="hidden")

            texto = self._tela.create_text(
                0, 0, text="", anchor=ancora, fill=CORES["texto_legenda"], font=FONTES["legenda_video"], state="hidden"
            )

            self._legendas[lado] = (fundo, texto)

        # Ponto vermelho do "AO VIVO" (pisca uma vez por segundo)
        self._ponto_ao_vivo = self._tela.create_oval(0, 0, 0, 0, fill=CORES["perigo"], outline="", state="hidden")

        # Mantém tudo no lugar quando o painel muda de tamanho
        self._tela.bind("<Configure>", self._ao_redimensionar_tela)

    def _montar_calibracao(self):
        """
        Linha que só aparece no modo calibração, logo abaixo do vídeo:
        o controle da confiança mínima, para ver o efeito nas barras na hora.
        """

        self._linha_calibracao = ttk.Frame(self, style="Cartao.TFrame", padding=(14, 8))

        self._linha_calibracao.columnconfigure(1, weight=1)

        ttk.Label(self._linha_calibracao, text="Confiança mínima", style="Cartao.TLabel", font=FONTES["texto_negrito"]).grid(
            row=0, column=0, sticky="w", padx=(0, 12)
        )

        ttk.Scale(
            self._linha_calibracao,
            from_=config.LIMIAR_CONFIANCA_MINIMO * 100,
            to=config.LIMIAR_CONFIANCA_MAXIMO * 100,
            orient="horizontal",
            variable=self._limiar_calibracao,
            command=self._ao_mover_limiar,
            takefocus=False,
        ).grid(row=0, column=1, sticky="ew")

        self._rotulo_limiar = ttk.Label(self._linha_calibracao, text="", style="Cartao.TLabel", font=FONTES["texto_negrito"], width=5)
        self._rotulo_limiar.grid(row=0, column=2, sticky="e", padx=(12, 0))

        ttk.Label(
            self._linha_calibracao,
            text="Verde: passou do limiar (risco branco) · Vermelha: não passou · Cinza: não exigido",
            style="Suave.Cartao.TLabel",
        ).grid(row=1, column=0, columnspan=3, sticky="w", pady=(4, 0))

        self._atualizar_rotulo_limiar()

    def _montar_status(self):

        self._faixa_status = tk.Frame(self, bg=CORES["cartao"])
        self._faixa_status.grid(row=3, column=0, sticky="ew", pady=(8, 8))

        self._faixa_status.columnconfigure(2, weight=1)

        # Filete colorido à esquerda (aparece nas situações discretas)
        self._filete_status = tk.Frame(self._faixa_status, bg=CORES["borda"], width=4)
        self._filete_status.grid(row=0, column=0, rowspan=2, sticky="ns")

        # Símbolo da situação (✔ ✖ ◔ ●), à esquerda dos textos
        self._icone_status = tk.Label(
            self._faixa_status,
            text=icone_da_cor(None),
            font=FONTES["status_icone"],
            bg=CORES["cartao"],
            fg=CORES["texto_suave"],
            width=2,
        )
        self._icone_status.grid(row=0, column=1, rowspan=2, sticky="w", padx=(12, 10), pady=8)

        self._rotulo_status = tk.Label(
            self._faixa_status,
            text="",
            font=FONTES["status_titulo"],
            bg=CORES["cartao"],
            fg=CORES["texto"],
            anchor="w",
        )
        self._rotulo_status.grid(row=0, column=2, sticky="ew", padx=(0, 16), pady=(8, 0))

        self._rotulo_detalhe = tk.Label(
            self._faixa_status,
            text="",
            font=FONTES["status_detalhe"],
            bg=CORES["cartao"],
            fg=CORES["texto_suave"],
            anchor="w",
            justify="left",
        )
        self._rotulo_detalhe.grid(row=1, column=2, sticky="ew", padx=(0, 16), pady=(0, 10))

        # O detalhe quebra a linha na largura da faixa (sem isso, um
        # texto comprido é cortado na borda da janela)
        self._rotulo_detalhe.bind(
            "<Configure>",
            lambda evento: self._rotulo_detalhe.config(wraplength=max(100, evento.width - 4)),
        )

    # ------------------------------------------------------
    # FISCALIZAÇÃO: setor, modo e EPIs exigidos
    # ------------------------------------------------------

    def _montar_controles(self):

        cartao = ttk.Frame(self, style="Cartao.TFrame", padding=(14, 10))
        cartao.grid(row=4, column=0, sticky="ew")

        cartao.columnconfigure(1, weight=1)

        # ---------------- linha 1: setor e modo ----------------

        ttk.Label(cartao, text="Setor", style="Suave.Cartao.TLabel").grid(row=0, column=0, sticky="w", padx=(0, 10))

        linha = ttk.Frame(cartao, style="Cartao.TFrame")
        linha.grid(row=0, column=1, sticky="ew")

        # Lista de setores prontos. "readonly": só dá para escolher da lista
        self._caixa_setor = ttk.Combobox(
            linha,
            textvariable=self._setor,
            values=list(config.SETORES),
            state="readonly",
            width=20,
            takefocus=False,
        )
        self._caixa_setor.pack(side="left")
        self._caixa_setor.bind("<<ComboboxSelected>>", self._ao_escolher_setor_na_lista)

        # Modo à direita: botões lado a lado em que só um fica marcado
        grupo_modo = ttk.Frame(linha, style="Cartao.TFrame")
        grupo_modo.pack(side="right")

        ttk.Label(grupo_modo, text="Modo", style="Suave.Cartao.TLabel").pack(side="left", padx=(12, 8))

        for modo, nome in config.MODOS_DETECCAO.items():

            botao = ttk.Radiobutton(
                grupo_modo,
                text=nome,
                value=modo,
                variable=self._modo,
                style="Modo.Toolbutton",
                command=lambda: self._ao_mudar_modo(self._modo.get()),
                takefocus=False,
            )
            botao.pack(side="left", padx=(0, 2))

            # Modo cujo detector não foi baixado não pode ser escolhido
            if modo not in self._modos_disponiveis:
                botao.state(["disabled"])

        # ---------------- linha 2: EPIs exigidos ----------------
        #
        # O sistema continua enxergando todos os EPIs: ligar um chip só
        # define quais contam para liberar (ou estar em conformidade).

        ttk.Label(cartao, text="Exige", style="Suave.Cartao.TLabel").grid(
            row=1, column=0, sticky="w", padx=(0, 10), pady=(10, 0)
        )

        linha_epis = ttk.Frame(cartao, style="Cartao.TFrame")
        linha_epis.grid(row=1, column=1, sticky="w", pady=(10, 0))

        for chave in config.EPIS:

            chip = ttk.Checkbutton(
                linha_epis,
                text=nome_do_epi(chave),
                variable=self._exigir[chave],
                style="Chip.Toolbutton",
                command=self._ao_marcar_exigido,
                takefocus=False,
            )
            chip.pack(side="left", padx=(0, 6))

            self._chips[chave] = chip

            # EPI que o modelo não reconhece não pode ser exigido
            if chave not in self._epis_do_modelo:
                chip.state(["disabled"])

        self.atualizar_icones()
        self._atualizar_chips()

        # Modelo antigo: não distingue os EPIs, então não há o que escolher
        if not self._epis_do_modelo & set(config.EPIS):

            self._caixa_setor.state(["disabled"])

            ttk.Label(
                cartao,
                text="O modelo instalado ainda não distingue os equipamentos. "
                     "Colete imagens (Configurações > Coleta) e rode o treinar.py.",
                style="Suave.Cartao.TLabel",
            ).grid(row=2, column=0, columnspan=2, sticky="w", pady=(6, 0))

    # ============================================================
    # EVENTOS INTERNOS
    # ============================================================

    def _ao_redimensionar_tela(self, _evento=None):

        largura = self._tela.winfo_width()
        altura = self._tela.winfo_height()

        self._tela.coords(self._item_imagem, largura // 2, altura // 2)

        self._posicionar_espera()
        self._posicionar_legendas()

    def _posicionar_espera(self):
        """Centraliza ícone, textos e botão da tela de espera."""

        largura = self._tela.winfo_width()
        altura = self._tela.winfo_height()

        centro_x = largura // 2

        # O bloco inteiro (ícone + textos + botão) fica no meio da tela
        topo = altura // 2 - 80

        corpo, visor, lente = self._icone_espera

        self._tela.coords(corpo, centro_x - 34, topo + 10, centro_x + 34, topo + 56)
        self._tela.coords(visor, centro_x - 12, topo, centro_x + 12, topo + 10)
        self._tela.coords(lente, centro_x - 13, topo + 20, centro_x + 13, topo + 46)

        self._tela.coords(self._item_mensagem, centro_x, topo + 74)
        self._tela.itemconfigure(self._item_mensagem, width=max(100, largura - 60))

        caixa = self._tela.bbox(self._item_mensagem)
        y = (caixa[3] if caixa else topo + 100) + 6

        self._tela.coords(self._item_detalhe, centro_x, y)
        self._tela.itemconfigure(self._item_detalhe, width=max(100, largura - 60))

        caixa = self._tela.bbox(self._item_detalhe)
        y = (caixa[3] if caixa else y + 20) + 16

        self._tela.coords(self._item_botao_espera, centro_x, y)

    def _posicionar_legendas(self):
        """Encosta as legendas nos cantos de cima e ajusta o fundo ao tamanho do texto."""

        largura = self._tela.winfo_width()
        margem = MARGEM_LEGENDA

        fundo, texto = self._legendas["esquerda"]

        # À esquerda sobra espaço para o ponto do "AO VIVO"
        self._tela.coords(texto, margem + 22, margem + 6)
        self._ajustar_fundo(fundo, texto, folga_esquerda=22)

        caixa = self._tela.bbox(texto)

        if caixa:
            meio = (caixa[1] + caixa[3]) // 2
            x = margem + 8
            self._tela.coords(self._ponto_ao_vivo, x, meio - 4, x + 8, meio + 4)

        fundo, texto = self._legendas["direita"]

        self._tela.coords(texto, largura - margem - 10, margem + 6)
        self._ajustar_fundo(fundo, texto)

    def _ajustar_fundo(self, fundo, texto, folga_esquerda=10):
        """Estica o retângulo escuro para envolver o texto, com uma folga em volta."""

        caixa = self._tela.bbox(texto)

        if caixa:
            x1, y1, x2, y2 = caixa
            self._tela.coords(fundo, x1 - folga_esquerda, y1 - 5, x2 + 10, y2 + 5)

    def _ao_clicar_calibrar(self):

        ligado = self._calibrando.get()

        # A linha do controle aparece entre o vídeo e a faixa de status
        if ligado:
            self._linha_calibracao.grid(row=2, column=0, sticky="ew", pady=(8, 0))
        else:
            self._linha_calibracao.grid_remove()

        self._ao_alternar_calibracao(ligado)

    def _ao_mover_limiar(self, _valor=None):

        self._atualizar_rotulo_limiar()

        self._ao_mudar_limiar(self._limiar_calibracao.get() / 100)

    def _atualizar_rotulo_limiar(self):

        self._rotulo_limiar.config(text=f"{self._limiar_calibracao.get():.0f}%")

    def definir_limiar(self, valor):
        """Mostra a confiança mínima (0 a 1) mudada em outro lugar. Não avisa ninguém."""

        self._limiar_calibracao.set(valor * 100)
        self._atualizar_rotulo_limiar()

    @property
    def calibrando(self) -> bool:
        return self._calibrando.get()

    def _exigidos(self):
        """Chaves dos EPIs marcados como obrigatórios, na ordem de config.EPIS."""

        return tuple(chave for chave in config.EPIS if self._exigir[chave].get())

    def atualizar_icones(self):
        """
        Põe o desenho do EPI em cada chip, na cor do texto de cada estado
        (apagado, marcado em azul, desativado). Chamado de novo depois de
        trocar o tema: os ícones são imagens, não acompanham sozinhos.
        """

        for chave, chip in self._chips.items():

            imagens = {
                estado: ImageTk.PhotoImage(desenhar_icone_epi(chave, TAMANHO_ICONE_CHIP, cor))
                for estado, cor in (("normal", CORES["texto_suave"]), ("marcado", "white"), ("desativado", CORES["borda"]))
            }

            self._icones_chips[chave] = imagens

            chip.configure(
                image=(imagens["normal"], "disabled", imagens["desativado"], "selected", imagens["marcado"]),
                compound="left",
            )

    def _atualizar_chips(self):
        """Chip ligado ganha um "✓" antes do nome: não depende só da cor."""

        for chave, chip in self._chips.items():

            # Espaço entre o ícone e o nome; o "✓" repete o "marcado" sem depender da cor
            marca = "  ✓ " if self._exigir[chave].get() else "  "

            chip.config(text=marca + nome_do_epi(chave))

    def _ao_escolher_setor_na_lista(self, _evento=None):

        # Tira a seleção azul do texto, que o Tkinter deixa na caixa
        self._caixa_setor.selection_clear()

        self._ao_escolher_setor(self._setor.get())

    def _ao_marcar_exigido(self):
        """
        Ligar ou desligar um EPI à mão: se a combinação bater com um
        setor pronto, o nome dele aparece; senão, vira "Personalizado".
        """

        self._atualizar_chips()

        marcados = set(self._exigidos())

        setor = config.SETOR_PERSONALIZADO

        for nome, exigidos_do_setor in config.SETORES.items():

            if set(exigidos_do_setor) == marcados:
                setor = nome
                break

        self._setor.set(setor)

        self._ao_mudar_fiscalizacao(setor, self._exigidos())

    # ============================================================
    # MÉTODOS USADOS PELA JANELA PRINCIPAL
    # ============================================================

    def mostrar_fiscalizacao(self, setor, exigidos):
        """Mostra o setor e liga os EPIs exigidos. Só muda a tela: não avisa ninguém."""

        self._setor.set(setor)

        for chave, variavel in self._exigir.items():
            variavel.set(chave in exigidos)

        self._atualizar_chips()

    def definir_modo(self, modo):
        """Marca o modo (catraca ou vigilância) mudado em outro lugar. Não avisa ninguém."""

        self._modo.set(modo)

    def definir_camera(self, nome_camera, comanda_catraca):
        """Nome da câmera da área e a etiqueta "comanda a catraca"."""

        self._rotulo_camera.config(text=nome_camera)

        # Curto: o cabeçalho divide a linha com quatro botões
        self._rotulo_catraca.config(text="· catraca" if comanda_catraca else "")

    def tamanho_do_video(self):
        """(largura, altura) em pixels do espaço disponível para o vídeo."""

        return self._tela.winfo_width(), self._tela.winfo_height()

    def mostrar_imagem(self, imagem_tk):
        """Exibe um frame já convertido para o formato do Tkinter."""

        self._imagem_video = imagem_tk

        self._tela.itemconfigure(self._item_imagem, image=imagem_tk)

        self._esconder_espera()

    def mostrar_mensagem(self, texto, botao=None):
        """
        Apaga o vídeo e mostra a tela de espera.

        texto -> a primeira linha é o título; as outras, a explicação
        botao -> texto do botão no meio da tela (liga a câmera); None = sem botão
        """

        self._imagem_video = None

        self._tela.itemconfigure(self._item_imagem, image="")

        titulo, _, detalhe = texto.partition("\n")

        self._tela.itemconfigure(self._item_mensagem, text=titulo, state="normal")
        self._tela.itemconfigure(self._item_detalhe, text=detalhe, state="normal")

        for item in self._icone_espera:
            self._tela.itemconfigure(item, state="normal")

        if botao:
            self._botao_espera.config(text=botao)
            self._tela.itemconfigure(self._item_botao_espera, state="normal")
        else:
            self._tela.itemconfigure(self._item_botao_espera, state="hidden")

        self._posicionar_espera()

        # Sem vídeo, as legendas de "ao vivo" não fazem sentido
        self.definir_legenda("", "")

    def mensagem(self):
        """(título, detalhe) da tela de espera; vazios com vídeo (usado nos testes)."""

        if self._tela.itemcget(self._item_mensagem, "state") == "hidden":
            return "", ""

        return self._tela.itemcget(self._item_mensagem, "text"), self._tela.itemcget(self._item_detalhe, "text")

    def _esconder_espera(self):

        for item in (*self._icone_espera, self._item_mensagem, self._item_detalhe, self._item_botao_espera):
            self._tela.itemconfigure(item, state="hidden")

    def definir_legenda(self, esquerda, direita, ponto_aceso=True):
        """
        Legendas sobre o vídeo. Texto da esquerda vazio esconde as duas.

        ponto_aceso -> o ponto vermelho do "AO VIVO" (alternar faz piscar)
        """

        visivel = "normal" if esquerda else "hidden"

        for lado, texto_lado in (("esquerda", esquerda), ("direita", direita)):

            fundo, texto = self._legendas[lado]

            self._tela.itemconfigure(texto, text=texto_lado, state=visivel)
            self._tela.itemconfigure(fundo, state=visivel if texto_lado else "hidden")

        self._tela.itemconfigure(self._ponto_ao_vivo, state=visivel if ponto_aceso else "hidden")

        # As legendas ficam por cima da imagem
        for fundo, texto in self._legendas.values():
            self._tela.tag_raise(fundo)
            self._tela.tag_raise(texto)

        self._tela.tag_raise(self._ponto_ao_vivo)

        if esquerda:
            self._posicionar_legendas()

    def legenda(self):
        """(esquerda, direita): os textos das legendas sobre o vídeo (usado nos testes)."""

        return tuple(self._tela.itemcget(texto, "text") for _, texto in self._legendas.values())

    def definir_status(self, titulo, detalhe, cor):
        """
        Atualiza a faixa de status.

        Liberado, negado e analisando: faixa CHEIA da cor, texto branco
        (precisa ser vista de longe, na catraca). Aguardando, câmera
        desligada e carregando: cartão discreto com um filete da cor.
        """

        forte = cor in (CORES[chave] for chave in CHAVES_DE_COR_FORTE)

        if forte:
            fundo, texto, apoio, filete = cor, "white", "white", cor
        else:
            fundo, texto, apoio, filete = CORES["cartao"], CORES["texto"], CORES["texto_suave"], cor

        self._faixa_status.config(bg=fundo)
        self._filete_status.config(bg=filete)

        self._icone_status.config(text=icone_da_cor(cor), bg=fundo, fg=texto if forte else cor)
        self._rotulo_status.config(text=titulo, bg=fundo, fg=texto)
        self._rotulo_detalhe.config(text=detalhe, bg=fundo, fg=apoio)

    def status(self):
        """(título, detalhe) da faixa de status (usado nos testes)."""

        return self._rotulo_status.cget("text"), self._rotulo_detalhe.cget("text")

    def definir_botao_camera(self, texto, estilo, habilitado=True):
        """Botão principal da câmera; "Foto" só funciona com vídeo."""

        self._botao_camera.config(
            text=texto,
            style=estilo,
            state="normal" if habilitado else "disabled",
        )

        # Só há o que capturar com a câmera ligada (botão virou "Parar")
        com_video = habilitado and estilo == "Perigo.TButton"

        self._botao_foto.state(["!disabled"] if com_video else ["disabled"])
