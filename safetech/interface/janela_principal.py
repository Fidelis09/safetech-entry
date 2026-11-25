"""
Janela principal do SafeTech Entry.

Monta a tela e liga as peças:

    em cima    -> marca do produto, selos de situação (IA, painel web,
                  catraca), botão do tema e relógio
    à esquerda -> as áreas (câmeras): barra de navegação, a página da
                  área escolhida e a visão geral
    à direita  -> a auditoria, UMA só para todas as áreas
    embaixo    -> avisos e atalhos

A janela não faz o trabalho de cada parte: ela o entrega a
CONTROLADORES, um por assunto, cada um no seu arquivo:

    ia          -> CargaIA              (controlador_ia.py)
    areas       -> ControladorAreas      (controlador_areas.py)
    cameras     -> ControladorCameras    (controlador_cameras.py)
    eventos     -> ControladorAuditoria  (controlador_auditoria.py)
    coleta      -> ControladorColeta     (controlador_coleta.py)
    painel_web  -> ControladorPainelWeb  (controlador_painel_web.py)
    catraca     -> ControladorCatraca    (controlador_catraca.py)

Os controladores usam da janela só o que é dela: a raiz do Tkinter, a
janela de Configurações, o painel da auditoria, o serviço de auditoria
e os avisos (veja as propriedades públicas logo abaixo do __init__).

Como as threads se dividem:

    uma thread de câmera por área     -> só captura frames
    uma thread de análise por área    -> detecta, rastreia, classifica,
                                         decide e audita
    thread da interface               -> (esta) desenha a tela ~30 vezes
                                         por segundo

A interface nunca faz trabalho pesado: a cada ciclo ela apenas pega o
frame mais recente e o último resultado do que está à vista e desenha.
É por isso que a janela não trava.
"""

import logging
import time
import tkinter as tk
import traceback
from datetime import datetime
from tkinter import ttk

from PIL import ImageTk

from safetech import config
from safetech.interface import tema
from safetech.interface.componentes import Selo
from safetech.interface.controlador_areas import ControladorAreas
from safetech.interface.controlador_auditoria import ControladorAuditoria
from safetech.interface.controlador_cameras import ControladorCameras
from safetech.interface.controlador_catraca import ControladorCatraca
from safetech.interface.controlador_coleta import ControladorColeta
from safetech.interface.controlador_ia import CargaIA
from safetech.interface.controlador_painel_web import ControladorPainelWeb
from safetech.interface.janela_configuracoes import JanelaConfiguracoes
from safetech.interface.painel_auditoria import PainelAuditoria
from safetech.interface.tema import CORES
from safetech.nucleo import detector, epis
from safetech.servicos import busca_cameras, preferencias
from safetech.servicos.auditoria import ServicoAuditoria
from safetech.servicos.camera import Camera


log = logging.getLogger(__name__)


TEXTO_ATALHOS = "Espaço: câmera   |   S: salvar imagem   |   Ctrl+V: colar imagem   |   F11: tela cheia   |   Esc: limpar busca"

# Tamanho do ícone do cabeçalho e da barra de tarefas (px a 100% de escala)
TAMANHO_ICONE_CABECALHO = 30
TAMANHO_ICONE_JANELA = 64


