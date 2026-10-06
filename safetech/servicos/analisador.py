"""
Linha de análise do SafeTech Entry.

Roda em uma thread própria e repete, para cada frame novo da câmera:

    1) DETECTAR   -> onde estão as pessoas (detector de rosto)
    2) RASTREAR   -> quem é quem em relação ao frame anterior
    3) CLASSIFICAR-> cada pessoa está com EPI? (de tempos em tempos, em lote)
    4) DECIDIR    -> liberado / negado por pessoa e para a catraca
    5) AUDITAR    -> grava no log quando a decisão de alguém muda
    6) PUBLICAR   -> deixa o resultado pronto para a interface desenhar

A interface nunca espera por esta thread: ela só lê o último resultado
publicado. É isso que mantém o vídeo fluido mesmo enquanto a IA trabalha.
"""

import queue
import threading
import time
from dataclasses import dataclass

from safetech import config
from safetech.nucleo import anotacao, decisao
from safetech.nucleo.rastreador import RastreadorPessoas
from safetech.nucleo.tipos import EstadoCena, PessoaObservada, StatusPessoa
from safetech.servicos import auditoria as modulo_auditoria


# ============================================================
# PARÂMETROS AJUSTÁVEIS EM TEMPO REAL
# ============================================================
#
# A interface altera estes valores (sliders) e a thread de análise
# os lê a cada ciclo. São números simples, então a troca entre
# threads é segura sem precisar de trava.
# ============================================================

@dataclass
class ParametrosAnalise:

    limiar_confianca: float = config.LIMIAR_CONFIANCA_PADRAO
    intervalo_classificacao: float = config.INTERVALO_CLASSIFICACAO_PADRAO_SEG


