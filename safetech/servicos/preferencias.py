"""
Preferências do usuário, lembradas entre uma execução e outra.

Guarda a última seleção feita na tela (setor, EPIs exigidos, modo de
detecção, câmera e câmeras IP cadastradas) num arquivo JSON pequeno, para o programa abrir já do jeito
que estava em uso: não é preciso selecionar tudo de novo a cada dia.
"""

import json

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
