"""
Painel de auditoria (lado direito da janela).

Mostra, na mesma tela do vídeo:

    - cartões com os totais do período (eventos, conformes, irregulares,
      taxa de conformidade). "Conforme" vale para os dois modos: na
      catraca é quem foi liberado; na vigilância, quem estava com todos
      os EPIs;
    - filtros (por resultado, por período e por texto);
    - a tabela de eventos, atualizada ao vivo, com ordenação por coluna;
    - "Exportar CSV": grava o que está filtrado numa planilha;
    - a foto de evidência do evento selecionado, com dois botões:
      "Salvar relatório" (relatório completo do momento, em
      auditoria/relatorios) e "Excluir" (tira o evento do log,
      movendo-o para auditoria/excluidos, sem apagar).

A auditoria acompanha o que está na tela da esquerda: com uma área
aberta, mostra só os eventos DELA (cartões, tabela e exportação); na
visão geral, os de todas. O título diz qual é ("Auditoria · Portaria").

Os registros ficam guardados em memória. Quando chega um evento novo
ele é apenas inserido no topo da tabela; o CSV não é relido.
"""

import os
import tkinter as tk
from datetime import date, timedelta
from tkinter import ttk

from PIL import Image, ImageTk

from safetech import config
from safetech.interface import dialogos
from safetech.interface.componentes import dica
from safetech.interface.tema import CORES, FONTES
from safetech.nucleo import horario, modos
from safetech.nucleo.epis import chave_do_epi, ler_confiancas
from safetech.nucleo.icones import desenhar_icone_epi


# Colunas da tabela: (campo do registro, título exibido, largura, alinhamento)
COLUNAS_TABELA = [
    ("timestamp", "Data e hora", 165, "w"),
    ("pessoa", "Pessoa", 60, "center"),
    ("setor", "Setor", 125, "w"),
    ("faltando", "Faltando", 160, "w"),
    ("area", "Área", 95, "w"),
    ("liberado", "Resultado", 100, "center"),
]

# Texto ao lado do título quando a auditoria mostra todas as áreas
TEXTO_TODAS_AS_AREAS = "Todas as áreas"

# Opção da lista de períodos que pede duas datas
PERIODO_PERSONALIZADO = "Escolher datas..."

# Textos mostrados no lugar da tabela quando ela está vazia
TEXTO_SEM_EVENTOS = "Nenhum evento registrado ainda.\nOs eventos aparecem aqui assim que alguém é analisado."
TEXTO_FILTRO_VAZIO = "Nenhum evento para os filtros escolhidos."
TEXTO_AREA_SEM_EVENTOS = "Nenhum evento registrado nesta área ainda."
TEXTO_SEM_SELECAO = "Selecione um evento para ver a foto. Duplo clique abre em tamanho real."

# Filtro por resultado: o valor é o da coluna "liberado" do CSV
# (SIM = conforme / liberado, NAO = irregular / negado)
FILTRO_TODOS = "todos"
FILTRO_LIBERADOS = "SIM"
FILTRO_NEGADOS = "NAO"

# Parte da largura do painel que a foto do evento selecionado pode ocupar
FRACAO_LARGURA_FOTO = 0.38

# Altura máxima da foto do evento selecionado (px a 100% de escala)
ALTURA_EVIDENCIA = 150

# Barras de confiança do evento selecionado: altura de cada linha e
# tamanho do ícone do EPI (px a 100% de escala)
ALTURA_LINHA_CONFIANCA = 24
TAMANHO_ICONE_CONFIANCA = 18