class Analisador:

    def __init__(self, camera, detector, classificador, auditoria, parametros):

        self._camera = camera
        self._detector = detector
        self._classificador = classificador
        self._auditoria = auditoria
        self._parametros = parametros

        self._rastreador = RastreadorPessoas()

        # Resultado mais recente, lido pela interface
        self._trava = threading.Lock()
        self._estado = EstadoCena()

        # Registros de auditoria novos, para a interface mostrar na tabela
        self.registros_novos: queue.Queue = queue.Queue()

        self._ultima_classificacao = 0.0

        # Mensagem do erro que interrompeu a análise (None = tudo certo)
        self.erro = None

        self._parar = threading.Event()
        self._thread = None

    # ============================================================
    # CONTROLE
    # ============================================================

    def iniciar(self):

        if self._thread is not None and self._thread.is_alive():
            return

        self._parar.clear()

        self._thread = threading.Thread(
            target=self._executar,
            name="analisador",
            daemon=True,
        )

        self._thread.start()

    def parar(self):

        self._parar.set()

        if self._thread is not None:
            self._thread.join(timeout=3)
            self._thread = None

    def estado(self) -> EstadoCena:
        """Último resultado publicado (seguro para ler de outra thread)."""

        with self._trava:
            return self._estado

    # ============================================================
    # LAÇO PRINCIPAL
    # ============================================================

    def _executar(self):

        # Se algo inesperado acontecer, a thread não morre em silêncio:
        # o erro fica guardado para a interface mostrar ao usuário.
        try:
            self._laco()

        except Exception as erro:
            self.erro = f"{type(erro).__name__}: {erro}"
            self._publicar(EstadoCena())

    def _laco(self):

        periodo_minimo = 1.0 / config.TAXA_MAXIMA_ANALISE_HZ

        ultimo_numero_frame = -1

        ciclos_no_periodo = 0
        inicio_periodo = time.perf_counter()
        analises_por_segundo = 0.0

        while not self._parar.is_set():

            inicio_ciclo = time.perf_counter()

            frame, numero_frame = self._camera.ler()

            # ------------------------------------------------------
            # Câmera desligada: esquece as pessoas e espera
            # ------------------------------------------------------

            if frame is None:

                self._rastreador.limpar()
                self._publicar(EstadoCena())

                ultimo_numero_frame = -1

                self._parar.wait(0.05)
                continue

            # ------------------------------------------------------
            # Ainda é o mesmo frame da última volta: espera o próximo
            # ------------------------------------------------------

            if numero_frame == ultimo_numero_frame:
                self._parar.wait(0.003)
                continue

            ultimo_numero_frame = numero_frame

            # ------------------------------------------------------
            # 1) DETECTAR  e  2) RASTREAR
            # ------------------------------------------------------

            caixas = self._detector.detectar(frame)

            rastros = self._rastreador.atualizar(caixas, inicio_ciclo)

            # ------------------------------------------------------
            # 3) CLASSIFICAR,  4) DECIDIR  e  5) AUDITAR
            # ------------------------------------------------------

            if self._hora_de_classificar(rastros, inicio_ciclo):

                self._classificar(frame, rastros)
                self._auditar_mudancas(frame, rastros)

                self._ultima_classificacao = inicio_ciclo

            # ------------------------------------------------------
            # 6) PUBLICAR
            # ------------------------------------------------------

            ciclos_no_periodo += 1
            decorrido = time.perf_counter() - inicio_periodo

            if decorrido >= 0.5:
                analises_por_segundo = ciclos_no_periodo / decorrido
                ciclos_no_periodo = 0
                inicio_periodo = time.perf_counter()

            self._publicar(self._montar_estado(rastros, analises_por_segundo))

            # Não analisa mais rápido do que o necessário
            sobra = periodo_minimo - (time.perf_counter() - inicio_ciclo)

            if sobra > 0:
                self._parar.wait(sobra)

    # ============================================================
    # 3) CLASSIFICAÇÃO
    # ============================================================

    def _hora_de_classificar(self, rastros, agora) -> bool:
        """
        Classificar é a etapa mais cara, então não roda em todo frame.

        Roda no intervalo configurado na tela; mas, se houver alguém
        que ainda não tem decisão, usa um intervalo bem menor para a
        resposta sair rápido.
        """

        visiveis = [rastro for rastro in rastros if rastro.visivel]

        if not visiveis:
            return False

        desde_a_ultima = agora - self._ultima_classificacao

        alguem_sem_decisao = any(
            len(rastro.historico) < config.AMOSTRAS_MINIMAS_DECISAO
            for rastro in visiveis
        )

        if alguem_sem_decisao:
            return desde_a_ultima >= config.INTERVALO_CLASSIFICACAO_RAPIDA_SEG

        return desde_a_ultima >= self._parametros.intervalo_classificacao

    def _classificar(self, frame, rastros):
        """Classifica todas as pessoas visíveis numa única chamada ao modelo."""

        visiveis = [rastro for rastro in rastros if rastro.visivel]

        recortes = []

        for rastro in visiveis:

            x1, y1, x2, y2 = rastro.caixa

            recortes.append(frame[y1:y2, x1:x2])

        probabilidades = self._classificador.classificar_lote(recortes)

        for rastro, vetor in zip(visiveis, probabilidades):
            rastro.historico.append(vetor)

    # ============================================================
    # 4) DECISÃO
    # ============================================================

    def _avaliar(self, rastro):

        return decisao.avaliar_pessoa(
            rastro.historico,
            self._classificador.classes,
            self._parametros.limiar_confianca,
        )

    def _montar_estado(self, rastros, analises_por_segundo) -> EstadoCena:

        pessoas = []

        for rastro in rastros:

            status, classe, confianca = self._avaliar(rastro)

            pessoas.append(
                PessoaObservada(
                    identificador=rastro.identificador,
                    caixa=rastro.caixa,
                    status=status,
                    classe=classe,
                    confianca=confianca,
                )
            )

        return EstadoCena(
            pessoas=tuple(pessoas),
            acesso=decisao.avaliar_acesso(pessoa.status for pessoa in pessoas),
            analises_por_segundo=analises_por_segundo,
        )

    # ============================================================
    # 5) AUDITORIA
    # ============================================================

    def _auditar_mudancas(self, frame, rastros):
        """Grava um evento para cada pessoa cuja decisão mudou."""

        for rastro in rastros:

            if not rastro.visivel:
                continue

            status, classe, confianca = self._avaliar(rastro)

            if status is StatusPessoa.ANALISANDO:
                continue

            liberado = status is StatusPessoa.LIBERADO

            if liberado == rastro.decisao_registrada:
                continue

            if rastro.decisao_registrada is None:
                evento = modulo_auditoria.EVENTO_ENTRADA
            else:
                evento = modulo_auditoria.EVENTO_MUDANCA

            # Foto de evidência: o frame inteiro (contexto) com a
            # pessoa em questão destacada. É uma CÓPIA, porque o
            # frame original é compartilhado com a interface.
            evidencia = anotacao.desenhar_pessoas(
                frame.copy(),
                [
                    PessoaObservada(
                        identificador=rastro.identificador,
                        caixa=rastro.caixa,
                        status=status,
                        classe=classe,
                        confianca=confianca,
                    )
                ],
            )

            registro = self._auditoria.registrar(
                evento,
                rastro.identificador,
                classe,
                confianca,
                liberado,
                evidencia,
            )

            rastro.decisao_registrada = liberado

            self.registros_novos.put(registro)

    # ============================================================
    # 6) PUBLICAÇÃO
    # ============================================================

    def _publicar(self, estado):

        with self._trava:
            self._estado = estado
