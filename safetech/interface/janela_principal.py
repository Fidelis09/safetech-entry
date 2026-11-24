"""
Janela principal do SafeTech Entry.

Monta a tela e liga a interface aos serviços:

    em cima    -> marca do produto e selos de situação (IA, painel web,
                  catraca) com o relógio
    à esquerda -> a barra de áreas (uma "pílula" por câmera, com um
                  ponto na cor da situação dela) e a página da área
                  escolhida: câmera, vídeo, status, setor, modo e EPIs
                  exigidos. "+ Nova área" cria outra; com duas áreas ou
                  mais, "Visão geral" mostra todas lado a lado
    à direita  -> a auditoria, UMA só para todas as áreas
    embaixo    -> avisos e atalhos

Como as threads se dividem:

    uma thread de câmera por área     -> só captura frames
    uma thread de análise por área    -> detecta, rastreia, classifica,
                                         decide e audita
    thread da interface               -> (esta) desenha a tela ~30 vezes
                                         por segundo

A interface nunca faz trabalho pesado: a cada ciclo ela apenas pega o
frame mais recente e o último resultado da área que está à vista e
desenha. As outras áreas continuam analisando e registrando sem gastar
tempo com desenho. É por isso que a janela não trava.
"""

import threading
import time
import webbrowser
import tkinter as tk
from datetime import datetime
from tkinter import filedialog, messagebox, ttk

from PIL import ImageTk

from safetech import config
from safetech.interface import tema
from safetech.interface.area_monitorada import AreaMonitorada, descrever_acesso
from safetech.interface.componentes import BarraAreas, Selo
from safetech.interface.dialogo_area import pedir_area
from safetech.interface.dialogo_camera_ip import pedir_camera_ip
from safetech.interface.janela_configuracoes import JanelaConfiguracoes
from safetech.interface.painel_auditoria import PainelAuditoria
from safetech.interface.painel_monitoramento import PainelMonitoramento
from safetech.interface.painel_visao_geral import PainelVisaoGeral
from safetech.interface.tema import CORES
from safetech.nucleo import detector, epis, modos
from safetech.nucleo.tipos import EstadoCena
from safetech.servicos import acesso_web
from safetech.servicos import auditoria as modulo_auditoria
from safetech.servicos import busca_cameras, capturas, importacao, preferencias, relatorio
from safetech.servicos.analisador import ClassificadorCompartilhado, ParametrosAnalise
from safetech.servicos.auditoria import ServicoAuditoria
from safetech.servicos.camera import Camera, EstadoCamera, eh_endereco_ip
from safetech.servicos.catraca_serial import CatracaSerial
from safetech.servicos.dataset import ColetorDataset
from safetech.web.servidor import ServidorWeb


TEXTO_ATALHOS = "Espaço: câmera   |   S: salvar imagem   |   Ctrl+V: colar imagem   |   F11: tela cheia   |   Esc: limpar busca"

# Tamanho do ícone do cabeçalho e da barra de tarefas (px a 100% de escala)
TAMANHO_ICONE_CABECALHO = 30
TAMANHO_ICONE_JANELA = 64

# Marca no nome da aba da área que comanda a catraca física
MARCA_CATRACA_NA_ABA = "  · catraca"

