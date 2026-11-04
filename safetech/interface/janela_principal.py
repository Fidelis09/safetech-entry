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
from tkinter import filedialog, messagebox, ttk

import cv2
from PIL import Image, ImageTk

from safetech import config
from safetech.interface import tema
from safetech.interface.dialogo_camera_ip import pedir_camera_ip
from safetech.interface.painel_auditoria import PainelAuditoria
from safetech.interface.painel_monitoramento import PainelMonitoramento
from safetech.interface.tema import CORES
from safetech.nucleo import anotacao, detector, epis, modos
from safetech.nucleo.tipos import EstadoCena, StatusAcesso, StatusPessoa
from safetech.servicos import busca_cameras, importacao, preferencias, relatorio
from safetech.servicos.analisador import Analisador, ParametrosAnalise
from safetech.servicos.auditoria import ServicoAuditoria
from safetech.servicos.camera import Camera, EstadoCamera, eh_endereco_ip
from safetech.servicos.catraca_serial import CatracaSerial
from safetech.servicos.dataset import ColetorDataset
from safetech.web.servidor import ServidorWeb


TEXTO_ATALHOS = "Espaço: câmera   |   S: salvar imagem   |   Ctrl+V: colar imagem   |   Esc: limpar busca"


class JanelaPrincipal:

    def __init__(self, raiz, escala=1.0, camera=None):

        self._raiz = raiz
        self._escala = escala

        # ------------------------------------------------------
        # SERVIÇOS QUE NÃO DEPENDEM DA IA (prontos na hora)
        # ------------------------------------------------------

        # A câmera pode ser trocada por outra fonte de frames (testes)
        # A câmera pode ser uma webcam (número) ou uma câmera IP (endereço)
        self._camera = camera if camera is not None else Camera(preferencias.carregar_fonte_camera())

        # Índices das câmeras achados pela busca (thread em segundo
        # plano); a interface os lê no ciclo e preenche a lista.
        self._cameras_encontradas = None

        self._auditoria = ServicoAuditoria()
        self._coletor = ColetorDataset()

        # EPIs que o modelo instalado reconhece. Lido sem carregar o
        # TensorFlow, para a tela já abrir com os controles certos.
        self._epis_do_modelo = epis.epis_do_modelo()

        # Fiscalização: reabre com o setor e os EPIs da última vez. Só
        # pode ser exigido o que o modelo sabe reconhecer.
        setor, exigidos, modo_deteccao = preferencias.carregar()

        # Modos de detecção cujo modelo está na pasta (o modo corpo
        # depende de um arquivo baixado à parte)
        self._modos_disponiveis = [
            modo for modo in config.MODOS_DETECCAO if detector.modo_disponivel(modo)
        ]

        # Se o modo salvo não estiver mais disponível, volta para o rosto
        if modo_deteccao not in self._modos_disponiveis:
            modo_deteccao = config.MODO_CATRACA

        self._parametros = ParametrosAnalise(
            setor=setor,
            exigidos=tuple(chave for chave in exigidos if chave in self._epis_do_modelo),
            modo_deteccao=modo_deteccao,
        )

        # Detectores usados só para importar imagens, um por modo
        # (cada um é criado no primeiro uso)
        self._detectores_importacao = {}

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

        self._montar()
        self._configurar_atalhos()

        self._painel_auditoria.carregar(self._auditoria.carregar_historico())
        self._atualizar_resumo_dataset()

        self._servidor_web = None
        self._iniciar_painel_web()

        self._catraca = None
        self._iniciar_catraca()

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

        # Procura as câmeras para a caixa de seleção (só com a câmera
        # real: uma câmera falsa de teste não tem o que procurar)
        if camera is None:
            busca_cameras.procurar_em_segundo_plano(self._guardar_cameras_encontradas)

        self._ciclo()

    # ============================================================
    # MONTAGEM
    # ============================================================

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
            epis_do_modelo=self._epis_do_modelo,
            modos_disponiveis=self._modos_disponiveis,
            modo_inicial=self._parametros.modo_deteccao,
            ao_mudar_modo=self._mudar_modo_deteccao,
            setor_inicial=self._parametros.setor,
            exigidos_iniciais=self._parametros.exigidos,
            limiar_inicial=self._parametros.limiar_confianca,
            intervalo_inicial=self._parametros.intervalo_classificacao,
            ao_alternar_camera=self._alternar_camera,
            ao_salvar_imagem=self._salvar_imagem,
            ao_enviar_arquivos=self._enviar_arquivos,
            ao_mudar_parametros=self._mudar_parametros,
            ao_mudar_fiscalizacao=self._mudar_fiscalizacao,
            fonte_camera_inicial=getattr(self._camera, "fonte", config.INDICE_CAMERA),
            cameras_ip_iniciais=preferencias.carregar_cameras_ip(),
            ao_escolher_camera=self._escolher_camera,
            ao_adicionar_camera_ip=self._adicionar_camera_ip,
            ao_remover_camera_ip=self._remover_camera_ip,
        )

        self._painel_auditoria = PainelAuditoria(
            divisor,
            pasta_imagens=self._auditoria.pasta_imagens,
            ao_zerar=self._zerar_auditoria,
            ao_excluir=self._excluir_evento,
            ao_salvar_relatorio=self._salvar_relatorio,
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

        # Situação da catraca de demonstração (ESP32 pelo cabo USB)
        self._rotulo_catraca = ttk.Label(rodape, text="", style="Suave.TLabel")
        self._rotulo_catraca.pack(side="left", padx=(0, 20))

        self._rotulo_aviso = ttk.Label(rodape, text="", style="TLabel")
        self._rotulo_aviso.pack(side="left")

        ttk.Label(rodape, text=TEXTO_ATALHOS, style="Suave.TLabel").pack(side="right")

    def _configurar_atalhos(self):

        self._raiz.bind_all("<space>", self._atalho(self._alternar_camera))
        self._raiz.bind_all("<Escape>", lambda _evento: self._painel_auditoria.limpar_filtro())

        # S (maiúsculo ou minúsculo) salva uma imagem com os rótulos marcados
        for tecla in ("s", "S"):
            self._raiz.bind_all(tecla, self._atalho(self._painel_monitoramento.salvar_imagem))

        # Ctrl+V cola no dataset uma imagem copiada. Enquanto o usuário
        # digita na busca, Ctrl+V continua colando TEXTO ali, como esperado.
        for tecla in ("<Control-v>", "<Control-V>"):
            self._raiz.bind_all(tecla, self._atalho(self._colar_imagem))

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
    # CATRACA DE DEMONSTRAÇÃO (ESP32 pelo cabo USB)
    # ============================================================

    def _iniciar_catraca(self):
        """
        Começa a enviar o status à catraca pelo cabo USB.

        Sem o ESP32 plugado não faz mal: a thread só fica procurando a
        placa em segundo plano. Se a biblioteca pyserial não estiver
        instalada, o programa segue normalmente, só sem a catraca.
        """

        if not config.CATRACA_SERIAL_ATIVA:
            return

        try:
            import serial  # noqa: F401  (só para saber se está instalada)

        except ImportError:

            self._rotulo_catraca.config(text="Catraca: instale o pyserial (veja o README)")
            return

        self._catraca = CatracaSerial(self._ler_ao_vivo)
        self._catraca.iniciar()

    def _atualizar_catraca(self):
        """Mostra na barra de status se a catraca está conectada."""

        if self._catraca is None:
            return

        texto = self._catraca.situacao

        # Só mexe no rótulo quando o texto muda
        if texto != self._rotulo_catraca.cget("text"):
            self._rotulo_catraca.config(text=texto)

    # ============================================================
    # CARGA DA IA (thread em segundo plano)
    # ============================================================

    def _carregar_ia(self):

        try:

            if not self._epis_do_modelo:

                raise FileNotFoundError(
                    "Nenhum modelo encontrado em 'modelos/'. Colete imagens "
                    "rotuladas e execute o treinar.py."
                )

            # Importados aqui, e não no topo do arquivo, porque trazem
            # o TensorFlow junto: é o que mais demora no programa.
            from safetech.nucleo.classificador import ClassificadorEPI

            # Os detectores dos dois modos ficam carregados desde já,
            # para a troca entre rosto e corpo na tela ser imediata.
            self._resultado_carga = ("ok", ClassificadorEPI(), detector.criar_detectores())

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

        if not self._resultado_carga[1].por_epi:

            self._avisar(
                "Modelo antigo em uso: avalia só o conjunto completo de EPIs, "
                "sem distinguir cada equipamento.",
                segundos=15,
            )

        _, classificador, detectores = self._resultado_carga

        self._analisador = Analisador(
            self._camera,
            detectores,
            classificador,
            self._auditoria,
            self._parametros,
        )

        self._analisador.iniciar()

        if not detectores[config.MODO_CATRACA].disponivel:

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

            if self._cameras_encontradas is not None:

                self._painel_monitoramento.definir_cameras(self._cameras_encontradas)
                self._cameras_encontradas = None

            self._verificar_carga()
            self._atualizar_catraca()

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

            if self._camera_e_ip():
                painel.mostrar_mensagem("Conectando à câmera IP...")
            else:
                painel.mostrar_mensagem("Abrindo a câmera...")

        elif estado is EstadoCamera.RECONECTANDO:

            # Câmera IP que caiu: a própria câmera tenta voltar sozinha
            painel.definir_botao_camera("Parar câmera", "Perigo.TButton")
            painel.mostrar_mensagem(
                "A conexão com a câmera IP caiu.\n"
                "Tentando reconectar..."
            )

        elif estado is EstadoCamera.ERRO:

            painel.definir_botao_camera("Tentar novamente", "Primario.TButton")

            if self._camera_e_ip():
                painel.mostrar_mensagem(
                    "Não foi possível conectar à câmera IP.\n"
                    "Confira o endereço, o usuário e a senha, e se a câmera\n"
                    "está ligada e na mesma rede que este computador."
                )
            else:
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

        anotacao.desenhar_pessoas(imagem, estado.pessoas, escala, modo=estado.modo)

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

        elif self._camera.estado is EstadoCamera.RECONECTANDO:
            status = ("RECONECTANDO", "A conexão com a câmera IP caiu. Tentando de novo...", CORES["alerta"])

        elif self._camera.estado is not EstadoCamera.ATIVA:
            status = ("CÂMERA DESLIGADA", "Ligue a câmera para iniciar o monitoramento.", CORES["neutro"])

        else:
            status = self._descrever_acesso(self._analisador.estado())

        if status != self._ultimo_status:

            self._ultimo_status = status

            self._painel_monitoramento.definir_status(*status)

    @staticmethod
    def _descrever_acesso(estado: EstadoCena):
        """
        Transforma o estado da cena em (título, detalhe, cor) para a faixa de status.

        Os títulos dependem do modo: na catraca, "ACESSO LIBERADO" /
        "ACESSO NEGADO"; na vigilância, "EM CONFORMIDADE" / "NÃO
        CONFORME" (lá não há acesso a liberar).
        """

        textos = modos.textos(estado.modo)

        total = len(estado.pessoas)

        plural = "pessoa" if total == 1 else "pessoas"

        # O que está sendo cobrado, para o status se explicar sozinho
        if estado.exigidos:
            exigencia = f"Setor {estado.setor}: exige {epis.nomes_dos_epis(estado.exigidos)}."
        else:
            exigencia = f"Setor {estado.setor}: nenhum EPI exigido."

        if estado.acesso is StatusAcesso.LIBERADO:

            return (
                textos["faixa_ok"],
                f"{total} {plural} {textos['lugar']}, todas com os EPIs exigidos.\n{exigencia}",
                CORES["sucesso"],
            )

        if estado.acesso is StatusAcesso.NEGADO:

            negadas = [
                pessoa for pessoa in estado.pessoas
                if pessoa.status is StatusPessoa.NEGADO
            ]

            # Com várias pessoas, listar uma por uma não cabe na faixa.
            # O resumo diz quantas estão irregulares e, para cada EPI
            # exigido, em quantas pessoas ele falta. O detalhe por
            # pessoa fica no log de auditoria, com a foto.
            faltas = ",  ".join(
                f"{epis.nome_do_epi(chave)} ({quantidade})"
                for chave in estado.exigidos
                if (quantidade := sum(1 for pessoa in negadas if chave in pessoa.faltando))
            )

            return (
                textos["faixa_irregular"],
                f"{len(negadas)} de {total} {plural} sem EPI exigido. Faltando: {faltas}\n{exigencia}",
                CORES["perigo"],
            )

        if estado.acesso is StatusAcesso.ANALISANDO:

            return (
                "ANALISANDO",
                f"{total} {plural} {textos['lugar']}, verificando os equipamentos...\n{exigencia}",
                CORES["alerta"],
            )

        return (
            "AGUARDANDO",
            f"Nenhuma pessoa {textos['lugar']}.\n{exigencia}",
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

        elif estado in (EstadoCamera.ATIVA, EstadoCamera.RECONECTANDO):
            self._camera.parar()

    def _guardar_cameras_encontradas(self, indices):
        """Chamado pela thread da busca; a interface preenche a lista no próximo ciclo."""

        self._cameras_encontradas = indices

    def _escolher_camera(self, fonte):
        """
        Chamado quando o usuário escolhe outra câmera na lista.

        fonte -> número da webcam ou endereço da câmera IP.

        Se a câmera estava ligada, a nova liga sozinha; se estava
        parada, só fica escolhida para o próximo "Iniciar câmera".
        """

        self._camera.trocar_fonte(fonte)

        preferencias.salvar_fonte_camera(fonte)

        # Faz o vídeo e o botão refletirem o novo estado da câmera
        self._ultimo_estado_camera = None
        self._ultimo_desenho = None

        # Pelo nome, nunca pelo endereço (que pode ter a senha)
        self._avisar(f"{self._painel_monitoramento.nome_camera(fonte)} selecionada.")

    def _camera_e_ip(self) -> bool:

        return eh_endereco_ip(getattr(self._camera, "fonte", None))

    # ------------------------------------------------------
    # CÂMERAS IP: ADICIONAR E REMOVER
    # ------------------------------------------------------

    def _adicionar_camera_ip(self):
        """
        Opção "+ Adicionar câmera IP..." da lista: pede nome e endereço,
        salva a câmera e já passa a usá-la.
        """

        cameras = preferencias.carregar_cameras_ip()

        resposta = pedir_camera_ip(self._raiz, f"Câmera IP {len(cameras) + 1}")

        if resposta is None:
            return

        nome, endereco = resposta

        # O mesmo endereço não entra duas vezes: só é selecionado
        if endereco not in [existente for _, existente in cameras]:

            cameras.append((nome, endereco))

            preferencias.salvar_cameras_ip(cameras)

        self._painel_monitoramento.definir_cameras_ip(cameras, endereco)

        self._escolher_camera(endereco)

        # Já liga a câmera nova, para o usuário ver na hora se conectou
        if self._analisador is not None and self._camera.estado is EstadoCamera.PARADA:
            self._camera.iniciar()

    def _remover_camera_ip(self, endereco):
        """Botão "Remover" ao lado da lista: tira a câmera IP do cadastro."""

        nome = self._painel_monitoramento.nome_camera(endereco)

        confirmou = messagebox.askyesno(
            "Remover câmera IP",
            f"Remover {nome} da lista de câmeras?\n\n"
            "O programa volta a usar a webcam.",
            default="no",
            parent=self._raiz,
        )

        if not confirmou:
            return

        cameras = [
            (nome_camera, existente)
            for nome_camera, existente in preferencias.carregar_cameras_ip()
            if existente != endereco
        ]

        preferencias.salvar_cameras_ip(cameras)

        # Se era a câmera em uso, volta para a última webcam usada
        if self._camera.fonte == endereco:
            fonte = self._painel_monitoramento.webcam_lembrada
        else:
            fonte = self._camera.fonte

        self._painel_monitoramento.definir_cameras_ip(cameras, fonte)

        self._escolher_camera(fonte)

    def _mudar_parametros(self, limiar_confianca, intervalo_classificacao):
        """Chamado quando o usuário move um controle deslizante."""

        self._parametros.limiar_confianca = limiar_confianca
        self._parametros.intervalo_classificacao = intervalo_classificacao

    def _mudar_fiscalizacao(self, setor, exigidos):
        """
        Chamado quando o usuário escolhe um setor ou marca/desmarca um EPI.

        O efeito é imediato: o analisador passa a cobrar só os EPIs
        marcados já no próximo ciclo. A seleção também é gravada, para
        o programa reabrir com ela.
        """

        self._parametros.setor = setor
        self._parametros.exigidos = tuple(exigidos)

        self._salvar_preferencias()

        # O texto da faixa de status depende do setor
        self._ultimo_status = None

    def _mudar_modo_deteccao(self, modo):
        """
        Chamado quando o usuário alterna entre "Catraca" e "Vigilância".

        A troca vale já no próximo ciclo de análise, sem reiniciar o
        programa nem a câmera. As pessoas que estavam sendo
        acompanhadas são esquecidas (o analisador cuida disso), porque
        a caixa de um modo (rosto) não corresponde à do outro (corpo).

        A catraca física acompanha sozinha: o envio pelo cabo e o
        painel web informam o modo, e na vigilância ela fica fechada.
        """

        self._parametros.modo_deteccao = modo

        self._salvar_preferencias()

        if modo == config.MODO_VIGILANCIA:
            self._avisar(
                "Modo vigilância: verifica se todos na área estão com os EPIs e registra. "
                "A catraca fica desligada.",
                segundos=7,
            )
        else:
            self._avisar(
                "Modo catraca: libera ou nega o acesso, uma pessoa por vez, de frente para a câmera.",
                segundos=7,
            )

    def _salvar_preferencias(self):
        """Grava setor, EPIs exigidos e modo de operação para a próxima abertura."""

        preferencias.salvar(
            self._parametros.setor,
            self._parametros.exigidos,
            self._parametros.modo_deteccao,
        )

    def _salvar_imagem(self, usando):
        """
        Salva no dataset o recorte de cada pessoa do frame atual, com
        os rótulos marcados na tela (quais EPIs a pessoa está usando).
        """

        frame, _ = self._camera.ler()

        if frame is None or self._analisador is None:
            self._avisar("Ligue a câmera antes de salvar imagens.")
            return

        caixas = [pessoa.caixa for pessoa in self._analisador.estado().pessoas]

        arquivos = self._coletor.salvar(frame, caixas, usando)

        self._atualizar_resumo_dataset()

        descricao = "1 imagem salva" if len(arquivos) == 1 else f"{len(arquivos)} imagens salvas"

        if not caixas:
            descricao += " (ninguém detectado: frame inteiro)"

        # Repete os rótulos no aviso: é a chance de perceber um engano
        rotulos = epis.nomes_dos_epis(chave for chave in config.EPIS if chave in usando)

        self._avisar(f"{descricao}, rotulada como usando: {rotulos or 'nenhum EPI'}.")

    # ------------------------------------------------------
    # RELATÓRIO DO MOMENTO
    # ------------------------------------------------------

    def _salvar_relatorio(self, registro):
        """
        Botão "Salvar relatório" da auditoria: grava um relatório
        completo do momento da linha selecionada e o abre no navegador.

        Além do evento escolhido, o relatório lista os outros eventos
        registrados no mesmo instante (mesmo segundo), para mostrar o
        momento inteiro, e não só uma pessoa.
        """

        mesmo_momento = [
            outro
            for outro in self._auditoria.carregar_historico()
            if outro.timestamp == registro.timestamp and outro != registro
        ]

        try:

            pasta = relatorio.salvar(
                registro,
                self._auditoria.pasta_imagens,
                outros_do_momento=mesmo_momento,
            )

        except OSError as erro:
            self._avisar(f"Não foi possível salvar o relatório: {erro}", segundos=10)
            return

        self._avisar(f"Relatório salvo em auditoria/relatorios/{pasta.name}.", segundos=8)

        webbrowser.open((pasta / "relatorio.html").as_uri())

    # ------------------------------------------------------
    # ZERAR A AUDITORIA
    # ------------------------------------------------------

    def _zerar_auditoria(self):
        """
        Botão "Zerar": esvazia o log e as fotos de evidência e recomeça
        a contagem. Pede confirmação, porque é um registro de auditoria.
        """

        confirmou = messagebox.askyesno(
            "Zerar a auditoria",
            "Zerar o log de auditoria e as fotos de evidência?\n\n"
            "A tela volta ao zero e as pessoas na câmera passam a contar "
            "como novas.\n\n"
            "Nada é apagado: os dados atuais vão para a pasta "
            "'auditoria/arquivados'.",
            icon="warning",
            default="no",
            parent=self._raiz,
        )

        if not confirmou:
            return

        try:
            destino, eventos, fotos = self._auditoria.zerar()

        except OSError as erro:

            # Ex.: o CSV ou uma foto está aberto em outro programa
            self._avisar(f"Não foi possível zerar: {erro}", segundos=10)
            return

        self._painel_auditoria.esvaziar()

        if self._analisador is not None:

            # Eventos que o analisador gravou e a tela ainda não mostrou
            # pertencem ao log antigo: não devem reaparecer na tabela.
            fila = self._analisador.registros_novos

            while not fila.empty():
                fila.get_nowait()

            # Quem está na câmera volta a gerar um evento de entrada
            self._analisador.reiniciar_pessoas()

        if destino is None:
            self._avisar("A auditoria já estava vazia.")
        else:
            self._avisar(
                f"Auditoria zerada: {eventos} evento(s) e {fotos} foto(s) "
                f"arquivados em auditoria/arquivados/{destino.name}.",
                segundos=8,
            )

    # ------------------------------------------------------
    # EXCLUIR UMA LINHA DA AUDITORIA
    # ------------------------------------------------------

    def _excluir_evento(self, registro):
        """
        Botão "Excluir linha": tira um evento da tabela e do log.

        Pede confirmação. Nada é apagado: a linha e a foto vão para
        'auditoria/excluidos' (o serviço de auditoria cuida disso).
        """

        resultado = modos.resultado(registro.modo, registro.liberado == "SIM").lower()

        confirmou = messagebox.askyesno(
            "Excluir evento",
            f"Excluir o evento de {registro.pessoa} ({resultado}) "
            f"de {registro.timestamp}?\n\n"
            "Ele sai da tabela, do log e do painel web.\n\n"
            "Nada é apagado: a linha e a foto vão para a pasta "
            "'auditoria/excluidos'.",
            icon="warning",
            default="no",
            parent=self._raiz,
        )

        if not confirmou:
            return

        try:
            excluido = self._auditoria.excluir(registro)

        except OSError as erro:

            # Ex.: o CSV está aberto no Excel
            self._avisar(f"Não foi possível excluir: {erro}", segundos=10)
            return

        # Some da tela de qualquer jeito: se não estava mais no log
        # (ex.: a auditoria foi zerada), também não deve aparecer.
        self._painel_auditoria.remover(registro)

        if excluido:
            self._avisar(f"Evento de {registro.pessoa} excluído e guardado em auditoria/excluidos.")
        else:
            self._avisar("Esse evento não estava mais no log.")

    # ------------------------------------------------------
    # IMPORTAÇÃO DE IMAGENS (arquivo ou Ctrl+V)
    # ------------------------------------------------------

    def _enviar_arquivos(self, usando):
        """Botão "Enviar arquivo": escolhe uma ou mais imagens do computador."""

        caminhos = filedialog.askopenfilenames(
            parent=self._raiz,
            title="Escolha as imagens para o dataset",
            filetypes=[
                ("Imagens", importacao.EXTENSOES),
                ("Todos os arquivos", "*.*"),
            ],
        )

        if not caminhos:
            return

        imagens = [importacao.abrir_arquivo(caminho) for caminho in caminhos]

        lidas = [imagem for imagem in imagens if imagem is not None]

        self._importar_imagens(lidas, len(imagens) - len(lidas), usando)

    def _colar_imagem(self):
        """Ctrl+V: importa a imagem (ou os arquivos de imagem) copiados."""

        imagens, falhas = importacao.ler_area_de_transferencia()

        if not imagens and not falhas:
            self._avisar("Nada para colar: copie uma imagem (ou um arquivo de imagem) primeiro.")
            return

        self._importar_imagens(
            imagens,
            falhas,
            self._painel_monitoramento.rotulos_marcados(),
        )

    def _importar_imagens(self, imagens, falhas, usando):
        """
        Grava no dataset imagens vindas de fora da câmera.

        Elas recebem o mesmo tratamento da captura: o detector acha as
        pessoas e o que é salvo é o recorte de cada uma (ou a imagem
        inteira, se ninguém for encontrado), com os rótulos marcados.
        """

        # Detector próprio da importação, criado só quando necessário.
        # O detector da linha de análise roda em outra thread e não
        # pode ser usado por duas ao mesmo tempo.
        #
        # Usa o MESMO modo da tela (rosto ou corpo): assim as imagens
        # importadas ficam com o mesmo enquadramento das capturadas
        # pela câmera naquele modo.
        modo = self._parametros.modo_deteccao

        if modo not in self._detectores_importacao:
            self._detectores_importacao[modo] = detector.criar_detector(modo)

        detector_importacao = self._detectores_importacao[modo]

        recortes = 0

        for imagem in imagens:

            caixas = detector_importacao.detectar(imagem)

            recortes += len(self._coletor.salvar(imagem, caixas, usando))

        self._atualizar_resumo_dataset()

        partes = []

        if imagens:

            rotulos = epis.nomes_dos_epis(chave for chave in config.EPIS if chave in usando)

            quantidade = "1 imagem importada" if len(imagens) == 1 else f"{len(imagens)} imagens importadas"

            partes.append(
                f"{quantidade} ({recortes} recorte(s) de pessoa), "
                f"rotulada(s) como usando: {rotulos or 'nenhum EPI'}."
            )

        if falhas:
            partes.append(f"{falhas} arquivo(s) não são imagens legíveis e foram ignorados.")

        self._avisar(" ".join(partes), segundos=7)

    def _atualizar_resumo_dataset(self):

        self._painel_monitoramento.definir_resumo_dataset(*self._coletor.resumo())

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

        if self._catraca is not None:
            self._catraca.parar()

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
