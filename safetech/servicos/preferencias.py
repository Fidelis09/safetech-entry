"""
Preferências do usuário, lembradas entre uma execução e outra.

Guarda a última seleção feita na tela (setor, EPIs exigidos e modo de
detecção) num arquivo JSON pequeno, para o programa abrir já do jeito
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

    if dados.get("modo_deteccao") in config.MODOS_DETECCAO:
        modo_deteccao = dados["modo_deteccao"]

    return setor, exigidos, modo_deteccao


def salvar(setor, exigidos, modo_deteccao, arquivo=config.ARQUIVO_PREFERENCIAS):
    """Grava a seleção atual. Falhar ao gravar não deve travar o programa."""

    try:

        with open(arquivo, "w", encoding="utf-8") as destino:
            json.dump(
                {
                    "setor": setor,
                    "exigidos": list(exigidos),
                    "modo_deteccao": modo_deteccao,
                },
                destino,
                ensure_ascii=False,
                indent=4,
            )

    except OSError:
        pass
