"""
Preferências do usuário, lembradas entre uma execução e outra.

Guarda o que foi escolhido na tela (as áreas com câmera, setor, EPIs
exigidos e modo; as câmeras IP cadastradas; a confiança e o intervalo)
num arquivo JSON pequeno, para o programa abrir já do jeito que estava
em uso: não é preciso selecionar tudo de novo a cada dia.
"""

import json
from dataclasses import asdict, dataclass, field

from safetech import config


def carregar(arquivo=config.ARQUIVO_PREFERENCIAS):
    """
    Devolve (setor, exigidos, modo_deteccao) salvos.

    Sem arquivo (ou com arquivo inválido), devolve os padrões de
    config.py. Cada item é validado separadamente: um valor estranho
    num deles não descarta os outros.
    """

    setor = config.SETOR_PADRAO
    exigidos = list(config.SETORES[config.SETOR_PADRAO])
    modo_deteccao = config.MODO_DETECCAO_PADRAO

    try:

        with open(arquivo, "r", encoding="utf-8") as origem:
            dados = json.load(origem)

    except (OSError, ValueError):
        # Primeira execução ou arquivo corrompido: usa os padrões
        return setor, exigidos, modo_deteccao

    if not isinstance(dados, dict):
        return setor, exigidos, modo_deteccao

    setor_salvo = dados.get("setor")
    exigidos_salvos = dados.get("exigidos")

    # Só aceita o que ainda faz sentido: um EPI removido de config.py
    # depois de salvo é descartado.
    if isinstance(setor_salvo, str) and isinstance(exigidos_salvos, list):
        setor = setor_salvo
        exigidos = [chave for chave in exigidos_salvos if chave in config.EPIS]

    # Versões anteriores salvavam "rosto" ou "corpo": viram "catraca"
    # e "vigilancia", que usam esses mesmos detectores
    modo_salvo = config.MODOS_ANTIGOS.get(dados.get("modo_deteccao"), dados.get("modo_deteccao"))

    if modo_salvo in config.MODOS_DETECCAO:
        modo_deteccao = modo_salvo

    return setor, exigidos, modo_deteccao


def _ler_dados(arquivo):
    """Conteúdo atual do arquivo como dicionário ({} se não existir ou for inválido)."""

    try:

        with open(arquivo, "r", encoding="utf-8") as origem:
            dados = json.load(origem)

    except (OSError, ValueError):
        return {}

    return dados if isinstance(dados, dict) else {}


def _gravar_dados(dados, arquivo):
    """Grava o dicionário. Falhar ao gravar não deve travar o programa."""

    try:

        with open(arquivo, "w", encoding="utf-8") as destino:
            json.dump(dados, destino, ensure_ascii=False, indent=4)

    except OSError:
        pass


def salvar(setor, exigidos, modo_deteccao, arquivo=config.ARQUIVO_PREFERENCIAS):
    """Grava a seleção atual, mantendo os outros itens (como a câmera)."""

    dados = _ler_dados(arquivo)

    dados.update(
        {
            "setor": setor,
            "exigidos": list(exigidos),
            "modo_deteccao": modo_deteccao,
        }
    )

    _gravar_dados(dados, arquivo)


# ============================================================
# AJUSTES DA ANÁLISE (confiança mínima e intervalo)
# ============================================================

def carregar_ajustes(arquivo=config.ARQUIVO_PREFERENCIAS):
    """
    Devolve (limiar_confianca, intervalo_classificacao) salvos.

    Valor ausente, de tipo errado ou fora da faixa dos controles da
    tela volta para o padrão de config.py.
    """

    dados = _ler_dados(arquivo)

    limiar = _numero_na_faixa(
        dados.get("limiar_confianca"),
        config.LIMIAR_CONFIANCA_MINIMO,
        config.LIMIAR_CONFIANCA_MAXIMO,
        config.LIMIAR_CONFIANCA_PADRAO,
    )

    intervalo = _numero_na_faixa(
        dados.get("intervalo_classificacao"),
        config.INTERVALO_CLASSIFICACAO_MINIMO_SEG,
        config.INTERVALO_CLASSIFICACAO_MAXIMO_SEG,
        config.INTERVALO_CLASSIFICACAO_PADRAO_SEG,
    )

    return limiar, intervalo


def salvar_ajustes(limiar_confianca, intervalo_classificacao, arquivo=config.ARQUIVO_PREFERENCIAS):
    """Grava a confiança mínima e o intervalo, mantendo o resto das preferências."""

    dados = _ler_dados(arquivo)

    # Arredondados: o controle deslizante dá números como 0.8312437...
    dados["limiar_confianca"] = round(float(limiar_confianca), 2)
    dados["intervalo_classificacao"] = round(float(intervalo_classificacao), 1)

    _gravar_dados(dados, arquivo)


def _numero_na_faixa(valor, minimo, maximo, padrao):

    # bool é subclasse de int; não vale como número aqui
    if isinstance(valor, (int, float)) and not isinstance(valor, bool) and minimo <= valor <= maximo:
        return float(valor)

    return padrao


