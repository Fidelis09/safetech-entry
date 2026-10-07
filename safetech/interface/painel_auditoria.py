"""
Painel de auditoria (lado direito da janela).

Mostra, na mesma tela do vídeo:

    - cartões com os totais (eventos, liberados, negados, taxa de liberação);
    - filtros (por texto e por resultado);
    - a tabela de eventos, atualizada ao vivo, com ordenação por coluna;
    - a foto de evidência do evento selecionado.

Os registros ficam guardados em memória. Quando chega um evento novo
ele é apenas inserido no topo da tabela; o CSV não é relido.
"""

import os
import tkinter as tk
from tkinter import ttk

from PIL import Image, ImageTk

from safetech import config
from safetech.interface.tema import CORES, FONTES


# Colunas da tabela: (campo do registro, título exibido, largura, alinhamento)
COLUNAS_TABELA = [
    ("timestamp", "Data e hora", 145, "w"),
    ("pessoa", "Pessoa", 60, "center"),
    ("setor", "Setor", 130, "w"),
    ("faltando", "Faltando", 140, "w"),
    ("liberado", "Acesso", 80, "center"),
]

FILTRO_TODOS = "todos"
FILTRO_LIBERADOS = "SIM"
FILTRO_NEGADOS = "NAO"

ALTURA_EVIDENCIA = 190