class JanelaPrincipal:

    def __init__(self, raiz, escala=1.0, camera=None, fabrica_camera=None):
        """
        camera         -> fonte de frames da PRIMEIRA área (testes passam
                          uma câmera falsa; None = a câmera salva)
        fabrica_camera -> cria a câmera das outras áreas a partir da fonte
                          (número ou endereço); None = Camera de verdade.
                          Criar uma Camera não liga a webcam: ela só abre
                          ao clicar em "Iniciar câmera".
        """

        self._raiz = raiz
        self._escala = escala

        # Tema salvo (escuro ou claro): aplicado ANTES de montar a tela,
        # para tudo já nascer com as cores certas
        tema_salvo = preferencias.carregar_tema()

        if tema_salvo != tema.tema_atual():
            tema.trocar_tema(raiz, tema_salvo, escala)

        # ------------------------------------------------------
        # SERVIÇOS E O QUE O MODELO SABE (prontos na hora)
        # ------------------------------------------------------

        # UMA auditoria para todas as áreas
        self._auditoria = ServicoAuditoria()

        # EPIs que o modelo instalado reconhece. Lido sem carregar o
        # TensorFlow, para a tela já abrir com os controles certos.
        self._epis_do_modelo = epis.epis_do_modelo()

        # Modos cujo detector está na pasta (a vigilância depende de um
        # arquivo baixado à parte)
        modos_disponiveis = [modo for modo in config.MODOS_DETECCAO if detector.modo_disponivel(modo)]

        self._aviso_ate = 0.0

        # Último segundo mostrado no relógio do cabeçalho
        self._ultimo_relogio = ""

        # Último erro do ciclo da tela que foi para o log (veja _ciclo)
        self._ultimo_erro_do_ciclo = None

        # Ícone do programa (título da janela e barra de tarefas). A
        # referência fica guardada: sem ela o Tkinter apaga a imagem.
        self._icone_janela = ImageTk.PhotoImage(tema.desenhar_icone(TAMANHO_ICONE_JANELA))
        self._raiz.iconphoto(True, self._icone_janela)

        # ------------------------------------------------------
        # CONTROLADORES (um por assunto)
        # ------------------------------------------------------
        #
        # Criados ANTES de montar a tela: os botões da tela chamam
        # funções deles. Eles só mexem na tela quando são usados.

        self.ia = CargaIA(self._epis_do_modelo)

        self.areas = ControladorAreas(self, self.ia, fabrica_camera or Camera, self._epis_do_modelo, modos_disponiveis)
        self.cameras = ControladorCameras(self, self.areas)

        # Um precisa do outro (os botões de uma área ligam a câmera dela)
        self.areas.cameras = self.cameras

        self.eventos = ControladorAuditoria(self, self.areas)
        self.coleta = ControladorColeta(self, self.areas)
        self.painel_web = ControladorPainelWeb(self, self.areas)
        self.catraca = ControladorCatraca(self.areas)

        # ------------------------------------------------------
        # MONTAGEM DA TELA
        # ------------------------------------------------------

        self._montar()

        for indice, dados in enumerate(preferencias.carregar_areas()):

            # A câmera recebida (testes) vai para a primeira área
            self.areas.criar(dados, camera=camera if indice == 0 else None)

        self.areas.selecionar(self.areas.lista[0])

        self._configurar_atalhos()

        self._painel_auditoria.carregar(self._auditoria.carregar_historico())
        self.coleta.atualizar_resumo()

        self.painel_web.iniciar()
        self.catraca.iniciar()

        self._raiz.protocol("WM_DELETE_WINDOW", self._ao_fechar)

        # Erro inesperado num botão ou atalho: vai para o log e para o
        # aviso no rodapé, em vez de sumir no terminal
        self._raiz.report_callback_exception = self._erro_na_interface

        self._atualizar_selo_ia()

        # A IA demora alguns segundos para carregar (TensorFlow). Isso
        # é feito em segundo plano para a janela abrir imediatamente.
        self.ia.iniciar()

        # Procura as câmeras para a lista (só com a câmera real: uma
        # câmera falsa de teste não tem o que procurar)
        if camera is None:
            busca_cameras.procurar_em_segundo_plano(self.cameras.guardar_encontradas)

        self._ciclo()

    # ============================================================
    # O QUE OS CONTROLADORES USAM DA JANELA
    # ============================================================

    @property
    def raiz(self):
        return self._raiz

    @property
    def escala(self):
        return self._escala

    @property
    def auditoria(self):
        """Serviço de auditoria (o log e as fotos): um só para todas as áreas."""

        return self._auditoria

    @property
    def configuracoes(self):
        return self._configuracoes

    @property
    def painel_auditoria(self):
        return self._painel_auditoria

    # A área à vista (atalhos para o código e para os testes)

    @property
    def _camera(self):
        return self.areas.atual.camera

    @property
    def _parametros(self):
        return self.areas.atual.parametros

    @property
    def _painel_monitoramento(self):
        return self.areas.atual.painel

    @property
    def _analisador(self):
        return self.areas.atual.analisador

    # ============================================================
    # MONTAGEM
    # ============================================================

    def _montar(self):

        self._raiz.columnconfigure(0, weight=1)
        self._raiz.rowconfigure(1, weight=1)

        self._montar_cabecalho()

        # ------------------------------------------------------
        # PAINÉIS LADO A LADO, COM DIVISOR ARRASTÁVEL
        # ------------------------------------------------------

        divisor = ttk.PanedWindow(self._raiz, orient="horizontal")
        divisor.grid(row=1, column=0, sticky="nsew", padx=12)

        # ---------------- esquerda: as áreas ----------------

        esquerda = ttk.Frame(divisor, style="Painel.TFrame", padding=18)
        esquerda.columnconfigure(0, weight=1)
        esquerda.rowconfigure(2, weight=1)

        topo = ttk.Frame(esquerda, style="Painel.TFrame")
        topo.grid(row=0, column=0, sticky="ew", pady=(0, 10))

        ttk.Label(topo, text="Monitoramento", style="Titulo.Painel.TLabel").pack(side="left")

        # Câmera, confiança, intervalo, painel web e coleta ficam numa janela à parte
        ttk.Button(
            topo,
            text="Configurações",
            style="Secundario.TButton",
            command=lambda: self._configuracoes.mostrar(),
            takefocus=False,
        ).pack(side="right")

        # Barra de áreas (linha 1) e as páginas / visão geral (linha 2)
        self.areas.montar(esquerda, linha_barra=1, linha_paginas=2)

        # ---------------- janela de Configurações (escondida) ----------------

        self._configuracoes = JanelaConfiguracoes(
            self._raiz,
            limiar_inicial=self.areas.limiar,
            intervalo_inicial=self.areas.intervalo,
            fonte_camera_inicial=config.INDICE_CAMERA,
            cameras_ip_iniciais=preferencias.carregar_cameras_ip(),
            ao_escolher_camera=self.cameras.escolher,
            ao_adicionar_camera_ip=self.cameras.adicionar_ip,
            ao_remover_camera_ip=self.cameras.remover_ip,
            ao_nova_area=self.areas.nova,
            ao_renomear_area=self.areas.renomear,
            ao_remover_area=self.areas.remover,
            ao_mudar_controle_catraca=self.areas.mudar_controle_catraca,
            ao_mudar_parametros=self.areas.mudar_parametros,
            ao_salvar_imagem=self.coleta.salvar_imagem,
            ao_enviar_arquivos=self.coleta.enviar_arquivos,
            ao_aplicar_painel_web=self.painel_web.aplicar,
            ao_abrir_painel_web=self.painel_web.abrir,
            escala=self._escala,
        )

        # ---------------- direita: auditoria (uma só) ----------------

        self._painel_auditoria = PainelAuditoria(
            divisor,
            pasta_imagens=self._auditoria.pasta_imagens,
            ao_zerar=self.eventos.zerar,
            ao_excluir=self.eventos.excluir,
            ao_salvar_relatorio=self.eventos.salvar_relatorio,
            ao_exportar=self.eventos.exportar,
            escala=self._escala,
        )

        divisor.add(esquerda, weight=3)
        divisor.add(self._painel_auditoria, weight=2)

        # ------------------------------------------------------
        # BARRA DE STATUS (avisos à esquerda, atalhos à direita)
        # ------------------------------------------------------

        rodape = ttk.Frame(self._raiz, padding=(20, 8, 20, 10))
        rodape.grid(row=2, column=0, sticky="ew")

        # Avisos temporários (o que acabou de acontecer)
        self._rotulo_aviso = ttk.Label(rodape, text="", style="TLabel")
        self._rotulo_aviso.pack(side="left")

        ttk.Label(rodape, text=TEXTO_ATALHOS, style="Suave.TLabel").pack(side="right")

    def _montar_cabecalho(self):

        cabecalho = ttk.Frame(self._raiz, padding=(18, 10, 20, 10))
        cabecalho.grid(row=0, column=0, sticky="ew")

        cabecalho.columnconfigure(2, weight=1)

        # Marca: ícone (escudo), nome e frase de apresentação
        tamanho_logo = int(TAMANHO_ICONE_CABECALHO * self._escala)

        self._logo = ImageTk.PhotoImage(tema.desenhar_icone(tamanho_logo))

        tk.Label(cabecalho, image=self._logo, bg=CORES["fundo"]).grid(row=0, column=0, rowspan=2, padx=(0, 10))

        ttk.Label(cabecalho, text=config.NOME_PRODUTO, style="Marca.TLabel").grid(row=0, column=1, sticky="sw")

        ttk.Label(cabecalho, text=config.SUBTITULO_PRODUTO, style="Suave.TLabel").grid(row=1, column=1, sticky="nw")

        # Selos de situação à direita: o operador vê de relance se a IA,
        # o painel web e a catraca estão funcionando
        selos = ttk.Frame(cabecalho)
        selos.grid(row=0, column=3, rowspan=2, sticky="e")

        self._selo_ia = Selo(selos)
        self._selo_ia.grid(row=0, column=0, padx=(0, 8))

        self._selo_painel_web = Selo(selos, ao_clicar=self.painel_web.abrir)
        self._selo_painel_web.grid(row=0, column=1, padx=(0, 8))
        self._selo_painel_web.grid_remove()

        self._selo_catraca = Selo(selos)
        self._selo_catraca.grid(row=0, column=2, padx=(0, 8))
        self._selo_catraca.grid_remove()

        # Cada selo é mantido pelo controlador do assunto
        self.painel_web.selo = self._selo_painel_web
        self.catraca.selo = self._selo_catraca

        # Os testes leem os textos por estes nomes
        self._rotulo_painel_web = self._selo_painel_web.rotulo
        self._rotulo_catraca = self._selo_catraca.rotulo

        # Tema escuro / claro: o botão mostra o tema para o qual muda
        self._botao_tema = ttk.Button(
            selos,
            text="",
            style="Pequeno.TButton",
            command=self._alternar_tema,
            takefocus=False,
        )
        self._botao_tema.grid(row=0, column=3, padx=(0, 8))
        self._atualizar_botao_tema()

        # Relógio: data e hora de referência para quem confere a tela
        self._rotulo_relogio = ttk.Label(selos, text="", style="TLabel", font=tema.FONTES["relogio"])
        self._rotulo_relogio.grid(row=0, column=4, padx=(8, 0))

    # ============================================================
    # ATALHOS DE TECLADO E TELA CHEIA
    # ============================================================

    def _configurar_atalhos(self):

        self._raiz.bind_all("<space>", self._atalho(self.cameras.alternar))
        self._raiz.bind_all("<Escape>", self._ao_apertar_esc)

        # F11: tela cheia (apresentação, monitor dedicado na portaria)
        self._raiz.bind_all("<F11>", lambda _evento: self._alternar_tela_cheia())

        # S (maiúsculo ou minúsculo) salva uma imagem com os rótulos marcados
        for tecla in ("s", "S"):
            self._raiz.bind_all(tecla, self._atalho(self._configuracoes.salvar_imagem))

        # Ctrl+V cola no dataset uma imagem copiada. Enquanto o usuário
        # digita na busca, Ctrl+V continua colando TEXTO ali, como esperado.
        for tecla in ("<Control-v>", "<Control-V>"):
            self._raiz.bind_all(tecla, self._atalho(self.coleta.colar_imagem))

    def _atalho(self, acao):
        """Embrulha uma ação de atalho: ela não dispara enquanto o usuário digita na busca."""

        def tratar(_evento):

            if not self._painel_auditoria.campo_de_busca_em_foco():
                acao()

        return tratar

    def _ao_apertar_esc(self, _evento=None):
        """Esc sai da tela cheia; fora dela, limpa a busca da auditoria."""

        if self._em_tela_cheia():
            self._alternar_tela_cheia()
        else:
            self._painel_auditoria.limpar_filtro()

    def _em_tela_cheia(self) -> bool:

        return bool(self._raiz.attributes("-fullscreen"))

    def _alternar_tela_cheia(self):

        cheia = not self._em_tela_cheia()

        self._raiz.attributes("-fullscreen", cheia)

        if cheia:
            self.avisar("Tela cheia. F11 ou Esc para sair.")

    # ============================================================
    # TEMA ESCURO / CLARO
    # ============================================================

    def _atualizar_botao_tema(self):

        if tema.tema_atual() == "escuro":
            self._botao_tema.config(text="☀  Tema claro")    # ☀
        else:
            self._botao_tema.config(text="☾  Tema escuro")   # ☾

    def _alternar_tema(self):
        """
        Botão do tema: troca entre escuro e claro com o programa aberto.

        O tema.trocar_tema repinta os componentes; aqui só se refaz o
        que guarda cores por conta própria (tabela, pontos da barra,
        faixa de status de cada área) e a escolha é salva.
        """

        novo = "claro" if tema.tema_atual() == "escuro" else "escuro"

        tema.trocar_tema(self._raiz, novo, self._escala)

        self._painel_auditoria.aplicar_cores()
        self.areas.esquecer_desenhos()

        self._atualizar_botao_tema()

        preferencias.salvar_tema(novo)

        self.avisar(f"Tema {tema.NOMES_DOS_TEMAS[novo].lower()} ativado.")

    # ============================================================
    # CARGA DA IA
    # ============================================================

    def _verificar_carga(self):
        """Chamado a cada ciclo; quando a IA termina de carregar, liga as áreas."""

        situacao = self.ia.verificar()

        if situacao == "erro":

            self.areas.mostrar_erro_de_carga()
            self._atualizar_selo_ia()

        elif situacao == "pronta":

            if not self.ia.por_epi:

                self.avisar(
                    "Modelo antigo em uso: avalia só o conjunto completo de EPIs, "
                    "sem distinguir cada equipamento.",
                    segundos=15,
                )

            self.areas.iniciar_analises()

            self._atualizar_selo_ia()

            if not self.ia.detectores_iniciais[config.MODO_CATRACA].disponivel:

                self.avisar(
                    "Detector de rosto não encontrado em 'modelos/': a cena inteira será "
                    "tratada como uma pessoa. Veja o README.",
                    segundos=15,
                )

    def _atualizar_selo_ia(self):
        """Selo da IA no cabeçalho: carregando, pronta (e com qual modelo) ou com erro."""

        if self.ia.erro:
            self._selo_ia.definir("IA com erro", CORES["perigo"])

        elif not self.ia.pronta:
            self._selo_ia.definir("IA carregando...", CORES["alerta"])

        elif self.ia.por_epi:
            self._selo_ia.definir(f"IA pronta: {len(self.ia.classificador.epis)} EPIs", CORES["sucesso"])

        else:
            self._selo_ia.definir("IA pronta: modelo antigo", CORES["alerta"])

    # ============================================================
    # CICLO DA INTERFACE (~30 vezes por segundo)
    # ============================================================

    def _ciclo(self):

        try:

            self.cameras.entregar_encontradas()

            self._verificar_carga()
            self.catraca.atualizar()
            self.areas.atualizar_pontos_da_barra()

            if self.ia.pronta:

                # Eventos de TODAS as áreas vão para a auditoria única
                self.eventos.receber()

                # Desenho só do que está à vista
                self.areas.desenhar()

            self._atualizar_relogio()
            self._expirar_aviso()

        except Exception as erro:

            # O ciclo nunca morre por um erro: ele é registrado e a tela
            # segue. Um erro que se repete a cada ciclo (30 vezes por
            # segundo) vai para o log uma vez só, até mudar.
            if repr(erro) != self._ultimo_erro_do_ciclo:

                self._ultimo_erro_do_ciclo = repr(erro)

                log.exception("Erro no ciclo da interface")

        finally:

            # Reagenda mesmo se algo falhar, para a tela não congelar
            self._raiz.after(config.INTERVALO_TELA_MS, self._ciclo)

    def _atualizar_relogio(self):

        agora = datetime.now().strftime("%d/%m/%Y  %H:%M:%S")

        # Só mexe no rótulo quando o segundo muda
        if agora != self._ultimo_relogio:
            self._ultimo_relogio = agora
            self._rotulo_relogio.config(text=agora)

    # ============================================================
    # AVISOS NA BARRA DE STATUS
    # ============================================================

    def avisar(self, texto, segundos=4):
        """Mostra um aviso temporário, sem interromper o usuário com janelas."""

        self._rotulo_aviso.config(text=texto)

        self._aviso_ate = time.perf_counter() + segundos

    def _expirar_aviso(self):

        if self._aviso_ate and time.perf_counter() > self._aviso_ate:

            self._rotulo_aviso.config(text="")

            self._aviso_ate = 0.0

    def _erro_na_interface(self, tipo, erro, rastro):
        """
        Erro inesperado num botão, atalho ou temporizador do Tkinter.

        Sem isto, o Tkinter só imprime o erro no terminal (que nem existe
        quando o programa é aberto com dois cliques) e ninguém fica sabendo.
        """

        log.error("Erro na interface:\n%s", "".join(traceback.format_exception(tipo, erro, rastro)))

        self.avisar(f"Erro inesperado: {erro} (detalhes em logs/{config.NOME_ARQUIVO_LOG})", segundos=10)

    # ============================================================
    # ENCERRAMENTO
    # ============================================================

    def _ao_fechar(self):

        log.info("Programa fechado")

        self.areas.parar_todas()
        self.painel_web.parar()
        self.catraca.parar()

        self._raiz.destroy()


