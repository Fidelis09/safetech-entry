"""
Linha de análise do SafeTech Entry.

Roda em uma thread própria e repete, para cada frame novo da câmera:

    1) DETECTAR   -> onde estão as pessoas (detector de rosto)
    2) RASTREAR   -> quem é quem em relação ao frame anterior
    3) CLASSIFICAR-> quais EPIs cada pessoa usa? (de tempos em tempos, em lote)
    4) DECIDIR    -> compara com os EPIs exigidos no setor: liberado / negado
    5) AUDITAR    -> grava no log quando a decisão de alguém muda
    6) PUBLICAR   -> deixa o resultado pronto para a interface desenhar

A interface nunca espera por esta thread: ela só lê o último resultado
publicado. É isso que mantém o vídeo fluido mesmo enquanto a IA trabalha.

Se algo inesperado quebrar a análise, a própria thread faz papel de
"vigia": guarda o erro no log, espera um pouco e recomeça sozinha
(veja _executar). Só desiste depois de várias falhas seguidas.
"""

import logging
import queue
import threading
import time
from dataclasses import dataclass

from safetech import config
from safetech.nucleo import anotacao, decisao, horario, modos
from safetech.nucleo.rastreador import RastreadorPessoas
from safetech.nucleo.tipos import EstadoCena, PessoaObservada, StatusPessoa
from safetech.servicos import auditoria as modulo_auditoria


log = logging.getLogger(__name__)


# ============================================================
# PARÂMETROS AJUSTÁVEIS EM TEMPO REAL
# ============================================================
#
# A interface altera estes valores (controles da tela) e a thread de
# análise os lê a cada ciclo. Cada valor é trocado inteiro de uma vez
# (número, texto ou tupla), então a troca entre threads é segura sem
# precisar de trava.
# ============================================================

@dataclass
class ParametrosAnalise:

    limiar_confianca: float = config.LIMIAR_CONFIANCA_PADRAO
    intervalo_classificacao: float = config.INTERVALO_CLASSIFICACAO_PADRAO_SEG

    # Setor em fiscalização e as chaves dos EPIs obrigatórios nele
    setor: str = config.SETOR_PADRAO
    exigidos: tuple = tuple(config.SETORES[config.SETOR_PADRAO])

    # Modo de operação: config.MODO_CATRACA (acha pelo rosto) ou config.MODO_VIGILANCIA (pelo corpo)
    modo_deteccao: str = config.MODO_DETECCAO_PADRAO

    # Nome da área (câmera) analisada: vai para cada evento da auditoria
    area: str = config.NOME_AREA_PADRAO


# ============================================================
# CLASSIFICADOR DIVIDIDO ENTRE VÁRIAS ÁREAS
# ============================================================
#
# Com várias câmeras, cada área tem a sua thread de análise, mas o
# modelo de EPI é carregado UMA vez (ocupa bastante memória e demora
# para abrir). Esta "capa" deixa só uma thread usá-lo por vez: as outras
# esperam a vez, em vez de chamarem o modelo ao mesmo tempo.
# ============================================================

class ClassificadorCompartilhado:

    def __init__(self, classificador):

        self._classificador = classificador
        self._trava = threading.Lock()

        # O resto do programa lê estes dois como no classificador original
        self.por_epi = classificador.por_epi
        self.epis = classificador.epis

    def classificar_lote(self, recortes):

        with self._trava:
            return self._classificador.classificar_lote(recortes)