# ============================================================
# CÂMERA ESCOLHIDA
# ============================================================
#
# A câmera em uso é guardada como "fonte": um número (webcam) ou o
# endereço de uma câmera IP (texto). A chave no arquivo continua
# "indice_camera", para aproveitar arquivos de versões anteriores.
# ============================================================

def carregar_fonte_camera(arquivo=config.ARQUIVO_PREFERENCIAS):
    """Câmera escolhida na última vez: índice da webcam ou endereço IP (ou o padrão de config.py)."""

    fonte = _ler_dados(arquivo).get("indice_camera")

    # bool é subclasse de int; não vale como índice
    if isinstance(fonte, int) and not isinstance(fonte, bool) and fonte >= 0:
        return fonte

    # Endereço de câmera IP: só vale se ainda estiver na lista salva
    # (o usuário pode ter removido a câmera)
    if isinstance(fonte, str) and fonte in [endereco for _, endereco in carregar_cameras_ip(arquivo)]:
        return fonte

    return config.INDICE_CAMERA


def salvar_fonte_camera(fonte, arquivo=config.ARQUIVO_PREFERENCIAS):
    """Grava a câmera escolhida, mantendo o resto das preferências."""

    dados = _ler_dados(arquivo)

    dados["indice_camera"] = fonte

    _gravar_dados(dados, arquivo)


# ============================================================
# CÂMERAS IP CADASTRADAS
# ============================================================
#
# Lista de (nome, endereço). O endereço pode conter usuário e senha
# da câmera; por isso ele fica só neste arquivo, que NÃO vai para o
# repositório (está no .gitignore), e nunca é mostrado inteiro na tela.
# ============================================================

def carregar_cameras_ip(arquivo=config.ARQUIVO_PREFERENCIAS):
    """Câmeras IP salvas, como lista de (nome, endereço), na ordem em que foram adicionadas."""

    cameras = []

    for item in _ler_dados(arquivo).get("cameras_ip", []):

        # Ignora itens estranhos (arquivo editado à mão)
        if (
            isinstance(item, dict)
            and isinstance(item.get("nome"), str)
            and isinstance(item.get("endereco"), str)
            and item["endereco"]
        ):
            cameras.append((item["nome"], item["endereco"]))

    return cameras


def salvar_cameras_ip(cameras, arquivo=config.ARQUIVO_PREFERENCIAS):
    """Grava a lista de (nome, endereço) das câmeras IP."""

    dados = _ler_dados(arquivo)

    dados["cameras_ip"] = [
        {"nome": nome, "endereco": endereco} for nome, endereco in cameras
    ]

    _gravar_dados(dados, arquivo)


# ============================================================
# ÁREAS (várias câmeras)
# ============================================================
#
# Cada área guarda a sua câmera e a sua fiscalização. Arquivos de
# versões anteriores não têm "areas": nesse caso, a área "Principal" é
# montada com o que já estava salvo (setor, EPIs, modo e câmera).
# ============================================================

@dataclass
class DadosArea:
    """O que define uma área. Mutável: muda quando o usuário mexe na tela."""

    nome: str

    # Índice da webcam (número) ou endereço da câmera IP (texto)
    fonte: object

    setor: str
    exigidos: list = field(default_factory=list)
    modo: str = config.MODO_DETECCAO_PADRAO

    # Só UMA área comanda a catraca física (ESP32)
    controla_catraca: bool = False


def carregar_areas(arquivo=config.ARQUIVO_PREFERENCIAS):
    """
    Devolve a lista de áreas salvas (sempre pelo menos uma).

    Cada item é conferido: valor estranho volta para o padrão, nomes
    repetidos são descartados, e no máximo uma área comanda a catraca.
    """

    dados = _ler_dados(arquivo)

    enderecos_ip = [endereco for _, endereco in carregar_cameras_ip(arquivo)]

    areas = []

    for item in dados.get("areas", []) if isinstance(dados.get("areas"), list) else []:

        area = _area_valida(item, enderecos_ip, [a.nome for a in areas])

        if area is not None:
            areas.append(area)

    if not areas:

        # Versão anterior (ou primeira vez): uma área com o que já havia
        setor, exigidos, modo = carregar(arquivo)

        areas = [
            DadosArea(
                nome=config.NOME_AREA_PADRAO,
                fonte=carregar_fonte_camera(arquivo),
                setor=setor,
                exigidos=list(exigidos),
                modo=modo,
                controla_catraca=True,
            )
        ]

    # No máximo uma área comanda a catraca: vale a primeira marcada
    marcada = False

    for area in areas:

        if area.controla_catraca and not marcada:
            marcada = True
        else:
            area.controla_catraca = False

    return areas[: config.MAXIMO_AREAS]


