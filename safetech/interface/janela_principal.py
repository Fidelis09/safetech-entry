"""
Janela principal do SafeTech Entry.

Monta a tela (cabeçalho, painel de monitoramento, painel de auditoria e
barra de status) e liga a interface aos serviços.

Como as threads se dividem:

    thread da câmera     -> só captura frames
    thread do analisador -> detecta, rastreia, classifica, decide e audita
    thread da interface  -> (esta) desenha a tela ~30 vezes por segundo

A interface nunca faz trabalho pesado: a cada ciclo ela apenas pega o
frame mais recente e o último resultado do analisador e desenha. É por
isso que a janela não trava, nem enquanto a IA carrega ou analisa.
"""

import threading
import time
import webbrowser
import tkinter as tk
from tkinter import ttk

import cv2
from PIL import Image, ImageTk

from safetech import config
from safetech.interface import tema
from safetech.interface.painel_auditoria import PainelAuditoria
from safetech.interface.painel_monitoramento import PainelMonitoramento
from safetech.interface.tema import CORES
from safetech.nucleo import anotacao
from safetech.nucleo.classes import carregar_classes
from safetech.nucleo.tipos import EstadoCena, StatusAcesso, StatusPessoa
from safetech.servicos.analisador import Analisador, ParametrosAnalise
from safetech.servicos.auditoria import ServicoAuditoria
from safetech.servicos.camera import Camera, EstadoCamera
from safetech.servicos.dataset import ColetorDataset
from safetech.web.servidor import ServidorWeb


TEXTO_ATALHOS = "Espaço: ligar/desligar câmera   |   1, 2...: salvar imagem na classe   |   Esc: limpar busca"