class PainelAuditoria(ttk.Frame):

    def __init__(self, pai, pasta_imagens, escala=1.0):

        super().__init__(pai, style="Painel.TFrame", padding=18)

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

        self._imagem_evidencia = None

        self.columnconfigure(0, weight=1)
        self.rowconfigure(3, weight=1)

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

        ttk.Button(
            cabecalho,
            text="Abrir pasta",
            command=self._abrir_pasta,
            takefocus=False,
        ).pack(side="right")

    def _montar_indicadores(self):

        linha = ttk.Frame(self, style="Painel.TFrame")
        linha.grid(row=1, column=0, sticky="ew", pady=(0, 12))

        self._valor_total = self._criar_indicador(linha, 0, "Eventos", CORES["texto"])
        self._valor_liberados = self._criar_indicador(linha, 1, "Liberados", CORES["sucesso_texto"])
        self._valor_negados = self._criar_indicador(linha, 2, "Negados", CORES["perigo_texto"])
        self._valor_taxa = self._criar_indicador(linha, 3, "Liberação", CORES["texto"])

    def _criar_indicador(self, pai, coluna, titulo, cor_valor):
        """Cria um cartão de indicador; devolve o rótulo do valor."""

        pai.columnconfigure(coluna, weight=1, uniform="indicadores")

        cartao = ttk.Frame(pai, style="Cartao.TFrame", padding=(14, 10))
        cartao.grid(row=0, column=coluna, sticky="ew", padx=(0 if coluna == 0 else 8, 0))

        ttk.Label(cartao, text=titulo, style="Suave.Cartao.TLabel").pack(anchor="w")

        valor = ttk.Label(cartao, text="0", style="Valor.Cartao.TLabel", foreground=cor_valor)
        valor.pack(anchor="w")

        return valor

    def _montar_filtros(self):

        linha = ttk.Frame(self, style="Painel.TFrame")
        linha.grid(row=2, column=0, sticky="ew", pady=(0, 10))

        # Botões que funcionam como abas: só um fica selecionado
        for texto, valor in (
            ("Todos", FILTRO_TODOS),
            ("Liberados", FILTRO_LIBERADOS),
            ("Negados", FILTRO_NEGADOS),
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

        self._campo_filtro = ttk.Entry(linha, textvariable=self._texto_filtro)
        self._campo_filtro.pack(side="right", fill="x", expand=True, padx=(12, 0))

        ttk.Label(linha, text="Buscar", style="Suave.Painel.TLabel").pack(side="right")

        # Refaz a tabela a cada tecla digitada na busca
        self._texto_filtro.trace_add("write", lambda *_: self._redesenhar_tabela())

    def _montar_tabela(self):

        moldura = ttk.Frame(self, style="Cartao.TFrame")
        moldura.grid(row=3, column=0, sticky="nsew")

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

        # Cores das linhas conforme o resultado
        self._tabela.tag_configure("liberado", foreground=CORES["sucesso_texto"])
        self._tabela.tag_configure("negado", foreground=CORES["perigo_texto"])

        barra = ttk.Scrollbar(moldura, orient="vertical", command=self._tabela.yview)
        self._tabela.configure(yscrollcommand=barra.set)

        self._tabela.grid(row=0, column=0, sticky="nsew")
        barra.grid(row=0, column=1, sticky="ns")

        self._tabela.bind("<<TreeviewSelect>>", self._ao_selecionar)
        self._tabela.bind("<Double-1>", self._ao_duplo_clique)

    def _montar_evidencia(self):

        cartao = ttk.Frame(self, style="Cartao.TFrame", padding=12)
        cartao.grid(row=4, column=0, sticky="ew", pady=(12, 0))

        ttk.Label(
            cartao,
            text="Foto de evidência",
            style="Cartao.TLabel",
            font=FONTES["texto_negrito"],
        ).pack(anchor="w")

        self._rotulo_evidencia = tk.Label(
            cartao,
            bg=CORES["cartao"],
            fg=CORES["texto_suave"],
            font=FONTES["pequena"],
            height=1,
        )
        self._rotulo_evidencia.pack(fill="x", pady=(8, 0))

        # Detalhes do evento selecionado: o que o setor exigia e a
        # confiança de cada EPI no momento da decisão
        self._rotulo_detalhes = ttk.Label(
            cartao,
            text="",
            style="Suave.Cartao.TLabel",
            justify="left",
        )
        self._rotulo_detalhes.pack(anchor="w", pady=(6, 0))

        self._mostrar_texto_evidencia(
            "Selecione um evento para ver a foto. Duplo clique abre em tamanho real."
        )

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

            if len(linhas) > config.MAXIMO_LINHAS_TABELA:
                self._remover_linha(linhas[-1])

    def limpar_filtro(self):

        self._texto_filtro.set("")

    def campo_de_busca_em_foco(self) -> bool:
        """True quando o usuário está digitando na busca (para não disparar atalhos)."""

        return self.focus_get() is self._campo_filtro

    # ============================================================
    # INDICADORES
    # ============================================================

    def _atualizar_indicadores(self):

        total = len(self._registros)
        liberados = sum(1 for registro in self._registros if registro.liberado == "SIM")

        self._valor_total.config(text=str(total))
        self._valor_liberados.config(text=str(liberados))
        self._valor_negados.config(text=str(total - liberados))

        taxa = f"{liberados / total * 100:.0f}%" if total else "-"

        self._valor_taxa.config(text=taxa)

    # ============================================================
    # TABELA
    # ============================================================

    def _passa_no_filtro(self, registro) -> bool:

        resultado = self._filtro_resultado.get()

        if resultado != FILTRO_TODOS and registro.liberado != resultado:
            return False

        busca = self._texto_filtro.get().strip().lower()

        if not busca:
            return True

        return any(busca in str(valor).lower() for valor in registro.como_linha())

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

        for registro in visiveis[: config.MAXIMO_LINHAS_TABELA]:
            self._inserir_linha(registro, posicao="end")

    def _inserir_linha(self, registro, posicao):

        liberado = registro.liberado == "SIM"

        valores = [
            registro.timestamp,
            registro.pessoa,
            registro.setor,
            registro.faltando or "-",
            "Liberado" if liberado else "Negado",
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
            return

        evento = "Primeira decisão" if registro.evento == "ENTRADA" else "Mudança de decisão"

        self._rotulo_detalhes.config(
            text=(
                f"{evento}   |   Exigidos: {registro.exigidos or 'nenhum'}\n"
                f"Confiança: {registro.confiancas or '-'}"
            )
        )

        caminho = self._pasta_imagens / registro.imagem if registro.imagem else None

        if caminho is None or not caminho.exists():
            self._mostrar_texto_evidencia("Este evento não tem foto de evidência.")
            return

        try:

            imagem = Image.open(caminho)

            # Reduz para caber no cartão, mantendo a proporção
            largura_maxima = max(100, self._rotulo_evidencia.winfo_width() - 8)

            imagem.thumbnail((largura_maxima, self._altura_evidencia))

            self._imagem_evidencia = ImageTk.PhotoImage(imagem)

        except OSError:
            self._mostrar_texto_evidencia("Não foi possível abrir a foto de evidência.")
            return

        self._rotulo_evidencia.config(image=self._imagem_evidencia, text="", height=self._altura_evidencia)

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

    def _abrir_pasta(self):
        """Abre a pasta de auditoria (CSV e fotos) no Explorador de Arquivos."""

        os.startfile(self._pasta_imagens.parent)
