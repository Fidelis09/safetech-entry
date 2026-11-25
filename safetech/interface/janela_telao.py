"""
Telão da catraca: a tela virada para o TRABALHADOR.

A janela principal é para o operador (cheia de detalhes). O telão é
para quem está na frente da câmera e precisa entender em um segundo, de
longe, se pode passar e o que falta:

    ┌──────────────────────────────────────────────┐
    │ Portaria                         09:18:51    │
    │                                              │
    │              ✖  ACESSO NEGADO                │
    │           Coloque antes de passar:           │
    │                                              │
    │          [capacete]   [luvas]                │
    │           Capacete     Luvas        [vídeo]  │
    └──────────────────────────────────────────────┘

A cor do fundo inteiro é a do resultado (verde, vermelho, amarelo,
cinza). Os textos e os tamanhos acompanham o tamanho da janela: num
monitor grande em tela cheia (F11), as letras ficam enormes.

Como os outros painéis, o telão só mostra o que recebe em atualizar().
"""

import tkinter as tk
import tkinter.font as tkfont
from datetime import datetime

import cv2
from PIL import Image, ImageTk

from safetech import config
from safetech.nucleo.icones import desenhar_icone_epi
from safetech.interface.tema import CORES, FAMILIA
from safetech.nucleo import anotacao, modos
from safetech.nucleo.epis import nome_do_epi
from safetech.nucleo.tipos import StatusAcesso, StatusPessoa


# Tamanhos relativos à ALTURA da janela (0.12 = 12% da altura)
PROPORCAO_TITULO = 0.12
PROPORCAO_MENSAGEM = 0.05
PROPORCAO_ICONE = 0.22
PROPORCAO_RODAPE = 0.03

# Largura do vídeo no canto, relativa à largura da janela
PROPORCAO_VIDEO = 0.24

# Símbolo antes do título, como na faixa de status da janela principal
SIMBOLOS = {
    StatusAcesso.LIBERADO: "✔",
    StatusAcesso.NEGADO: "✖",
    StatusAcesso.ANALISANDO: "◔",
    StatusAcesso.SEM_PESSOAS: "",
}


def situacao_do_telao(estado, camera_ligada=True):
    """
    O que o telão mostra para o estado da cena: (titulo, mensagem, cor, epis).

    epis -> chaves dos EPIs a desenhar: no negado, os que FALTAM (de
            todas as pessoas irregulares); no liberado, os exigidos.

    Função separada da janela para poder ser testada sem tela.
    """

    if not camera_ligada:
        return "FORA DE OPERAÇÃO", "Câmera desligada", CORES["neutro"], ()

    textos = modos.textos(estado.modo)

    titulo = modos.titulo_da_situacao(estado.modo, estado.acesso)

    simbolo = SIMBOLOS.get(estado.acesso, "")

    if simbolo:
        titulo = f"{simbolo}  {titulo}"

    if estado.acesso is StatusAcesso.LIBERADO:
        return titulo, textos["telao_ok"], CORES["sucesso"], tuple(estado.exigidos)

    if estado.acesso is StatusAcesso.NEGADO:

        faltando = []

        for pessoa in estado.pessoas:

            if pessoa.status is not StatusPessoa.NEGADO:
                continue

            for chave in pessoa.faltando:
                if chave not in faltando:
                    faltando.append(chave)

        # Na ordem de config.EPIS (sempre a mesma, para não "pular")
        faltando.sort(key=lambda chave: list(config.EPIS).index(chave) if chave in config.EPIS else len(config.EPIS))

        return titulo, textos["telao_irregular"], CORES["perigo"], tuple(faltando)

    if estado.acesso is StatusAcesso.ANALISANDO:
        return titulo, textos["telao_analisando"], CORES["alerta"], ()

    return titulo, textos["telao_sem_pessoas"], CORES["neutro"], ()


