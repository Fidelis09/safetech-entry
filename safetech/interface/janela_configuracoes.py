"""
Janela de Configurações.

Junta, numa janela à parte, tudo o que se ajusta de vez em quando e
não precisa ficar o tempo todo na tela principal:

    Área e câmera  -> a área ABERTA na tela: nome, câmera, se comanda a
                      catraca, criar e remover áreas, câmeras IP
    Análise        -> confiança mínima e intervalo (valem para todas)
    Painel web     -> ligar, porta, acesso pela rede, usuário e senha do
                      painel do gerente
    Coleta         -> salvar imagens rotuladas para treinar o modelo
    Sistema        -> assistente de configuração, backup e restauração
                      das configurações, pasta de logs

(Setor, modo e EPIs exigidos ficam na própria aba de cada área, na tela
principal: é o que se mexe durante a operação.)

A janela é criada UMA vez, escondida, quando o programa abre. O botão
"Configurações" só a mostra, e fechar só a esconde de novo. Assim:

    - o que foi marcado (ex.: os rótulos da coleta) não se perde;
    - a janela principal pode atualizá-la a qualquer momento (lista de
      câmeras, área aberta, resumo do dataset), mesmo com ela fechada.

Como os painéis, ela só exibe e avisa: quem faz as coisas de verdade
(trocar a câmera, criar uma área, salvar a imagem) são funções
recebidas da janela principal.
"""

import tkinter as tk
from tkinter import ttk

from safetech import config
from safetech.interface.tema import CORES, FONTES
from safetech.nucleo.epis import nome_do_epi


