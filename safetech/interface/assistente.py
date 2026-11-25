"""
Assistente de configuração (abre sozinho na primeira execução).

Em cinco passos, deixa o programa pronto para usar sem precisar
procurar nada nas Configurações:

    1) Boas-vindas  -> o que o programa faz e o que vem a seguir
    2) Câmera       -> escolher a câmera e TESTAR (a imagem aparece ali)
    3) Área         -> nome da área, setor (quais EPIs exige) e modo
    4) Painel web   -> ligar ou não e trocar a senha padrão
    5) Pronto       -> resumo; "Concluir" aplica tudo

Como os outros painéis, o assistente só coleta as respostas: quem
aplica (troca a câmera, o setor, a senha...) é quem o abriu, pelas
funções recebidas. Pode ser reaberto em Configurações > Sistema.
"""

import tkinter as tk
from tkinter import ttk

import cv2
from PIL import Image, ImageTk

from safetech import config
from safetech.interface.tema import CORES, FONTES


# Ordem dos passos (o nome de cada um aparece no topo)
PASSOS = [
    ("boas_vindas", "Boas-vindas"),
    ("camera", "Câmera"),
    ("area", "Área"),
    ("painel", "Painel web"),
    ("pronto", "Pronto"),
]

# De quanto em quanto tempo (ms) a prévia da câmera é redesenhada
INTERVALO_PREVIA_MS = 100

# Tamanho da prévia da câmera (px a 100% de escala)
TAMANHO_PREVIA = (360, 203)


