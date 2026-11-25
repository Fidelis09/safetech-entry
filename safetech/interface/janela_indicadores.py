"""
Janela de Indicadores: o resumo da auditoria para o gerente.

    - período (Hoje, 7 dias, 30 dias, tudo) e área (todas ou uma);
    - quatro números: eventos, conformidade, EPI que mais falta e
      horário crítico;
    - quatro gráficos: EPIs que mais faltam, conformidade por área,
      irregulares por dia e irregulares por hora do dia;
    - "Salvar PDF": o mesmo conteúdo num relatório para imprimir.

Os gráficos são imagens desenhadas pelo servicos/graficos.py (os mesmos
do PDF), nas cores do tema da tela. São refeitos quando a janela muda de
tamanho, quando o período ou a área mudam, e a cada poucos segundos
enquanto a janela está aberta (eventos novos entram sozinhos).

Como os outros painéis, a janela só mostra: os registros vêm de
ler_registros() e salvar o PDF é com quem a abriu (ao_salvar_pdf).
"""

import tkinter as tk
from tkinter import ttk

from PIL import ImageTk

from safetech import config
from safetech.interface.tema import CORES, FONTES
from safetech.servicos import graficos, indicadores as modulo_indicadores


# Texto da opção "todas as áreas" na lista de áreas
TODAS_AS_AREAS = "Todas as áreas"

# Espera depois de a janela mudar de tamanho antes de redesenhar os
# gráficos (arrastar a borda não redesenha dezenas de vezes)
ESPERA_REDESENHO_MS = 150


