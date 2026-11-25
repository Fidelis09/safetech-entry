"""
Uma ÁREA monitorada: uma câmera e tudo o que vem junto com ela.

Com várias câmeras, cada área tem as suas próprias peças:

    dados       -> nome, câmera, setor, EPIs exigidos, modo e se
                   comanda a catraca (é o que fica salvo)
    camera      -> captura (thread própria)
    parametros  -> o que a análise desta área cobra
    analisador  -> detecta, classifica, decide e audita (thread própria;
                   criado quando a IA termina de carregar)
    painel      -> a aba da tela com o vídeo, o status e os controles

Também desenha o vídeo e a faixa de status da sua aba. A janela
principal só chama atualizar_tela() da área que está à vista: as outras
continuam analisando e registrando, sem gastar tempo com desenho.

A auditoria NÃO fica aqui: ela é uma só para todas as áreas.
"""

import time
from datetime import datetime

import cv2
from PIL import Image, ImageTk

from safetech.interface.tema import CORES
from safetech.nucleo import anotacao, epis, modos
from safetech.nucleo.tipos import EstadoCena, StatusAcesso, StatusPessoa
from safetech.servicos.analisador import Analisador
from safetech.servicos.camera import EstadoCamera, eh_endereco_ip


# Textos do botão da câmera. Os símbolos ▶ e ■ são os de "tocar" e
# "parar" de qualquer aparelho: dizem a ação antes mesmo de ler.
TEXTO_INICIAR = "\u25b6  Iniciar câmera"
TEXTO_PARAR = "\u25a0  Parar câmera"