def salvar_areas(areas, arquivo=config.ARQUIVO_PREFERENCIAS):
    """Grava as áreas (lista de DadosArea), mantendo o resto das preferências."""

    dados = _ler_dados(arquivo)

    dados["areas"] = [asdict(area) for area in areas]

    _gravar_dados(dados, arquivo)


def _area_valida(item, enderecos_ip, nomes_usados):
    """Converte um item do arquivo em DadosArea, ou None se não der para aproveitar."""

    if not isinstance(item, dict):
        return None

    nome = item.get("nome")

    if not isinstance(nome, str) or not nome.strip() or nome.strip() in nomes_usados:
        return None

    # Câmera: webcam (número >= 0) ou câmera IP ainda cadastrada
    fonte = item.get("fonte")

    webcam = isinstance(fonte, int) and not isinstance(fonte, bool) and fonte >= 0

    if not webcam and not (isinstance(fonte, str) and fonte in enderecos_ip):
        fonte = config.INDICE_CAMERA

    setor = item.get("setor") if isinstance(item.get("setor"), str) else config.SETOR_PADRAO

    exigidos = item.get("exigidos")
    exigidos = [chave for chave in exigidos if chave in config.EPIS] if isinstance(exigidos, list) else []

    modo = config.MODOS_ANTIGOS.get(item.get("modo"), item.get("modo"))

    if modo not in config.MODOS_DETECCAO:
        modo = config.MODO_DETECCAO_PADRAO

    return DadosArea(
        nome=nome.strip(),
        fonte=fonte,
        setor=setor,
        exigidos=exigidos,
        modo=modo,
        controla_catraca=item.get("controla_catraca") is True,
    )



# ============================================================
# TEMA DA TELA (escuro ou claro)
# ============================================================

def carregar_colunas_auditoria(arquivo=config.ARQUIVO_PREFERENCIAS):
    """Colunas escolhidas para a tabela da auditoria (None = todas)."""

    colunas = _ler_dados(arquivo).get("colunas_auditoria")

    if isinstance(colunas, list) and all(isinstance(campo, str) for campo in colunas):
        return colunas

    return None


def salvar_colunas_auditoria(colunas, arquivo=config.ARQUIVO_PREFERENCIAS):

    dados = _ler_dados(arquivo)

    dados["colunas_auditoria"] = list(colunas)

    _gravar_dados(dados, arquivo)


def assistente_concluido(arquivo=config.ARQUIVO_PREFERENCIAS) -> bool:
    """O assistente de configuração já foi concluído (não precisa abrir sozinho)?"""

    return bool(_ler_dados(arquivo).get("assistente_concluido"))


def marcar_assistente_concluido(arquivo=config.ARQUIVO_PREFERENCIAS):

    dados = _ler_dados(arquivo)

    dados["assistente_concluido"] = True

    _gravar_dados(dados, arquivo)


def carregar_tema(arquivo=config.ARQUIVO_PREFERENCIAS):
    """Tema escolhido da última vez ("escuro" ou "claro"); o padrão se não houver."""

    tema = _ler_dados(arquivo).get("tema")

    return tema if tema in config.TEMAS else config.TEMA_PADRAO


def salvar_tema(tema, arquivo=config.ARQUIVO_PREFERENCIAS):
    """Grava o tema escolhido, mantendo o resto das preferências."""

    dados = _ler_dados(arquivo)

    dados["tema"] = tema

    _gravar_dados(dados, arquivo)


# ============================================================
# PAINEL WEB (ligar, porta, rede, usuário e hash da senha)
# ============================================================

def carregar_painel_web(arquivo=config.ARQUIVO_PREFERENCIAS):
    """
    Ajustes do painel web salvos pela tela (AjustesPainelWeb).

    Sem nada salvo, ou com algum valor estragado, vale o config.py.
    """

    from safetech.servicos.acesso_web import AjustesPainelWeb, ajustes_padrao

    salvo = _ler_dados(arquivo).get("painel_web")

    if not isinstance(salvo, dict):
        return ajustes_padrao()

    try:

        porta = int(salvo["porta"])

        if not config.PAINEL_WEB_PORTA_MINIMA <= porta <= config.PAINEL_WEB_PORTA_MAXIMA:
            raise ValueError(porta)

        return AjustesPainelWeb(
            ativo=bool(salvo["ativo"]),
            na_rede=bool(salvo["na_rede"]),
            porta=porta,
            usuario=str(salvo["usuario"]),
            hash_senha=str(salvo["hash_senha"]),
        )

    except (KeyError, TypeError, ValueError):
        return ajustes_padrao()


def salvar_painel_web(ajustes, arquivo=config.ARQUIVO_PREFERENCIAS):
    """Grava os ajustes do painel web (a senha só como hash), mantendo o resto."""

    dados = _ler_dados(arquivo)

    dados["painel_web"] = {
        "ativo": ajustes.ativo,
        "na_rede": ajustes.na_rede,
        "porta": ajustes.porta,
        "usuario": ajustes.usuario,
        "hash_senha": ajustes.hash_senha,
    }

    _gravar_dados(dados, arquivo)