class JanelaIndicadores(tk.Toplevel):

    def __init__(self, pai, ler_registros, nomes_das_areas, ao_salvar_pdf, escala=1.0):
        """
        ler_registros   -> função que devolve todos os registros da auditoria
        nomes_das_areas -> função que devolve os nomes das áreas abertas
        ao_salvar_pdf   -> chamado com (inicio, fim, area ou None)
        """

        super().__init__(pai)

        self.withdraw()

        self.title("Indicadores")
        self.configure(bg=CORES["painel"])

        self._ler_registros = ler_registros
        self._nomes_das_areas = nomes_das_areas
        self._ao_salvar_pdf = ao_salvar_pdf
        self._escala = escala

        # Tamanho ajustado à escala do monitor, sem passar do tamanho da tela
        largura, altura = config.TAMANHO_JANELA_INDICADORES

        largura = min(int(largura * escala), self.winfo_screenwidth() - 80)
        altura = min(int(altura * escala), self.winfo_screenheight() - 120)

        self.geometry(f"{largura}x{altura}")
        self.minsize(int(largura * 0.7), int(altura * 0.7))

        # Fechar só esconde: reabrir é instantâneo e lembra a escolha
        self.protocol("WM_DELETE_WINDOW", self.withdraw)
        self.bind("<Escape>", lambda _evento: self.withdraw())

        self._periodo = tk.StringVar(value="Últimos 30 dias")
        self._area = tk.StringVar(value=TODAS_AS_AREAS)

        # Imagens em exibição (sem a referência, o Tkinter as apaga)
        self._fotos = {}
        self._redesenho_agendado = None

        self._montar()

    # ============================================================
    # MONTAGEM
    # ============================================================

    def _montar(self):

        corpo = ttk.Frame(self, style="Painel.TFrame", padding=18)
        corpo.pack(fill="both", expand=True)

        corpo.columnconfigure(0, weight=1)
        corpo.rowconfigure(2, weight=1)

        # ---------------- título, filtros e PDF ----------------

        topo = ttk.Frame(corpo, style="Painel.TFrame")
        topo.grid(row=0, column=0, sticky="ew", pady=(0, 12))

        ttk.Label(topo, text="Indicadores", style="Titulo.Painel.TLabel").pack(side="left")

        ttk.Button(
            topo,
            text="Salvar PDF",
            style="Primario.TButton",
            command=self._salvar_pdf,
            takefocus=False,
        ).pack(side="right")

        self._caixa_area = ttk.Combobox(topo, textvariable=self._area, state="readonly", width=18, takefocus=False)
        self._caixa_area.pack(side="right", padx=(0, 10))
        self._caixa_area.bind("<<ComboboxSelected>>", lambda _evento: self._ao_mudar_filtro(self._caixa_area))

        caixa_periodo = ttk.Combobox(
            topo,
            textvariable=self._periodo,
            values=list(config.PERIODOS_AUDITORIA),
            state="readonly",
            width=16,
            takefocus=False,
        )
        caixa_periodo.pack(side="right", padx=(0, 8))
        caixa_periodo.bind("<<ComboboxSelected>>", lambda _evento: self._ao_mudar_filtro(caixa_periodo))

        # ---------------- os quatro números ----------------

        numeros = ttk.Frame(corpo, style="Painel.TFrame")
        numeros.grid(row=1, column=0, sticky="ew", pady=(0, 12))

        self._numeros = {}

        for coluna, (chave, titulo, cor) in enumerate(
            (
                ("eventos", "Eventos", CORES["texto"]),
                ("taxa", "Conformidade", CORES["destaque"]),
                ("epi", "EPI que mais falta", CORES["perigo_texto"]),
                ("hora", "Horário crítico", CORES["alerta_texto"]),
            )
        ):

            numeros.columnconfigure(coluna, weight=1, uniform="numeros")

            cartao = ttk.Frame(numeros, style="Cartao.TFrame", padding=(14, 10))
            cartao.grid(row=0, column=coluna, sticky="ew", padx=(0 if coluna == 0 else 8, 0))

            ttk.Label(cartao, text=titulo, style="Suave.Cartao.TLabel").pack(anchor="w")

            valor = ttk.Label(cartao, text="-", style="Valor.Cartao.TLabel", foreground=cor)
            valor.pack(anchor="w")

            apoio = ttk.Label(cartao, text="", style="Suave.Cartao.TLabel")
            apoio.pack(anchor="w")

            self._numeros[chave] = (valor, apoio)

        # ---------------- os quatro gráficos (2 x 2) ----------------

        self._grade = ttk.Frame(corpo, style="Painel.TFrame")
        self._grade.grid(row=2, column=0, sticky="nsew")

        self._quadros = {}

        for posicao, (chave, titulo) in enumerate(graficos.TITULOS_DOS_GRAFICOS.items()):

            linha, coluna = divmod(posicao, 2)

            self._grade.columnconfigure(coluna, weight=1, uniform="graficos")
            self._grade.rowconfigure(linha, weight=1, uniform="graficos")

            cartao = ttk.Frame(self._grade, style="Cartao.TFrame", padding=12)
            cartao.grid(row=linha, column=coluna, sticky="nsew", padx=(0 if coluna == 0 else 10, 0), pady=(0 if linha == 0 else 10, 0))

            cartao.columnconfigure(0, weight=1)
            cartao.rowconfigure(1, weight=1)

            ttk.Label(cartao, text=titulo, style="Cartao.TLabel", font=FONTES["texto_negrito"]).grid(row=0, column=0, sticky="w")

            # Canvas, e não Label: o Label cresceria junto com a imagem a cada
            # redesenho; o Canvas fica do tamanho que a grade der a ele
            tela = tk.Canvas(cartao, bg=CORES["cartao"], highlightthickness=0, width=10, height=10)
            tela.grid(row=1, column=0, sticky="nsew", pady=(8, 0))

            tela.create_image(0, 0, anchor="nw", tags="grafico")

            self._quadros[chave] = tela

        self._grade.bind("<Configure>", lambda _evento: self._agendar_redesenho())

    # ============================================================
    # MOSTRAR E ATUALIZAR
    # ============================================================

    def mostrar(self):

        self._caixa_area.config(values=[TODAS_AS_AREAS, *self._nomes_das_areas()])

        if self._area.get() not in self._caixa_area.cget("values"):
            self._area.set(TODAS_AS_AREAS)

        self.deiconify()
        self.lift()
        self.focus_set()

        self.redesenhar()

    def _ao_mudar_filtro(self, caixa):

        caixa.selection_clear()

        self.redesenhar()

    def _agendar_redesenho(self):

        if self._redesenho_agendado is not None:
            self.after_cancel(self._redesenho_agendado)

        self._redesenho_agendado = self.after(ESPERA_REDESENHO_MS, self.redesenhar)

    def filtro(self):
        """(inicio, fim, area ou None) escolhidos na janela."""

        inicio, fim = modulo_indicadores.periodo(self._periodo.get())

        area = self._area.get()

        return inicio, fim, None if area == TODAS_AS_AREAS else area

    def calcular(self):
        """Indicadores do período e da área escolhidos."""

        inicio, fim, area = self.filtro()

        registros = self._ler_registros()

        if area:
            registros = [registro for registro in registros if registro.area == area]

        return modulo_indicadores.calcular(registros, inicio, fim)

    def redesenhar(self):
        """Refaz os números e os gráficos (também depois de trocar o tema)."""

        self._redesenho_agendado = None

        if not self.winfo_viewable():
            return

        dados = self.calcular()

        # ---------------- números ----------------

        taxa = f"{dados.taxa * 100:.0f}%" if dados.taxa is not None else "-"
        mais_falta = dados.epi_que_mais_falta
        hora = dados.hora_critica

        textos = {
            "eventos": (str(dados.total), f"{dados.irregulares} irregular(es)"),
            "taxa": (taxa, f"meta: {config.META_CONFORMIDADE * 100:.0f}%"),
            "epi": (mais_falta[0] if mais_falta else "-", f"faltou {mais_falta[1]} vez(es)" if mais_falta else "nenhuma falta"),
            "hora": (f"{hora}h às {hora + 1}h" if hora is not None else "-", "mais irregulares" if hora is not None else "sem irregulares"),
        }

        for chave, (valor, apoio) in textos.items():
            self._numeros[chave][0].config(text=valor)
            self._numeros[chave][1].config(text=apoio)

        # ---------------- gráficos ----------------

        cores = {
            "fundo": CORES["cartao"],
            "texto": CORES["texto"],
            "texto_suave": CORES["texto_suave"],
            "grade": CORES["borda"],
            "barra": CORES["destaque"],
            "sucesso": CORES["sucesso"],
            "perigo": CORES["perigo"],
        }

        # Cada gráfico no tamanho do SEU quadro (os de baixo podem ser um
        # pouco mais baixos que os de cima, por causa do espaço entre eles)
        for chave, quadro in self._quadros.items():

            largura = max(120, quadro.winfo_width())
            altura = max(80, quadro.winfo_height())

            imagem = graficos.graficos_dos_indicadores(dados, largura, altura, cores, tamanho_letra=int(12 * self._escala))[chave]

            self._fotos[chave] = ImageTk.PhotoImage(imagem)

            quadro.itemconfigure("grafico", image=self._fotos[chave])

    def _salvar_pdf(self):

        self._ao_salvar_pdf(*self.filtro())