class JanelaTelao(tk.Toplevel):

    def __init__(self, pai, ao_fechar):
        """ao_fechar -> chamado quando o telão é fechado (pelo X ou pelo Esc)."""

        super().__init__(pai)

        self.title(f"{config.NOME_PRODUTO} - Telão")

        largura, altura = config.TAMANHO_JANELA_TELAO
        self.geometry(f"{largura}x{altura}")

        self._ao_fechar = ao_fechar

        self.protocol("WM_DELETE_WINDOW", self.fechar)

        # F11 = tela cheia (arraste antes para o monitor do trabalhador);
        # Esc sai da tela cheia e, fora dela, fecha o telão
        self.bind("<F11>", lambda _evento: self._alternar_tela_cheia())
        self.bind("<Escape>", lambda _evento: self._ao_apertar_esc())

        self._cor = None
        self._ultima_situacao = None
        self._icones = []
        self._foto_video = None

        # Fontes que crescem com a janela (tamanho negativo = em pixels)
        self._fonte_titulo = tkfont.Font(family=FAMILIA, size=-60, weight="bold")
        self._fonte_mensagem = tkfont.Font(family=FAMILIA, size=-30)
        self._fonte_rodape = tkfont.Font(family=FAMILIA, size=-18, weight="bold")
        self._fonte_nome_epi = tkfont.Font(family=FAMILIA, size=-22, weight="bold")

        self._tela = tk.Canvas(self, highlightthickness=0, bg=CORES["neutro"])
        self._tela.pack(fill="both", expand=True)

        self._tela.bind("<Configure>", lambda _evento: self._redesenhar())

        self._dados = ("", "", "", CORES["neutro"], (), None)

    # ============================================================
    # TELA CHEIA E FECHAR
    # ============================================================

    def _em_tela_cheia(self):
        return bool(self.attributes("-fullscreen"))

    def _alternar_tela_cheia(self):
        self.attributes("-fullscreen", not self._em_tela_cheia())

    def _ao_apertar_esc(self):

        if self._em_tela_cheia():
            self._alternar_tela_cheia()
        else:
            self.fechar()

    def fechar(self):

        self._ao_fechar()
        self.destroy()

    # ============================================================
    # ATUALIZAR (chamado pela janela principal)
    # ============================================================

    def atualizar(self, nome_area, estado, frame, camera_ligada=True):
        """Mostra a situação da área. O vídeo só é redesenhado se TELAO_MOSTRAR_VIDEO."""

        titulo, mensagem, cor, epis = situacao_do_telao(estado, camera_ligada)

        self._dados = (nome_area, titulo, mensagem, cor, epis, estado)

        situacao = (nome_area, titulo, mensagem, cor, epis)

        if situacao != self._ultima_situacao:
            self._ultima_situacao = situacao
            self._redesenhar()

        self._atualizar_relogio()

        if config.TELAO_MOSTRAR_VIDEO:
            self._desenhar_video(frame, estado)

    def situacao(self):
        """(título, mensagem, epis) em exibição (usado nos testes)."""

        _, titulo, mensagem, _, epis, _ = self._dados

        return titulo, mensagem, epis

    # ============================================================
    # DESENHO
    # ============================================================

    def _redesenhar(self):

        nome_area, titulo, mensagem, cor, epis, _ = self._dados

        tela = self._tela

        largura = max(1, tela.winfo_width())
        altura = max(1, tela.winfo_height())

        tela.delete("conteudo")
        tela.configure(bg=cor)

        # Tamanhos a partir da altura da janela
        self._fonte_titulo.configure(size=-int(altura * PROPORCAO_TITULO))
        self._fonte_mensagem.configure(size=-int(altura * PROPORCAO_MENSAGEM))
        self._fonte_rodape.configure(size=-int(altura * PROPORCAO_RODAPE))
        self._fonte_nome_epi.configure(size=-int(altura * PROPORCAO_RODAPE * 1.2))

        margem = int(altura * 0.04)

        # ---------------- topo: área (o relógio é atualizado à parte) ----------------

        tela.create_text(margem, margem, text=nome_area, anchor="nw", fill="white", font=self._fonte_rodape, tags="conteudo")

        # ---------------- título e mensagem ----------------

        centro_x = largura / 2

        tela.create_text(
            centro_x, altura * 0.3, text=titulo, fill="white", font=self._fonte_titulo, tags="conteudo", width=largura - 2 * margem
        )

        tela.create_text(centro_x, altura * 0.45, text=mensagem, fill="white", font=self._fonte_mensagem, tags="conteudo")

        # ---------------- ícones dos EPIs ----------------

        self._icones = []

        if epis:

            tamanho = int(altura * PROPORCAO_ICONE)
            espaco = int(tamanho * 0.35)

            total = len(epis) * tamanho + (len(epis) - 1) * espaco
            x = centro_x - total / 2
            y = altura * 0.55

            for chave in epis:

                icone = ImageTk.PhotoImage(desenhar_icone_epi(chave, tamanho, "white"))
                self._icones.append(icone)

                tela.create_image(x, y, image=icone, anchor="nw", tags="conteudo")
                tela.create_text(
                    x + tamanho / 2, y + tamanho + margem / 2, text=nome_do_epi(chave), anchor="n",
                    fill="white", font=self._fonte_nome_epi, tags="conteudo",
                )

                x += tamanho + espaco

        # ---------------- dica no rodapé ----------------

        tela.create_text(
            margem, altura - margem, text="F11: tela cheia   ·   Esc: sair", anchor="sw",
            fill="white", font=self._fonte_rodape, tags=("conteudo", "dica"),
        )

        tela.itemconfigure("dica", state="normal" if not self._em_tela_cheia() else "hidden")

        self._ultimo_relogio = None
        self._atualizar_relogio()

    def _atualizar_relogio(self):

        agora = datetime.now().strftime("%H:%M:%S")

        if agora == getattr(self, "_ultimo_relogio", None):
            return

        self._ultimo_relogio = agora

        tela = self._tela
        margem = int(max(1, tela.winfo_height()) * 0.04)

        tela.delete("relogio")
        tela.create_text(
            tela.winfo_width() - margem, margem, text=agora, anchor="ne", fill="white", font=self._fonte_rodape, tags="relogio"
        )

    def _desenhar_video(self, frame, estado):
        """A imagem da câmera, pequena, no canto de baixo à direita (a pessoa se vê)."""

        tela = self._tela

        if frame is None:
            tela.delete("video")
            self._foto_video = None
            return

        largura = max(1, tela.winfo_width())
        altura = max(1, tela.winfo_height())

        altura_frame, largura_frame = frame.shape[:2]

        largura_video = int(largura * PROPORCAO_VIDEO)
        escala = largura_video / largura_frame
        tamanho = (largura_video, max(1, int(altura_frame * escala)))

        imagem = cv2.resize(frame, tamanho, interpolation=cv2.INTER_AREA)

        if estado is not None:
            anotacao.desenhar_pessoas(imagem, estado.pessoas, escala, modo=estado.modo)

        imagem = Image.fromarray(cv2.cvtColor(imagem, cv2.COLOR_BGR2RGB))

        if self._foto_video is not None and (self._foto_video.width(), self._foto_video.height()) == tamanho:
            self._foto_video.paste(imagem)
        else:
            self._foto_video = ImageTk.PhotoImage(imagem)

        margem = int(altura * 0.04)

        tela.delete("video")
        tela.create_image(largura - margem, altura - margem, image=self._foto_video, anchor="se", tags="video")
