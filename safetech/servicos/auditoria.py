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

E guarda o MODO de operação ("catraca" ou "vigilancia"): na catraca o
resultado é lido como liberado/negado; na vigilância, como conforme/
não conforme. A coluna "liberado" (SIM/NAO) vale para os dois.

E a ÁREA (câmera) onde o evento aconteceu: com várias câmeras, a
auditoria continua uma só, e cada linha diz de onde veio.
"""

import csv
import threading
from datetime import datetime

import cv2

from safetech import config
from safetech.nucleo import horario, modos
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
    "modo",
    "area",
]

# Colunas de versões anteriores. Um log nesses formatos é CONVERTIDO
# para o atual, preenchendo as colunas que faltam com os valores
# abaixo (o arquivo original fica guardado, intacto):
#
#   sem "modo" e "area" -> modo "catraca" (o único sentido que existia)
#   sem "area"          -> área "Principal" (havia uma câmera só)
COLUNAS_SEM_MODO = COLUNAS[:-2]
COLUNAS_SEM_AREA = COLUNAS[:-1]

VALORES_PARA_COLUNAS_NOVAS = {
    "modo": config.MODO_CATRACA,
    "area": config.NOME_AREA_PADRAO,
}

# Log das linhas excluídas: as mesmas colunas e a data da exclusão
COLUNAS_EXCLUIDOS = COLUNAS + ["excluido_em"]

EVENTO_ENTRADA = "ENTRADA"
EVENTO_MUDANCA = "MUDANCA"


class ServicoAuditoria:

    def __init__(
        self,
        arquivo_log=config.ARQUIVO_LOG_AUDITORIA,
        pasta_imagens=config.PASTA_IMAGENS_AUDITORIA,
        pasta_excluidos=config.PASTA_EXCLUIDOS,
    ):

        self._arquivo_log = arquivo_log
        self._pasta_imagens = pasta_imagens
        self._pasta_excluidos = pasta_excluidos

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
        #
        # Se for só a versão sem a coluna "modo", os eventos são
        # COPIADOS para o log novo (com o modo "catraca"): o histórico
        # continua aparecendo na tela, e o arquivo original fica
        # guardado intacto.
        if self._arquivo_log.exists():

            cabecalho = _ler_cabecalho(self._arquivo_log)

            if cabecalho in (COLUNAS_SEM_MODO, COLUNAS_SEM_AREA):

                antigo = _renomear_formato_antigo(self._arquivo_log)

                self._copiar_formato_anterior(antigo, cabecalho)

            elif cabecalho != COLUNAS:

                _renomear_formato_antigo(self._arquivo_log)

        # O log dos excluídos segue a mesma regra (sem copiar: ele não
        # aparece na tela)
        log_excluidos = self._pasta_excluidos / "log_excluidos.csv"

        if log_excluidos.exists() and _ler_cabecalho(log_excluidos) != COLUNAS_EXCLUIDOS:
            _renomear_formato_antigo(log_excluidos)

        if not self._arquivo_log.exists():

            with open(self._arquivo_log, "w", newline="", encoding="utf-8") as arquivo:
                csv.writer(arquivo).writerow(COLUNAS)

    def _copiar_formato_anterior(self, antigo, cabecalho):
        """
        Cria o log atual com os eventos de um log de versão anterior,
        que tinha só as primeiras colunas de COLUNAS. As que faltam
        recebem os valores de VALORES_PARA_COLUNAS_NOVAS.
        """

        complemento = [VALORES_PARA_COLUNAS_NOVAS[coluna] for coluna in COLUNAS[len(cabecalho):]]

        with open(antigo, "r", newline="", encoding="utf-8", errors="replace") as origem:

            leitor = csv.reader(origem)

            next(leitor, None)  # cabeçalho antigo

            linhas = [
                linha + complemento
                for linha in leitor
                if len(linha) == len(cabecalho)
            ]

        with open(self._arquivo_log, "w", newline="", encoding="utf-8") as destino:

            escritor = csv.writer(destino)

            escritor.writerow(COLUNAS)
            escritor.writerows(linhas)

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
        modo=config.MODO_CATRACA,
        area=config.NOME_AREA_PADRAO,
    ) -> RegistroAuditoria:
        """
        Grava um evento no CSV (e a foto de evidência, se houver).

        exigidos / faltando -> chaves dos EPIs, ex.: ("capacete", "luvas")
        itens               -> ResultadoEPI de cada EPI avaliado
        liberado            -> True se a pessoa estava com tudo o que o
                               setor exige
        modo                -> "catraca" ou "vigilancia"
        area                -> nome da área (câmera) do evento
        """

        agora = horario.agora()

        nome_imagem = ""

        if imagem_bgr is not None:

            nome_imagem = (
                f"{agora.strftime('%Y%m%d_%H%M%S_%f')}"
                f"_P{identificador_pessoa:03d}.jpg"
            )

        registro = RegistroAuditoria(
            # ISO 8601 com o fuso, ex.: 2026-11-25T09:18:51-03:00
            timestamp=agora.isoformat(timespec="seconds"),
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
            modo=modos.modo_valido(modo),
            area=area or config.NOME_AREA_PADRAO,
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

            base = self._arquivo_log.parent / "arquivados" / datetime.now().strftime("%Y-%m-%d_%H-%M-%S")

            # Duas vezes "Zerar" no mesmo segundo: a segunda pasta
            # ganha um número, para não esbarrar na primeira.
            destino = base
            numero = 2

            while destino.exists():
                destino = base.with_name(f"{base.name}_{numero}")
                numero += 1

            (destino / "imagens").mkdir(parents=True, exist_ok=True)

            self._arquivo_log.rename(destino / self._arquivo_log.name)

            for foto in fotos:
                foto.rename(destino / "imagens" / foto.name)

            # Log novo, vazio, só com o cabeçalho
            with open(self._arquivo_log, "w", newline="", encoding="utf-8") as arquivo:
                csv.writer(arquivo).writerow(COLUNAS)

        return destino, eventos, len(fotos)

    # ============================================================
    # EXCLUIR UMA LINHA (movendo para "excluidos", sem apagar)
    # ============================================================

    def excluir(self, registro: RegistroAuditoria) -> bool:
        """
        Tira um evento do log de auditoria.

        Assim como o "Zerar", nada é apagado de verdade:

            - a linha sai do log principal e vai para
              "excluidos/log_excluidos.csv", com a data da exclusão;
            - a foto de evidência é MOVIDA para "excluidos/imagens".

        Assim um evento registrado por engano some da tabela, mas
        continua existindo para quem precisar conferir depois.

        Devolve True se a linha foi encontrada e excluída. Pode lançar
        OSError (ex.: o CSV está aberto no Excel); nesse caso o log
        principal fica como estava.
        """

        linha_procurada = registro.como_linha()

        with self._trava:

            with open(self._arquivo_log, "r", newline="", encoding="utf-8", errors="replace") as arquivo:
                linhas = list(csv.reader(arquivo))

            # linhas[0] é o cabeçalho; procura a partir da primeira linha de dados
            posicao = next(
                (
                    indice
                    for indice, linha in enumerate(linhas[1:], start=1)
                    if linha == linha_procurada
                ),
                None,
            )

            if posicao is None:
                return False

            del linhas[posicao]

            # O log novo é escrito num arquivo temporário e só depois
            # troca de lugar com o antigo. Se algo falhar no meio, o
            # log original continua inteiro.
            temporario = self._arquivo_log.with_suffix(".tmp")

            try:

                with open(temporario, "w", newline="", encoding="utf-8") as arquivo:
                    csv.writer(arquivo).writerows(linhas)

                temporario.replace(self._arquivo_log)

            finally:

                if temporario.exists():
                    temporario.unlink()

            # Daqui em diante a linha já saiu do log: guarda a cópia
            pasta_excluidos = self._pasta_excluidos
            (pasta_excluidos / "imagens").mkdir(parents=True, exist_ok=True)

            log_excluidos = pasta_excluidos / "log_excluidos.csv"
            novo = not log_excluidos.exists()

            with open(log_excluidos, "a", newline="", encoding="utf-8") as arquivo:

                escritor = csv.writer(arquivo)

                if novo:
                    escritor.writerow(COLUNAS_EXCLUIDOS)

                escritor.writerow(
                    linha_procurada + [horario.agora_iso()]
                )

            foto = self._pasta_imagens / registro.imagem if registro.imagem else None

            if foto is not None and foto.exists():

                try:
                    foto.rename(pasta_excluidos / "imagens" / foto.name)

                except OSError:

                    # Foto aberta em outro programa: ela fica onde está.
                    # A linha já foi excluída e continua registrada.
                    pass

        return True

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


# ============================================================
# EXPORTAÇÃO (planilha para o Excel)
# ============================================================
#
# O log interno usa chaves curtas ("SIM"/"NAO", "vigilancia") e vírgula
# como separador. A exportação é para PESSOAS: cabeçalhos por extenso,
# resultado no texto do modo ("Liberado", "Não conforme") e o formato
# que o Excel em português abre direto (veja SEPARADOR_CSV_EXPORTACAO).
# O log original nunca é alterado: só se gera uma cópia legível.
# ============================================================

# (título da coluna, como obter o valor do registro)
COLUNAS_EXPORTACAO = [
    ("Data e hora", lambda r: horario.para_exibir(r.timestamp)),
    ("Área", lambda r: r.area),
    ("Modo", lambda r: modos.nome_do_modo(r.modo)),
    ("Evento", lambda r: "Entrada" if r.evento == EVENTO_ENTRADA else "Mudança"),
    ("Pessoa", lambda r: r.pessoa),
    ("Setor", lambda r: r.setor),
    ("EPIs exigidos", lambda r: r.exigidos),
    ("Faltando", lambda r: r.faltando),
    ("Resultado", lambda r: modos.resultado(r.modo, r.liberado == "SIM")),
    ("Confiança", lambda r: r.confiancas),
    ("Foto", lambda r: r.imagem),
    # Fuso da "Data e hora" (ex.: -03:00); vazio nos eventos antigos, sem fuso
    ("Fuso (UTC)", lambda r: horario.fuso(r.timestamp)),
]


def gerar_csv_exportacao(registros) -> str:
    """Texto da planilha de exportação (cabeçalho + uma linha por registro)."""

    import io

    saida = io.StringIO()

    escritor = csv.writer(saida, delimiter=config.SEPARADOR_CSV_EXPORTACAO, lineterminator="\r\n")

    escritor.writerow([titulo for titulo, _ in COLUNAS_EXPORTACAO])

    for registro in registros:
        escritor.writerow([valor(registro) for _, valor in COLUNAS_EXPORTACAO])

    return saida.getvalue()


def exportar_csv(registros, caminho):
    """Grava a planilha de exportação em 'caminho'. Pode lançar OSError (ex.: arquivo aberto no Excel)."""

    with open(caminho, "w", newline="", encoding=config.CODIFICACAO_CSV_EXPORTACAO) as arquivo:
        arquivo.write(gerar_csv_exportacao(registros))


# ============================================================
# FUNÇÕES DE APOIO
# ============================================================

def _ler_cabecalho(caminho):
    """A primeira linha do CSV (ou None se o arquivo estiver vazio)."""

    with open(caminho, "r", newline="", encoding="utf-8", errors="replace") as arquivo:
        return next(csv.reader(arquivo), None)


def _renomear_formato_antigo(caminho):
    """
    Renomeia um CSV de formato antigo (nunca apaga) e devolve o novo
    caminho: log_auditoria.csv -> log_auditoria_formato_antigo_<data>.csv
    """

    sufixo = datetime.now().strftime("%Y%m%d_%H%M%S")

    novo = caminho.with_name(f"{caminho.stem}_formato_antigo_{sufixo}{caminho.suffix}")

    caminho.rename(novo)

    return novo