class AreaMonitorada:

    def __init__(self, dados, camera, parametros, painel):

        self.dados = dados
        self.camera = camera
        self.parametros = parametros
        self.painel = painel

        # Criado quando a IA terminar de carregar
        self.analisador = None

        # Controle do desenho (para não redesenhar o que não mudou)
        self._foto = None
        self._ultimo_desenho = None
        self._ultimo_status = None
        self._ultimo_estado_camera = None
        self._proxima_medicao = 0.0

    @property
    def nome(self):
        return self.dados.nome

    # ============================================================
    # ANÁLISE
    # ============================================================

    def iniciar_analise(self, detectores, classificador, auditoria):
        """Cria e liga a linha de análise desta área (quando a IA fica pronta)."""

        self.analisador = Analisador(self.camera, detectores, classificador, auditoria, self.parametros)
        self.analisador.iniciar()

        self.esquecer_desenho()

    def ler_ao_vivo(self):
        """
        (frame, estado) do momento, para o painel web e a catraca.
        Chamado por outras threads: só usa leituras seguras entre threads.
        """

        frame, _ = self.camera.ler()

        if self.analisador is None:
            return frame, EstadoCena(modo=self.parametros.modo_deteccao, area=self.nome)

        return frame, self.analisador.estado()

    def parar(self):

        if self.analisador is not None:
            self.analisador.parar()

        self.camera.parar()

    # ============================================================
    # DESENHO DA ABA
    # ============================================================

    def esquecer_desenho(self):
        """Força a aba a ser redesenhada inteira (ex.: ao voltar a ficar à vista)."""

        self._ultimo_desenho = None
        self._ultimo_status = None
        self._ultimo_estado_camera = None

    def atualizar_tela(self):
        """Chamado ~30 vezes por segundo, só para a área que está à vista."""

        if self.analisador is None:
            return

        self._atualizar_camera()
        self._desenhar_video()
        self._atualizar_status()
        self._atualizar_legenda()

    # ------------------------------------------------------
    # CÂMERA: botão e mensagens conforme o estado
    # ------------------------------------------------------

    def _atualizar_camera(self):

        estado = self.camera.estado

        if estado is self._ultimo_estado_camera:
            return

        self._ultimo_estado_camera = estado

        painel = self.painel
        camera_ip = eh_endereco_ip(getattr(self.camera, "fonte", None))

        if estado is EstadoCamera.ATIVA:

            painel.definir_botao_camera(TEXTO_PARAR, "Perigo.TButton")

        elif estado is EstadoCamera.ABRINDO:

            painel.definir_botao_camera("Abrindo...", "Primario.TButton", False)

            if camera_ip:
                painel.mostrar_mensagem("Conectando à câmera IP...\nIsso pode levar alguns segundos.")
            else:
                painel.mostrar_mensagem("Abrindo a câmera...")

        elif estado is EstadoCamera.RECONECTANDO:

            # Câmera que caiu no meio do uso: ela mesma tenta voltar sozinha
            painel.definir_botao_camera(TEXTO_PARAR, "Perigo.TButton")

            if camera_ip:
                painel.mostrar_mensagem("A conexão com a câmera IP caiu\nTentando reconectar sozinho...")
            else:
                painel.mostrar_mensagem("A webcam parou de responder\nConfira o cabo USB. Tentando reabrir sozinho...")

        elif estado is EstadoCamera.ERRO:

            painel.definir_botao_camera("Tentar novamente", "Primario.TButton")

            if camera_ip:
                painel.mostrar_mensagem(
                    "Não foi possível conectar à câmera IP\n"
                    "Confira o endereço, o usuário e a senha, e se a câmera está "
                    "ligada e na mesma rede que este computador.",
                    botao="Tentar novamente",
                )
            else:
                painel.mostrar_mensagem(
                    "Não foi possível acessar a webcam\n"
                    "Verifique se ela está conectada e se outro programa "
                    "(ou outra área) não a está usando.",
                    botao="Tentar novamente",
                )

        else:

            painel.definir_botao_camera(TEXTO_INICIAR, "Primario.TButton")
            painel.mostrar_mensagem(
                "Câmera desligada\nLigue a câmera para começar a fiscalizar esta área (ou pressione Espaço).",
                botao=TEXTO_INICIAR,
            )

        # O vídeo e o status precisam ser redesenhados para o novo estado
        self._ultimo_desenho = None
        self._ultimo_status = None

    # ------------------------------------------------------
    # VÍDEO
    # ------------------------------------------------------

    def _desenhar_video(self):

        frame, numero_frame = self.camera.ler()

        if frame is None:
            return

        estado = self.analisador.estado()

        largura_tela, altura_tela = self.painel.tamanho_do_video()

        # Não redesenha se nada mudou desde o último ciclo
        assinatura = (numero_frame, id(estado), largura_tela, altura_tela)

        if assinatura == self._ultimo_desenho or largura_tela < 20 or altura_tela < 20:
            return

        self._ultimo_desenho = assinatura

        # Ajusta o frame ao espaço disponível, mantendo a proporção
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

        self.painel.mostrar_imagem(self._foto)

    # ------------------------------------------------------
    # FAIXA DE STATUS
    # ------------------------------------------------------

    def resumo_status(self):
        """
        (título, detalhe, cor) da situação da área agora.

        Usado na faixa de status da aba e nos quadros da visão geral.
        """

        if self.analisador is None:
            return ("CARREGANDO", "Preparando o modelo de IA...", CORES["neutro"])

        if self.analisador.reiniciando:
            return (
                "REINICIANDO A ANÁLISE",
                f"Erro inesperado: {self.analisador.erro}. Recomeçando sozinha em instantes "
                "(detalhes em logs/safetech.log).",
                CORES["alerta"],
            )

        if self.analisador.erro:
            return ("ERRO NA ANÁLISE", self.analisador.erro, CORES["perigo"])

        if self.camera.estado is EstadoCamera.RECONECTANDO:

            if eh_endereco_ip(getattr(self.camera, "fonte", None)):
                detalhe = "A conexão com a câmera IP caiu. Tentando de novo..."
            else:
                detalhe = "A webcam parou de responder. Tentando reabrir..."

            return ("RECONECTANDO", detalhe, CORES["alerta"])

        if self.camera.estado is not EstadoCamera.ATIVA:
            return ("CÂMERA DESLIGADA", "Ligue a câmera para iniciar o monitoramento.", CORES["neutro"])

        return descrever_acesso(self.analisador.estado())

    def _atualizar_status(self):

        status = self.resumo_status()

        if status != self._ultimo_status:

            self._ultimo_status = status

            self.painel.definir_status(*status)

    # ------------------------------------------------------
    # LEGENDAS SOBRE O VÍDEO (ao vivo, relógio e desempenho)
    # ------------------------------------------------------

    def _atualizar_legenda(self):

        agora = time.perf_counter()

        # Duas vezes por segundo é suficiente; mais que isso só pisca
        if agora < self._proxima_medicao:
            return

        self._proxima_medicao = agora + 0.5

        frame, _ = self.camera.ler()

        if self.camera.estado is not EstadoCamera.ATIVA or frame is None:
            self.painel.definir_legenda("", "")
            return

        esquerda, direita = textos_da_legenda(self.nome, frame, self.camera.fps, self.analisador.estado())

        # O ponto do "AO VIVO" fica aceso nos segundos pares: pisca
        self.painel.definir_legenda(esquerda, direita, ponto_aceso=datetime.now().second % 2 == 0)


