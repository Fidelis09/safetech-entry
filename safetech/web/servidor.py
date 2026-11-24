"""
Servidor do painel web do gerente.

Roda em uma thread própria, dentro do aplicativo, e entrega:

    /                 -> a página do painel
    /api/ao-vivo      -> status atual da catraca e das pessoas (JSON)
    /api/historico    -> totais, eventos por hora e lista de eventos (JSON)
    /api/areas        -> situação de cada área (câmera), para a visão geral
    /ao-vivo.jpg      -> imagem atual da câmera, com as caixas desenhadas
                         (?area=N: a imagem da área N da lista de /api/areas)
    /imagens/<nome>   -> foto de evidência de um evento
    /exportar.csv     -> o histórico inteiro numa planilha (download)

SOMENTE LEITURA: o servidor só aceita pedidos GET. Qualquer outro
método (POST, PUT, DELETE...) é recusado, e nenhuma rota altera
configurações, apaga registros ou controla a câmera.
"""

import base64
import hashlib
import json
import socket
import threading
from dataclasses import asdict
from datetime import datetime
from http import HTTPStatus
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from urllib.parse import parse_qs, unquote, urlsplit

import cv2

from safetech import config
from safetech.nucleo import anotacao, modos
from safetech.nucleo.epis import nome_do_epi
from safetech.nucleo.tipos import EstadoCena, StatusPessoa
from safetech.servicos import acesso_web
from safetech.servicos.auditoria import gerar_csv_exportacao


ARQUIVO_PAGINA = Path(__file__).resolve().parent / "painel.html"