class PainelAuditoria(ttk.Frame):

    def __init__(
        self,
        pai,
        pasta_imagens,
        ao_zerar,
        ao_excluir,
        ao_salvar_relatorio,
        ao_exportar=None,
        ao_indicadores=None,
        colunas_visiveis=None,
        ao_mudar_colunas=None,
        escala=1.0,
    ):
        """
        ao_zerar            -> chamado pelo botão "Zerar" (sem argumentos).
        ao_excluir          -> chamado pelo botão "Excluir" com o
                               registro da linha selecionada.
        ao_salvar_relatorio -> chamado pelo botão "Salvar relatório" com
                               o registro da linha selecionada.
        ao_exportar         -> chamado pelo botão "Exportar CSV" com a
                               lista dos registros que passam nos filtros
                               (do mais antigo para o mais recente).

        Quem confirma com o usuário e mexe nos arquivos é a janela
        principal; o painel só diz qual linha foi escolhida.
        """

        super().__init__(pai, style="Painel.TFrame", padding=18)

        self._ao_zerar = ao_zerar
        self._ao_excluir = ao_excluir
        self._ao_salvar_relatorio = ao_salvar_relatorio
        self._ao_exportar = ao_exportar
        self._ao_indicadores = ao_indicadores
        self._ao_mudar_colunas = ao_mudar_colunas or (lambda _colunas: None)

        # Colunas que aparecem (as outras ficam escondidas, não somem dos dados)
        todas = [campo for campo, *_ in COLUNAS_TABELA]
        escolhidas = [campo for campo in (colunas_visiveis or todas) if campo in todas]

        self._mostrar_coluna = {campo: tk.BooleanVar(value=campo in (escolhidas or todas)) for campo in todas}

        # Quantas linhas a tabela mostra agora ("Mostrar mais" aumenta)
        self._limite_linhas = config.MAXIMO_LINHAS_TABELA

        # Período com datas escolhidas: (inicio, fim) "AAAA-MM-DD", ou None
        self._intervalo = None
        self._periodo_anterior = config.PERIODO_AUDITORIA_PADRAO
        self._pasta_imagens = pasta_imagens
        self._escala = escala
        self._altura_evidencia = int(ALTURA_EVIDENCIA * escala)

        # Todos os registros, do mais antigo para o mais recente
        self._registros = []

        # Liga cada linha da tabela ao registro correspondente
        self._registro_por_linha = {}

        # Ordenação escolhida pelo usuário: (campo, crescente) ou None
        self._ordenacao = None

        self._texto_filtro = tk.StringVar()
        self._filtro_resultado = tk.StringVar(value=FILTRO_TODOS)
        self._periodo = tk.StringVar(value=config.PERIODO_AUDITORIA_PADRAO)

        # Área cujos eventos aparecem (None = todas as áreas)
        self._area = None

        self._imagem_evidencia = None

        # Evento mostrado nas barras de confiança e os ícones já desenhados
        self._registro_nas_barras = None
        self._icones = {}

        self.columnconfigure(0, weight=1)
        self.rowconfigure(4, weight=1)

        self._montar_cabecalho()
        self._montar_indicadores()
        self._montar_filtros()
        self._montar_tabela()
        self._montar_evidencia()

    # ============================================================
    # MONTAGEM
    # ============================================================

    def _montar_cabecalho(self):

        cabecalho = ttk.Frame(self, style="Painel.TFrame")
        cabecalho.grid(row=0, column=0, sticky="ew", pady=(0, 12))

        ttk.Label(
            cabecalho, text="Auditoria", style="Titulo.Painel.TLabel"
        ).pack(side="left")

        # De qual área são os eventos mostrados ("· Portaria" ou "· Todas as áreas")
        self._rotulo_area = ttk.Label(cabecalho, text="", style="Suave.Painel.TLabel", font=FONTES["texto_negrito"])
        self._rotulo_area.pack(side="left", padx=(8, 0), pady=(3, 0))
        self._atualizar_rotulo_area()

        # Ações sobre a auditoria INTEIRA. As que agem sobre UMA linha
        # (relatório e excluir) ficam no cartão do evento selecionado,
        # embaixo, junto da foto.
        #
        # "Mais ▾": abrir a pasta e zerar. Zerar é a ação mais drástica:
        # fica dentro do menu, longe de um clique sem querer. Quem confirma
        # com o usuário e arquiva os dados é a janela principal.
        self._menu_mais = tk.Menu(
            self,
            tearoff=False,
            bg=CORES["cartao"],
            fg=CORES["texto"],
            activebackground=CORES["destaque"],
            activeforeground="white",
        )
        self._menu_mais.add_command(label="Abrir a pasta da auditoria", command=self._abrir_pasta)
        self._menu_mais.add_separator()
        self._menu_mais.add_command(label="Zerar a auditoria...", command=self._ao_zerar, foreground=CORES["perigo_texto"])

        dica(
            ttk.Menubutton(cabecalho, text="Mais ▾", menu=self._menu_mais, style="TButton", takefocus=False),
            "Abrir a pasta da auditoria e zerar (nada é apagado: vai para auditoria/arquivados)",
        ).pack(side="right")

        # Planilha com o que está filtrado na tela (período, resultado, busca)
        self._botao_exportar = ttk.Button(
            cabecalho,
            text="Exportar",
            command=self._exportar_filtrados,
            takefocus=False,
        )
        self._botao_exportar.pack(side="right", padx=(0, 8))

        dica(self._botao_exportar, "Grava numa planilha (Excel) os eventos que estão filtrados na tela")

        # Gráficos e relatório em PDF (janela à parte)
        if self._ao_indicadores is not None:

            dica(
                ttk.Button(cabecalho, text="Indicadores", style="Secundario.TButton", command=self._ao_indicadores, takefocus=False),
                "Gráficos (EPI que mais falta, conformidade por área e por dia, horários críticos) e relatório em PDF",
            ).pack(side="right", padx=(0, 8))

    def _montar_indicadores(self):

        linha = ttk.Frame(self, style="Painel.TFrame")
        linha.grid(row=1, column=0, sticky="ew", pady=(0, 12))

        self._valor_total = self._criar_indicador(linha, 0, "Eventos", CORES["texto"])
        # Nomes que servem aos dois modos (catraca e vigilância)
        self._valor_liberados = self._criar_indicador(linha, 1, "Conformes", CORES["sucesso_texto"])
        self._valor_negados = self._criar_indicador(linha, 2, "Irregulares", CORES["perigo_texto"])
        self._valor_taxa = self._criar_indicador(linha, 3, "Conformidade", CORES["destaque"])

    def _criar_indicador(self, pai, coluna, titulo, cor_valor):
        """Cria um cartão de indicador (com um filete colorido no topo); devolve o rótulo do valor."""

        pai.columnconfigure(coluna, weight=1, uniform="indicadores")

        cartao = ttk.Frame(pai, style="Cartao.TFrame")
        cartao.grid(row=0, column=coluna, sticky="ew", padx=(0 if coluna == 0 else 8, 0))

        # Filete na cor do indicador: identifica o cartão de relance
        tk.Frame(cartao, bg=cor_valor, height=3).pack(fill="x")

        miolo = ttk.Frame(cartao, style="Cartao.TFrame", padding=(14, 8, 14, 10))
        miolo.pack(fill="x")

        ttk.Label(miolo, text=titulo, style="Suave.Cartao.TLabel").pack(anchor="w")

        valor = ttk.Label(miolo, text="0", style="Valor.Cartao.TLabel", foreground=cor_valor)
        valor.pack(anchor="w")

        return valor

    def _montar_filtros(self):

        linha = ttk.Frame(self, style="Painel.TFrame")
        linha.grid(row=2, column=0, sticky="ew", pady=(0, 10))

        # Botões que funcionam como abas: só um fica selecionado
        for texto, valor in (
            ("Todos", FILTRO_TODOS),
            ("Conformes", FILTRO_LIBERADOS),
            ("Irregulares", FILTRO_NEGADOS),
        ):

            ttk.Radiobutton(
                linha,
                text=texto,
                value=valor,
                variable=self._filtro_resultado,
                style="Filtro.Toolbutton",
                command=self._redesenhar_tabela,
                takefocus=False,
            ).pack(side="left", padx=(0, 4))

        # Período: os cartões, a tabela e a exportação o seguem
        caixa_periodo = ttk.Combobox(
            linha,
            textvariable=self._periodo,
            values=[*config.PERIODOS_AUDITORIA, PERIODO_PERSONALIZADO],
            state="readonly",
            width=15,
            style="Pequena.TCombobox",
            takefocus=False,
        )
        caixa_periodo.pack(side="left", padx=(8, 0))
        caixa_periodo.bind("<<ComboboxSelected>>", lambda _evento: self._ao_mudar_periodo(caixa_periodo))

        # Escolher as colunas da tabela (um menu com uma caixa por coluna)
        self._botao_colunas = ttk.Button(linha, text="Colunas", command=self._abrir_menu_colunas, takefocus=False)
        self._botao_colunas.pack(side="left", padx=(8, 0))

        dica(self._botao_colunas, "Escolhe quais colunas aparecem na tabela (fica salvo)")

        # Busca numa linha própria, embaixo: cabe inteira mesmo com o painel estreito
        linha_busca = ttk.Frame(self, style="Painel.TFrame")
        linha_busca.grid(row=3, column=0, sticky="ew", pady=(0, 10))

        ttk.Label(linha_busca, text="Buscar", style="Suave.Painel.TLabel").pack(side="left", padx=(0, 8))

        self._campo_filtro = ttk.Entry(linha_busca, textvariable=self._texto_filtro)
        self._campo_filtro.pack(side="left", fill="x", expand=True)

        # Refaz a tabela a cada tecla digitada na busca
        self._texto_filtro.trace_add("write", lambda *_: self._redesenhar_tabela())

    def _montar_tabela(self):

        moldura = ttk.Frame(self, style="Cartao.TFrame")
        moldura.grid(row=4, column=0, sticky="nsew")

        moldura.columnconfigure(0, weight=1)
        moldura.rowconfigure(0, weight=1)

        self._tabela = ttk.Treeview(
            moldura,
            columns=[campo for campo, *_ in COLUNAS_TABELA],
            show="headings",
            selectmode="browse",
        )

        for campo, titulo, largura, alinhamento in COLUNAS_TABELA:

            self._tabela.heading(
                campo,
                text=titulo,
                command=lambda c=campo: self._ordenar_por(c),
            )

            # Larguras em pixels acompanham a escala do monitor
            self._tabela.column(
                campo,
                width=int(largura * self._escala),
                minwidth=int(60 * self._escala),
                anchor=alinhamento,
            )

        self.aplicar_cores()

        # Mensagem no meio da tabela quando ela está vazia
        self._rotulo_tabela_vazia = tk.Label(
            moldura,
            text=TEXTO_SEM_EVENTOS,
            bg=CORES["cartao"],
            fg=CORES["texto_suave"],
            font=FONTES["texto"],
            justify="center",
        )

        barra = ttk.Scrollbar(moldura, orient="vertical", command=self._tabela.yview)
        self._tabela.configure(yscrollcommand=barra.set)

        self._tabela.grid(row=0, column=0, sticky="nsew")
        barra.grid(row=0, column=1, sticky="ns")

        # Embaixo da tabela: "Mostrando 500 de 1.234" e o botão para ver mais
        self._linha_mais = ttk.Frame(moldura, style="Cartao.TFrame", padding=(10, 6))

        self._rotulo_quantas = ttk.Label(self._linha_mais, text="", style="Suave.Cartao.TLabel")
        self._rotulo_quantas.pack(side="left")

        ttk.Button(
            self._linha_mais,
            text=f"Mostrar mais {config.MAXIMO_LINHAS_TABELA}",
            style="Secundario.TButton",
            command=self.mostrar_mais,
            takefocus=False,
        ).pack(side="right")

        self._aplicar_colunas()

        self._tabela.bind("<<TreeviewSelect>>", self._ao_selecionar)
        self._tabela.bind("<Double-1>", self._ao_duplo_clique)

        # Tecla Delete com a tabela em foco: o mesmo que o botão Excluir
        self._tabela.bind("<Delete>", lambda _evento: self._excluir_selecionado())

    def _montar_evidencia(self):

        cartao = ttk.Frame(self, style="Cartao.TFrame", padding=12)
        cartao.grid(row=5, column=0, sticky="ew", pady=(12, 0))

        cabeca = ttk.Frame(cartao, style="Cartao.TFrame")
        cabeca.pack(fill="x")

        ttk.Label(
            cabeca,
            text="Evento selecionado",
            style="Cartao.TLabel",
            font=FONTES["texto_negrito"],
        ).pack(side="left")

        # Os dois botões agem sobre a linha escolhida na tabela: começam
        # desativados e são ativados quando o usuário escolhe uma linha.
        #
        # Excluir tira o evento do log (a janela principal confirma e o
        # guarda em auditoria/excluidos; nada é apagado).
        self._botao_excluir = ttk.Button(
            cabeca,
            text="Excluir",
            style="Suave.Perigo.TButton",
            command=self._excluir_selecionado,
            takefocus=False,
            state="disabled",
        )
        self._botao_excluir.pack(side="right")

        dica(self._botao_excluir, "Tira este evento do log (ele é guardado em auditoria/excluidos). Tecla Delete")

        # Relatório completo do momento (dados do evento, confiança de
        # cada EPI e a foto), aberto no navegador
        self._botao_relatorio = ttk.Button(
            cabeca,
            text="Salvar relatório",
            style="Secundario.TButton",
            command=self._salvar_relatorio_selecionado,
            takefocus=False,
            state="disabled",
        )
        self._botao_relatorio.pack(side="right", padx=(0, 8))

        dica(self._botao_relatorio, "Relatório completo deste momento (dados, confiança de cada EPI e a foto), aberto no navegador")

        # Embaixo do título: a foto à esquerda e os detalhes à direita (lado
        # a lado, para o cartão não roubar a altura da tabela)
        corpo = ttk.Frame(cartao, style="Cartao.TFrame")
        corpo.pack(fill="x", pady=(8, 0))

        corpo.columnconfigure(0, weight=2, uniform="evento")
        corpo.columnconfigure(1, weight=3, uniform="evento")

        self._rotulo_evidencia = tk.Label(
            corpo,
            bg=CORES["cartao"],
            fg=CORES["texto_suave"],
            font=FONTES["pequena"],
            height=1,
        )
        self._rotulo_evidencia.grid(row=0, column=0, sticky="nw")

        lado = ttk.Frame(corpo, style="Cartao.TFrame")
        lado.grid(row=0, column=1, sticky="nsew", padx=(12, 0))

        # Detalhes do evento selecionado: tipo, área, modo e setor
        self._rotulo_detalhes = ttk.Label(
            lado,
            text="",
            style="Suave.Cartao.TLabel",
            justify="left",
        )
        self._rotulo_detalhes.pack(anchor="w")

        # O texto quebra na largura do lado direito (e não empurra o painel)
        lado.bind("<Configure>", lambda evento: self._rotulo_detalhes.config(wraplength=max(120, evento.width - 4)))

        # Uma linha por EPI: ícone, nome, barra da confiança e o número.
        # Vermelho = faltou (exigido e abaixo do limiar); verde = exigido
        # e presente; cinza = o setor não exigia
        self._tela_confiancas = tk.Canvas(lado, bg=CORES["cartao"], highlightthickness=0, height=1)
        self._tela_confiancas.pack(fill="x", pady=(6, 0))

        self._tela_confiancas.bind("<Configure>", lambda _evento: self._desenhar_confiancas())

        self._mostrar_texto_evidencia(TEXTO_SEM_SELECAO)

    # ============================================================
    # DADOS
    # ============================================================

    def carregar(self, registros):
        """Substitui todo o histórico (usado ao abrir o programa)."""

        self._registros = list(registros)

        self._atualizar_indicadores()
        self._redesenhar_tabela()

    def adicionar(self, registro):
        """Acrescenta um evento novo, sem refazer a tabela inteira."""

        self._registros.append(registro)

        self._atualizar_indicadores()

        # Com ordenação personalizada a posição da linha nova depende
        # das outras, então é mais simples redesenhar.
        if self._ordenacao is not None:
            self._redesenhar_tabela()
            return

        if self._passa_no_filtro(registro):

            self._inserir_linha(registro, posicao=0)

            # Mantém o limite de linhas removendo a mais antiga
            linhas = self._tabela.get_children()

            if len(linhas) > self._limite_linhas:
                self._remover_linha(linhas[-1])

            # A linha nova empurrou as outras: refaz as listras
            self._reaplicar_listras()

    def remover(self, registro):
        """Tira um evento da tela (depois de excluído do log)."""

        # Os registros são comparados pelo conteúdo (dataclass): sai
        # só a primeira ocorrência, como no CSV.
        if registro in self._registros:
            self._registros.remove(registro)

        self._atualizar_indicadores()
        self._redesenhar_tabela()
        self._limpar_evidencia()

    def esvaziar(self):
        """Tira tudo da tela: tabela, indicadores e a foto de evidência."""

        self.carregar([])

        self._limpar_evidencia()

    def _limpar_evidencia(self):
        """Volta o cartão da foto ao texto inicial (nenhuma linha selecionada)."""

        self._rotulo_detalhes.config(text="")

        self._registro_nas_barras = None
        self._desenhar_confiancas()

        self._ativar_botoes_da_linha(False)

        self._mostrar_texto_evidencia(TEXTO_SEM_SELECAO)

    def aplicar_cores(self):
        """
        Cores das linhas conforme o resultado, e listras alternadas no
        fundo para o olho seguir a linha até o fim.

        Chamado ao montar e depois de trocar o tema: as cores das linhas
        ficam guardadas na tabela, não nos componentes.
        """

        self._tabela.tag_configure("liberado", foreground=CORES["sucesso_texto"])
        self._tabela.tag_configure("negado", foreground=CORES["perigo_texto"])
        self._tabela.tag_configure("par", background=CORES["linha_par"])
        self._tabela.tag_configure("impar", background=CORES["linha_impar"])

        # As barras do evento selecionado também têm cores do tema
        if hasattr(self, "_tela_confiancas"):
            self._icones = {}
            self._desenhar_confiancas()

    def definir_area(self, nome):
        """
        Mostra só os eventos da área 'nome' (None = de todas as áreas).

        Chamado pela janela principal quando o operador abre uma área ou
        a visão geral. Os cartões, a tabela e a exportação seguem junto.
        """

        if nome == self._area:
            return

        self._area = nome

        self._atualizar_rotulo_area()
        self._atualizar_indicadores()
        self._redesenhar_tabela()

        # A linha que estava selecionada pode não estar mais na tabela
        self._limpar_evidencia()

    @property
    def area(self):
        """Área mostrada (None = todas)."""

        return self._area

    def _atualizar_rotulo_area(self):

        self._rotulo_area.config(text="\u00b7  " + (self._area or TEXTO_TODAS_AS_AREAS))

    def _da_area(self, registro) -> bool:
        """O evento é da área mostrada? (sempre, quando são todas)"""

        return self._area is None or registro.area == self._area

    def limpar_filtro(self):

        self._texto_filtro.set("")

    def campo_de_busca_em_foco(self) -> bool:
        """True quando o usuário está digitando na busca (para não disparar atalhos)."""

        return self.focus_get() is self._campo_filtro

    # ============================================================
    # INDICADORES
    # ============================================================

    def _atualizar_indicadores(self):

        do_periodo = [
            registro for registro in self._registros if self._no_periodo(registro) and self._da_area(registro)
        ]

        total = len(do_periodo)
        liberados = sum(1 for registro in do_periodo if registro.liberado == "SIM")

        self._valor_total.config(text=str(total))
        self._valor_liberados.config(text=str(liberados))
        self._valor_negados.config(text=str(total - liberados))

        taxa = f"{liberados / total * 100:.0f}%" if total else "-"

        self._valor_taxa.config(text=taxa)

    # ============================================================
    # TABELA
    # ============================================================

    def _no_periodo(self, registro) -> bool:
        """O evento aconteceu dentro do período escolhido?"""

        # Datas escolhidas pelo usuário
        if self._intervalo is not None:

            inicio, fim = self._intervalo

            return inicio <= horario.data(registro.timestamp) <= fim

        dias = config.PERIODOS_AUDITORIA.get(self._periodo.get())

        if dias is None:
            return True

        # As datas do log são "AAAA-MM-DD HH:MM:SS": comparar o texto
        # da data já compara a ordem cronológica
        limite = (date.today() - timedelta(days=dias)).isoformat()

        return horario.data(registro.timestamp) >= limite

    def _ao_mudar_periodo(self, caixa):

        # Tira a seleção azul do texto, que o Tkinter deixa na caixa
        caixa.selection_clear()

        if self._periodo.get() == PERIODO_PERSONALIZADO:

            inicio, fim = self._intervalo or (None, None)

            escolhido = dialogos.pedir_intervalo(self.winfo_toplevel(), inicio, fim)

            if escolhido is None:

                # Cancelou: volta ao período de antes
                self._periodo.set(self._periodo_anterior)
                return

            self.definir_intervalo(*escolhido)
            return

        self._intervalo = None
        self._periodo_anterior = self._periodo.get()

        self._limite_linhas = config.MAXIMO_LINHAS_TABELA

        self._atualizar_indicadores()
        self._redesenhar_tabela()

    def definir_intervalo(self, inicio, fim):
        """Período com datas escolhidas (inclusive), "AAAA-MM-DD"."""

        self._intervalo = (inicio, fim)

        # A caixa mostra as datas escolhidas, ex.: "12/11 a 25/11/2026"
        texto = f"{inicio[8:10]}/{inicio[5:7]} a {fim[8:10]}/{fim[5:7]}/{fim[0:4]}"

        self._periodo.set(texto)
        self._periodo_anterior = texto

        self._limite_linhas = config.MAXIMO_LINHAS_TABELA

        self._atualizar_indicadores()
        self._redesenhar_tabela()

    # ------------------------------------------------------
    # COLUNAS E "MOSTRAR MAIS"
    # ------------------------------------------------------

    def _abrir_menu_colunas(self):

        menu = tk.Menu(
            self,
            tearoff=False,
            bg=CORES["cartao"],
            fg=CORES["texto"],
            activebackground=CORES["destaque"],
            activeforeground="white",
            selectcolor=CORES["texto"],
        )

        for campo, titulo, *_ in COLUNAS_TABELA:
            menu.add_checkbutton(label=titulo, variable=self._mostrar_coluna[campo], command=self._ao_mudar_coluna)

        botao = self._botao_colunas

        menu.tk_popup(botao.winfo_rootx(), botao.winfo_rooty() + botao.winfo_height())

    def _ao_mudar_coluna(self):

        # Pelo menos uma coluna fica sempre à vista
        if not any(variavel.get() for variavel in self._mostrar_coluna.values()):
            self._mostrar_coluna["timestamp"].set(True)

        self._aplicar_colunas()

        self._ao_mudar_colunas(self.colunas_visiveis())

    def colunas_visiveis(self):
        """Campos das colunas que aparecem, na ordem da tabela."""

        return [campo for campo, *_ in COLUNAS_TABELA if self._mostrar_coluna[campo].get()]

    def _aplicar_colunas(self):

        self._tabela.configure(displaycolumns=self.colunas_visiveis())

    def mostrar_mais(self):
        """Botão "Mostrar mais": a tabela passa a mostrar mais linhas."""

        self._limite_linhas += config.MAXIMO_LINHAS_TABELA

        self._redesenhar_tabela()

    def _passa_no_filtro(self, registro) -> bool:

        if not self._no_periodo(registro) or not self._da_area(registro):
            return False

        resultado = self._filtro_resultado.get()

        if resultado != FILTRO_TODOS and registro.liberado != resultado:
            return False

        busca = self._texto_filtro.get().strip().lower()

        if not busca:
            return True

        # Também busca pela data como aparece na tela (sem o "T" e o fuso)
        valores = [*registro.como_linha(), horario.para_exibir(registro.timestamp)]

        return any(busca in str(valor).lower() for valor in valores)

    def _redesenhar_tabela(self):

        self._tabela.delete(*self._tabela.get_children())
        self._registro_por_linha.clear()

        visiveis = [registro for registro in self._registros if self._passa_no_filtro(registro)]

        if self._ordenacao is None:

            # Padrão: mais recentes primeiro
            visiveis.reverse()

        else:

            campo, crescente = self._ordenacao

            visiveis.sort(key=lambda registro: self._chave_de_ordenacao(registro, campo), reverse=not crescente)

        for registro in visiveis[: self._limite_linhas]:
            self._inserir_linha(registro, posicao="end")

        self._reaplicar_listras()

        # Há mais eventos do que linhas na tela: mostra quantos e o botão
        if len(visiveis) > self._limite_linhas:

            self._rotulo_quantas.config(text=f"Mostrando {self._limite_linhas} de {len(visiveis)} eventos")
            self._linha_mais.grid(row=1, column=0, columnspan=2, sticky="ew")

        else:
            self._linha_mais.grid_remove()

    def registros_filtrados(self):
        """Todos os registros que passam nos filtros (sem o limite de linhas da tela), do mais antigo ao mais recente."""

        return [registro for registro in self._registros if self._passa_no_filtro(registro)]

    def _reaplicar_listras(self):
        """
        Pinta as linhas alternadas e mostra a mensagem de tabela vazia.

        As listras são refeitas a cada mudança porque uma linha nova no
        topo troca a posição (par/ímpar) de todas as outras.
        """

        linhas = self._tabela.get_children()

        for posicao, linha in enumerate(linhas):

            registro = self._registro_por_linha.get(linha)
            resultado = "liberado" if registro is not None and registro.liberado == "SIM" else "negado"

            self._tabela.item(linha, tags=(resultado, "par" if posicao % 2 == 0 else "impar"))

        if linhas:
            self._rotulo_tabela_vazia.place_forget()
        else:
            if not self._registros:
                texto = TEXTO_SEM_EVENTOS
            elif not any(self._da_area(registro) for registro in self._registros):
                texto = TEXTO_AREA_SEM_EVENTOS
            else:
                texto = TEXTO_FILTRO_VAZIO

            self._rotulo_tabela_vazia.config(text=texto)
            self._rotulo_tabela_vazia.place(relx=0.5, rely=0.4, anchor="center")

    def _inserir_linha(self, registro, posicao):

        liberado = registro.liberado == "SIM"

        valores = [
            # Fácil de ler; o fuso fica no relatório e na planilha
            horario.para_exibir(registro.timestamp),
            registro.pessoa,
            registro.setor,
            registro.faltando or "-",
            registro.area,
            # "Liberado"/"Negado" na catraca; "Conforme"/"Não conforme" na vigilância
            modos.resultado(registro.modo, liberado),
        ]

        linha = self._tabela.insert(
            "",
            posicao,
            values=valores,
            tags=("liberado" if liberado else "negado",),
        )

        self._registro_por_linha[linha] = registro

    def _remover_linha(self, linha):

        self._tabela.delete(linha)
        self._registro_por_linha.pop(linha, None)

    def _ordenar_por(self, campo):
        """Clique no título da coluna: ordena; clicar de novo inverte."""

        if self._ordenacao is not None and self._ordenacao[0] == campo:
            self._ordenacao = (campo, not self._ordenacao[1])
        else:
            self._ordenacao = (campo, True)

        self._redesenhar_tabela()

    @staticmethod
    def _chave_de_ordenacao(registro, campo):

        # A data pelo jeito de exibir: ordena junto eventos novos (com
        # fuso) e antigos (sem fuso)
        if campo == "timestamp":
            return horario.para_exibir(registro.timestamp)

        # Sem diferenciar maiúsculas de minúsculas
        return getattr(registro, campo).lower()

    # ============================================================
    # FOTO DE EVIDÊNCIA
    # ============================================================

    def _registro_selecionado(self):

        selecao = self._tabela.selection()

        if not selecao:
            return None

        return self._registro_por_linha.get(selecao[0])

    def _ao_selecionar(self, _evento=None):

        registro = self._registro_selecionado()

        if registro is None:
            self._ativar_botoes_da_linha(False)
            return

        self._ativar_botoes_da_linha(True)

        evento = "Primeira decisão" if registro.evento == "ENTRADA" else "Mudança de decisão"

        self._rotulo_detalhes.config(
            text=(
                f"{evento}  ·  {registro.area}  ·  {modos.nome_do_modo(registro.modo)}\n"
                f"Setor: {registro.setor or '-'}"
            )
        )

        self._registro_nas_barras = registro
        self._desenhar_confiancas()

        caminho = self._pasta_imagens / registro.imagem if registro.imagem else None

        if caminho is None or not caminho.exists():
            self._mostrar_texto_evidencia("Este evento não tem foto de evidência.")
            return

        try:

            # Reduz para caber no cartão, mantendo a proporção
            # No máximo 38% da largura do painel: a foto divide o cartão com
            # as barras. (Medir a própria foto faria ela crescer a cada clique.)
            largura_maxima = max(100, int(self.winfo_width() * FRACAO_LARGURA_FOTO))

            # O "with" fecha o arquivo assim que a miniatura fica
            # pronta. Sem isso o Windows manteria a foto "em uso" e o
            # botão Zerar não conseguiria movê-la para o arquivo.
            with Image.open(caminho) as imagem:

                imagem.thumbnail((largura_maxima, self._altura_evidencia))

                self._imagem_evidencia = ImageTk.PhotoImage(imagem)

        except OSError:
            self._mostrar_texto_evidencia("Não foi possível abrir a foto de evidência.")
            return

        self._rotulo_evidencia.config(image=self._imagem_evidencia, text="", height=self._altura_evidencia)

    def _icone(self, chave, cor):
        """Ícone do EPI na cor dada (guardado: o Tkinter apaga imagem sem referência)."""

        tamanho = int(TAMANHO_ICONE_CONFIANCA * self._escala)

        if (chave, cor) not in self._icones:
            self._icones[(chave, cor)] = ImageTk.PhotoImage(desenhar_icone_epi(chave, tamanho, cor))

        return self._icones[(chave, cor)]

    def _desenhar_confiancas(self):
        """Barras de confiança do evento selecionado (nada sem evento)."""

        tela = self._tela_confiancas
        tela.delete("all")

        registro = self._registro_nas_barras

        itens = ler_confiancas(registro.confiancas) if registro is not None else []

        altura_linha = int(ALTURA_LINHA_CONFIANCA * self._escala)

        tela.configure(height=max(1, altura_linha * len(itens)))

        if not itens:
            return

        exigidos = {nome.strip() for nome in registro.exigidos.split(",") if nome.strip()}
        faltando = {nome.strip() for nome in registro.faltando.split(",") if nome.strip()}

        largura = max(200, tela.winfo_width())

        inicio_nome = int(26 * self._escala)
        inicio_barra = int(100 * self._escala)
        fim_barra = largura - int(92 * self._escala)

        for posicao, (nome, confianca) in enumerate(itens):

            if nome in faltando:
                cor, legenda = CORES["perigo"], "faltou"
            elif nome in exigidos:
                cor, legenda = CORES["sucesso"], "ok"
            else:
                cor, legenda = CORES["texto_suave"], "não exigido"

            meio = posicao * altura_linha + altura_linha // 2

            chave = chave_do_epi(nome)

            if chave:
                tela.create_image(0, meio, image=self._icone(chave, cor), anchor="w")

            tela.create_text(inicio_nome, meio, text=nome, anchor="w", fill=CORES["texto"], font=FONTES["texto"])

            grossura = max(6, altura_linha // 3)

            tela.create_rectangle(inicio_barra, meio - grossura // 2, fim_barra, meio + grossura // 2, fill=CORES["borda"], outline="")

            ponta = inicio_barra + int((fim_barra - inicio_barra) * max(0.0, min(1.0, confianca)))

            tela.create_rectangle(inicio_barra, meio - grossura // 2, ponta, meio + grossura // 2, fill=cor, outline="")

            tela.create_text(
                fim_barra + 8, meio, text=f"{confianca * 100:.0f}%  {legenda}", anchor="w", fill=CORES["texto_suave"], font=FONTES["pequena"]
            )

    def _mostrar_texto_evidencia(self, texto):

        self._imagem_evidencia = None

        self._rotulo_evidencia.config(image="", text=texto, height=1)

    def _ao_duplo_clique(self, _evento=None):
        """Abre a foto de evidência no visualizador de imagens do sistema."""

        registro = self._registro_selecionado()

        if registro is None or not registro.imagem:
            return

        caminho = self._pasta_imagens / registro.imagem

        if caminho.exists():
            os.startfile(caminho)

    def _ativar_botoes_da_linha(self, ativo):
        """Os botões que agem sobre UMA linha só funcionam com uma linha selecionada."""

        estado = ["!disabled"] if ativo else ["disabled"]

        self._botao_excluir.state(estado)
        self._botao_relatorio.state(estado)

    def _salvar_relatorio_selecionado(self):
        """Botão "Salvar relatório": repassa à janela principal."""

        registro = self._registro_selecionado()

        if registro is not None:
            self._ao_salvar_relatorio(registro)

    def _exportar_filtrados(self):
        """Botão "Exportar CSV": repassa à janela principal o que está filtrado."""

        if self._ao_exportar is not None:
            self._ao_exportar(self.registros_filtrados())

    def _excluir_selecionado(self):
        """Botão "Excluir linha" (ou tecla Delete): repassa à janela principal."""

        registro = self._registro_selecionado()

        if registro is not None:
            self._ao_excluir(registro)

    def _abrir_pasta(self):
        """Abre a pasta de auditoria (CSV e fotos) no Explorador de Arquivos."""

        os.startfile(self._pasta_imagens.parent)