class JanelaPrincipal:

    def __init__(self, raiz, escala=1.0, camera=None):

        self._raiz = raiz
        self._escala = escala

        # ------------------------------------------------------
        # SERVIÇOS QUE NÃO DEPENDEM DA IA (prontos na hora)
        # ------------------------------------------------------

        # A câmera pode ser trocada por outra fonte de frames (testes)
        self._camera = camera if camera is not None else Camera()

        self._auditoria = ServicoAuditoria()
        self._coletor = ColetorDataset()
        self._parametros = ParametrosAnalise()

        # Criados quando a IA terminar de carregar
        self._analisador = None

        # Resultado do carregamento da IA, preenchido pela thread de
        # carga e lido pela interface: None, ("ok", ...) ou ("erro", msg)
        self._resultado_carga = None
        self._erro_fatal = None

        # ------------------------------------------------------
        # CONTROLE DO DESENHO
        # ------------------------------------------------------

        self._foto = None
        self._ultimo_desenho = None
        self._ultimo_status = None
        self._ultimo_estado_camera = None
        self._proxima_medicao = 0.0
        self._aviso_ate = 0.0

        # ------------------------------------------------------
        # MONTAGEM DA TELA
        # ------------------------------------------------------

        self._classes = self._ler_classes()

        self._montar()
        self._configurar_atalhos()

        self._painel_auditoria.carregar(self._auditoria.carregar_historico())
        self._atualizar_contagens()

        self._servidor_web = None
        self._iniciar_painel_web()

        self._raiz.protocol("WM_DELETE_WINDOW", self._ao_fechar)

        # A IA demora alguns segundos para carregar (TensorFlow). Isso
        # é feito em segundo plano para a janela abrir imediatamente.
        self._painel_monitoramento.definir_status(
            "CARREGANDO",
            "Preparando o modelo de IA. Isso leva alguns segundos...",
            CORES["neutro"],
        )
        self._painel_monitoramento.mostrar_mensagem("Carregando o modelo de IA...")

        threading.Thread(target=self._carregar_ia, name="carga-ia", daemon=True).start()

        self._ciclo()

    # ============================================================
    # MONTAGEM
    # ============================================================

    @staticmethod
    def _ler_classes():
        """Lê as classes para montar os botões de coleta (lista vazia se não houver modelo)."""

        try:
            return carregar_classes()
        except (OSError, ValueError):
            return []

    def _montar(self):

        self._raiz.columnconfigure(0, weight=1)
        self._raiz.rowconfigure(1, weight=1)

        # ------------------------------------------------------
        # CABEÇALHO
        # ------------------------------------------------------

        cabecalho = ttk.Frame(self._raiz, padding=(20, 14, 20, 10))
        cabecalho.grid(row=0, column=0, sticky="ew")

        ttk.Label(cabecalho, text="SafeTech Entry", style="Marca.TLabel").pack(side="left")

        ttk.Label(
            cabecalho,
            text="Catraca inteligente com reconhecimento de EPI",
            style="Suave.TLabel",
        ).pack(side="left", padx=(12, 0), pady=(4, 0))

        # ------------------------------------------------------
        # PAINÉIS LADO A LADO, COM DIVISOR ARRASTÁVEL
        # ------------------------------------------------------

        divisor = ttk.PanedWindow(self._raiz, orient="horizontal")
        divisor.grid(row=1, column=0, sticky="nsew", padx=12)

        self._painel_monitoramento = PainelMonitoramento(
            divisor,
            classes=self._classes,
            limiar_inicial=self._parametros.limiar_confianca,
            intervalo_inicial=self._parametros.intervalo_classificacao,
            ao_alternar_camera=self._alternar_camera,
            ao_capturar=self._capturar,
            ao_mudar_parametros=self._mudar_parametros,
        )

        self._painel_auditoria = PainelAuditoria(
            divisor,
            pasta_imagens=self._auditoria.pasta_imagens,
            escala=self._escala,
        )

        divisor.add(self._painel_monitoramento, weight=3)
        divisor.add(self._painel_auditoria, weight=2)

        # ------------------------------------------------------
        # BARRA DE STATUS (avisos à esquerda, atalhos à direita)
        # ------------------------------------------------------

        rodape = ttk.Frame(self._raiz, padding=(20, 8, 20, 10))
        rodape.grid(row=2, column=0, sticky="ew")

        # Endereço do painel web do gerente; clicar abre no navegador
        self._rotulo_painel_web = ttk.Label(rodape, text="", style="Suave.TLabel", cursor="hand2")
        self._rotulo_painel_web.pack(side="left", padx=(0, 20))

        self._rotulo_aviso = ttk.Label(rodape, text="", style="TLabel")
        self._rotulo_aviso.pack(side="left")

        ttk.Label(rodape, text=TEXTO_ATALHOS, style="Suave.TLabel").pack(side="right")

    def _configurar_atalhos(self):

        self._raiz.bind_all("<space>", self._atalho(self._alternar_camera))
        self._raiz.bind_all("<Escape>", lambda _evento: self._painel_auditoria.limpar_filtro())

        # Teclas 1, 2, ... salvam uma imagem na classe correspondente
        for indice, nome_classe in enumerate(self._classes[:9], start=1):

            self._raiz.bind_all(
                str(indice),
                self._atalho(lambda classe=nome_classe: self._capturar(classe)),
            )

    def _atalho(self, acao):
        """Embrulha uma ação de atalho: ela não dispara enquanto o usuário digita na busca."""

        def tratar(_evento):

            if not self._painel_auditoria.campo_de_busca_em_foco():
                acao()

        return tratar

    # ============================================================
    # PAINEL WEB DO GERENTE (somente leitura)
    # ============================================================

    def _iniciar_painel_web(self):
        """Sobe o servidor do painel web; se não der, o aplicativo segue normalmente."""

        if not config.PAINEL_WEB_ATIVO:
            return

        servidor = ServidorWeb(self._auditoria, self._ler_ao_vivo)

        try:
            servidor.iniciar()

        except OSError:

            # Porta ocupada (outro programa ou outra cópia do aplicativo)
            self._rotulo_painel_web.config(
                text=f"Painel web indisponível (porta {config.PAINEL_WEB_PORTA} em uso)",
                cursor="",
            )
            return

        self._servidor_web = servidor

        endereco = servidor.endereco()

        self._rotulo_painel_web.config(text=f"Painel web: {endereco}")
        self._rotulo_painel_web.bind("<Button-1>", lambda _evento: webbrowser.open(endereco))

    def _ler_ao_vivo(self):
        """
        Entrega ao painel web o frame e o estado do momento.

        É chamada pelas threads do servidor web; só usa leituras que
        já são seguras entre threads (câmera e analisador).
        """

        frame, _ = self._camera.ler()

        if self._analisador is None:
            return frame, EstadoCena()

        return frame, self._analisador.estado()

    # ============================================================
    # CARGA DA IA (thread em segundo plano)
    # ============================================================

    def _carregar_ia(self):

        try:

            if not config.ARQUIVO_MODELO.exists() or not config.ARQUIVO_CLASSES.exists():

                raise FileNotFoundError(
                    "Modelo não encontrado em 'modelos/'. Execute o treinar.py primeiro."
                )

            # Importados aqui, e não no topo do arquivo, porque trazem
            # o TensorFlow junto: é o que mais demora no programa.
            from safetech.nucleo.classificador import ClassificadorEPI
            from safetech.nucleo.detector import DetectorPessoas

            classificador = ClassificadorEPI()

            if config.CLASSE_LIBERA_ACESSO not in classificador.classes:

                raise ValueError(
                    f"A classe '{config.CLASSE_LIBERA_ACESSO}' não existe em classes.json "
                    f"(classes encontradas: {classificador.classes})."
                )

            self._resultado_carga = ("ok", classificador, DetectorPessoas())

        except Exception as erro:
            self._resultado_carga = ("erro", str(erro))

    def _verificar_carga(self):
        """Chamado a cada ciclo até a carga terminar; então ativa o programa."""

        if self._resultado_carga is None or self._analisador is not None or self._erro_fatal:
            return

        if self._resultado_carga[0] == "erro":

            self._erro_fatal = self._resultado_carga[1]

            self._painel_monitoramento.definir_status(
                "ERRO AO CARREGAR", self._erro_fatal, CORES["perigo"]
            )
            self._painel_monitoramento.mostrar_mensagem("Não foi possível carregar o modelo de IA.")
            self._painel_monitoramento.definir_botao_camera("Indisponível", "Primario.TButton", False)

            return

        _, classificador, detector = self._resultado_carga

        self._analisador = Analisador(
            self._camera,
            detector,
            classificador,
            self._auditoria,
            self._parametros,
        )

        self._analisador.iniciar()

        if not detector.disponivel:

            self._avisar(
                "Detector de rosto não encontrado em 'modelos/': a cena inteira será "
                "tratada como uma pessoa. Veja o README.",
                segundos=15,
            )

        # Força a tela a refletir o novo estado (IA pronta, câmera parada)
        self._ultimo_estado_camera = None
        self._ultimo_status = None

    # ============================================================
    # CICLO DA INTERFACE (~30 vezes por segundo)
    # ============================================================

    def _ciclo(self):

        try:

            self._verificar_carga()

            if self._analisador is not None:

                self._atualizar_camera()
                self._desenhar_video()
                self._atualizar_status()
                self._receber_registros()
                self._atualizar_desempenho()

            self._expirar_aviso()

        finally:

            # Reagenda mesmo se algo falhar, para a tela não congelar
            self._raiz.after(config.INTERVALO_TELA_MS, self._ciclo)

    # ------------------------------------------------------
    # CÂMERA: botão e mensagens conforme o estado
    # ------------------------------------------------------

    def _atualizar_camera(self):

        estado = self._camera.estado

        if estado is self._ultimo_estado_camera:
            return

        self._ultimo_estado_camera = estado

        painel = self._painel_monitoramento

        if estado is EstadoCamera.ATIVA:

            painel.definir_botao_camera("Parar câmera", "Perigo.TButton")

        elif estado is EstadoCamera.ABRINDO:

            painel.definir_botao_camera("Abrindo...", "Primario.TButton", False)
            painel.mostrar_mensagem("Abrindo a câmera...")

        elif estado is EstadoCamera.ERRO:

            painel.definir_botao_camera("Tentar novamente", "Primario.TButton")
            painel.mostrar_mensagem(
                "Não foi possível acessar a webcam.\n"
                "Verifique se ela está conectada e se outro programa não a está usando."
            )

        else:

            painel.definir_botao_camera("Iniciar câmera", "Primario.TButton")
            painel.mostrar_mensagem("Câmera desligada\nClique em Iniciar câmera ou pressione Espaço")

        # O vídeo e o status precisam ser redesenhados para o novo estado
        self._ultimo_desenho = None
        self._ultimo_status = None

    # ------------------------------------------------------
    # VÍDEO
    # ------------------------------------------------------

    def _desenhar_video(self):

        frame, numero_frame = self._camera.ler()

        if frame is None:
            return

        estado = self._analisador.estado()

        largura_tela, altura_tela = self._painel_monitoramento.tamanho_do_video()

        # Não redesenha se nada mudou desde o último ciclo
        assinatura = (numero_frame, id(estado), largura_tela, altura_tela)

        if assinatura == self._ultimo_desenho or largura_tela < 20 or altura_tela < 20:
            return

        self._ultimo_desenho = assinatura

        # Ajusta o frame ao espaço disponível, mantendo a proporção.
        # É isso que torna o vídeo responsivo ao tamanho da janela.
        altura_frame, largura_frame = frame.shape[:2]

        escala = min(largura_tela / largura_frame, altura_tela / altura_frame)

        tamanho = (max(1, int(largura_frame * escala)), max(1, int(altura_frame * escala)))

        # cv2.resize devolve uma imagem NOVA, então desenhar nela não
        # altera o frame original (que é compartilhado com o analisador).
        imagem = cv2.resize(frame, tamanho, interpolation=cv2.INTER_LINEAR)

        anotacao.desenhar_pessoas(imagem, estado.pessoas, escala)

        imagem = Image.fromarray(cv2.cvtColor(imagem, cv2.COLOR_BGR2RGB))

        # Reaproveita o mesmo objeto de imagem enquanto o tamanho não
        # muda: é mais rápido e evita piscadas.
        if self._foto is not None and (self._foto.width(), self._foto.height()) == tamanho:
            self._foto.paste(imagem)
        else:
            self._foto = ImageTk.PhotoImage(imagem)

        self._painel_monitoramento.mostrar_imagem(self._foto)

    # ------------------------------------------------------
    # FAIXA DE STATUS
    # ------------------------------------------------------

    def _atualizar_status(self):

        if self._analisador.erro:
            status = ("ERRO NA ANÁLISE", self._analisador.erro, CORES["perigo"])

        elif self._camera.estado is not EstadoCamera.ATIVA:
            status = ("CÂMERA DESLIGADA", "Ligue a câmera para iniciar o monitoramento.", CORES["neutro"])

        else:
            status = self._descrever_acesso(self._analisador.estado())

        if status != self._ultimo_status:

            self._ultimo_status = status

            self._painel_monitoramento.definir_status(*status)

    @staticmethod
    def _descrever_acesso(estado: EstadoCena):
        """Transforma o estado da cena em (título, detalhe, cor) para a faixa de status."""

        total = len(estado.pessoas)

        liberadas = sum(1 for pessoa in estado.pessoas if pessoa.status is StatusPessoa.LIBERADO)
        negadas = sum(1 for pessoa in estado.pessoas if pessoa.status is StatusPessoa.NEGADO)

        plural = "pessoa" if total == 1 else "pessoas"

        if estado.acesso is StatusAcesso.LIBERADO:

            return (
                "ACESSO LIBERADO",
                f"{total} {plural} na imagem, todas com EPI.",
                CORES["sucesso"],
            )

        if estado.acesso is StatusAcesso.NEGADO:

            return (
                "ACESSO NEGADO",
                f"{total} {plural} na imagem: {liberadas} com EPI, {negadas} sem EPI.",
                CORES["perigo"],
            )

        if estado.acesso is StatusAcesso.ANALISANDO:

            return (
                "ANALISANDO",
                f"{total} {plural} na imagem, verificando os equipamentos...",
                CORES["alerta"],
            )

        return (
            "AGUARDANDO",
            "Nenhuma pessoa na frente da câmera.",
            CORES["neutro"],
        )

    # ------------------------------------------------------
    # AUDITORIA AO VIVO
    # ------------------------------------------------------

    def _receber_registros(self):
        """Passa para a tabela os eventos gravados pelo analisador desde o último ciclo."""

        fila = self._analisador.registros_novos

        while not fila.empty():
            self._painel_auditoria.adicionar(fila.get_nowait())

    # ------------------------------------------------------
    # INDICADORES DE DESEMPENHO
    # ------------------------------------------------------

    def _atualizar_desempenho(self):

        agora = time.perf_counter()

        # Duas vezes por segundo é suficiente; mais que isso só pisca
        if agora < self._proxima_medicao:
            return

        self._proxima_medicao = agora + 0.5

        if self._camera.estado is not EstadoCamera.ATIVA:
            self._painel_monitoramento.definir_desempenho("")
            return

        estado = self._analisador.estado()

        self._painel_monitoramento.definir_desempenho(
            f"Câmera {self._camera.fps:.0f} fps   |   "
            f"Análise {estado.analises_por_segundo:.0f}/s   |   "
            f"Pessoas {len(estado.pessoas)}"
        )

    # ============================================================
    # AÇÕES DO USUÁRIO
    # ============================================================

    def _alternar_camera(self):

        # Antes de a IA carregar não há o que fazer com a câmera
        if self._analisador is None:
            return

        estado = self._camera.estado

        if estado in (EstadoCamera.PARADA, EstadoCamera.ERRO):
            self._camera.iniciar()

        elif estado is EstadoCamera.ATIVA:
            self._camera.parar()

    def _mudar_parametros(self, limiar_confianca, intervalo_classificacao):
        """Chamado quando o usuário move um controle deslizante."""

        self._parametros.limiar_confianca = limiar_confianca
        self._parametros.intervalo_classificacao = intervalo_classificacao

    def _capturar(self, nome_classe):
        """Salva no dataset o recorte de cada pessoa do frame atual."""

        frame, _ = self._camera.ler()

        if frame is None or self._analisador is None:
            self._avisar("Ligue a câmera antes de salvar imagens.")
            return

        caixas = [pessoa.caixa for pessoa in self._analisador.estado().pessoas]

        arquivos = self._coletor.salvar(frame, caixas, nome_classe)

        self._atualizar_contagens()

        descricao = "1 imagem salva" if len(arquivos) == 1 else f"{len(arquivos)} imagens salvas"

        if not caixas:
            descricao += " (ninguém detectado: frame inteiro)"

        self._avisar(f"{descricao} em dataset/{nome_classe}.")

    def _atualizar_contagens(self):

        for nome_classe in self._classes:

            self._painel_monitoramento.definir_contagem(
                nome_classe,
                self._coletor.contar_imagens(nome_classe),
            )

    # ============================================================
    # AVISOS NA BARRA DE STATUS
    # ============================================================

    def _avisar(self, texto, segundos=4):
        """Mostra um aviso temporário, sem interromper o usuário com janelas."""

        self._rotulo_aviso.config(text=texto)

        self._aviso_ate = time.perf_counter() + segundos

    def _expirar_aviso(self):

        if self._aviso_ate and time.perf_counter() > self._aviso_ate:

            self._rotulo_aviso.config(text="")

            self._aviso_ate = 0.0

    # ============================================================
    # ENCERRAMENTO
    # ============================================================

    def _ao_fechar(self):

        if self._analisador is not None:
            self._analisador.parar()

        self._camera.parar()

        if self._servidor_web is not None:
            self._servidor_web.parar()

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
