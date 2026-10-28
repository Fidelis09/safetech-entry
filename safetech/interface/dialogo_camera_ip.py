"""
Janela "Adicionar câmera IP".

Pede ao usuário o nome da câmera, o endereço do vídeo e, se a câmera
pedir, o usuário e a senha. Devolve (nome, endereço completo) ou None
se o usuário cancelar.

A janela só coleta e confere o que foi digitado; quem salva a câmera
e passa a usá-la é a janela principal.
"""

import tkinter as tk
from tkinter import ttk

from safetech.interface.tema import CORES
from safetech.servicos.camera import montar_endereco


# Começos de endereço aceitos (protocolos que o FFMPEG abre)
PROTOCOLOS_ACEITOS = ("rtsp://", "http://", "https://")

TEXTO_AJUDA = (
    "Exemplos de endereço:\n"
    "   Intelbras:  rtsp://192.168.0.50:554/cam/realmonitor?channel=1&subtype=1\n"
    "   Hikvision:  rtsp://192.168.0.50:554/Streaming/Channels/102\n"
    "   Celular (app IP Webcam):  http://192.168.0.20:8080/video\n\n"
    "Dica: prefira o stream de qualidade menor (substream). A análise fica mais rápida.\n"
    "A câmera precisa estar na mesma rede que este computador."
)


def pedir_camera_ip(pai, nome_sugerido):
    """
    Mostra a janela e espera o usuário responder.

    Devolve (nome, endereço) ou None. O endereço já vem com usuário e
    senha embutidos (rtsp://usuario:senha@...), pronto para abrir.
    """

    dialogo = _DialogoCameraIP(pai, nome_sugerido)

    # Espera a janela fechar (o resto do programa continua rodando)
    pai.wait_window(dialogo.janela)

    return dialogo.resultado


class _DialogoCameraIP:

    def __init__(self, pai, nome_sugerido):

        self.resultado = None

        self.janela = tk.Toplevel(pai)
        self.janela.title("Adicionar câmera IP")
        self.janela.configure(bg=CORES["painel"])
        self.janela.resizable(False, False)

        # Fica na frente da janela principal e bloqueia cliques nela
        # enquanto estiver aberta
        self.janela.transient(pai)

        self._nome = tk.StringVar(value=nome_sugerido)
        self._endereco = tk.StringVar(value="rtsp://")
        self._usuario = tk.StringVar()
        self._senha = tk.StringVar()

        self._montar()

        self.janela.bind("<Return>", lambda _evento: self._confirmar())
        self.janela.bind("<Escape>", lambda _evento: self._cancelar())
        self.janela.protocol("WM_DELETE_WINDOW", self._cancelar)

        self.janela.grab_set()
        self._campo_endereco.focus_set()
        self._campo_endereco.icursor("end")

    # ============================================================
    # MONTAGEM
    # ============================================================

    def _montar(self):

        corpo = ttk.Frame(self.janela, style="Painel.TFrame", padding=18)
        corpo.pack(fill="both", expand=True)

        corpo.columnconfigure(1, weight=1)

        ttk.Label(
            corpo, text="Adicionar câmera IP", style="Titulo.Painel.TLabel"
        ).grid(row=0, column=0, columnspan=2, sticky="w", pady=(0, 12))

        self._criar_campo(corpo, 1, "Nome", self._nome)
        self._campo_endereco = self._criar_campo(corpo, 2, "Endereço do vídeo", self._endereco, largura=58)
        self._criar_campo(corpo, 3, "Usuário (opcional)", self._usuario)

        # A senha aparece como pontinhos
        self._criar_campo(corpo, 4, "Senha (opcional)", self._senha, oculto=True)

        ttk.Label(
            corpo, text=TEXTO_AJUDA, style="Suave.Painel.TLabel", justify="left"
        ).grid(row=5, column=0, columnspan=2, sticky="w", pady=(10, 0))

        # Mensagem de erro (endereço inválido, por exemplo)
        self._rotulo_erro = ttk.Label(
            corpo, text="", style="Painel.TLabel", foreground=CORES["perigo_texto"]
        )
        self._rotulo_erro.grid(row=6, column=0, columnspan=2, sticky="w", pady=(10, 0))

        botoes = ttk.Frame(corpo, style="Painel.TFrame")
        botoes.grid(row=7, column=0, columnspan=2, sticky="e", pady=(12, 0))

        ttk.Button(
            botoes, text="Cancelar", style="Secundario.TButton", command=self._cancelar
        ).pack(side="left", padx=(0, 8))

        ttk.Button(
            botoes, text="Adicionar", style="Primario.TButton", command=self._confirmar
        ).pack(side="left")

    @staticmethod
    def _criar_campo(pai, linha, titulo, variavel, largura=30, oculto=False):

        ttk.Label(pai, text=titulo, style="Suave.Painel.TLabel").grid(
            row=linha, column=0, sticky="w", padx=(0, 12), pady=4
        )

        campo = ttk.Entry(pai, textvariable=variavel, width=largura, show="•" if oculto else "")
        campo.grid(row=linha, column=1, sticky="ew", pady=4)

        return campo

    # ============================================================
    # RESPOSTA
    # ============================================================

    def _confirmar(self):

        nome = self._nome.get().strip()
        endereco = self._endereco.get().strip()

        if not nome:
            self._rotulo_erro.config(text="Dê um nome para a câmera.")
            return

        if not endereco.lower().startswith(PROTOCOLOS_ACEITOS) or endereco.lower() in PROTOCOLOS_ACEITOS:
            self._rotulo_erro.config(
                text="O endereço deve começar com rtsp://, http:// ou https:// e ter o IP da câmera."
            )
            return

        self.resultado = (
            nome,
            montar_endereco(endereco, self._usuario.get().strip(), self._senha.get()),
        )

        self.janela.destroy()

    def _cancelar(self):

        self.resultado = None

        self.janela.destroy()