class ServidorWeb:

    def __init__(
        self,
        auditoria,
        fonte_ao_vivo=None,
        host=None,
        porta=None,
        fonte_areas=None,
        ajustes=None,
    ):
        """
        auditoria      -> ServicoAuditoria, de onde vêm os eventos e as fotos
        fonte_ao_vivo  -> função que devolve (frame, EstadoCena) do momento;
                          None quando não há câmera (painel só com histórico)
        fonte_areas    -> função que devolve TODAS as áreas, como lista de
                          (nome, frame, EstadoCena, comanda_catraca); None
                          sem o aplicativo
        ajustes        -> AjustesPainelWeb (porta, rede, usuário, hash da
                          senha), da tela de Configurações; None = config.py
        host, porta    -> trocam os dos ajustes (usado nos testes)
        """

        self._auditoria = auditoria
        self._fonte_ao_vivo = fonte_ao_vivo
        self._fonte_areas = fonte_areas

        self._ajustes = ajustes or acesso_web.ajustes_padrao()

        self._host = host or self._ajustes.host
        self._porta = porta or self._ajustes.porta

        # Logins já conferidos (só o resumo do cabeçalho, nunca a senha).
        # Conferir a senha é lento de propósito (veja acesso_web), e o
        # navegador manda o login a cada pedido, várias vezes por segundo.
        self._logins_aceitos = set()

        self._servidor = None
        self._thread = None

    # ============================================================
    # CONTROLE
    # ============================================================

    def iniciar(self):
        """Abre a porta e começa a atender. Lança OSError se a porta estiver ocupada."""

        # A classe que atende os pedidos precisa enxergar este objeto;
        # isso é feito criando uma subclasse com a referência embutida.
        tratador = type("Tratador", (_TratadorPainel,), {"painel": self})

        self._servidor = ThreadingHTTPServer((self._host, self._porta), tratador)

        # Threads de atendimento não impedem o programa de fechar
        self._servidor.daemon_threads = True

        self._thread = threading.Thread(
            target=self._servidor.serve_forever,
            name="painel-web",
            daemon=True,
        )

        self._thread.start()

    def parar(self):

        if self._servidor is not None:

            self._servidor.shutdown()
            self._servidor.server_close()

            self._servidor = None

    def autoriza(self, cabecalho) -> bool:
        """
        Confere o cabeçalho "Authorization: Basic ..." de um pedido.

        Chamado pelas threads de atendimento; o conjunto de logins
        aceitos só cresce, então ler e acrescentar sem trava é seguro.
        """

        if not self._ajustes.exige_login:
            return True

        if not cabecalho.startswith("Basic "):
            return False

        marca = hashlib.sha256(cabecalho.encode("utf-8")).digest()

        if marca in self._logins_aceitos:
            return True

        try:
            recebido = base64.b64decode(cabecalho[6:], validate=True).decode("utf-8")
        except ValueError:
            return False

        usuario, separador, senha = recebido.partition(":")

        if not separador or usuario != self._ajustes.usuario:
            return False

        if not acesso_web.senha_confere(senha, self._ajustes.hash_senha):
            return False

        self._logins_aceitos.add(marca)

        return True

    @property
    def porta(self) -> int:
        return self._porta

    def endereco(self) -> str:
        """Endereço para abrir o painel no navegador."""

        if self._host in ("127.0.0.1", "localhost"):
            return f"http://localhost:{self._porta}"

        return f"http://{_ip_na_rede()}:{self._porta}"

    # ============================================================
    # DADOS ENTREGUES AO PAINEL
    # ============================================================

    def dados_ao_vivo(self) -> dict:
        """Status do momento: a câmera está ligada? quem está na imagem?"""

        frame, estado = self._ler_ao_vivo()

        textos = modos.textos(estado.modo)

        # Título da faixa já no texto do modo, para a página não
        # precisar saber o que é "liberado" na catraca ou na vigilância
        titulos = {
            "liberado": textos["faixa_ok"],
            "negado": textos["faixa_irregular"],
            "analisando": "ANALISANDO",
            "sem_pessoas": "AGUARDANDO",
        }

        return {
            # False quando o painel roda sem o aplicativo (só histórico)
            "disponivel": self._fonte_ao_vivo is not None,
            "camera_ativa": frame is not None,
            "acesso": estado.acesso.value,
            # Modo de operação: "catraca" ou "vigilancia". A catraca
            # ESP32 (pelo Wi-Fi) fica fechada na vigilância.
            "modo": modos.modo_valido(estado.modo),
            # Área (câmera) mostrada: a que comanda a catraca, ou a primeira
            "area": estado.area,
            "nome_modo": modos.nome_do_modo(estado.modo),
            "titulo": titulos[estado.acesso.value],
            "lugar": textos["lugar"],
            # O que está sendo fiscalizado (o painel só mostra; quem
            # escolhe o setor é o operador, no aplicativo)
            "setor": estado.setor,
            "exigidos": [nome_do_epi(chave) for chave in estado.exigidos],
            "pessoas": [
                {
                    "identificador": pessoa.identificador,
                    "status": pessoa.status.value,
                    "faltando": [nome_do_epi(chave) for chave in pessoa.faltando],
                    "itens": [
                        {
                            "nome": nome_do_epi(item.chave),
                            "presente": item.presente,
                            "confianca": round(item.confianca * 100),
                        }
                        for item in pessoa.itens
                    ],
                }
                for pessoa in estado.pessoas
            ],
        }

    def dados_historico(self) -> dict:
        """Totais, eventos por hora de hoje e os eventos mais recentes."""

        registros = self._auditoria.carregar_historico()

        hoje = datetime.now().strftime("%Y-%m-%d")

        registros_hoje = [r for r in registros if r.timestamp.startswith(hoje)]

        # Uma posição por hora do dia (0h a 23h)
        por_hora = [{"hora": hora, "liberados": 0, "negados": 0} for hora in range(24)]

        for registro in registros_hoje:

            try:
                hora = int(registro.timestamp[11:13])
            except ValueError:
                continue

            chave = "liberados" if registro.liberado == "SIM" else "negados"

            por_hora[hora][chave] += 1

        # Mais recentes primeiro, limitado para a página não pesar
        recentes = registros[::-1][: config.PAINEL_WEB_MAXIMO_EVENTOS]

        return {
            "gerado_em": datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
            "hoje": _totalizar(registros_hoje),
            "geral": _totalizar(registros),
            "por_hora": por_hora,
            # Cada evento leva também o resultado já em texto, conforme o
            # modo em que aconteceu ("Liberado" ou "Conforme", por exemplo)
            "eventos": [
                {
                    **asdict(registro),
                    "resultado": modos.resultado(registro.modo, registro.liberado == "SIM"),
                    "nome_modo": modos.nome_do_modo(registro.modo),
                }
                for registro in recentes
            ],
        }

    def dados_areas(self) -> list:
        """
        Situação de cada área, na ordem das abas do aplicativo.

        É o resumo da visão geral: o detalhe de cada pessoa fica no
        /api/ao-vivo (da área que comanda a catraca).
        """

        areas = []

        for indice, (nome, frame, estado, comanda_catraca) in enumerate(self._ler_areas()):

            textos = modos.textos(estado.modo)

            titulos = {
                "liberado": textos["faixa_ok"],
                "negado": textos["faixa_irregular"],
                "analisando": "ANALISANDO",
                "sem_pessoas": "AGUARDANDO",
            }

            camera_ativa = frame is not None

            areas.append({
                "indice": indice,
                "area": nome,
                "modo": modos.modo_valido(estado.modo),
                "nome_modo": modos.nome_do_modo(estado.modo),
                "camera_ativa": camera_ativa,
                "acesso": estado.acesso.value if camera_ativa else "camera_desligada",
                "titulo": titulos[estado.acesso.value] if camera_ativa else "CÂMERA DESLIGADA",
                "setor": estado.setor,
                "pessoas": len(estado.pessoas),
                "irregulares": sum(1 for pessoa in estado.pessoas if pessoa.status is StatusPessoa.NEGADO),
                "comanda_catraca": bool(comanda_catraca),
            })

        return areas

    def planilha_csv(self) -> bytes:
        """O histórico inteiro no formato de exportação (o mesmo do botão "Exportar CSV")."""

        texto = gerar_csv_exportacao(self._auditoria.carregar_historico())

        return texto.encode(config.CODIFICACAO_CSV_EXPORTACAO)

    def imagem_ao_vivo(self, indice_area=None):
        """
        Frame atual em JPEG, com as caixas desenhadas; None sem câmera.

        indice_area -> None = a área do "ao vivo" (a que comanda a
                       catraca); um número = aquela área da lista.
        """

        if indice_area is None:
            frame, estado = self._ler_ao_vivo()
        else:
            areas = self._ler_areas()

            if not 0 <= indice_area < len(areas):
                return None

            _, frame, estado, _ = areas[indice_area]

        if frame is None:
            return None

        # Cópia: o frame original é compartilhado com as outras threads
        imagem = anotacao.desenhar_pessoas(frame.copy(), estado.pessoas, modo=estado.modo)

        sucesso, dados = cv2.imencode(".jpg", imagem, [cv2.IMWRITE_JPEG_QUALITY, 80])

        return dados.tobytes() if sucesso else None

    def caminho_evidencia(self, nome):
        """
        Caminho de uma foto de evidência, ou None se não existir.

        Só o NOME do arquivo é aproveitado: assim um pedido malicioso
        como "/imagens/../../config.py" não consegue sair da pasta.
        """

        nome = Path(nome).name

        if not nome.lower().endswith(".jpg"):
            return None

        caminho = self._auditoria.pasta_imagens / nome

        return caminho if caminho.is_file() else None

    def _ler_ao_vivo(self):

        if self._fonte_ao_vivo is None:
            return None, EstadoCena()

        return self._fonte_ao_vivo()

    def _ler_areas(self):

        if self._fonte_areas is None:
            return []

        return self._fonte_areas()


