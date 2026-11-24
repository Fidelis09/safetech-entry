"""
Janela "Nova área" (e "Renomear área").

Pede o NOME da área (ex.: "Portaria", "Laboratório") e, para uma área
nova, qual CÂMERA ela usa. Devolve a resposta ou None se o usuário
cancelar.

A janela só coleta e confere o que foi digitado (nome vazio ou
repetido não passa); quem cria a área é a janela principal.
"""

import tkinter as tk
from tkinter import ttk

from safetech.interface.tema import CORES


def pedir_area(pai, titulo, nome_sugerido, nomes_usados, cameras=None, fonte_sugerida=None):
    """
    Mostra a janela e espera o usuário responder.

    nomes_usados   -> nomes de outras áreas (não pode repetir)
    cameras        -> lista de (texto, fonte) para escolher a câmera;
                      None = só o nome (para renomear)
    fonte_sugerida -> câmera já selecionada na lista

    Devolve (nome, fonte) — fonte é None ao só renomear — ou None.
    """

    dialogo = _DialogoArea(pai, titulo, nome_sugerido, nomes_usados, cameras, fonte_sugerida)

    # Espera a janela fechar (o resto do programa continua rodando)
    pai.wait_window(dialogo.janela)

    return dialogo.resultado


class _DialogoArea:

    def __init__(self, pai, titulo, nome_sugerido, nomes_usados, cameras, fonte_sugerida):

        self.resultado = None

        self._nomes_usados = {nome.strip().lower() for nome in nomes_usados}
        self._cameras = list(cameras) if cameras else []
        self._pede_camera = cameras is not None

        self.janela = tk.Toplevel(pai)
        self.janela.title(titulo)
        self.janela.configure(bg=CORES["painel"])
        self.janela.resizable(False, False)

        # Fica na frente da janela de quem chamou e bloqueia cliques nela
        self.janela.transient(pai)

        self._nome = tk.StringVar(value=nome_sugerido)
        self._camera = tk.StringVar()

        self._montar(titulo, fonte_sugerida)

        self.janela.bind("<Return>", lambda _evento: self._confirmar())
        self.janela.bind("<Escape>", lambda _evento: self._cancelar())
        self.janela.protocol("WM_DELETE_WINDOW", self._cancelar)

        self.janela.grab_set()
        self._campo_nome.focus_set()
        self._campo_nome.select_range(0, "end")

    # ============================================================
    # MONTAGEM
    # ============================================================

    def _montar(self, titulo, fonte_sugerida):

        corpo = ttk.Frame(self.janela, style="Painel.TFrame", padding=18)
        corpo.pack(fill="both", expand=True)

        corpo.columnconfigure(1, weight=1)

        ttk.Label(corpo, text=titulo, style="Titulo.Painel.TLabel").grid(
            row=0, column=0, columnspan=2, sticky="w", pady=(0, 12)
        )

        ttk.Label(corpo, text="Nome da área", style="Suave.Painel.TLabel").grid(
            row=1, column=0, sticky="w", padx=(0, 12), pady=4
        )

        self._campo_nome = ttk.Entry(corpo, textvariable=self._nome, width=32)
        self._campo_nome.grid(row=1, column=1, sticky="ew", pady=4)

        if self._pede_camera:

            ttk.Label(corpo, text="Câmera", style="Suave.Painel.TLabel").grid(
                row=2, column=0, sticky="w", padx=(0, 12), pady=4
            )

            self._caixa_camera = ttk.Combobox(
                corpo,
                textvariable=self._camera,
                values=[texto for texto, _ in self._cameras],
                state="readonly",
                width=30,
            )
            self._caixa_camera.grid(row=2, column=1, sticky="ew", pady=4)

            # Câmera sugerida já selecionada
            posicao = next(
                (indice for indice, (_, fonte) in enumerate(self._cameras) if fonte == fonte_sugerida),
                0,
            )

            if self._cameras:
                self._caixa_camera.current(posicao)

            ttk.Label(
                corpo,
                text="Uma webcam só pode ser usada por uma área de cada vez.\n"
                     "Câmeras IP novas são cadastradas em Configurações > Área e câmera.",
                style="Suave.Painel.TLabel",
                justify="left",
            ).grid(row=3, column=0, columnspan=2, sticky="w", pady=(8, 0))

        # Mensagem de erro (nome vazio ou repetido)
        self._rotulo_erro = ttk.Label(corpo, text="", style="Painel.TLabel", foreground=CORES["perigo_texto"])
        self._rotulo_erro.grid(row=4, column=0, columnspan=2, sticky="w", pady=(10, 0))

        botoes = ttk.Frame(corpo, style="Painel.TFrame")
        botoes.grid(row=5, column=0, columnspan=2, sticky="e", pady=(12, 0))

        ttk.Button(botoes, text="Cancelar", style="Secundario.TButton", command=self._cancelar).pack(
            side="left", padx=(0, 8)
        )
        ttk.Button(botoes, text="Confirmar", style="Primario.TButton", command=self._confirmar).pack(side="left")

    # ============================================================
    # RESPOSTA
    # ============================================================

    def _confirmar(self):

        nome = self._nome.get().strip()

        if not nome:
            self._rotulo_erro.config(text="Dê um nome para a área.")
            return

        if nome.lower() in self._nomes_usados:
            self._rotulo_erro.config(text="Já existe uma área com esse nome.")
            return

        fonte = None

        if self._pede_camera:

            posicao = self._caixa_camera.current()

            if posicao < 0:
                self._rotulo_erro.config(text="Escolha a câmera da área.")
                return

            fonte = self._cameras[posicao][1]

        self.resultado = (nome, fonte)

        self.janela.destroy()

    def _cancelar(self):

        self.resultado = None

        self.janela.destroy()