class JanelaConfiguracoes(tk.Toplevel):

    def __init__(
        self,
        pai,
        limiar_inicial,
        intervalo_inicial,
        fonte_camera_inicial,
        cameras_ip_iniciais,
        ao_escolher_camera,
        ao_adicionar_camera_ip,
        ao_remover_camera_ip,
        ao_nova_area,
        ao_renomear_area,
        ao_remover_area,
        ao_mudar_controle_catraca,
        ao_mudar_parametros,
        ao_salvar_imagem,
        ao_enviar_arquivos,
        ao_aplicar_painel_web=None,
        ao_abrir_painel_web=None,
        ao_assistente=None,
        ao_salvar_backup=None,
        ao_restaurar_backup=None,
        ao_abrir_logs=None,
        escala=1.0,
    ):
        """
        fonte_camera_inicial     -> câmera da área aberta: número (webcam) ou endereço (IP)
        cameras_ip_iniciais      -> câmeras IP cadastradas: lista de (nome, endereço)
        ao_mudar_controle_catraca-> chamado com True/False ao marcar "comanda a catraca"
        ao_aplicar_painel_web    -> chamado com os campos da aba Painel web
                                    (por nome); devolve (deu_certo, mensagem)
        ao_abrir_painel_web      -> botão "Abrir no navegador"
        """

        super().__init__(pai)

        # Escondida desde o primeiro instante: só aparece pelo botão
        self.withdraw()

        self.title("Configurações")
        self.configure(bg=CORES["painel"])
        self.transient(pai)

        tamanho = config.TAMANHO_JANELA_CONFIGURACOES
        self.geometry(f"{int(tamanho[0] * escala)}x{int(tamanho[1] * escala)}")
        self.minsize(int(tamanho[0] * escala * 0.8), int(tamanho[1] * escala * 0.8))

        # Fechar só esconde (os ajustes continuam valendo)
        self.protocol("WM_DELETE_WINDOW", self.esconder)
        self.bind("<Escape>", lambda _evento: self.esconder())

        # ---------------- área e câmera ----------------
        self._ao_escolher_camera = ao_escolher_camera
        self._ao_adicionar_camera_ip = ao_adicionar_camera_ip
        self._ao_remover_camera_ip = ao_remover_camera_ip
        self._ao_nova_area = ao_nova_area
        self._ao_renomear_area = ao_renomear_area
        self._ao_remover_area = ao_remover_area
        self._ao_mudar_controle_catraca = ao_mudar_controle_catraca

        self._fonte_camera = fonte_camera_inicial
        self._webcams = []
        self._cameras_ip = list(cameras_ip_iniciais)

        # Última webcam usada: fica sempre na lista, para dar para
        # voltar a ela mesmo antes de a busca terminar (ou se a busca
        # não achar nenhuma).
        if isinstance(fonte_camera_inicial, int):
            self._webcam_lembrada = fonte_camera_inicial
        else:
            self._webcam_lembrada = config.INDICE_CAMERA

        # Fonte de cada item da lista, na mesma ordem dos textos
        self._fontes_da_lista = []
        self._nome_da_camera = tk.StringVar()

        self._nome_da_area = tk.StringVar()
        self._controla_catraca = tk.BooleanVar(value=False)

        # ---------------- análise ----------------
        self._ao_mudar_parametros = ao_mudar_parametros
        self._limiar = tk.DoubleVar(value=limiar_inicial * 100)
        self._intervalo = tk.DoubleVar(value=intervalo_inicial)

        # ---------------- coleta ----------------
        self._ao_salvar_imagem = ao_salvar_imagem
        self._ao_enviar_arquivos = ao_enviar_arquivos

        # O que a pessoa na câmera está usando (rótulos da próxima imagem)
        self._usando = {chave: tk.BooleanVar(value=False) for chave in config.EPIS}

        # ---------------- painel web ----------------
        self._ao_aplicar_painel_web = ao_aplicar_painel_web or (lambda **_campos: (False, ""))
        self._ao_abrir_painel_web = ao_abrir_painel_web or (lambda: None)

        # ---------------- sistema ----------------
        self._acoes_sistema = {
            "assistente": ao_assistente,
            "salvar_backup": ao_salvar_backup,
            "restaurar_backup": ao_restaurar_backup,
            "abrir_logs": ao_abrir_logs,
        }

        self._web_ativo = tk.BooleanVar(value=False)
        self._web_na_rede = tk.BooleanVar(value=False)
        self._web_porta = tk.StringVar()
        self._web_exigir_login = tk.BooleanVar(value=True)
        self._web_usuario = tk.StringVar()
        self._web_senha = tk.StringVar()
        self._web_confirmacao = tk.StringVar()
        self._web_mostrar_senha = tk.BooleanVar(value=False)

        self._montar()

    # ============================================================
    # MOSTRAR E ESCONDER
    # ============================================================

    def mostrar(self, aba=None):
        """Mostra a janela na frente (opcionalmente já numa aba: "area", "analise", "painel", "coleta", "sistema")."""

        if aba in self._abas:
            self._caderno.select(self._abas[aba])

        self.deiconify()
        self.lift()
        self.focus_set()

    def esconder(self):

        self.withdraw()

    def pai_para_dialogos(self, padrao):
        """
        Janela "dona" das caixas de diálogo (confirmar, escolher arquivo).

        Com as Configurações abertas, a caixa precisa aparecer na frente
        DELAS; senão ficaria escondida atrás.
        """

        return self if self.winfo_viewable() else padrao

    # ============================================================
    # MONTAGEM
    # ============================================================

    def _montar(self):

        corpo = ttk.Frame(self, style="Painel.TFrame", padding=18)
        corpo.pack(fill="both", expand=True)

        corpo.columnconfigure(0, weight=1)
        corpo.rowconfigure(1, weight=1)

        ttk.Label(corpo, text="Configurações", style="Titulo.Painel.TLabel").grid(
            row=0, column=0, sticky="w", pady=(0, 12)
        )

        self._caderno = ttk.Notebook(corpo, takefocus=False)
        self._caderno.grid(row=1, column=0, sticky="nsew")

        # nome interno -> quadro da aba (para abrir direto numa aba)
        self._abas = {
            "area": self._montar_aba_area(),
            "analise": self._montar_aba_analise(),
            "painel": self._montar_aba_painel_web(),
            "coleta": self._montar_aba_coleta(),
            "sistema": self._montar_aba_sistema(),
        }

        self._caderno.add(self._abas["area"], text="Área e câmera")
        self._caderno.add(self._abas["analise"], text="Análise")
        self._caderno.add(self._abas["painel"], text="Painel web")
        self._caderno.add(self._abas["coleta"], text="Coleta de imagens")
        self._caderno.add(self._abas["sistema"], text="Sistema")

        rodape = ttk.Frame(corpo, style="Painel.TFrame")
        rodape.grid(row=2, column=0, sticky="ew", pady=(12, 0))

        ttk.Label(
            rodape,
            text="As mudanças valem na hora e ficam salvas (no Painel web, ao clicar em Aplicar).",
            style="Suave.Painel.TLabel",
        ).pack(side="left")

        ttk.Button(
            rodape, text="Fechar", style="Primario.TButton", command=self.esconder, takefocus=False
        ).pack(side="right")

    def _nova_aba(self):
        """Quadro de uma aba, com o mesmo fundo dos cartões."""

        aba = ttk.Frame(self._caderno, style="Cartao.TFrame", padding=18)
        aba.columnconfigure(0, weight=1)

        return aba

    @staticmethod
    def _titulo(pai, texto, linha):

        ttk.Label(pai, text=texto, style="Cartao.TLabel", font=FONTES["texto_negrito"]).grid(
            row=linha, column=0, sticky="w"
        )

    @staticmethod
    def _explicacao(pai, texto, linha, espaco_depois=14):

        ttk.Label(pai, text=texto, style="Suave.Cartao.TLabel", justify="left", wraplength=560).grid(
            row=linha, column=0, sticky="w", pady=(4, espaco_depois)
        )

    # ------------------------------------------------------
    # ABA: ÁREA E CÂMERA
    # ------------------------------------------------------

    def _montar_aba_area(self):

        aba = self._nova_aba()

        # ---------------- a área aberta ----------------

        cabeca = ttk.Frame(aba, style="Cartao.TFrame")
        cabeca.grid(row=0, column=0, sticky="ew")

        ttk.Label(cabeca, text="Área aberta:", style="Cartao.TLabel", font=FONTES["texto_negrito"]).pack(side="left")

        ttk.Label(cabeca, textvariable=self._nome_da_area, style="Cartao.TLabel", font=FONTES["texto_negrito"]).pack(
            side="left", padx=(6, 0)
        )

        # Remover vai primeiro (à direita); fica desativado na última área
        self._botao_remover_area = ttk.Button(
            cabeca,
            text="Remover esta área",
            style="Pequeno.Perigo.TButton",
            command=self._ao_remover_area,
            takefocus=False,
        )
        self._botao_remover_area.pack(side="right")

        ttk.Button(
            cabeca,
            text="Renomear...",
            style="Secundario.TButton",
            command=self._ao_renomear_area,
            takefocus=False,
        ).pack(side="right", padx=(0, 8))

        self._explicacao(
            aba,
            "Cada área é uma câmera com a sua própria fiscalização (setor, EPIs e modo, "
            "escolhidos na aba dela na tela principal). Tudo abaixo vale para a área aberta "
            "na tela principal.",
            1,
        )

        ttk.Checkbutton(
            aba,
            text="Esta área comanda a catraca física (ESP32)",
            variable=self._controla_catraca,
            style="Cartao.TCheckbutton",
            command=lambda: self._ao_mudar_controle_catraca(self._controla_catraca.get()),
            takefocus=False,
        ).grid(row=2, column=0, sticky="w")

        self._explicacao(
            aba,
            "Só uma área pode comandar a catraca: marcar aqui desmarca a outra. A catraca só "
            "abre no modo Catraca; nas outras áreas, ou sem nenhuma marcada, ela fica desligada.",
            3,
        )

        # ---------------- câmera da área ----------------

        self._titulo(aba, "Câmera da área", 4)

        linha = ttk.Frame(aba, style="Cartao.TFrame")
        linha.grid(row=5, column=0, sticky="w", pady=(6, 0))

        # "readonly": só dá para escolher da lista
        self._caixa_camera = ttk.Combobox(
            linha,
            textvariable=self._nome_da_camera,
            state="readonly",
            width=30,
            takefocus=False,
        )
        self._caixa_camera.pack(side="left")
        self._caixa_camera.bind("<<ComboboxSelected>>", self._ao_escolher_camera_na_lista)

        ttk.Button(
            linha,
            text="Adicionar câmera IP...",
            style="Secundario.TButton",
            command=self._ao_adicionar_camera_ip,
            takefocus=False,
        ).pack(side="left", padx=(10, 0))

        # Só funciona com uma câmera IP selecionada (webcam não se remove)
        self._botao_remover_ip = ttk.Button(
            linha,
            text="Remover câmera IP",
            style="Pequeno.Perigo.TButton",
            command=lambda: self._ao_remover_camera_ip(self._fonte_camera),
            takefocus=False,
        )
        self._botao_remover_ip.pack(side="left", padx=(10, 0))

        self._explicacao(
            aba,
            "Webcams ligadas ao computador aparecem sozinhas; uma webcam só funciona em uma "
            "área de cada vez. Câmeras IP (de segurança ou o celular com o app IP Webcam) são "
            "adicionadas pelo botão. A senha de uma câmera IP nunca aparece na tela.",
            6,
        )

        # ---------------- mais áreas ----------------

        ttk.Button(
            aba,
            text="+ Nova área...",
            style="Primario.TButton",
            command=self._ao_nova_area,
            takefocus=False,
        ).grid(row=7, column=0, sticky="w")

        self._atualizar_lista_cameras()

        return aba

    # ------------------------------------------------------
    # ABA: ANÁLISE
    # ------------------------------------------------------

    def _montar_aba_analise(self):

        aba = self._nova_aba()

        self._rotulo_limiar = self._criar_deslizante(
            aba,
            linha=0,
            titulo="Confiança mínima",
            explicacao=(
                "Certeza que o modelo precisa ter para considerar que a pessoa ESTÁ usando um "
                "EPI. Mais alto = mais rigoroso (nega mais); mais baixo = mais tolerante. "
                "Vale para todas as áreas."
            ),
            variavel=self._limiar,
            minimo=config.LIMIAR_CONFIANCA_MINIMO * 100,
            maximo=config.LIMIAR_CONFIANCA_MAXIMO * 100,
        )

        self._rotulo_intervalo = self._criar_deslizante(
            aba,
            linha=3,
            titulo="Intervalo de análise",
            explicacao=(
                "De quanto em quanto tempo cada pessoa é verificada de novo. Menor = reage "
                "mais rápido, mas usa mais o computador (pesa mais com várias áreas)."
            ),
            variavel=self._intervalo,
            minimo=config.INTERVALO_CLASSIFICACAO_MINIMO_SEG,
            maximo=config.INTERVALO_CLASSIFICACAO_MAXIMO_SEG,
        )

        ttk.Button(
            aba,
            text="Voltar aos valores padrão",
            style="Secundario.TButton",
            command=self._restaurar_padroes,
            takefocus=False,
        ).grid(row=6, column=0, sticky="w", pady=(8, 0))

        self._atualizar_rotulos_parametros()

        return aba

    def _criar_deslizante(self, pai, linha, titulo, explicacao, variavel, minimo, maximo):
        """Título com o valor à direita, explicação e o controle deslizante."""

        cabeca = ttk.Frame(pai, style="Cartao.TFrame")
        cabeca.grid(row=linha, column=0, sticky="ew")

        ttk.Label(cabeca, text=titulo, style="Cartao.TLabel", font=FONTES["texto_negrito"]).pack(side="left")

        rotulo_valor = ttk.Label(cabeca, text="", style="Cartao.TLabel", font=FONTES["texto_negrito"])
        rotulo_valor.pack(side="right")

        ttk.Label(pai, text=explicacao, style="Suave.Cartao.TLabel", justify="left", wraplength=560).grid(
            row=linha + 1, column=0, sticky="w", pady=(4, 6)
        )

        ttk.Scale(
            pai,
            from_=minimo,
            to=maximo,
            orient="horizontal",
            variable=variavel,
            command=self._ao_mover_deslizante,
            takefocus=False,
        ).grid(row=linha + 2, column=0, sticky="ew", pady=(0, 18))

        return rotulo_valor

    # ------------------------------------------------------
    # ABA: PAINEL WEB
    # ------------------------------------------------------
    #
    # Nada aqui vale enquanto não se clica em "Aplicar": trocar a porta
    # ou a senha derruba quem está conectado, então a mudança é feita de
    # uma vez, conferida e com o resultado escrito embaixo.

    def _montar_aba_painel_web(self):

        aba = self._nova_aba()

        # ---------------- situação e ações ----------------

        cabeca = ttk.Frame(aba, style="Cartao.TFrame")
        cabeca.grid(row=0, column=0, sticky="ew")

        self._rotulo_situacao_web = ttk.Label(cabeca, text="", style="Cartao.TLabel", font=FONTES["texto_negrito"])
        self._rotulo_situacao_web.pack(side="left")

        self._botao_abrir_web = ttk.Button(
            cabeca,
            text="Abrir no navegador",
            style="Secundario.TButton",
            command=lambda: self._ao_abrir_painel_web(),
            takefocus=False,
        )
        self._botao_abrir_web.pack(side="right")

        # Aviso da senha padrão (pública no repositório) ou de painel sem senha
        self._rotulo_aviso_web = ttk.Label(
            aba, text="", style="Cartao.TLabel", foreground=CORES["alerta_texto"], wraplength=600, justify="left"
        )
        self._rotulo_aviso_web.grid(row=1, column=0, sticky="w", pady=(6, 10))

        # ---------------- ligar e quem pode acessar ----------------

        ttk.Checkbutton(
            aba,
            text="Ligar o painel web do gerente",
            variable=self._web_ativo,
            style="Cartao.TCheckbutton",
            command=self._atualizar_campos_web,
            takefocus=False,
        ).grid(row=2, column=0, sticky="w")

        self._caixa_rede = ttk.Checkbutton(
            aba,
            text="Permitir acesso pela rede (computador do gerente, celular, catraca pelo Wi-Fi)",
            variable=self._web_na_rede,
            style="Cartao.TCheckbutton",
            takefocus=False,
        )
        self._caixa_rede.grid(row=3, column=0, sticky="w", pady=(4, 0))

        self._explicacao(
            aba,
            "Desmarcado, só este computador abre o painel. Pela rede, o Windows pode perguntar "
            "se o Python pode aceitar conexões: permita em redes privadas.",
            4,
            espaco_depois=10,
        )

        # ---------------- formulário: porta, usuário e senha ----------------

        formulario = ttk.Frame(aba, style="Cartao.TFrame")
        formulario.grid(row=5, column=0, sticky="w")

        def campo(linha, titulo, variavel, largura, oculto=False):

            ttk.Label(formulario, text=titulo, style="Suave.Cartao.TLabel").grid(
                row=linha, column=0, sticky="w", padx=(0, 12), pady=3
            )

            entrada = ttk.Entry(formulario, textvariable=variavel, width=largura, show="\u2022" if oculto else "")
            entrada.grid(row=linha, column=1, sticky="w", pady=3)

            return entrada

        self._campo_porta = campo(0, "Porta", self._web_porta, 8)

        self._caixa_login = ttk.Checkbutton(
            formulario,
            text="Exigir usuário e senha",
            variable=self._web_exigir_login,
            style="Cartao.TCheckbutton",
            command=self._atualizar_campos_web,
            takefocus=False,
        )
        self._caixa_login.grid(row=1, column=0, columnspan=2, sticky="w", pady=(8, 2))

        self._campo_usuario = campo(2, "Usuário", self._web_usuario, 24)
        self._campo_senha = campo(3, "Nova senha", self._web_senha, 24, oculto=True)
        self._campo_confirmacao = campo(4, "Confirmar senha", self._web_confirmacao, 24, oculto=True)

        ttk.Checkbutton(
            formulario,
            text="Mostrar senha",
            variable=self._web_mostrar_senha,
            style="Cartao.TCheckbutton",
            command=self._mostrar_ou_esconder_senha,
            takefocus=False,
        ).grid(row=5, column=1, sticky="w", pady=(2, 0))

        self._explicacao(
            aba,
            f"Deixe a senha em branco para manter a atual. Mínimo de {config.PAINEL_WEB_SENHA_MINIMA} "
            "caracteres. A senha não fica guardada: só um código calculado a partir dela (hash). "
            "Se a catraca ESP32 usa o Wi-Fi, atualize usuário, senha e porta no config.h dela.",
            6,
            espaco_depois=10,
        )

        # ---------------- aplicar ----------------

        rodape = ttk.Frame(aba, style="Cartao.TFrame")
        rodape.grid(row=7, column=0, sticky="ew")

        ttk.Button(
            rodape,
            text="Aplicar",
            style="Primario.TButton",
            command=self._aplicar_painel_web,
            takefocus=False,
        ).pack(side="left")

        # Resultado do último "Aplicar" (verde deu certo, vermelho não)
        self._rotulo_resultado_web = ttk.Label(rodape, text="", style="Cartao.TLabel", wraplength=480, justify="left")
        self._rotulo_resultado_web.pack(side="left", padx=(12, 0))

        return aba

    def _mostrar_ou_esconder_senha(self):

        simbolo = "" if self._web_mostrar_senha.get() else "\u2022"

        for entrada in (self._campo_senha, self._campo_confirmacao):
            entrada.config(show=simbolo)

    def _atualizar_campos_web(self):
        """Painel desligado: nada mais se ajusta. Sem login: usuário e senha não valem."""

        ligado = self._web_ativo.get()
        com_login = ligado and self._web_exigir_login.get()

        for componente in (self._caixa_rede, self._campo_porta, self._caixa_login):
            componente.state(["!disabled"] if ligado else ["disabled"])

        for componente in (self._campo_usuario, self._campo_senha, self._campo_confirmacao):
            componente.state(["!disabled"] if com_login else ["disabled"])

    def _aplicar_painel_web(self):
        """Botão "Aplicar": a janela principal confere, salva e reinicia o painel."""

        deu_certo, mensagem = self._ao_aplicar_painel_web(
            ativo=self._web_ativo.get(),
            na_rede=self._web_na_rede.get(),
            porta=self._web_porta.get(),
            exigir_login=self._web_exigir_login.get(),
            usuario=self._web_usuario.get(),
            nova_senha=self._web_senha.get(),
            confirmacao=self._web_confirmacao.get(),
        )

        # A senha digitada não fica na tela depois de aplicada
        if deu_certo:
            self._web_senha.set("")
            self._web_confirmacao.set("")

        self._rotulo_resultado_web.config(
            text=mensagem,
            foreground=CORES["sucesso_texto"] if deu_certo else CORES["perigo_texto"],
        )

    def definir_painel_web(self, ajustes, endereco, usa_senha_padrao, erro=None):
        """
        Mostra os ajustes em uso e a situação do painel (chamado pela
        janela principal ao abrir e depois de cada "Aplicar").

        endereco -> onde o painel está no ar (None = desligado ou com erro)
        """

        self._web_ativo.set(ajustes.ativo)
        self._web_na_rede.set(ajustes.na_rede)
        self._web_porta.set(str(ajustes.porta))
        self._web_exigir_login.set(ajustes.exige_login)
        self._web_usuario.set(ajustes.usuario)

        if erro:
            situacao = f"Painel fora do ar: {erro}"
        elif endereco:
            situacao = f"No ar em {endereco}"
        else:
            situacao = "Painel desligado"

        self._rotulo_situacao_web.config(text=situacao)

        self._botao_abrir_web.state(["!disabled"] if endereco else ["disabled"])

        if ajustes.ativo and usa_senha_padrao:
            aviso = (
                "Atenção: o painel usa a senha padrão do projeto, que é pública. "
                "Defina uma senha nova antes de usar de verdade."
            )
        elif ajustes.ativo and not ajustes.exige_login:
            aviso = "Atenção: sem senha, qualquer pessoa na rede vê o painel, inclusive as fotos."
        else:
            aviso = ""

        self._rotulo_aviso_web.config(text=aviso)

        self._atualizar_campos_web()

    def mensagem_painel_web(self) -> str:
        """Texto do resultado do último "Aplicar" (usado nos testes)."""

        return self._rotulo_resultado_web.cget("text")

    # ------------------------------------------------------
    # ABA: COLETA DE IMAGENS
    # ------------------------------------------------------

    def _montar_aba_sistema(self):
        """Assistente, backup e restauração das configurações, e a pasta de logs."""

        aba = self._nova_aba()

        def acao(nome):
            return lambda: (self._acoes_sistema[nome] or (lambda: None))()

        # ---------------- assistente ----------------

        self._titulo(aba, "Assistente de configuração", 0)
        self._explicacao(
            aba,
            "Passo a passo para deixar o programa pronto: câmera, setor e modo da área "
            "principal e a senha do painel web. Ele abre sozinho na primeira vez.",
            1,
            espaco_depois=8,
        )

        ttk.Button(aba, text="Abrir o assistente...", style="Secundario.TButton", command=acao("assistente"), takefocus=False).grid(
            row=2, column=0, sticky="w", pady=(0, 18)
        )

        # ---------------- backup ----------------

        self._titulo(aba, "Backup das configurações", 3)
        self._explicacao(
            aba,
            "Um arquivo só com as áreas, câmeras, ajustes da análise, tema e painel web, para "
            "levar a outro computador ou guardar antes de grandes mudanças. Não leva a auditoria "
            "nem o dataset. Atenção: o endereço de uma câmera IP pode conter a senha dela.",
            4,
            espaco_depois=8,
        )

        botoes = ttk.Frame(aba, style="Cartao.TFrame")
        botoes.grid(row=5, column=0, sticky="w", pady=(0, 18))

        ttk.Button(botoes, text="Salvar backup...", style="Secundario.TButton", command=acao("salvar_backup"), takefocus=False).pack(side="left")

        ttk.Button(
            botoes, text="Restaurar backup...", style="Secundario.TButton", command=acao("restaurar_backup"), takefocus=False
        ).pack(side="left", padx=(10, 0))

        # ---------------- logs ----------------

        self._titulo(aba, "Registro de erros", 6)
        self._explicacao(
            aba,
            f"Tudo o que deu errado (e as ações importantes) fica em logs/{config.NOME_ARQUIVO_LOG}, "
            "com data, hora e de qual parte do programa veio.",
            7,
            espaco_depois=8,
        )

        ttk.Button(aba, text="Abrir pasta de logs", style="Secundario.TButton", command=acao("abrir_logs"), takefocus=False).grid(
            row=8, column=0, sticky="w"
        )

        return aba

    def _montar_aba_coleta(self):

        aba = self._nova_aba()

        self._titulo(aba, "A pessoa na câmera está usando", 0)
        self._explicacao(
            aba,
            "Marque o que a pessoa está usando AGORA e salve. A imagem vem da câmera da área "
            "aberta na tela principal, e cada uma é gravada com esses rótulos para treinar o "
            "modelo; um rótulo errado ensina errado. A tecla S salva e Ctrl+V cola uma imagem "
            "copiada, mesmo com esta janela fechada.",
            1,
        )

        linha_epis = ttk.Frame(aba, style="Cartao.TFrame")
        linha_epis.grid(row=2, column=0, sticky="w", pady=(0, 14))

        for chave in config.EPIS:

            ttk.Checkbutton(
                linha_epis,
                text=nome_do_epi(chave),
                variable=self._usando[chave],
                style="Cartao.TCheckbutton",
                takefocus=False,
            ).pack(side="left", padx=(0, 18))

        botoes = ttk.Frame(aba, style="Cartao.TFrame")
        botoes.grid(row=3, column=0, sticky="w")

        ttk.Button(
            botoes,
            text="Salvar imagem da câmera  [S]",
            style="Primario.TButton",
            command=self.salvar_imagem,
            takefocus=False,
        ).pack(side="left")

        # Aproveita imagens que já existem no computador
        ttk.Button(
            botoes,
            text="Enviar arquivo...",
            style="Secundario.TButton",
            command=lambda: self._ao_enviar_arquivos(self.rotulos_marcados()),
            takefocus=False,
        ).pack(side="left", padx=(10, 0))

        # Situação do dataset (total e quantas imagens por EPI)
        self._rotulo_dataset = ttk.Label(aba, text="", style="Suave.Cartao.TLabel", wraplength=560)
        self._rotulo_dataset.grid(row=4, column=0, sticky="w", pady=(14, 0))

        ttk.Label(
            aba,
            text="Depois de coletar, feche o programa e rode o treinar.py.",
            style="Suave.Cartao.TLabel",
        ).grid(row=5, column=0, sticky="w", pady=(6, 0))

        return aba

    # ============================================================
    # EVENTOS INTERNOS
    # ============================================================

    def _ao_escolher_camera_na_lista(self, _evento=None):

        # Tira a seleção azul do texto, que o Tkinter deixa na caixa
        self._caixa_camera.selection_clear()

        posicao = self._caixa_camera.current()

        if posicao < 0:
            return

        self._fonte_camera = self._fontes_da_lista[posicao]

        self._atualizar_lista_cameras()

        self._ao_escolher_camera(self._fonte_camera)

    def _ao_mover_deslizante(self, _valor=None):

        self._atualizar_rotulos_parametros()

        self._ao_mudar_parametros(self._limiar.get() / 100, self._intervalo.get())

    def _atualizar_rotulos_parametros(self):

        self._rotulo_limiar.config(text=f"{self._limiar.get():.0f}%")
        self._rotulo_intervalo.config(text=f"{self._intervalo.get():.1f} s")

    def definir_limiar(self, valor):
        """Mostra a confiança mínima (0 a 1) mudada em outro lugar (ex.: modo calibração)."""

        if abs(self._limiar.get() - valor * 100) > 0.01:
            self._limiar.set(valor * 100)
            self._atualizar_rotulos_parametros()

    def _restaurar_padroes(self):

        self._limiar.set(config.LIMIAR_CONFIANCA_PADRAO * 100)
        self._intervalo.set(config.INTERVALO_CLASSIFICACAO_PADRAO_SEG)

        self._ao_mover_deslizante()

    # ============================================================
    # MÉTODOS USADOS PELA JANELA PRINCIPAL
    # ============================================================

    # ---------------- área aberta ----------------

    def definir_area_atual(self, nome, fonte, controla_catraca, pode_remover):
        """Mostra a área aberta na tela principal: nome, câmera e se comanda a catraca."""

        self._nome_da_area.set(nome)
        self._controla_catraca.set(controla_catraca)
        self._fonte_camera = fonte

        if pode_remover:
            self._botao_remover_area.state(["!disabled"])
        else:
            self._botao_remover_area.state(["disabled"])

        self._atualizar_lista_cameras()

    # ---------------- câmeras ----------------

    def nome_camera(self, fonte):
        """
        Texto mostrado para uma câmera.

        Webcam: "Câmera N" (o OpenCV só informa o número, não o nome).
        Câmera IP: o nome dado pelo usuário. O endereço nunca aparece,
        porque pode conter a senha da câmera.
        """

        if isinstance(fonte, int):
            return f"Câmera {fonte}"

        for nome, endereco in self._cameras_ip:
            if endereco == fonte:
                return f"{nome} (IP)"

        return "Câmera IP"

    def opcoes_de_camera(self):
        """Todas as câmeras conhecidas, como lista de (texto, fonte): webcams e depois IPs."""

        webcams = sorted(set(self._webcams) | {self._webcam_lembrada})

        fontes = webcams + [endereco for _, endereco in self._cameras_ip]

        return [(self.nome_camera(fonte), fonte) for fonte in fontes]

    @property
    def webcam_lembrada(self) -> int:
        """Última webcam usada (para onde voltar quando uma câmera IP é removida)."""

        return self._webcam_lembrada

    def _atualizar_lista_cameras(self):
        """Refaz a lista: webcams e depois câmeras IP."""

        if isinstance(self._fonte_camera, int):
            self._webcam_lembrada = self._fonte_camera

        opcoes = self.opcoes_de_camera()

        self._fontes_da_lista = [fonte for _, fonte in opcoes]

        self._caixa_camera.config(values=[texto for texto, _ in opcoes])

        self._nome_da_camera.set(self.nome_camera(self._fonte_camera))

        # "Remover" só faz sentido para câmera IP
        if isinstance(self._fonte_camera, str):
            self._botao_remover_ip.state(["!disabled"])
        else:
            self._botao_remover_ip.state(["disabled"])

    def definir_cameras(self, indices):
        """Preenche a lista com as webcams encontradas pela busca."""

        self._webcams = list(indices)

        self._atualizar_lista_cameras()

    def definir_cameras_ip(self, cameras_ip, fonte_em_uso):
        """Atualiza as câmeras IP e a câmera da área aberta (depois de adicionar ou remover)."""

        self._cameras_ip = list(cameras_ip)
        self._fonte_camera = fonte_em_uso

        self._atualizar_lista_cameras()

    # ---------------- coleta ----------------

    def rotulos_marcados(self):
        """Chaves dos EPIs marcados em "A pessoa na câmera está usando"."""

        return {chave for chave, variavel in self._usando.items() if variavel.get()}

    def salvar_imagem(self):
        """Pede à janela principal para salvar o frame com os rótulos marcados."""

        self._ao_salvar_imagem(self.rotulos_marcados())

    def definir_resumo_dataset(self, total, usando_por_epi):
        """Mostra quantas imagens rotuladas existem, no total e por EPI."""

        if total == 0:
            texto = "Nenhuma imagem rotulada ainda."

        else:

            # Ex.: "128 imagens: Capacete 60, Óculos 41, ..." (quantas
            # mostram a pessoa USANDO cada equipamento)
            partes = [f"{nome_do_epi(chave)} {quantidade}" for chave, quantidade in usando_por_epi.items()]

            texto = f"Dataset: {total} imagens. Usando: " + ", ".join(partes)

        self._rotulo_dataset.config(text=texto)
