"""
As áreas monitoradas: criar, mostrar, renomear, remover e fiscalizar.

Cada área é uma câmera com a sua própria fiscalização (setor, EPIs,
modo) e a sua própria análise (AreaMonitorada). Este controlador cuida
do lado ESQUERDO da janela:

    - a barra de áreas (uma "pílula" por área, "Visão geral" e "+ Nova área");
    - as páginas das áreas (um ttk.Notebook com as abas escondidas);
    - a visão geral (todas as áreas lado a lado);

e de tudo o que muda uma área: o setor, os EPIs exigidos, o modo, a
confiança e o intervalo da análise, quem comanda a catraca.

As áreas ficam salvas em preferencias.json. A auditoria NÃO fica aqui
(ela é uma só para todas); este controlador só avisa o painel da
auditoria de qual área mostrar.
"""

import logging
import time
from tkinter import messagebox, ttk

from safetech import config
from safetech.interface.area_monitorada import AreaMonitorada
from safetech.interface.componentes import BarraAreas
from safetech.interface.dialogo_area import pedir_area
from safetech.interface.painel_monitoramento import PainelMonitoramento
from safetech.interface.painel_visao_geral import PainelVisaoGeral
from safetech.interface.tema import CORES
from safetech.nucleo import detector
from safetech.servicos import preferencias
from safetech.servicos.analisador import ParametrosAnalise
from safetech.servicos.camera import eh_endereco_ip


log = logging.getLogger(__name__)


# Marca no nome da área que comanda a catraca física
MARCA_CATRACA_NA_ABA = "  · catraca"

# De quanto em quanto tempo (s) os pontos de situação da barra de áreas
# são conferidos. Mais que isso só gasta tempo da tela.
INTERVALO_PONTOS_DA_BARRA_SEG = 0.5