# ============================================================
# INICIALIZAÇÃO DA JANELA
# ============================================================

def _ativar_nitidez_no_windows():
    """
    Avisa o Windows que o programa sabe lidar com telas de alta
    resolução. Sem isso, em monitores com escala acima de 100% o
    Windows amplia a janela como imagem e tudo fica borrado.
    """

    try:
        import ctypes

        ctypes.windll.shcore.SetProcessDpiAwareness(1)

    except (ImportError, AttributeError, OSError):
        pass


def executar():
    """Cria a janela e entra no laço de eventos do Tkinter."""

    _ativar_nitidez_no_windows()

    raiz = tk.Tk()
    raiz.title(config.TITULO_JANELA)

    # Fator de escala do monitor (1.0 = 100%, 1.5 = 150%...)
    escala = raiz.winfo_fpixels("1i") / 96

    largura, altura = (int(valor) for valor in config.TAMANHO_INICIAL_JANELA.split("x"))

    # Tamanho inicial ajustado à escala, sem passar do tamanho da tela
    largura = min(int(largura * escala), raiz.winfo_screenwidth() - 80)
    altura = min(int(altura * escala), raiz.winfo_screenheight() - 120)

    raiz.geometry(f"{largura}x{altura}")

    raiz.minsize(
        min(int(config.TAMANHO_MINIMO_JANELA[0] * escala), largura),
        min(int(config.TAMANHO_MINIMO_JANELA[1] * escala), altura),
    )

    tema.aplicar_tema(raiz, escala)

    JanelaPrincipal(raiz, escala)

    raiz.mainloop()