class Analisador:

    def __init__(self, camera, detectores, classificador, auditoria, parametros):
        """
        detectores -> um detector por modo de detecção: {modo: detector}.
                      Ficam todos carregados, para a troca de modo na
                      tela ser imediata.
        """

        self._camera = camera
        self._detectores = detectores

        # Modo em uso no último ciclo (None = ainda não começou)
        self._modo_em_uso = None
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

        # Mensagem do último erro da análise (None = tudo certo). Lida
        # pela interface; trocada inteira de uma vez (seguro entre threads).
        self.erro = None

        # True enquanto a análise espera para recomeçar depois de um erro
        self.reiniciando = False

        # Quantas vezes a análise já recomeçou sozinha desde que abriu
        self.reinicios = 0

        self._parar = threading.Event()
        self._thread = None

        # Levantado por reiniciar_pessoas() e atendido pela thread de análise
        self._pedido_de_reinicio = threading.Event()

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

    def reiniciar_pessoas(self):
        """
        Faz o sistema esquecer todas as pessoas que está acompanhando.

        Usado quando a auditoria é zerada: quem está na imagem passa a
        contar como pessoa nova e volta a gerar um evento de ENTRADA,
        em vez de ficar sem registro no log recém-esvaziado.

        Pode ser chamado de outra thread: só levanta um aviso, e quem
        de fato esquece as pessoas é a própria thread de análise, no
        começo do ciclo seguinte.
        """

        self._pedido_de_reinicio.set()

    def estado(self) -> EstadoCena:
        """Último resultado publicado (seguro para ler de outra thread)."""

        with self._trava:
            return self._estado

    # ============================================================
    # LAÇO PRINCIPAL
    # ============================================================

    def _executar(self):
        """
        Roda a análise e, se ela quebrar, recomeça sozinha (o "vigia").

            falhou  -> guarda o erro no log e na tela, espera
                       ESPERA_REINICIO_ANALISE_SEG e tenta de novo;
            de novo -> conta as falhas SEGUIDAS; passou de
                       MAXIMO_REINICIOS_ANALISE, desiste (o erro fica na
                       tela até o programa ser reaberto).

        Uma análise que rodou bem por TEMPO_ESTAVEL_ANALISE_SEG antes de
        falhar zera a contagem: é um problema novo, não o mesmo de antes.
        """

        falhas_seguidas = 0

        while not self._parar.is_set():

            inicio = time.perf_counter()

            try:
                self._laco()
                return   # parou porque pediram (parar())

            except Exception as erro:

                if time.perf_counter() - inicio >= config.TEMPO_ESTAVEL_ANALISE_SEG:
                    falhas_seguidas = 0

                falhas_seguidas += 1

                descricao = f"{type(erro).__name__}: {erro}"

                log.exception(
                    "Erro na análise da área %s (falha seguida %d de %d)",
                    self._parametros.area,
                    falhas_seguidas,
                    config.MAXIMO_REINICIOS_ANALISE,
                )

                # A tela não fica mostrando caixas velhas enquanto isso
                self._publicar(EstadoCena(modo=self._parametros.modo_deteccao, area=self._parametros.area))

                if falhas_seguidas > config.MAXIMO_REINICIOS_ANALISE:

                    self.reiniciando = False
                    self.erro = (
                        f"{descricao}. A análise parou depois de {config.MAXIMO_REINICIOS_ANALISE} "
                        "tentativas seguidas (detalhes em logs/safetech.log)."
                    )

                    log.error("Análise da área %s desistiu de recomeçar", self._parametros.area)
                    return

                self.erro = descricao
                self.reiniciando = True

                if self._parar.wait(config.ESPERA_REINICIO_ANALISE_SEG):
                    return

                # Recomeça do zero: sem pessoas lembradas de antes do erro
                self._rastreador = RastreadorPessoas()
                self._modo_em_uso = None
                self._ultima_classificacao = 0.0

                self.reinicios += 1
                self.reiniciando = False
                self.erro = None

                log.warning("Análise da área %s recomeçou (reinício nº %d)", self._parametros.area, self.reinicios)

    def _laco(self):

        periodo_minimo = 1.0 / config.TAXA_MAXIMA_ANALISE_HZ

        ultimo_numero_frame = -1

        ciclos_no_periodo = 0
        inicio_periodo = time.perf_counter()
        analises_por_segundo = 0.0

        while not self._parar.is_set():

            inicio_ciclo = time.perf_counter()

            # Pedido para esquecer todo mundo (a auditoria foi zerada)
            if self._pedido_de_reinicio.is_set():

                self._pedido_de_reinicio.clear()

                # Rastreador novo: além de esquecer as pessoas, a
                # numeração recomeça em P001.
                self._rastreador = RastreadorPessoas()

            frame, numero_frame = self._camera.ler()

            # ------------------------------------------------------
            # Câmera desligada: esquece as pessoas e espera
            # ------------------------------------------------------

            if frame is None:

                self._rastreador.limpar()
                self._publicar(EstadoCena(modo=self._parametros.modo_deteccao, area=self._parametros.area))

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

            caixas = self._detector_do_modo().detectar(frame)

            rastros = self._rastreador.atualizar(caixas, inicio_ciclo)

            # O setor e os EPIs exigidos são lidos UMA vez por ciclo,
            # para a decisão e a auditoria usarem exatamente os mesmos
            # valores mesmo que o usuário mude a seleção no meio.
            setor = self._parametros.setor
            exigidos = self._exigidos()

            # ------------------------------------------------------
            # 3) CLASSIFICAR,  4) DECIDIR  e  5) AUDITAR
            # ------------------------------------------------------

            if self._hora_de_classificar(rastros, inicio_ciclo):

                self._classificar(frame, rastros)
                self._auditar_mudancas(frame, rastros, setor, exigidos)

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

            # O rastreador lembra por alguns segundos de quem sumiu (para
            # reconhecer a pessoa quando ela voltar), mas na tela só
            # aparece quem foi visto há bem pouco tempo.
            na_tela = [
                rastro
                for rastro in rastros
                if inicio_ciclo - rastro.ultimo_visto <= config.TEMPO_MAXIMO_AUSENTE_SEG
            ]

            self._publicar(
                self._montar_estado(na_tela, setor, exigidos, analises_por_segundo)
            )

            # Não analisa mais rápido do que o necessário
            sobra = periodo_minimo - (time.perf_counter() - inicio_ciclo)

            if sobra > 0:
                self._parar.wait(sobra)

    # ============================================================
    # 1) DETECÇÃO: ROSTO OU CORPO
    # ============================================================

    def _detector_do_modo(self):
        """
        Devolve o detector do modo escolhido na tela.

        Quando o modo muda, o rastreador recomeça do zero: a caixa de
        um rosto e a caixa de um corpo inteiro têm tamanhos muito
        diferentes, então não dá para dizer que uma é "a mesma pessoa"
        da outra. Quem está na imagem passa a contar como pessoa nova.
        """

        modo = self._parametros.modo_deteccao

        # Modo pedido sem detector carregado (modelo ausente): continua
        # no que já estava em uso, ou no primeiro que existir.
        if modo not in self._detectores:
            modo = self._modo_em_uso or next(iter(self._detectores))

        if modo != self._modo_em_uso:

            self._modo_em_uso = modo
            self._rastreador = RastreadorPessoas()

        return self._detectores[modo]

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
        """
        Classifica todas as pessoas visíveis numa única chamada ao modelo.

        O modelo sempre avalia TODOS os EPIs que conhece; quais deles
        são obrigatórios é decidido depois, na etapa de decisão. Por
        isso trocar de setor tem efeito imediato, sem reclassificar.
        """

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

    def _exigidos(self):
        """EPIs obrigatórios agora, conforme o setor escolhido na tela."""

        # O modelo antigo só conhece o "conjunto completo": nesse modo
        # a seleção por equipamento não tem como ser aplicada.
        if not self._classificador.por_epi:
            return (config.EPI_CONJUNTO,)

        return tuple(self._parametros.exigidos)

    def _avaliar(self, rastro, exigidos):

        return decisao.avaliar_pessoa(
            rastro.historico,
            self._classificador.epis,
            exigidos,
            self._parametros.limiar_confianca,
        )

    def _observar(self, rastro, exigidos) -> PessoaObservada:
        """Retrato imutável de uma pessoa, com a decisão do momento."""

        status, itens, faltando = self._avaliar(rastro, exigidos)

        return PessoaObservada(
            identificador=rastro.identificador,
            caixa=rastro.caixa,
            status=status,
            itens=itens,
            faltando=faltando,
        )

    def _montar_estado(self, rastros, setor, exigidos, analises_por_segundo) -> EstadoCena:

        pessoas = tuple(self._observar(rastro, exigidos) for rastro in rastros)

        return EstadoCena(
            pessoas=pessoas,
            acesso=decisao.avaliar_acesso(pessoa.status for pessoa in pessoas),
            setor=setor,
            exigidos=exigidos,
            analises_por_segundo=analises_por_segundo,
            # O modo em uso de fato (o pedido na tela pode não ter
            # detector carregado: veja _detector_do_modo)
            modo=self._modo_em_uso or self._parametros.modo_deteccao,
            area=self._parametros.area,
        )

    # ============================================================
    # 5) AUDITORIA
    # ============================================================

    def _auditar_mudancas(self, frame, rastros, setor, exigidos):
        """
        Grava um evento (com UMA foto de evidência) só em dois casos:

            ENTRADA -> primeira decisão sobre uma pessoa nova;
            MUDANCA -> a decisão dessa pessoa mudou de verdade
                       (liberado <-> negado).

        Enquanto a pessoa continua na mesma situação, nada é gravado,
        por mais tempo que ela fique na imagem.
        """

        for rastro in rastros:

            if not rastro.visivel:
                continue

            pessoa = self._observar(rastro, exigidos)

            if pessoa.status is StatusPessoa.ANALISANDO:
                continue

            liberado = pessoa.status is StatusPessoa.LIBERADO

            if liberado == rastro.decisao_registrada:

                # Voltou a concordar: a discordância era passageira
                rastro.confirmacoes_de_mudanca = 0
                continue

            if rastro.decisao_registrada is None:

                evento = modulo_auditoria.EVENTO_ENTRADA

            else:

                # Uma mudança só vale depois de se repetir em várias
                # classificações seguidas. Sem isso, um único resultado
                # diferente geraria um evento e uma foto a mais.
                rastro.confirmacoes_de_mudanca += 1

                if rastro.confirmacoes_de_mudanca < config.CONFIRMACOES_PARA_MUDANCA:
                    continue

                evento = modulo_auditoria.EVENTO_MUDANCA

            rastro.confirmacoes_de_mudanca = 0

            # Foto de evidência: o frame inteiro (contexto) com a
            # pessoa em questão destacada. É uma CÓPIA, porque o
            # frame original é compartilhado com a interface.
            evidencia = anotacao.desenhar_pessoas(frame.copy(), [pessoa], modo=self._modo_em_uso)

            if config.CARIMBAR_EVIDENCIA:
                anotacao.carimbar(evidencia, self._texto_do_carimbo(rastro.identificador, liberado))

            registro = self._auditoria.registrar(
                evento=evento,
                identificador_pessoa=rastro.identificador,
                setor=setor,
                exigidos=exigidos,
                itens=pessoa.itens,
                faltando=pessoa.faltando,
                liberado=liberado,
                imagem_bgr=evidencia,
                modo=self._modo_em_uso,
                area=self._parametros.area,
            )

            rastro.decisao_registrada = liberado

            self.registros_novos.put(registro)

    def _texto_do_carimbo(self, identificador, liberado) -> str:
        """
        Texto gravado na foto de evidência, ex.:
        "SafeTech Entry | 2026-11-24 14:10:32 | Area: Portaria | P003 | Negado"
        """

        resultado = modos.resultado(self._modo_em_uso, liberado)

        agora = horario.agora_iso()

        partes = [
            config.NOME_PRODUTO,
            # Data e hora com o fuso, ex.: 2026-11-25 09:18:51 UTC-03:00
            f"{horario.para_exibir(agora)} UTC{horario.fuso(agora)}",
            f"Area: {self._parametros.area}",
            f"P{identificador:03d}",
            resultado,
        ]

        return anotacao.sem_acentos(" | ".join(partes))

    # ============================================================
    # 6) PUBLICAÇÃO
    # ============================================================

    def _publicar(self, estado):

        with self._trava:
            self._estado = estado