class Assistente(tk.Toplevel):

    def __init__(
        self,
        pai,
        opcoes_camera,
        fonte_atual,
        nome_area,
        nomes_ocupados,
        setor,
        modo,
        modos_disponiveis,
        painel_ativo,
        usa_senha_padrao,
        ao_testar_camera,
        ler_previa,
        ao_concluir,
        escala=1.0,
        mostrar=True,
    ):
        """
        opcoes_camera    -> lista de (texto, fonte) das câmeras conhecidas
        nomes_ocupados   -> nomes das OUTRAS áreas (o nome não pode repetir)
        ao_testar_camera -> chamado com a fonte: liga aquela câmera
        ler_previa       -> devolve o frame atual da câmera testada (ou None)
        ao_concluir      -> chamado com o dicionário de respostas; devolve
                            (deu_certo, mensagem)
        mostrar          -> False nos testes (a janela não aparece)
        """

        super().__init__(pai)

        self.withdraw()

        self.title("Assistente de configuração")
        self.configure(bg=CORES["painel"])
        self.transient(pai)

        largura, altura = config.TAMANHO_JANELA_ASSISTENTE
        self.geometry(f"{int(largura * escala)}x{int(altura * escala)}")

        self.protocol("WM_DELETE_WINDOW", self.fechar)

        self._opcoes_camera = list(opcoes_camera)
        self._nomes_ocupados = {nome.lower() for nome in nomes_ocupados}
        self._ao_testar_camera = ao_testar_camera
        self._ler_previa = ler_previa
        self._ao_concluir = ao_concluir
        self._usa_senha_padrao = usa_senha_padrao
        self._escala = escala

        # Respostas (começam com o que já está configurado)
        texto_camera = next((texto for texto, fonte in self._opcoes_camera if fonte == fonte_atual), "")

        self._camera = tk.StringVar(value=texto_camera)
        self._nome_area = tk.StringVar(value=nome_area)
        self._setor = tk.StringVar(value=setor)
        self._modo = tk.StringVar(value=modo)
        self._painel_ativo = tk.BooleanVar(value=painel_ativo)
        self._senha = tk.StringVar()
        self._confirmacao = tk.StringVar()

        self._modos_disponiveis = modos_disponiveis

        self._passo = 0
        self._foto_previa = None
        self._previa_agendada = None

        self._montar()
        self._mostrar_passo()

        if mostrar:
            self.deiconify()
            self.lift()
            self.focus_set()

    # ============================================================
    # MONTAGEM
    # ============================================================

    def _montar(self):

        corpo = ttk.Frame(self, style="Painel.TFrame", padding=22)
        corpo.pack(fill="both", expand=True)

        corpo.columnconfigure(0, weight=1)
        corpo.rowconfigure(1, weight=1)

        # Trilha dos passos no topo: o atual em destaque
        trilha = ttk.Frame(corpo, style="Painel.TFrame")
        trilha.grid(row=0, column=0, sticky="ew", pady=(0, 16))

        self._rotulos_trilha = []

        for numero, (_, nome) in enumerate(PASSOS, start=1):

            rotulo = tk.Label(trilha, text=f"{numero}  {nome}", bg=CORES["painel"], fg=CORES["texto_suave"], font=FONTES["texto_negrito"], padx=10, pady=4)
            rotulo.pack(side="left", padx=(0, 6))

            self._rotulos_trilha.append(rotulo)

        # Uma página por passo, no mesmo lugar (só a atual aparece)
        self._area_paginas = ttk.Frame(corpo, style="Cartao.TFrame", padding=20)
        self._area_paginas.grid(row=1, column=0, sticky="nsew")
        self._area_paginas.columnconfigure(0, weight=1)
        self._area_paginas.rowconfigure(0, weight=1)

        self._paginas = {
            "boas_vindas": self._pagina_boas_vindas(),
            "camera": self._pagina_camera(),
            "area": self._pagina_area(),
            "painel": self._pagina_painel(),
            "pronto": self._pagina_pronto(),
        }

        # Navegação
        rodape = ttk.Frame(corpo, style="Painel.TFrame")
        rodape.grid(row=2, column=0, sticky="ew", pady=(14, 0))

        self._rotulo_erro = ttk.Label(rodape, text="", style="Painel.TLabel", foreground=CORES["perigo_texto"])
        self._rotulo_erro.pack(side="left")

        self._botao_avancar = ttk.Button(rodape, text="Avançar", style="Primario.TButton", command=self._avancar, takefocus=False)
        self._botao_avancar.pack(side="right")

        self._botao_voltar = ttk.Button(rodape, text="Voltar", style="Secundario.TButton", command=self._voltar, takefocus=False)
        self._botao_voltar.pack(side="right", padx=(0, 8))

        ttk.Button(rodape, text="Agora não", command=self.fechar, takefocus=False).pack(side="right", padx=(0, 8))

    def _pagina(self, titulo, texto):
        """Página com título e explicação; devolve (página, quadro para os campos)."""

        pagina = ttk.Frame(self._area_paginas, style="Cartao.TFrame")
        pagina.columnconfigure(0, weight=1)

        ttk.Label(pagina, text=titulo, style="Cartao.TLabel", font=FONTES["titulo"]).grid(row=0, column=0, sticky="w")

        ttk.Label(pagina, text=texto, style="Suave.Cartao.TLabel", wraplength=int(560 * self._escala), justify="left").grid(
            row=1, column=0, sticky="w", pady=(6, 16)
        )

        campos = ttk.Frame(pagina, style="Cartao.TFrame")
        campos.grid(row=2, column=0, sticky="nsew")

        return pagina, campos

    def _pagina_boas_vindas(self):

        pagina, campos = self._pagina(
            f"Bem-vindo ao {config.NOME_PRODUTO}",
            "O programa verifica, pela câmera, se cada pessoa está usando os EPIs exigidos no setor "
            "(capacete, óculos, colete, luvas), libera ou nega o acesso e registra tudo na auditoria, com foto.\n\n"
            "Em quatro passos rápidos você escolhe a câmera, diz o que a área exige e protege o painel web do "
            "gerente. Tudo pode ser mudado depois em Configurações.",
        )

        return pagina

    def _pagina_camera(self):

        pagina, campos = self._pagina(
            "Qual câmera vigia a entrada?",
            "Escolha a câmera e clique em Testar: a imagem dela aparece abaixo. Câmeras IP (de segurança "
            "ou o celular) são adicionadas depois, em Configurações > Área e câmera.",
        )

        linha = ttk.Frame(campos, style="Cartao.TFrame")
        linha.grid(row=0, column=0, sticky="w")

        self._caixa_camera = ttk.Combobox(
            linha, textvariable=self._camera, values=[texto for texto, _ in self._opcoes_camera], state="readonly", width=28, takefocus=False
        )
        self._caixa_camera.pack(side="left")

        ttk.Button(linha, text="Testar", style="Secundario.TButton", command=self._testar_camera, takefocus=False).pack(side="left", padx=(10, 0))

        largura, altura = (int(medida * self._escala) for medida in TAMANHO_PREVIA)

        self._previa = tk.Canvas(campos, width=largura, height=altura, bg=CORES["video"], highlightthickness=0)
        self._previa.grid(row=1, column=0, sticky="w", pady=(14, 0))

        self._previa.create_image(largura // 2, altura // 2, tags="imagem")
        self._previa.create_text(largura // 2, altura // 2, text="Clique em Testar", fill=CORES["texto_suave"], font=FONTES["texto"], tags="texto")

        return pagina

    def _pagina_area(self):

        pagina, campos = self._pagina(
            "O que esta área exige?",
            "Dê um nome à área (ex.: Portaria) e escolha o setor: ele define quais EPIs são obrigatórios. "
            "No modo Catraca o programa libera ou nega o acesso; no modo Vigilância só confere quem está na área.",
        )

        ttk.Label(campos, text="Nome da área", style="Suave.Cartao.TLabel").grid(row=0, column=0, sticky="w", padx=(0, 12), pady=4)
        ttk.Entry(campos, textvariable=self._nome_area, width=28).grid(row=0, column=1, sticky="w", pady=4)

        ttk.Label(campos, text="Setor", style="Suave.Cartao.TLabel").grid(row=1, column=0, sticky="w", padx=(0, 12), pady=4)
        ttk.Combobox(campos, textvariable=self._setor, values=list(config.SETORES), state="readonly", width=26, takefocus=False).grid(
            row=1, column=1, sticky="w", pady=4
        )

        ttk.Label(campos, text="Modo", style="Suave.Cartao.TLabel").grid(row=2, column=0, sticky="w", padx=(0, 12), pady=4)

        modos = ttk.Frame(campos, style="Cartao.TFrame")
        modos.grid(row=2, column=1, sticky="w", pady=4)

        for modo, nome in config.MODOS_DETECCAO.items():

            botao = ttk.Radiobutton(modos, text=nome, value=modo, variable=self._modo, style="Modo.Toolbutton", takefocus=False)
            botao.pack(side="left", padx=(0, 2))

            if modo not in self._modos_disponiveis:
                botao.state(["disabled"])

        return pagina

    def _pagina_painel(self):

        pagina, campos = self._pagina(
            "Painel web do gerente",
            "Uma página, aberta no navegador de outro computador ou do celular, com o status ao vivo e a "
            "auditoria. Ela mostra fotos de pessoas: defina uma senha só sua (a padrão está no código do "
            "projeto, que é público). Deixe em branco para manter a atual.",
        )

        ttk.Checkbutton(campos, text="Ligar o painel web", variable=self._painel_ativo, style="Cartao.TCheckbutton", takefocus=False).grid(
            row=0, column=0, columnspan=2, sticky="w", pady=(0, 8)
        )

        ttk.Label(campos, text="Nova senha", style="Suave.Cartao.TLabel").grid(row=1, column=0, sticky="w", padx=(0, 12), pady=4)
        ttk.Entry(campos, textvariable=self._senha, width=24, show="•").grid(row=1, column=1, sticky="w", pady=4)

        ttk.Label(campos, text="Confirmar senha", style="Suave.Cartao.TLabel").grid(row=2, column=0, sticky="w", padx=(0, 12), pady=4)
        ttk.Entry(campos, textvariable=self._confirmacao, width=24, show="•").grid(row=2, column=1, sticky="w", pady=4)

        if self._usa_senha_padrao:
            ttk.Label(
                campos, text="Hoje o painel usa a senha padrão: recomendamos trocar.", style="Cartao.TLabel", foreground=CORES["alerta_texto"]
            ).grid(row=3, column=0, columnspan=2, sticky="w", pady=(8, 0))

        return pagina

    def _pagina_pronto(self):

        pagina, campos = self._pagina(
            "Tudo pronto",
            "Confira o resumo e clique em Concluir. Depois é só ligar a câmera (botão ▶ ou a tecla Espaço) "
            "e abrir o Telão (F2) no monitor virado para o trabalhador.",
        )

        self._rotulo_resumo = ttk.Label(campos, text="", style="Cartao.TLabel", justify="left")
        self._rotulo_resumo.grid(row=0, column=0, sticky="w")

        return pagina

    # ============================================================
    # NAVEGAÇÃO
    # ============================================================

    def passo_atual(self) -> str:
        return PASSOS[self._passo][0]

    def _mostrar_passo(self):

        for pagina in self._paginas.values():
            pagina.grid_remove()

        chave = self.passo_atual()

        self._paginas[chave].grid(row=0, column=0, sticky="nsew")

        for indice, rotulo in enumerate(self._rotulos_trilha):

            atual = indice == self._passo
            rotulo.config(bg=CORES["destaque"] if atual else CORES["painel"], fg="white" if atual else CORES["texto_suave"])

        self._botao_voltar.state(["!disabled"] if self._passo > 0 else ["disabled"])
        self._botao_avancar.config(text="Concluir" if chave == "pronto" else "Avançar")

        if chave == "pronto":
            self._rotulo_resumo.config(text=self._resumo())

        self._rotulo_erro.config(text="")

    def _validar(self):
        """Erro do passo atual (texto) ou None."""

        if self.passo_atual() == "area":

            nome = self._nome_area.get().strip()

            if not nome:
                return "Dê um nome à área."

            if nome.lower() in self._nomes_ocupados:
                return "Já existe outra área com esse nome."

        if self.passo_atual() == "painel" and self._senha.get() != self._confirmacao.get():
            return "A senha e a confirmação estão diferentes."

        return None

    def _avancar(self):

        erro = self._validar()

        if erro:
            self._rotulo_erro.config(text=erro)
            return

        if self.passo_atual() == "pronto":
            self._concluir()
            return

        self._passo += 1
        self._mostrar_passo()

    def _voltar(self):

        if self._passo > 0:
            self._passo -= 1
            self._mostrar_passo()

    def respostas(self) -> dict:
        """O que foi escolhido em cada passo."""

        fonte = next((fonte for texto, fonte in self._opcoes_camera if texto == self._camera.get()), None)

        return {
            "camera": fonte,
            "nome_area": self._nome_area.get().strip(),
            "setor": self._setor.get(),
            "modo": self._modo.get(),
            "painel_ativo": self._painel_ativo.get(),
            "senha": self._senha.get(),
            "confirmacao": self._confirmacao.get(),
        }

    def _resumo(self):

        respostas = self.respostas()

        senha = "nova senha definida" if respostas["senha"] else "senha mantida"

        linhas = [
            f"Câmera:   {self._camera.get() or '-'}",
            f"Área:     {respostas['nome_area']}",
            f"Setor:    {respostas['setor']} (exige {', '.join(config.EPIS[c] for c in config.SETORES.get(respostas['setor'], [])) or 'nada'})",
            f"Modo:     {config.MODOS_DETECCAO.get(respostas['modo'], respostas['modo'])}",
            f"Painel:   {'ligado, ' + senha if respostas['painel_ativo'] else 'desligado'}",
        ]

        return "\n".join(linhas)

    def _concluir(self):

        deu_certo, mensagem = self._ao_concluir(self.respostas())

        if not deu_certo:
            self._rotulo_erro.config(text=mensagem)
            return

        self.fechar()

    def fechar(self):

        if self._previa_agendada is not None:
            self.after_cancel(self._previa_agendada)
            self._previa_agendada = None

        self.destroy()

    # ============================================================
    # PRÉVIA DA CÂMERA
    # ============================================================

    def _testar_camera(self):

        fonte = self.respostas()["camera"]

        if fonte is None:
            self._rotulo_erro.config(text="Escolha uma câmera da lista.")
            return

        self._rotulo_erro.config(text="")

        self._ao_testar_camera(fonte)

        self._previa.itemconfigure("texto", text="Abrindo a câmera...")

        if self._previa_agendada is None:
            self._atualizar_previa()

    def _atualizar_previa(self):

        frame = self._ler_previa()

        if frame is not None:

            largura = self._previa.winfo_width()
            altura = self._previa.winfo_height()

            altura_frame, largura_frame = frame.shape[:2]
            escala = min(largura / largura_frame, altura / altura_frame)

            tamanho = (max(1, int(largura_frame * escala)), max(1, int(altura_frame * escala)))

            imagem = Image.fromarray(cv2.cvtColor(cv2.resize(frame, tamanho), cv2.COLOR_BGR2RGB))

            self._foto_previa = ImageTk.PhotoImage(imagem)

            self._previa.itemconfigure("imagem", image=self._foto_previa)
            self._previa.itemconfigure("texto", text="")

        self._previa_agendada = self.after(INTERVALO_PREVIA_MS, self._atualizar_previa)
