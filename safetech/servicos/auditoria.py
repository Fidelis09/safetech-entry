"""
Serviço de auditoria.

Mantém o log em CSV (auditoria/log_auditoria.csv) e as fotos de
evidência (auditoria/imagens).

O log registra EVENTOS, não cada análise da IA:

    ENTRADA  -> primeira decisão sobre uma pessoa que apareceu
    MUDANCA  -> a decisão dessa pessoa mudou (negado -> liberado ou o contrário)

Assim o histórico fica legível (uma linha por acontecimento relevante)
e cada linha tem a foto do momento exato da decisão.

Cada linha guarda também o SETOR fiscalizado, os EPIs que ele exigia e
quais deles estavam faltando: dá para saber não só que o acesso foi
negado, mas por quê.
"""

import csv
import threading
from datetime import datetime

import cv2

from safetech import config
from safetech.nucleo.epis import nome_do_epi, nomes_dos_epis
from safetech.nucleo.tipos import RegistroAuditoria


COLUNAS = [
    "timestamp",
    "evento",
    "pessoa",
    "setor",
    "exigidos",
    "faltando",
    "confiancas",
    "liberado",
    "imagem",
]

EVENTO_ENTRADA = "ENTRADA"
EVENTO_MUDANCA = "MUDANCA"


class ServicoAuditoria:

    def __init__(
        self,
        arquivo_log=config.ARQUIVO_LOG_AUDITORIA,
        pasta_imagens=config.PASTA_IMAGENS_AUDITORIA,
    ):

        self._arquivo_log = arquivo_log
        self._pasta_imagens = pasta_imagens

        # O registro é chamado pela thread de análise e a leitura pela
        # interface; a trava impede que as duas mexam no arquivo juntas.
        self._trava = threading.Lock()

        self._preparar_arquivos()

    @property
    def pasta_imagens(self):
        return self._pasta_imagens

    # ============================================================
    # PREPARAÇÃO
    # ============================================================

    def _preparar_arquivos(self):

        self._arquivo_log.parent.mkdir(parents=True, exist_ok=True)
        self._pasta_imagens.mkdir(parents=True, exist_ok=True)

        # Um log criado por uma versão anterior do programa tem colunas
        # diferentes. Ele é RENOMEADO (nunca apagado) e um log novo é
        # iniciado no formato atual.
        if self._arquivo_log.exists() and not self._cabecalho_atual():

            sufixo = datetime.now().strftime("%Y%m%d_%H%M%S")

            self._arquivo_log.rename(
                self._arquivo_log.with_name(
                    f"{self._arquivo_log.stem}_formato_antigo_{sufixo}"
                    f"{self._arquivo_log.suffix}"
                )
            )

        if not self._arquivo_log.exists():

            with open(self._arquivo_log, "w", newline="", encoding="utf-8") as arquivo:
                csv.writer(arquivo).writerow(COLUNAS)

    def _cabecalho_atual(self) -> bool:
        """True se a primeira linha do CSV é o cabeçalho deste formato."""

        with open(self._arquivo_log, "r", newline="", encoding="utf-8", errors="replace") as arquivo:
            primeira_linha = next(csv.reader(arquivo), None)

        return primeira_linha == COLUNAS

    # ============================================================
    # GRAVAÇÃO
    # ============================================================

    def registrar(
        self,
        evento,
        identificador_pessoa,
        setor,
        exigidos,
        itens,
        faltando,
        liberado,
        imagem_bgr=None,
    ) -> RegistroAuditoria:
        """
        Grava um evento no CSV (e a foto de evidência, se houver).

        exigidos / faltando -> chaves dos EPIs, ex.: ("capacete", "luvas")
        itens               -> ResultadoEPI de cada EPI avaliado
        """

        agora = datetime.now()

        nome_imagem = ""

        if imagem_bgr is not None:

            nome_imagem = (
                f"{agora.strftime('%Y%m%d_%H%M%S_%f')}"
                f"_P{identificador_pessoa:03d}.jpg"
            )

        registro = RegistroAuditoria(
            timestamp=agora.strftime("%Y-%m-%d %H:%M:%S"),
            evento=evento,
            pessoa=f"P{identificador_pessoa:03d}",
            setor=setor,
            # No CSV vão os nomes legíveis, não as chaves internas
            exigidos=nomes_dos_epis(exigidos),
            faltando=nomes_dos_epis(faltando),
            confiancas=", ".join(
                f"{nome_do_epi(item.chave)} {item.confianca * 100:.0f}%"
                for item in itens
            ),
            liberado="SIM" if liberado else "NAO",
            imagem=nome_imagem,
        )

        # A foto e a linha do CSV são gravadas juntas, dentro da trava:
        # assim o botão "Zerar" nunca pega um evento pela metade (a
        # foto de um lado e a linha do outro).
        with self._trava:

            if nome_imagem:
                cv2.imwrite(str(self._pasta_imagens / nome_imagem), imagem_bgr)

            with open(self._arquivo_log, "a", newline="", encoding="utf-8") as arquivo:
                csv.writer(arquivo).writerow(registro.como_linha())

        return registro

    # ============================================================
    # ZERAR (arquivando, sem apagar)
    # ============================================================

    def zerar(self):
        """
        Esvazia o log e a pasta de fotos, deixando tudo pronto para
        começar do zero.

        Nada é apagado: o log e as fotos são MOVIDOS para uma pasta
        "arquivados/<data e hora>", dentro da pasta de auditoria. Um
        registro de auditoria não deve sumir por um clique; se o
        arquivo não interessar, a pasta pode ser excluída à mão.

        Devolve (pasta_do_arquivo, eventos, fotos); a pasta é None se
        não havia nada para arquivar.
        """

        with self._trava:

            eventos = self._contar_eventos()

            fotos = [caminho for caminho in self._pasta_imagens.iterdir() if caminho.is_file()]

            if eventos == 0 and not fotos:
                return None, 0, 0

            destino = (
                self._arquivo_log.parent
                / "arquivados"
                / datetime.now().strftime("%Y-%m-%d_%H-%M-%S")
            )

            (destino / "imagens").mkdir(parents=True, exist_ok=True)

            self._arquivo_log.rename(destino / self._arquivo_log.name)

            for foto in fotos:
                foto.rename(destino / "imagens" / foto.name)

            # Log novo, vazio, só com o cabeçalho
            with open(self._arquivo_log, "w", newline="", encoding="utf-8") as arquivo:
                csv.writer(arquivo).writerow(COLUNAS)

        return destino, eventos, len(fotos)

    def _contar_eventos(self) -> int:
        """Linhas de evento no CSV (sem o cabeçalho). Chamar dentro da trava."""

        with open(self._arquivo_log, "r", newline="", encoding="utf-8", errors="replace") as arquivo:
            return max(0, sum(1 for _ in csv.reader(arquivo)) - 1)

    # ============================================================
    # LEITURA
    # ============================================================

    def carregar_historico(self) -> list[RegistroAuditoria]:
        """Lê o CSV inteiro, do registro mais antigo para o mais recente."""

        registros = []

        with self._trava:

            with open(self._arquivo_log, "r", newline="", encoding="utf-8", errors="replace") as arquivo:

                leitor = csv.reader(arquivo)

                next(leitor, None)  # pula o cabeçalho

                for linha in leitor:

                    # Ignora linhas incompletas (ex.: arquivo editado à mão)
                    if len(linha) == len(COLUNAS):
                        registros.append(RegistroAuditoria(*linha))

        return registros