class ControladorAreas:

    def __init__(self, janela, ia, fabrica_camera, epis_do_modelo, modos_disponiveis):
        """
        janela            -> JanelaPrincipal (Configurações, auditoria, avisos)
        ia                -> CargaIA (para ligar a análise de cada área)
        fabrica_camera    -> cria a câmera de uma área a partir da fonte
                             (número ou endereço). Criar não liga a webcam.
        epis_do_modelo    -> EPIs que o modelo reconhece (só eles podem ser exigidos)
        modos_disponiveis -> modos cujo detector está instalado
        """

        self._janela = janela
        self._ia = ia
        self._fabrica_camera = fabrica_camera
        self._epis_do_modelo = epis_do_modelo
        self._modos_disponiveis = modos_disponiveis

        # Ações das câmeras (ControladorCameras); a janela entrega depois
        # de criar os dois, porque um precisa do outro
        self.cameras = None

        # Áreas abertas (na ordem da barra) e a que está à vista
        self.lista = []
        self.atual = None

        # Confiança mínima e intervalo: valem para TODAS as áreas
        self.limiar, self.intervalo = preferencias.carregar_ajustes()

        # Gravação dos ajustes agendada (veja mudar_parametros)
        self._gravacao_de_ajustes = None

        # Próxima conferência dos pontos de situação da barra
        self._proxima_conferencia_pontos = 0.0

    # ============================================================
    # MONTAGEM (o lado esquerdo da janela, abaixo do título)
    # ============================================================

    def montar(self, pai, linha_barra, linha_paginas):
        """Cria a barra de áreas, as páginas e a visão geral dentro de 'pai'."""

        self._linha_paginas = linha_paginas

        # Barra de áreas: "Visão geral", uma pílula por área e "+ Nova área"
        self.barra = BarraAreas(
            pai,
            ao_escolher_area=self.ao_escolher_na_barra,
            ao_nova_area=self.nova,
            ao_alternar_visao_geral=self.ao_alternar_visao_geral,
        )
        self.barra.grid(row=linha_barra, column=0, sticky="ew", pady=(0, 6))

        # O Notebook só guarda as páginas das áreas: a fileira de abas
        # fica escondida (a navegação é a barra acima)
        self.caderno = ttk.Notebook(pai, style="SemAbas.TNotebook", takefocus=False)
        self.caderno.grid(row=linha_paginas, column=0, sticky="nsew")

        # Mesmo lugar das páginas; aparece no lugar delas
        self.visao_geral = PainelVisaoGeral(
            pai,
            ao_abrir_area=self.abrir_da_visao_geral,
            ao_alternar_camera=lambda area: self.cameras.alternar(area),
        )

        # Última página: não é uma área, é o "botão" de criar uma
        self.aba_nova = ttk.Frame(self.caderno, style="Painel.TFrame")
        self.caderno.add(self.aba_nova, text="  +  Nova área  ")

        self.caderno.bind("<<NotebookTabChanged>>", self._ao_trocar_aba)

    @property
    def visao_geral_ativa(self):
        """Variável do botão "Visão geral" (ligado = todas lado a lado)."""

        return self.barra.visao_geral_ativa

    @property
    def botao_visao_geral(self):
        return self.barra.botao_visao_geral

    # ============================================================
    # CRIAR UMA ÁREA
    # ============================================================

    def criar(self, dados, camera=None):
        """
        Monta uma área a partir dos seus dados: câmera, parâmetros da
        análise e a página na tela. Se a IA já carregou, a análise dela
        começa na hora.

        camera -> câmera pronta (testes); None = cria pela fabrica_camera
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
            limiar_confianca=self.limiar,
            intervalo_classificacao=self.intervalo,
            area=dados.nome,
        )

        area = AreaMonitorada(dados, camera, parametros, painel=None)

        # Cada controle da página avisa DE QUAL área veio
        area.painel = PainelMonitoramento(
            self.caderno,
            epis_do_modelo=self._epis_do_modelo,
            modos_disponiveis=self._modos_disponiveis,
            modo_inicial=dados.modo,
            setor_inicial=dados.setor,
            exigidos_iniciais=dados.exigidos,
            ao_mudar_modo=lambda modo: self.mudar_modo(area, modo),
            ao_escolher_setor=lambda setor: self.escolher_setor(area, setor),
            ao_mudar_fiscalizacao=lambda setor, exigidos: self.mudar_fiscalizacao(area, setor, exigidos),
            ao_alternar_camera=lambda: self.cameras.alternar(area),
            ao_capturar_foto=lambda: self.cameras.capturar_foto(area),
            ao_trocar_camera=lambda: self.cameras.trocar_da_area(area),
        )

        # Entra antes da página "+ Nova área", que fica sempre por último
        self.caderno.insert(self.aba_nova, area.painel, text=self.texto_da_aba(dados))

        self.lista.append(area)

        self.atualizar_barra()
        self.atualizar_botao_visao_geral()

        if self._ia.pronta:

            area.iniciar_analise(detector.criar_detectores(), self._ia.classificador, self._janela.auditoria)

        elif self._ia.erro:

            self.mostrar_erro_de_carga(area)

        else:

            area.painel.definir_status(
                "CARREGANDO",
                "Preparando o modelo de IA. Isso leva alguns segundos...",
                CORES["neutro"],
            )
            area.painel.mostrar_mensagem("Carregando o modelo de IA...")

        return area

    # ============================================================
    # IA PRONTA (ou com erro)
    # ============================================================

    def iniciar_analises(self):
        """A IA terminou de carregar: liga a análise de cada área."""

        for indice, area in enumerate(self.lista):

            # Os detectores não podem ser divididos entre threads: a
            # primeira área usa os já carregados; as outras, novos
            detectores = self._ia.detectores_iniciais if indice == 0 else detector.criar_detectores()

            area.iniciar_analise(detectores, self._ia.classificador, self._janela.auditoria)

    def mostrar_erro_de_carga(self, area=None):
        """Mostra o erro da IA na área (ou em todas, sem área)."""

        for alvo in [area] if area else self.lista:

            alvo.painel.definir_status("ERRO AO CARREGAR", self._ia.erro, CORES["perigo"])
            alvo.painel.mostrar_mensagem("Não foi possível carregar o modelo de IA.")
            alvo.painel.definir_botao_camera("Indisponível", "Primario.TButton", False)

    # ============================================================
    # BARRA DE ÁREAS
    # ============================================================

    @staticmethod
    def texto_da_aba(dados):
        """Nome da área, com a marca de quem comanda a catraca."""

        return dados.nome + (MARCA_CATRACA_NA_ABA if dados.controla_catraca else "")

    def atualizar_textos(self):
        """O nome ou a marca da catraca mudou: refaz os textos das páginas e da barra."""

        for area in self.lista:
            self.caderno.tab(area.painel, text=self.texto_da_aba(area.dados))

        self.atualizar_barra()

    def atualizar_barra(self):
        """Refaz as pílulas da barra de áreas e o cabeçalho de câmera de cada área."""

        configuracoes = self._janela.configuracoes

        # Espaço antes do nome: o ponto de situação não encosta no texto
        self.barra.definir_areas(
            [(str(area.painel), "  " + self.texto_da_aba(area.dados).strip()) for area in self.lista]
        )

        for area in self.lista:
            area.painel.definir_camera(configuracoes.nome_camera(area.dados.fonte), area.dados.controla_catraca)

        if self.atual is not None and not self.visao_geral_na_tela():
            self.barra.selecionar(str(self.atual.painel))

        self._proxima_conferencia_pontos = 0.0

    def ao_escolher_na_barra(self, chave):
        """Clique na pílula de uma área: abre a página dela."""

        for area in self.lista:

            if str(area.painel) == chave:
                self.selecionar(area)
                return

    def atualizar_pontos_da_barra(self):
        """Pinta o ponto de cada área com a cor da situação dela agora (duas vezes por segundo)."""

        agora = time.perf_counter()

        if agora < self._proxima_conferencia_pontos:
            return

        self._proxima_conferencia_pontos = agora + INTERVALO_PONTOS_DA_BARRA_SEG

        for area in self.lista:
            self.barra.definir_cor(str(area.painel), area.resumo_status()[2])

    # ============================================================
    # MOSTRAR UMA ÁREA
    # ============================================================

    def selecionar(self, area):
        """Mostra a página da área e faz as Configurações e a auditoria valerem para ela."""

        self.atual = area

        # Escolher uma área é sair da visão geral para a página dela
        self.esconder_visao_geral()

        self.caderno.select(area.painel)

        self.barra.selecionar(str(area.painel))

        # A auditoria mostra só os eventos da área aberta
        self._janela.painel_auditoria.definir_area(area.nome)

        area.esquecer_desenho()

        self.atualizar_configuracoes_da_area()

    def atualizar_configuracoes_da_area(self):

        area = self.atual

        self._janela.configuracoes.definir_area_atual(
            area.nome,
            area.dados.fonte,
            area.dados.controla_catraca,
            pode_remover=len(self.lista) > 1,
        )

    def _ao_trocar_aba(self, _evento=None):

        if not self.lista:
            return

        escolhida = self.caderno.select()

        # Escolheu "+ Nova área": volta para a área de antes e abre o
        # pedido de nome (depois que o clique terminar de ser tratado)
        if escolhida == str(self.aba_nova):

            self.caderno.select(self.atual.painel)
            self._janela.raiz.after_idle(self.nova)
            return

        for area in self.lista:

            if str(area.painel) == escolhida and area is not self.atual:
                self.selecionar(area)
                break

    # ============================================================
    # NOVA, RENOMEAR, REMOVER
    # ============================================================

    def nova(self):
        """"+ Nova área" (barra ou Configurações): cria outra área com outra câmera."""

        configuracoes = self._janela.configuracoes

        if len(self.lista) >= config.MAXIMO_AREAS:
            self._janela.avisar(f"Limite de {config.MAXIMO_AREAS} áreas abertas ao mesmo tempo (MAXIMO_AREAS).", segundos=7)
            return

        opcoes = configuracoes.opcoes_de_camera()

        # Sugere uma câmera que nenhuma área está usando
        em_uso = {area.dados.fonte for area in self.lista}
        livre = next((fonte for _, fonte in opcoes if fonte not in em_uso), opcoes[0][1] if opcoes else 0)

        resposta = pedir_area(
            configuracoes.pai_para_dialogos(self._janela.raiz),
            "Nova área",
            f"Área {len(self.lista) + 1}",
            [area.nome for area in self.lista],
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

        area = self.criar(dados)

        self.selecionar(area)
        self.salvar()

        log.info("Área criada: %s", nome)

        # Uma webcam não abre em duas áreas ao mesmo tempo
        outra = next((a for a in self.lista if a is not area and a.dados.fonte == fonte), None)

        if outra is not None and not eh_endereco_ip(fonte):
            self._janela.avisar(
                f"Área \"{nome}\" criada. Atenção: a área \"{outra.nome}\" usa a mesma webcam; "
                "só uma delas consegue ligá-la de cada vez.",
                segundos=10,
            )
        else:
            self._janela.avisar(f"Área \"{nome}\" criada. Escolha o setor, o modo e ligue a câmera.", segundos=7)

    def renomear(self):

        area = self.atual

        resposta = pedir_area(
            self._janela.configuracoes.pai_para_dialogos(self._janela.raiz),
            "Renomear área",
            area.nome,
            [outra.nome for outra in self.lista if outra is not area],
        )

        if resposta is None:
            return

        nome, _ = resposta

        log.info("Área renomeada: %s -> %s", area.nome, nome)

        # Os próximos eventos da auditoria já saem com o nome novo
        area.dados.nome = nome
        area.parametros.area = nome

        # Os eventos de antes continuam com o nome antigo (o log não é
        # reescrito); a auditoria passa a mostrar os do nome novo
        if not self.visao_geral_na_tela():
            self._janela.painel_auditoria.definir_area(nome)

        self.atualizar_textos()
        self.atualizar_configuracoes_da_area()
        self.salvar()

    def remover(self):
        """Tira a área aberta (a câmera dela é desligada). A auditoria não muda."""

        if len(self.lista) <= 1:
            return

        area = self.atual

        confirmou = messagebox.askyesno(
            "Remover área",
            f"Remover a área \"{area.nome}\"?\n\n"
            "A câmera dela é desligada. Os eventos que ela já registrou "
            "continuam na auditoria.",
            default="no",
            parent=self._janela.configuracoes.pai_para_dialogos(self._janela.raiz),
        )

        if not confirmou:
            return

        area.parar()

        self.lista.remove(area)

        self.caderno.forget(area.painel)
        area.painel.destroy()

        self.atualizar_barra()
        self.atualizar_botao_visao_geral()

        self.selecionar(self.lista[0])
        self.salvar()

        log.info("Área removida: %s", area.nome)

        if area.dados.controla_catraca:
            self._janela.avisar(f"Área \"{area.nome}\" removida. Nenhuma área comanda a catraca agora.", segundos=7)
        else:
            self._janela.avisar(f"Área \"{area.nome}\" removida.")

    # ============================================================
    # CATRACA FÍSICA: QUAL ÁREA COMANDA
    # ============================================================

    def mudar_controle_catraca(self, marcado):
        """
        "Esta área comanda a catraca física": só uma área pode. Marcar
        na área aberta desmarca todas as outras.
        """

        for area in self.lista:
            area.dados.controla_catraca = marcado and area is self.atual

        self.atualizar_textos()
        self.salvar()

        if marcado:
            log.info("A catraca passou a obedecer à área %s", self.atual.nome)
            self._janela.avisar(f"A catraca agora obedece à área \"{self.atual.nome}\".")
        else:
            self._janela.avisar("Nenhuma área comanda a catraca: ela fica desligada.")

    def da_catraca(self):
        """A área que comanda a catraca física, ou None."""

        return next((area for area in self.lista if area.dados.controla_catraca), None)

    # ============================================================
    # VISÃO GERAL (todas as áreas lado a lado)
    # ============================================================

    def ao_alternar_visao_geral(self):
        """Botão "Visão geral": mostra ou esconde todas as áreas lado a lado."""

        if self.visao_geral_ativa.get() and len(self.lista) >= 2:

            self.visao_geral.definir_areas(self.lista)

            self.caderno.grid_remove()
            self.visao_geral.grid(row=self._linha_paginas, column=0, sticky="nsew")

            # Nenhuma área marcada na barra: a visão geral está na tela
            self.barra.selecionar("")

            # Na visão geral, a auditoria mostra os eventos de todas as áreas
            self._janela.painel_auditoria.definir_area(None)

        else:
            self.esconder_visao_geral()

            if self.atual is not None:
                self.barra.selecionar(str(self.atual.painel))
                self._janela.painel_auditoria.definir_area(self.atual.nome)

    def esconder_visao_geral(self):

        self.visao_geral_ativa.set(False)

        self.visao_geral.grid_remove()
        self.caderno.grid()

    def visao_geral_na_tela(self) -> bool:

        return self.visao_geral_ativa.get()

    def abrir_da_visao_geral(self, area):
        """Clique num quadro da visão geral: abre a página daquela área."""

        if area in self.lista:
            self.selecionar(area)

    def atualizar_botao_visao_geral(self):
        """A visão geral só existe com duas áreas ou mais; acompanha quem entra e sai."""

        if len(self.lista) >= 2:
            self.botao_visao_geral.state(["!disabled"])
        else:
            self.botao_visao_geral.state(["disabled"])
            self.esconder_visao_geral()

        if self.visao_geral_na_tela():
            self.visao_geral.definir_areas(self.lista)

    # ============================================================
    # FISCALIZAÇÃO: SETOR, EPIs E MODO DE UMA ÁREA
    # ============================================================

    def escolher_setor(self, area, setor):
        """
        Setor escolhido na lista de uma área: marca de uma vez os EPIs
        que ele exige. Só entram os EPIs que o modelo sabe reconhecer.
        """

        exigidos = tuple(chave for chave in config.SETORES.get(setor, []) if chave in self._epis_do_modelo)

        self.mudar_fiscalizacao(area, setor, exigidos)

    def mudar_fiscalizacao(self, area, setor, exigidos):
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

        self.salvar()

        # O texto da faixa de status depende do setor
        area.esquecer_desenho()

    def mudar_modo(self, area, modo):
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

        self.salvar()

        if modo == config.MODO_VIGILANCIA:
            self._janela.avisar(
                f"\"{area.nome}\" em modo vigilância: verifica se todos na área estão com os EPIs "
                "e registra. A catraca não obedece a ela.",
                segundos=7,
            )
        else:
            self._janela.avisar(
                f"\"{area.nome}\" em modo catraca: libera ou nega o acesso, uma pessoa por vez.",
                segundos=7,
            )

    # ============================================================
    # CONFIANÇA MÍNIMA E INTERVALO (todas as áreas)
    # ============================================================

    def mudar_parametros(self, limiar_confianca, intervalo_classificacao):
        """
        Configurações > Análise: confiança mínima e intervalo, para TODAS as áreas.

        As análises usam o valor novo já no próximo ciclo. A gravação em
        preferencias.json espera o controle parar de mexer por
        ESPERA_SALVAR_AJUSTES_MS: arrastar o controle não regrava o
        arquivo dezenas de vezes.
        """

        self.limiar = limiar_confianca
        self.intervalo = intervalo_classificacao

        for area in self.lista:
            area.parametros.limiar_confianca = limiar_confianca
            area.parametros.intervalo_classificacao = intervalo_classificacao

        raiz = self._janela.raiz

        if self._gravacao_de_ajustes is not None:
            raiz.after_cancel(self._gravacao_de_ajustes)

        self._gravacao_de_ajustes = raiz.after(config.ESPERA_SALVAR_AJUSTES_MS, self._salvar_ajustes)

    def _salvar_ajustes(self):

        self._gravacao_de_ajustes = None

        preferencias.salvar_ajustes(self.limiar, self.intervalo)

    def gravar_ajustes_pendentes(self):
        """Ao fechar: um ajuste mexido há menos de ESPERA_SALVAR_AJUSTES_MS é gravado agora."""

        if self._gravacao_de_ajustes is not None:
            self._janela.raiz.after_cancel(self._gravacao_de_ajustes)
            self._salvar_ajustes()

    # ============================================================
    # DESENHO, TEMA E ENCERRAMENTO
    # ============================================================

    def desenhar(self):
        """
        Chamado a cada ciclo da janela: desenha só o que está à vista,
        a visão geral (todas, em ritmo menor) ou a página da área aberta.
        As outras áreas continuam analisando sem gastar tempo com desenho.
        """

        if self.visao_geral_na_tela():
            self.visao_geral.atualizar()
        else:
            self.atual.atualizar_tela()

    def esquecer_desenhos(self):
        """Depois de trocar o tema: tudo é redesenhado com as cores novas."""

        self.barra.esquecer_cores()
        self.visao_geral.esquecer_desenho()

        for area in self.lista:
            area.esquecer_desenho()

        self._proxima_conferencia_pontos = 0.0

    def salvar(self):

        preferencias.salvar_areas([area.dados for area in self.lista])

    def parar_todas(self):
        """Desliga as câmeras e as análises de todas as áreas (ao fechar)."""

        self.gravar_ajustes_pendentes()

        for area in self.lista:
            area.parar()