# De quanto em quanto tempo (s) os pontos de situação da barra de áreas
# são conferidos. Mais que isso só gasta tempo da tela.
INTERVALO_PONTOS_DA_BARRA_SEG = 0.5


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

        # Próxima conferência dos pontos de situação da barra de áreas
        self._proxima_conferencia_pontos = 0.0

        self._fabrica_camera = fabrica_camera or Camera

        # ------------------------------------------------------
        # SERVIÇOS QUE NÃO DEPENDEM DA IA (prontos na hora)
        # ------------------------------------------------------

        # Índices das câmeras achados pela busca (thread em segundo
        # plano); a interface os lê no ciclo e preenche a lista.
        self._cameras_encontradas = None

        # UMA auditoria para todas as áreas
        self._auditoria = ServicoAuditoria()
        self._coletor = ColetorDataset()

        # EPIs que o modelo instalado reconhece. Lido sem carregar o
        # TensorFlow, para a tela já abrir com os controles certos.
        self._epis_do_modelo = epis.epis_do_modelo()

        # Modos cujo detector está na pasta (a vigilância depende de um
        # arquivo baixado à parte)
        self._modos_disponiveis = [
            modo for modo in config.MODOS_DETECCAO if detector.modo_disponivel(modo)
        ]

        # Confiança mínima e intervalo: valem para TODAS as áreas
        self._limiar, self._intervalo = preferencias.carregar_ajustes()

        # Gravação dos ajustes agendada (veja _mudar_parametros)
        self._gravacao_de_ajustes = None

        # Detectores usados só para importar imagens, um por modo
        # (cada um é criado no primeiro uso)
        self._detectores_importacao = {}

        # IA: carregada uma vez e dividida entre as áreas
        self._classificador = None
        self._detectores_carregados = None
        self._ia_pronta = False

        # Resultado do carregamento da IA, preenchido pela thread de
        # carga e lido pela interface: None, ("ok", ...) ou ("erro", msg)
        self._resultado_carga = None
        self._erro_fatal = None

        self._aviso_ate = 0.0

        # Último segundo mostrado no relógio do cabeçalho
        self._ultimo_relogio = ""

        # Áreas abertas (na ordem das abas) e a que está à vista
        self._areas = []
        self._area_atual = None

        # Ícone do programa (título da janela e barra de tarefas). A
        # referência fica guardada: sem ela o Tkinter apaga a imagem.
        self._icone_janela = ImageTk.PhotoImage(tema.desenhar_icone(TAMANHO_ICONE_JANELA))
        self._raiz.iconphoto(True, self._icone_janela)

        # ------------------------------------------------------
        # MONTAGEM DA TELA
        # ------------------------------------------------------

        self._montar()

        for indice, dados in enumerate(preferencias.carregar_areas()):

            # A câmera recebida (testes) vai para a primeira área
            self._criar_area(dados, camera=camera if indice == 0 else None)

        self._selecionar_area(self._areas[0])

        self._configurar_atalhos()

        self._painel_auditoria.carregar(self._auditoria.carregar_historico())
        self._atualizar_resumo_dataset()

        self._servidor_web = None
        self._iniciar_painel_web()

        self._catraca = None
        self._iniciar_catraca()

        self._raiz.protocol("WM_DELETE_WINDOW", self._ao_fechar)

        self._atualizar_selo_ia()

        # A IA demora alguns segundos para carregar (TensorFlow). Isso
        # é feito em segundo plano para a janela abrir imediatamente.
        threading.Thread(target=self._carregar_ia, name="carga-ia", daemon=True).start()

        # Procura as câmeras para a lista (só com a câmera real: uma
        # câmera falsa de teste não tem o que procurar)
        if camera is None:
            busca_cameras.procurar_em_segundo_plano(self._guardar_cameras_encontradas)

        self._ciclo()

    # ============================================================
    # A ÁREA À VISTA (atalhos para o código e para os testes)
    # ============================================================

    @property
    def _camera(self):
        return self._area_atual.camera

    @property
    def _parametros(self):
        return self._area_atual.parametros

    @property
    def _painel_monitoramento(self):
        return self._area_atual.painel

    @property
    def _analisador(self):
        return self._area_atual.analisador

    # Texto da faixa de status (fica em area_monitorada.py)
    _descrever_acesso = staticmethod(descrever_acesso)

    # ============================================================
    # MONTAGEM
    # ============================================================

    def _montar(self):

        self._raiz.columnconfigure(0, weight=1)
        self._raiz.rowconfigure(1, weight=1)

        # ------------------------------------------------------
        # CABEÇALHO
        # ------------------------------------------------------

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

        self._selo_painel_web = Selo(selos, ao_clicar=self._abrir_painel_web)
        self._selo_painel_web.grid(row=0, column=1, padx=(0, 8))
        self._selo_painel_web.grid_remove()

        self._selo_catraca = Selo(selos)
        self._selo_catraca.grid(row=0, column=2, padx=(0, 8))
        self._selo_catraca.grid_remove()

        # Os testes e o resto do código leem os textos por estes nomes
        self._rotulo_painel_web = self._selo_painel_web.rotulo
        self._rotulo_catraca = self._selo_catraca.rotulo

        # Endereço do painel web (preenchido quando o servidor sobe)
        self._endereco_painel_web = None

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

        # ------------------------------------------------------
        # PAINÉIS LADO A LADO, COM DIVISOR ARRASTÁVEL
        # ------------------------------------------------------

        divisor = ttk.PanedWindow(self._raiz, orient="horizontal")
        divisor.grid(row=1, column=0, sticky="nsew", padx=12)

        # ---------------- esquerda: as áreas, uma por aba ----------------

        esquerda = ttk.Frame(divisor, style="Painel.TFrame", padding=18)
        esquerda.columnconfigure(0, weight=1)
        esquerda.rowconfigure(2, weight=1)

        topo = ttk.Frame(esquerda, style="Painel.TFrame")
        topo.grid(row=0, column=0, sticky="ew", pady=(0, 10))

        ttk.Label(topo, text="Monitoramento", style="Titulo.Painel.TLabel").pack(side="left")

        # Câmera, confiança, intervalo e coleta ficam numa janela à parte
        ttk.Button(
            topo,
            text="Configurações",
            style="Secundario.TButton",
            command=self._abrir_configuracoes,
            takefocus=False,
        ).pack(side="right")

        # Barra de áreas: "Visão geral", uma pílula por área e "+ Nova área"
        self._barra_areas = BarraAreas(
            esquerda,
            ao_escolher_area=self._ao_escolher_na_barra,
            ao_nova_area=self._nova_area,
            ao_alternar_visao_geral=self._ao_alternar_visao_geral,
        )
        self._barra_areas.grid(row=1, column=0, sticky="ew", pady=(0, 6))

        # Todas as áreas lado a lado. Só faz sentido com duas ou mais:
        # fica desativado enquanto houver uma área só.
        self._visao_geral_ativa = self._barra_areas.visao_geral_ativa
        self._botao_visao_geral = self._barra_areas.botao_visao_geral

        # O Notebook só guarda as páginas das áreas: a fileira de abas
        # fica escondida (a navegação é a barra acima)
        self._caderno = ttk.Notebook(esquerda, style="SemAbas.TNotebook", takefocus=False)
        self._caderno.grid(row=2, column=0, sticky="nsew")

        # Mesmo lugar das abas; aparece no lugar delas (grid_remove nas abas)
        self._visao_geral = PainelVisaoGeral(
            esquerda,
            ao_abrir_area=self._abrir_area_da_visao_geral,
            ao_alternar_camera=self._alternar_camera,
        )

        # Última aba: não é uma área, é o botão de criar uma
        self._aba_nova = ttk.Frame(self._caderno, style="Painel.TFrame")
        self._caderno.add(self._aba_nova, text="  +  Nova área  ")

        self._caderno.bind("<<NotebookTabChanged>>", self._ao_trocar_aba)

        # ---------------- janela de Configurações (escondida) ----------------

        self._configuracoes = JanelaConfiguracoes(
            self._raiz,
            limiar_inicial=self._limiar,
            intervalo_inicial=self._intervalo,
            fonte_camera_inicial=config.INDICE_CAMERA,
            cameras_ip_iniciais=preferencias.carregar_cameras_ip(),
            ao_escolher_camera=self._escolher_camera,
            ao_adicionar_camera_ip=self._adicionar_camera_ip,
            ao_remover_camera_ip=self._remover_camera_ip,
            ao_nova_area=self._nova_area,
            ao_renomear_area=self._renomear_area,
            ao_remover_area=self._remover_area,
            ao_mudar_controle_catraca=self._mudar_controle_catraca,
            ao_mudar_parametros=self._mudar_parametros,
            ao_salvar_imagem=self._salvar_imagem,
            ao_enviar_arquivos=self._enviar_arquivos,
            ao_aplicar_painel_web=self._aplicar_painel_web,
            ao_abrir_painel_web=self._abrir_painel_web,
            escala=self._escala,
        )

        # ---------------- direita: auditoria (uma só) ----------------

        self._painel_auditoria = PainelAuditoria(
            divisor,
            pasta_imagens=self._auditoria.pasta_imagens,
            ao_zerar=self._zerar_auditoria,
            ao_excluir=self._excluir_evento,
            ao_salvar_relatorio=self._salvar_relatorio,
            ao_exportar=self._exportar_auditoria,
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

    def _configurar_atalhos(self):

        self._raiz.bind_all("<space>", self._atalho(self._alternar_camera))
        self._raiz.bind_all("<Escape>", self._ao_apertar_esc)

        # F11: tela cheia (apresentação, monitor dedicado na portaria)
        self._raiz.bind_all("<F11>", lambda _evento: self._alternar_tela_cheia())

        # S (maiúsculo ou minúsculo) salva uma imagem com os rótulos marcados
        for tecla in ("s", "S"):
            self._raiz.bind_all(tecla, self._atalho(self._configuracoes.salvar_imagem))

        # Ctrl+V cola no dataset uma imagem copiada. Enquanto o usuário
        # digita na busca, Ctrl+V continua colando TEXTO ali, como esperado.
        for tecla in ("<Control-v>", "<Control-V>"):
            self._raiz.bind_all(tecla, self._atalho(self._colar_imagem))

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
            self._avisar("Tela cheia. F11 ou Esc para sair.")

    def _atalho(self, acao):
        """Embrulha uma ação de atalho: ela não dispara enquanto o usuário digita na busca."""

        def tratar(_evento):

            if not self._painel_auditoria.campo_de_busca_em_foco():
                acao()

        return tratar

    # ============================================================
    # ÁREAS: criar, mostrar, renomear, remover
    # ============================================================

    def _criar_area(self, dados, camera=None):
        """
        Monta uma área a partir dos seus dados: câmera, parâmetros da
        análise e a aba na tela. Se a IA já carregou, a análise dela
        começa na hora.
        """

        # Modo sem detector instalado volta para a catraca; só pode ser
        # exigido o que o modelo sabe reconhecer
        if dados.modo not in self._modos_disponiveis:
            dados.modo = config.MODO_CATRACA

        dados.exigidos = [chave for chave in dados.exigidos if chave in self._epis_do_modelo]

        if camera is None:
            camera = self._fabrica_camera(dados.fonte)
        else:
            # Câmera recebida pronta (testes): a área passa a ser a dela
            dados.fonte = getattr(camera, "fonte", dados.fonte)

        parametros = ParametrosAnalise(
            setor=dados.setor,
            exigidos=tuple(dados.exigidos),
            modo_deteccao=dados.modo,
            limiar_confianca=self._limiar,
            intervalo_classificacao=self._intervalo,
            area=dados.nome,
        )

        area = AreaMonitorada(dados, camera, parametros, painel=None)

        # Cada controle da aba avisa a janela dizendo DE QUAL área veio
        area.painel = PainelMonitoramento(
            self._caderno,
            epis_do_modelo=self._epis_do_modelo,
            modos_disponiveis=self._modos_disponiveis,
            modo_inicial=dados.modo,
            setor_inicial=dados.setor,
            exigidos_iniciais=dados.exigidos,
            ao_mudar_modo=lambda modo: self._mudar_modo(area, modo),
            ao_escolher_setor=lambda setor: self._escolher_setor(area, setor),
            ao_mudar_fiscalizacao=lambda setor, exigidos: self._mudar_fiscalizacao(area, setor, exigidos),
            ao_alternar_camera=lambda: self._alternar_camera(area),
            ao_capturar_foto=lambda: self._capturar_foto(area),
            ao_trocar_camera=lambda: self._trocar_camera_da_area(area),
        )

        # Entra antes da aba "+ Nova área", que fica sempre por último
        self._caderno.insert(self._aba_nova, area.painel, text=self._texto_da_aba(dados))

        self._areas.append(area)

        self._atualizar_barra()
        self._atualizar_botao_visao_geral()

        if self._ia_pronta:

            area.iniciar_analise(detector.criar_detectores(), self._classificador, self._auditoria)

        elif self._erro_fatal:

            self._mostrar_erro_de_carga(area)

        else:

            area.painel.definir_status(
                "CARREGANDO",
                "Preparando o modelo de IA. Isso leva alguns segundos...",
                CORES["neutro"],
            )
            area.painel.mostrar_mensagem("Carregando o modelo de IA...")

        return area

    @staticmethod
    def _texto_da_aba(dados):
        """Nome da área na aba, com a marca de quem comanda a catraca."""

        return dados.nome + (MARCA_CATRACA_NA_ABA if dados.controla_catraca else "")

    def _atualizar_textos_das_abas(self):

        for area in self._areas:
            self._caderno.tab(area.painel, text=self._texto_da_aba(area.dados))

        self._atualizar_barra()

    def _atualizar_barra(self):
        """Refaz as pílulas da barra de áreas e o cabeçalho de câmera de cada área."""

        # Espaço antes do nome: o ponto de situação não encosta no texto
        self._barra_areas.definir_areas(
            [(str(area.painel), "  " + self._texto_da_aba(area.dados).strip()) for area in self._areas]
        )

        for area in self._areas:
            area.painel.definir_camera(self._configuracoes.nome_camera(area.dados.fonte), area.dados.controla_catraca)

        if self._area_atual is not None and not self._visao_geral_na_tela():
            self._barra_areas.selecionar(str(self._area_atual.painel))

        self._proxima_conferencia_pontos = 0.0

    def _ao_escolher_na_barra(self, chave):
        """Clique na pílula de uma área: abre a página dela."""

        for area in self._areas:

            if str(area.painel) == chave:
                self._selecionar_area(area)
                return

    def _atualizar_pontos_da_barra(self):
        """Pinta o ponto de cada área com a cor da situação dela agora (duas vezes por segundo)."""

        agora = time.perf_counter()

        if agora < self._proxima_conferencia_pontos:
            return

        self._proxima_conferencia_pontos = agora + INTERVALO_PONTOS_DA_BARRA_SEG

        for area in self._areas:
            self._barra_areas.definir_cor(str(area.painel), area.resumo_status()[2])

    def _selecionar_area(self, area):
        """Mostra a aba da área e faz as Configurações valerem para ela."""

        self._area_atual = area

        # Escolher uma área é sair da visão geral para a aba dela
        self._esconder_visao_geral()

        self._caderno.select(area.painel)

        self._barra_areas.selecionar(str(area.painel))

        # A auditoria mostra só os eventos da área aberta
        self._painel_auditoria.definir_area(area.nome)

        area.esquecer_desenho()

        self._atualizar_configuracoes_da_area()

    def _atualizar_configuracoes_da_area(self):

        area = self._area_atual

        self._configuracoes.definir_area_atual(
            area.nome,
            area.dados.fonte,
            area.dados.controla_catraca,
            pode_remover=len(self._areas) > 1,
        )

    def _ao_trocar_aba(self, _evento=None):

        if not self._areas:
            return

        escolhida = self._caderno.select()

        # Clicou em "+ Nova área": volta para a área de antes e abre o
        # pedido de nome (depois que o clique terminar de ser tratado)
        if escolhida == str(self._aba_nova):

            self._caderno.select(self._area_atual.painel)
            self._raiz.after_idle(self._nova_area)
            return

        for area in self._areas:

            if str(area.painel) == escolhida and area is not self._area_atual:
                self._selecionar_area(area)
                break

    def _nova_area(self):
        """Aba "+ Nova área" (ou botão nas Configurações): cria outra área com outra câmera."""

        if len(self._areas) >= config.MAXIMO_AREAS:
            self._avisar(f"Limite de {config.MAXIMO_AREAS} áreas abertas ao mesmo tempo (MAXIMO_AREAS).", segundos=7)
            return

        opcoes = self._configuracoes.opcoes_de_camera()

        # Sugere uma câmera que nenhuma área está usando
        em_uso = {area.dados.fonte for area in self._areas}
        livre = next((fonte for _, fonte in opcoes if fonte not in em_uso), opcoes[0][1] if opcoes else 0)

        resposta = pedir_area(
            self._configuracoes.pai_para_dialogos(self._raiz),
            "Nova área",
            f"Área {len(self._areas) + 1}",
            [area.nome for area in self._areas],
            cameras=opcoes,
            fonte_sugerida=livre,
        )

        if resposta is None:
            return

        nome, fonte = resposta

        dados = preferencias.DadosArea(
            nome=nome,
            fonte=fonte,
            setor=config.SETOR_PADRAO,
            exigidos=list(config.SETORES[config.SETOR_PADRAO]),
            modo=config.MODO_DETECCAO_PADRAO,
            controla_catraca=False,
        )

        area = self._criar_area(dados)

        self._selecionar_area(area)
        self._salvar_areas()

        # Uma webcam não abre em duas áreas ao mesmo tempo
        outra = next((a for a in self._areas if a is not area and a.dados.fonte == fonte), None)

        if outra is not None and not eh_endereco_ip(fonte):
            self._avisar(
                f"Área \"{nome}\" criada. Atenção: a área \"{outra.nome}\" usa a mesma webcam; "
                "só uma delas consegue ligá-la de cada vez.",
                segundos=10,
            )
        else:
            self._avisar(f"Área \"{nome}\" criada. Escolha o setor, o modo e ligue a câmera.", segundos=7)

    def _renomear_area(self):

        area = self._area_atual

        resposta = pedir_area(
            self._configuracoes.pai_para_dialogos(self._raiz),
            "Renomear área",
            area.nome,
            [outra.nome for outra in self._areas if outra is not area],
        )

        if resposta is None:
            return

        nome, _ = resposta

        # Os próximos eventos da auditoria já saem com o nome novo
        area.dados.nome = nome
        area.parametros.area = nome

        # Os eventos de antes continuam com o nome antigo (o log não é
        # reescrito); a auditoria passa a mostrar os do nome novo
        if area is self._area_atual and not self._visao_geral_na_tela():
            self._painel_auditoria.definir_area(nome)

        self._atualizar_textos_das_abas()
        self._atualizar_configuracoes_da_area()
        self._salvar_areas()

    def _remover_area(self):
        """Tira a área aberta (a câmera dela é desligada). A auditoria não muda."""

        if len(self._areas) <= 1:
            return

        area = self._area_atual

        confirmou = messagebox.askyesno(
            "Remover área",
            f"Remover a área \"{area.nome}\"?\n\n"
            "A câmera dela é desligada. Os eventos que ela já registrou "
            "continuam na auditoria.",
            default="no",
            parent=self._configuracoes.pai_para_dialogos(self._raiz),
        )

        if not confirmou:
            return

        area.parar()

        self._areas.remove(area)

        self._caderno.forget(area.painel)
        area.painel.destroy()

        self._atualizar_barra()
        self._atualizar_botao_visao_geral()

        self._selecionar_area(self._areas[0])
        self._salvar_areas()

        if area.dados.controla_catraca:
            self._avisar(f"Área \"{area.nome}\" removida. Nenhuma área comanda a catraca agora.", segundos=7)
        else:
            self._avisar(f"Área \"{area.nome}\" removida.")

    def _mudar_controle_catraca(self, marcado):
        """
        "Esta área comanda a catraca física": só uma área pode. Marcar
        na área aberta desmarca todas as outras.
        """

        for area in self._areas:
            area.dados.controla_catraca = marcado and area is self._area_atual

        self._atualizar_textos_das_abas()
        self._salvar_areas()

        if marcado:
            self._avisar(f"A catraca agora obedece à área \"{self._area_atual.nome}\".")
        else:
            self._avisar("Nenhuma área comanda a catraca: ela fica desligada.")

    # ------------------------------------------------------
    # VISÃO GERAL (todas as áreas lado a lado)
    # ------------------------------------------------------

    def _ao_alternar_visao_geral(self):
        """Botão "Visão geral": mostra ou esconde todas as áreas lado a lado."""

        if self._visao_geral_ativa.get() and len(self._areas) >= 2:

            self._visao_geral.definir_areas(self._areas)

            self._caderno.grid_remove()
            self._visao_geral.grid(row=2, column=0, sticky="nsew")

            # Nenhuma área marcada na barra: a visão geral está na tela
            self._barra_areas.selecionar("")

            # Na visão geral, a auditoria mostra os eventos de todas as áreas
            self._painel_auditoria.definir_area(None)

        else:
            self._esconder_visao_geral()

            if self._area_atual is not None:
                self._barra_areas.selecionar(str(self._area_atual.painel))
                self._painel_auditoria.definir_area(self._area_atual.nome)

    def _esconder_visao_geral(self):

        self._visao_geral_ativa.set(False)

        self._visao_geral.grid_remove()
        self._caderno.grid()

    def _visao_geral_na_tela(self) -> bool:

        return self._visao_geral_ativa.get()

    def _abrir_area_da_visao_geral(self, area):
        """Clique num quadro da visão geral: abre a aba daquela área."""

        if area in self._areas:
            self._selecionar_area(area)

    def _atualizar_botao_visao_geral(self):
        """A visão geral só existe com duas áreas ou mais; acompanha quem entra e sai."""

        if len(self._areas) >= 2:
            self._botao_visao_geral.state(["!disabled"])
        else:
            self._botao_visao_geral.state(["disabled"])
            self._esconder_visao_geral()

        if self._visao_geral_na_tela():
            self._visao_geral.definir_areas(self._areas)

    def _area_da_catraca(self):
        """A área que comanda a catraca física, ou None."""

        return next((area for area in self._areas if area.dados.controla_catraca), None)

    def _salvar_areas(self):

        preferencias.salvar_areas([area.dados for area in self._areas])

    # ============================================================
    # PAINEL WEB DO GERENTE (somente leitura)
    # ============================================================

    def _iniciar_painel_web(self):
        """Sobe o painel web com os ajustes salvos; se não der, o aplicativo segue normalmente."""

        # Ligar, porta, rede, usuário e hash da senha (Configurações > Painel web)
        self._ajustes_web = preferencias.carregar_painel_web()

        self._ligar_painel_web()

    def _ligar_painel_web(self):
        """
        Para o servidor que estiver no ar e sobe outro com os ajustes atuais.

        Devolve o texto do erro (ex.: porta em uso) ou None.
        """

        if self._servidor_web is not None:
            self._servidor_web.parar()
            self._servidor_web = None

        self._endereco_painel_web = None

        ajustes = self._ajustes_web

        senha_padrao = acesso_web.usa_senha_padrao(ajustes)

        if not ajustes.ativo:

            # Clicar no selo leva às Configurações, para ligar
            self._selo_painel_web.definir("Painel web desligado", CORES["texto_suave"])
            self._configuracoes.definir_painel_web(ajustes, None, senha_padrao)

            return None

        servidor = ServidorWeb(self._auditoria, self._ler_ao_vivo, fonte_areas=self._ler_areas, ajustes=ajustes)

        try:
            servidor.iniciar()

        except OSError:

            # Porta ocupada (outro programa ou outra cópia do aplicativo)
            erro = f"A porta {ajustes.porta} está em uso por outro programa."

            self._selo_painel_web.definir(f"Painel web indisponível (porta {ajustes.porta} em uso)", CORES["perigo"])
            self._configuracoes.definir_painel_web(ajustes, None, senha_padrao, erro=erro)

            return erro

        self._servidor_web = servidor

        self._endereco_painel_web = servidor.endereco()

        # Sem login, ou com a senha padrão (pública no repositório): o
        # selo fica amarelo, para lembrar de proteger o painel
        if senha_padrao:
            texto, cor = f"Painel web: {self._endereco_painel_web}  (troque a senha)", CORES["alerta"]
        elif not ajustes.exige_login:
            texto, cor = f"Painel web: {self._endereco_painel_web}  (sem senha)", CORES["alerta"]
        else:
            texto, cor = f"Painel web: {self._endereco_painel_web}", CORES["sucesso"]

        self._selo_painel_web.definir(texto, cor)
        self._configuracoes.definir_painel_web(ajustes, self._endereco_painel_web, senha_padrao)

        return None

    def _aplicar_painel_web(self, **campos):
        """
        Configurações > Painel web > Aplicar.

        Confere o que foi digitado, salva (a senha só como hash) e reinicia
        o servidor com os ajustes novos. Devolve (deu_certo, mensagem)
        para a janela de Configurações mostrar.
        """

        novos, erro = acesso_web.montar_ajustes(self._ajustes_web, **campos)

        if erro:
            return False, erro

        self._ajustes_web = novos

        preferencias.salvar_painel_web(novos)

        erro = self._ligar_painel_web()

        if erro:
            return False, f"{erro} Os ajustes foram salvos: escolha outra porta e aplique de novo."

        if not novos.ativo:
            self._avisar("Painel web desligado.")
            return True, "Painel web desligado."

        self._avisar(f"Painel web no ar em {self._endereco_painel_web}.")

        return True, f"Painel no ar em {self._endereco_painel_web}."

    def _abrir_painel_web(self):
        """Clique no selo do painel web: abre no navegador (ou, desligado, as Configurações)."""

        if self._endereco_painel_web:
            webbrowser.open(self._endereco_painel_web)
        else:
            self._configuracoes.mostrar("painel")

    def _ler_ao_vivo(self):
        """
        Entrega ao painel web o frame e o estado do momento: da área que
        comanda a catraca ou, sem nenhuma, da primeira área.

        É chamada pelas threads do servidor web; só usa leituras que
        já são seguras entre threads (câmera e analisador).
        """

        areas = list(self._areas)

        if not areas:
            return None, EstadoCena()

        area = self._area_da_catraca() or areas[0]

        return area.ler_ao_vivo()

    def _ler_areas(self):
        """
        Todas as áreas, para a visão geral do painel web: lista de
        (nome, frame, estado, comanda_catraca).

        Chamada pelas threads do servidor web, como _ler_ao_vivo.
        """

        resultado = []

        for area in list(self._areas):

            frame, estado = area.ler_ao_vivo()

            resultado.append((area.nome, frame, estado, area.dados.controla_catraca))

        return resultado

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

            self._selo_catraca.definir("Catraca: instale o pyserial (veja o README)", CORES["alerta"])
            return

        self._catraca = CatracaSerial(self._ler_para_catraca)
        self._catraca.iniciar()

    def _ler_para_catraca(self):
        """
        O que a catraca física deve seguir: a área marcada para comandá-la.

        Sem nenhuma área marcada, a catraca recebe "vigilância" e fica
        desligada (fechada): na dúvida, nega.
        """

        area = self._area_da_catraca()

        if area is None:
            return None, EstadoCena(modo=config.MODO_VIGILANCIA)

        return area.ler_ao_vivo()

    def _atualizar_catraca(self):
        """Mostra na barra de status se a catraca está conectada."""

        if self._catraca is None:
            return

        texto = self._catraca.situacao

        # Ponto verde só com a placa conectada; procurando = amarelo
        cor = CORES["sucesso"] if texto.endswith("conectada") else CORES["alerta"]

        # Só mexe no selo quando o texto muda
        if texto != self._rotulo_catraca.cget("text"):
            self._selo_catraca.definir(texto, cor)

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
            # para a troca entre catraca e vigilância ser imediata.
            self._resultado_carga = ("ok", ClassificadorEPI(), detector.criar_detectores())

        except Exception as erro:
            self._resultado_carga = ("erro", str(erro))

    def _verificar_carga(self):
        """Chamado a cada ciclo até a carga terminar; então ativa as áreas."""

        if self._resultado_carga is None or self._ia_pronta or self._erro_fatal:
            return

        if self._resultado_carga[0] == "erro":

            self._erro_fatal = self._resultado_carga[1]

            for area in self._areas:
                self._mostrar_erro_de_carga(area)

            self._atualizar_selo_ia()

            return

        _, classificador, detectores = self._resultado_carga

        if not classificador.por_epi:

            self._avisar(
                "Modelo antigo em uso: avalia só o conjunto completo de EPIs, "
                "sem distinguir cada equipamento.",
                segundos=15,
            )

        # O modelo de EPI é um só, dividido entre as áreas (uma por vez).
        # Os detectores não podem ser divididos: cada área tem os seus.
        self._classificador = ClassificadorCompartilhado(classificador)

        for indice, area in enumerate(self._areas):

            detectores_da_area = detectores if indice == 0 else detector.criar_detectores()

            area.iniciar_analise(detectores_da_area, self._classificador, self._auditoria)

        self._ia_pronta = True

        self._atualizar_selo_ia()

        if not detectores[config.MODO_CATRACA].disponivel:

            self._avisar(
                "Detector de rosto não encontrado em 'modelos/': a cena inteira será "
                "tratada como uma pessoa. Veja o README.",
                segundos=15,
            )

    def _atualizar_selo_ia(self):
        """Selo da IA no cabeçalho: carregando, pronta (e com qual modelo) ou com erro."""

        if self._erro_fatal:
            self._selo_ia.definir("IA com erro", CORES["perigo"])

        elif not self._ia_pronta:
            self._selo_ia.definir("IA carregando...", CORES["alerta"])

        elif self._classificador.por_epi:
            self._selo_ia.definir(f"IA pronta: {len(self._classificador.epis)} EPIs", CORES["sucesso"])

        else:
            self._selo_ia.definir("IA pronta: modelo antigo", CORES["alerta"])

    def _mostrar_erro_de_carga(self, area):

        area.painel.definir_status("ERRO AO CARREGAR", self._erro_fatal, CORES["perigo"])
        area.painel.mostrar_mensagem("Não foi possível carregar o modelo de IA.")
        area.painel.definir_botao_camera("Indisponível", "Primario.TButton", False)

    # ============================================================
    # CICLO DA INTERFACE (~30 vezes por segundo)
    # ============================================================

    def _ciclo(self):

        try:

            if self._cameras_encontradas is not None:

                self._configuracoes.definir_cameras(self._cameras_encontradas)
                self._cameras_encontradas = None

            self._verificar_carga()
            self._atualizar_catraca()
            self._atualizar_pontos_da_barra()

            if self._ia_pronta:

                # Eventos de TODAS as áreas vão para a auditoria única
                self._receber_registros()

                # Desenho só do que está à vista: a visão geral (todas,
                # em ritmo menor) ou a aba da área aberta
                if self._visao_geral_na_tela():
                    self._visao_geral.atualizar()
                else:
                    self._area_atual.atualizar_tela()

            self._atualizar_relogio()
            self._expirar_aviso()

        finally:

            # Reagenda mesmo se algo falhar, para a tela não congelar
            self._raiz.after(config.INTERVALO_TELA_MS, self._ciclo)

    def _atualizar_relogio(self):

        agora = datetime.now().strftime("%d/%m/%Y  %H:%M:%S")

        # Só mexe no rótulo quando o segundo muda
        if agora != self._ultimo_relogio:
            self._ultimo_relogio = agora
            self._rotulo_relogio.config(text=agora)

    def _receber_registros(self):
        """Passa para a tabela os eventos gravados pelas análises desde o último ciclo."""

        houve_negado_na_catraca = False

        for area in self._areas:

            if area.analisador is None:
                continue

            fila = area.analisador.registros_novos

            while not fila.empty():

                registro = fila.get_nowait()

                self._painel_auditoria.adicionar(registro)

                if registro.liberado == "NAO" and not modos.eh_vigilancia(registro.modo):
                    houve_negado_na_catraca = True

        # Um bipe só, mesmo que várias pessoas tenham sido negadas juntas
        if houve_negado_na_catraca:
            self._alertar_negado()

    def _alertar_negado(self):
        """
        Bipe de "acesso negado" (config.ALERTA_SONORO_NEGADO).

        Usa o som de erro do Windows, que toca sem travar a tela; fora
        do Windows, o bipe simples do Tkinter.
        """

        if not config.ALERTA_SONORO_NEGADO:
            return

        try:
            import winsound

            winsound.MessageBeep(winsound.MB_ICONHAND)

        except (ImportError, RuntimeError):
            self._raiz.bell()

    # ============================================================
    # AÇÕES DO USUÁRIO: câmera
    # ============================================================

    def _alternar_camera(self, area=None):
        """Botão da câmera de uma área (ou tecla Espaço, na área à vista)."""

        # Tecla Espaço na visão geral: não há UMA área à vista para ligar
        if area is None and self._visao_geral_na_tela():
            return

        area = area or self._area_atual

        # Antes de a IA carregar não há o que fazer com a câmera
        if area.analisador is None:
            return

        estado = area.camera.estado

        if estado in (EstadoCamera.PARADA, EstadoCamera.ERRO):
            area.camera.iniciar()

        elif estado in (EstadoCamera.ATIVA, EstadoCamera.RECONECTANDO):
            area.camera.parar()

    def _guardar_cameras_encontradas(self, indices):
        """Chamado pela thread da busca; a interface preenche a lista no próximo ciclo."""

        self._cameras_encontradas = indices

    def _escolher_camera(self, fonte):
        """
        Configurações > Área e câmera: troca a câmera da área aberta.

        fonte -> número da webcam ou endereço da câmera IP.

        Se a câmera estava ligada, a nova liga sozinha; se estava
        parada, só fica escolhida para o próximo "Iniciar câmera".
        """

        area = self._area_atual

        area.camera.trocar_fonte(fonte)
        area.dados.fonte = fonte

        area.painel.definir_camera(self._configuracoes.nome_camera(fonte), area.dados.controla_catraca)

        self._salvar_areas()

        # Faz o vídeo e o botão refletirem o novo estado da câmera
        area.esquecer_desenho()

        # Pelo nome, nunca pelo endereço (que pode ter a senha)
        self._avisar(f"{self._configuracoes.nome_camera(fonte)} selecionada na área \"{area.nome}\".")

    def _trocar_camera_da_area(self, area):
        """Botão "Trocar câmera" de uma área: abre as Configurações já na aba dela."""

        if area is not self._area_atual:
            self._selecionar_area(area)

        self._configuracoes.mostrar("area")

    def _capturar_foto(self, area):
        """
        Botão "Capturar foto": guarda a imagem do momento da área, com as
        caixas e o carimbo, em auditoria/capturas (fora do log).
        """

        frame, estado = area.ler_ao_vivo()

        if frame is None:
            self._avisar(f"Ligue a câmera da área \"{area.nome}\" para capturar uma foto.")
            return

        try:
            caminho = capturas.salvar(frame, estado, area.nome)

        except OSError as erro:
            self._avisar(f"Não foi possível salvar a foto: {erro}", segundos=10)
            return

        self._ultima_captura = caminho

        self._avisar(f"Foto da área \"{area.nome}\" salva em auditoria/capturas/{caminho.name}.", segundos=7)

    # ------------------------------------------------------
    # TEMA ESCURO / CLARO
    # ------------------------------------------------------

    def _atualizar_botao_tema(self):

        if tema.tema_atual() == "escuro":
            self._botao_tema.config(text="\u2600  Tema claro")    # ☀
        else:
            self._botao_tema.config(text="\u263e  Tema escuro")   # ☾

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
        self._barra_areas.esquecer_cores()
        self._visao_geral.esquecer_desenho()

        for area in self._areas:
            area.esquecer_desenho()

        self._proxima_conferencia_pontos = 0.0

        self._atualizar_botao_tema()

        preferencias.salvar_tema(novo)

        self._avisar(f"Tema {tema.NOMES_DOS_TEMAS[novo].lower()} ativado.")

    # ------------------------------------------------------
    # CÂMERAS IP: ADICIONAR E REMOVER
    # ------------------------------------------------------

    def _adicionar_camera_ip(self):
        """
        "Adicionar câmera IP...": pede nome e endereço, salva a câmera e
        já passa a usá-la na área aberta.
        """

        cameras = preferencias.carregar_cameras_ip()

        resposta = pedir_camera_ip(self._configuracoes.pai_para_dialogos(self._raiz), f"Câmera IP {len(cameras) + 1}")

        if resposta is None:
            return

        nome, endereco = resposta

        # O mesmo endereço não entra duas vezes: só é selecionado
        if endereco not in [existente for _, existente in cameras]:

            cameras.append((nome, endereco))

            preferencias.salvar_cameras_ip(cameras)

        self._configuracoes.definir_cameras_ip(cameras, endereco)

        self._escolher_camera(endereco)

        # Já liga a câmera nova, para o usuário ver na hora se conectou
        area = self._area_atual

        if area.analisador is not None and area.camera.estado is EstadoCamera.PARADA:
            area.camera.iniciar()

    def _remover_camera_ip(self, endereco):
        """"Remover câmera IP": tira a câmera do cadastro (as áreas que a usavam voltam para a webcam)."""

        nome = self._configuracoes.nome_camera(endereco)

        confirmou = messagebox.askyesno(
            "Remover câmera IP",
            f"Remover {nome} da lista de câmeras?\n\n"
            "As áreas que usavam essa câmera voltam a usar a webcam.",
            default="no",
            parent=self._configuracoes.pai_para_dialogos(self._raiz),
        )

        if not confirmou:
            return

        cameras = [
            (nome_camera, existente)
            for nome_camera, existente in preferencias.carregar_cameras_ip()
            if existente != endereco
        ]

        preferencias.salvar_cameras_ip(cameras)

        webcam = self._configuracoes.webcam_lembrada

        # Toda área que usava a câmera removida volta para a webcam
        for area in self._areas:

            if area.dados.fonte == endereco:

                area.camera.trocar_fonte(webcam)
                area.dados.fonte = webcam
                area.esquecer_desenho()

                area.painel.definir_camera(self._configuracoes.nome_camera(webcam), area.dados.controla_catraca)

        self._salvar_areas()

        self._configuracoes.definir_cameras_ip(cameras, self._area_atual.dados.fonte)

        self._avisar(f"{nome} removida.")

    # ============================================================
    # AÇÕES DO USUÁRIO: análise e fiscalização
    # ============================================================

    def _mudar_parametros(self, limiar_confianca, intervalo_classificacao):
        """
        Configurações > Análise: confiança mínima e intervalo, para TODAS as áreas.

        As análises usam o valor novo já no próximo ciclo. A gravação em
        preferencias.json espera o controle parar de mexer por
        ESPERA_SALVAR_AJUSTES_MS: arrastar o controle não regrava o
        arquivo dezenas de vezes.
        """

        self._limiar = limiar_confianca
        self._intervalo = intervalo_classificacao

        for area in self._areas:
            area.parametros.limiar_confianca = limiar_confianca
            area.parametros.intervalo_classificacao = intervalo_classificacao

        if self._gravacao_de_ajustes is not None:
            self._raiz.after_cancel(self._gravacao_de_ajustes)

        self._gravacao_de_ajustes = self._raiz.after(config.ESPERA_SALVAR_AJUSTES_MS, self._salvar_ajustes)

    def _salvar_ajustes(self):

        self._gravacao_de_ajustes = None

        preferencias.salvar_ajustes(self._limiar, self._intervalo)

    def _abrir_configuracoes(self):
        """Botão "Configurações" da tela principal."""

        self._configuracoes.mostrar()

    def _escolher_setor(self, area, setor):
        """
        Setor escolhido na lista de uma área: marca de uma vez os EPIs
        que ele exige. Só entram os EPIs que o modelo sabe reconhecer.
        """

        exigidos = tuple(
            chave for chave in config.SETORES.get(setor, []) if chave in self._epis_do_modelo
        )

        self._mudar_fiscalizacao(area, setor, exigidos)

    def _mudar_fiscalizacao(self, area, setor, exigidos):
        """
        Setor ou EPIs exigidos de uma área mudaram.

        O efeito é imediato: a análise da área passa a cobrar só os EPIs
        marcados já no próximo ciclo. A escolha também é gravada, para o
        programa reabrir com ela.
        """

        area.parametros.setor = setor
        area.parametros.exigidos = tuple(exigidos)

        area.dados.setor = setor
        area.dados.exigidos = list(exigidos)

        area.painel.mostrar_fiscalizacao(setor, area.parametros.exigidos)

        self._salvar_areas()

        # O texto da faixa de status depende do setor
        area.esquecer_desenho()

    def _mudar_modo(self, area, modo):
        """
        Uma área alternou entre "Catraca" e "Vigilância".

        A troca vale já no próximo ciclo de análise, sem reiniciar o
        programa nem a câmera. As pessoas que estavam sendo
        acompanhadas são esquecidas (o analisador cuida disso), porque
        a caixa de um modo (rosto) não corresponde à do outro (corpo).

        Se for a área que comanda a catraca física, ela acompanha: na
        vigilância, a catraca fica fechada.
        """

        area.parametros.modo_deteccao = modo
        area.dados.modo = modo

        self._salvar_areas()

        if modo == config.MODO_VIGILANCIA:
            self._avisar(
                f"\"{area.nome}\" em modo vigilância: verifica se todos na área estão com os EPIs "
                "e registra. A catraca não obedece a ela.",
                segundos=7,
            )
        else:
            self._avisar(
                f"\"{area.nome}\" em modo catraca: libera ou nega o acesso, uma pessoa por vez.",
                segundos=7,
            )

    # ============================================================
    # COLETA DE IMAGENS (da área à vista)
    # ============================================================

    def _salvar_imagem(self, usando):
        """
        Salva no dataset o recorte de cada pessoa do frame atual da área
        à vista, com os rótulos marcados (quais EPIs a pessoa está usando).
        """

        area = self._area_atual

        frame, _ = area.camera.ler()

        if frame is None or area.analisador is None:
            self._avisar(f"Ligue a câmera da área \"{area.nome}\" antes de salvar imagens.")
            return

        caixas = [pessoa.caixa for pessoa in area.analisador.estado().pessoas]

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
        registrados no mesmo instante (mesmo segundo), de qualquer área,
        para mostrar o momento inteiro.
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
    # EXPORTAR A AUDITORIA (planilha)
    # ------------------------------------------------------

    def _exportar_auditoria(self, registros):
        """
        Botão "Exportar CSV": grava numa planilha os eventos que estão
        filtrados na tela (período, resultado e busca).

        O log de auditoria não muda: a planilha é uma cópia legível,
        no formato que o Excel em português abre direto.
        """

        if not registros:
            self._avisar("Nenhum evento para exportar com os filtros escolhidos.")
            return

        caminho = filedialog.asksaveasfilename(
            parent=self._raiz,
            title="Exportar auditoria",
            defaultextension=".csv",
            initialfile=f"auditoria_safetech_{datetime.now().strftime('%Y-%m-%d_%H-%M')}.csv",
            filetypes=[("Planilha CSV", "*.csv"), ("Todos os arquivos", "*.*")],
        )

        if not caminho:
            return

        try:
            modulo_auditoria.exportar_csv(registros, caminho)

        except OSError as erro:

            # Ex.: um arquivo com esse nome está aberto no Excel
            self._avisar(f"Não foi possível exportar: {erro}", segundos=10)
            return

        quantidade = "1 evento exportado" if len(registros) == 1 else f"{len(registros)} eventos exportados"

        self._avisar(f"{quantidade} para {caminho}.", segundos=8)

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
            "A tela volta ao zero e as pessoas nas câmeras passam a contar "
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

        for area in self._areas:

            if area.analisador is None:
                continue

            # Eventos que a análise gravou e a tela ainda não mostrou
            # pertencem ao log antigo: não devem reaparecer na tabela.
            fila = area.analisador.registros_novos

            while not fila.empty():
                fila.get_nowait()

            # Quem está na câmera volta a gerar um evento de entrada
            area.analisador.reiniciar_pessoas()

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
            f"Excluir o evento de {registro.pessoa} ({resultado}, área {registro.area}) "
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
            parent=self._configuracoes.pai_para_dialogos(self._raiz),
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
            self._configuracoes.rotulos_marcados(),
        )

    def _importar_imagens(self, imagens, falhas, usando):
        """
        Grava no dataset imagens vindas de fora da câmera.

        Elas recebem o mesmo tratamento da captura: o detector acha as
        pessoas e o que é salvo é o recorte de cada uma (ou a imagem
        inteira, se ninguém for encontrado), com os rótulos marcados.
        """

        # Detector próprio da importação, criado só quando necessário.
        # O detector das análises roda em outras threads e não pode ser
        # usado por duas ao mesmo tempo.
        #
        # Usa o MESMO modo da área à vista (rosto ou corpo): assim as
        # imagens importadas ficam com o mesmo enquadramento das
        # capturadas pela câmera naquele modo.
        modo = self._area_atual.parametros.modo_deteccao

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

        self._configuracoes.definir_resumo_dataset(*self._coletor.resumo())

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

        # Ajuste mexido há menos de ESPERA_SALVAR_AJUSTES_MS: grava agora
        if self._gravacao_de_ajustes is not None:
            self._raiz.after_cancel(self._gravacao_de_ajustes)
            self._salvar_ajustes()

        for area in self._areas:
            area.parar()

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