# ============================================================
# TEXTOS DAS LEGENDAS SOBRE O VÍDEO
# ============================================================

def textos_da_legenda(nome_area, frame, fps, estado: EstadoCena):
    """
    (esquerda, direita) das legendas sobre o vídeo, ex.:

        "AO VIVO   Portaria   24/11/2026 14:10:32"
        "1280×720   30 fps   Análise 13/s   3 pessoas"

    A resolução é a do frame recebido, que nem sempre é a pedida
    (cada webcam usa a mais próxima que suporta).
    """

    altura, largura = frame.shape[:2]

    total = len(estado.pessoas)

    esquerda = f"AO VIVO   {nome_area}   {datetime.now().strftime('%d/%m/%Y %H:%M:%S')}"

    direita = (
        f"{largura}\u00d7{altura}   {fps:.0f} fps   "
        f"Análise {estado.analises_por_segundo:.0f}/s   "
        f"{total} {'pessoa' if total == 1 else 'pessoas'}"
    )

    return esquerda, direita


# ============================================================
# TEXTO DA FAIXA DE STATUS
# ============================================================

def descrever_acesso(estado: EstadoCena):
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
            modos.titulo_da_situacao(estado.modo, estado.acesso),
            f"{total} {plural} {textos['lugar']}, todas com os EPIs exigidos.\n{exigencia}",
            CORES["sucesso"],
        )

    if estado.acesso is StatusAcesso.NEGADO:

        negadas = [pessoa for pessoa in estado.pessoas if pessoa.status is StatusPessoa.NEGADO]

        # Com várias pessoas, listar uma por uma não cabe na faixa. O
        # resumo diz quantas estão irregulares e, para cada EPI
        # exigido, em quantas pessoas ele falta. O detalhe por pessoa
        # fica no log de auditoria, com a foto.
        faltas = ", ".join(
            f"{epis.nome_do_epi(chave)} ({quantidade})"
            for chave in estado.exigidos
            if (quantidade := sum(1 for pessoa in negadas if chave in pessoa.faltando))
        )

        return (
            modos.titulo_da_situacao(estado.modo, estado.acesso),
            f"{len(negadas)} de {total} {plural} sem EPI exigido. Faltando: {faltas}\n{exigencia}",
            CORES["perigo"],
        )

    if estado.acesso is StatusAcesso.ANALISANDO:

        return (
            modos.titulo_da_situacao(estado.modo, estado.acesso),
            f"{total} {plural} {textos['lugar']}, verificando os equipamentos...\n{exigencia}",
            CORES["alerta"],
        )

    return (
        modos.titulo_da_situacao(estado.modo, StatusAcesso.SEM_PESSOAS),
        f"Nenhuma pessoa {textos['lugar']}.\n{exigencia}",
        CORES["neutro"],
    )