# ============================================================
# ATENDIMENTO DOS PEDIDOS
# ============================================================

class _TratadorPainel(BaseHTTPRequestHandler):

    # Preenchido por ServidorWeb.iniciar()
    painel: ServidorWeb = None

    server_version = "SafeTechPainel"

    # ------------------------------------------------------
    # ÚNICO MÉTODO ACEITO: GET
    # ------------------------------------------------------

    def do_GET(self):

        if not self._autorizado():
            self._pedir_login()
            return

        partes = urlsplit(self.path)

        rota = unquote(partes.path)

        if rota == "/":
            self._enviar(ARQUIVO_PAGINA.read_bytes(), "text/html; charset=utf-8")

        elif rota == "/api/ao-vivo":
            self._enviar_json(self.painel.dados_ao_vivo())

        elif rota == "/api/historico":
            self._enviar_json(self.painel.dados_historico())

        elif rota == "/api/areas":
            self._enviar_json(self.painel.dados_areas())

        elif rota == "/exportar.csv":

            nome = f"auditoria_safetech_{datetime.now().strftime('%Y-%m-%d_%H-%M')}.csv"

            # "attachment": o navegador baixa o arquivo em vez de mostrar
            self._enviar(
                self.painel.planilha_csv(),
                "text/csv; charset=utf-8",
                extras={"Content-Disposition": f'attachment; filename="{nome}"'},
            )

        elif rota == "/ao-vivo.jpg":

            imagem = self.painel.imagem_ao_vivo(_numero_da_area(partes.query))

            if imagem is None:
                self.send_error(HTTPStatus.SERVICE_UNAVAILABLE, "Camera desligada")
            else:
                self._enviar(imagem, "image/jpeg")

        elif rota.startswith("/imagens/"):

            caminho = self.painel.caminho_evidencia(rota.removeprefix("/imagens/"))

            if caminho is None:
                self.send_error(HTTPStatus.NOT_FOUND)
            else:
                # Fotos de evidência nunca mudam: o navegador pode guardar
                self._enviar(caminho.read_bytes(), "image/jpeg", cache="max-age=86400")

        else:
            self.send_error(HTTPStatus.NOT_FOUND)

    # ------------------------------------------------------
    # TODO O RESTO É RECUSADO (painel somente leitura)
    # ------------------------------------------------------

    def _recusar(self):

        self.send_response(HTTPStatus.METHOD_NOT_ALLOWED)
        self.send_header("Allow", "GET")
        self.send_header("Content-Length", "0")
        self.end_headers()

    do_POST = do_PUT = do_DELETE = do_PATCH = do_OPTIONS = _recusar

    # ------------------------------------------------------
    # LOGIN
    # ------------------------------------------------------

    def _autorizado(self) -> bool:

        return self.painel.autoriza(self.headers.get("Authorization", ""))

    def _pedir_login(self):

        self.send_response(HTTPStatus.UNAUTHORIZED)
        self.send_header("WWW-Authenticate", 'Basic realm="SafeTech Entry", charset="UTF-8"')
        self.send_header("Content-Length", "0")
        self.end_headers()

    # ------------------------------------------------------
    # RESPOSTAS
    # ------------------------------------------------------

    def _enviar(self, corpo, tipo, cache="no-store", extras=None):

        self.send_response(HTTPStatus.OK)
        self.send_header("Content-Type", tipo)
        self.send_header("Content-Length", str(len(corpo)))
        self.send_header("Cache-Control", cache)
        self.send_header("X-Content-Type-Options", "nosniff")

        for nome, valor in (extras or {}).items():
            self.send_header(nome, valor)

        self.end_headers()

        try:
            self.wfile.write(corpo)

        except (BrokenPipeError, ConnectionError):
            # O navegador fechou a aba no meio da resposta: não é erro
            pass

    def _enviar_json(self, dados):

        self._enviar(
            json.dumps(dados, ensure_ascii=False).encode("utf-8"),
            "application/json; charset=utf-8",
        )

    def log_message(self, formato, *argumentos):
        """Silencia o registro de cada pedido no terminal."""


# ============================================================
# FUNÇÕES DE APOIO
# ============================================================

def _numero_da_area(consulta):
    """
    Número da área pedido em "?area=N", ou None se não houver.

    Qualquer valor que não seja um número inteiro também vira None (a
    área do "ao vivo"): o pedido nunca derruba o servidor.
    """

    valores = parse_qs(consulta).get("area")

    if not valores:
        return None

    try:
        return int(valores[0])
    except ValueError:
        return None


def _totalizar(registros) -> dict:

    total = len(registros)
    liberados = sum(1 for registro in registros if registro.liberado == "SIM")

    return {
        "total": total,
        "liberados": liberados,
        "negados": total - liberados,
    }


def _ip_na_rede() -> str:
    """
    Descobre o endereço deste computador na rede local.

    "Conectar" um soquete UDP não envia nada; serve só para o sistema
    dizer qual endereço usaria para sair para a rede.
    """

    try:

        with socket.socket(socket.AF_INET, socket.SOCK_DGRAM) as soquete:
            soquete.connect(("10.255.255.255", 1))
            return soquete.getsockname()[0]

    except OSError:
        return "localhost"
