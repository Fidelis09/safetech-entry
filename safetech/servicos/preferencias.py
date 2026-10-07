"""
Preferências do usuário, lembradas entre uma execução e outra.

Guarda a última seleção de fiscalização (setor e EPIs exigidos) num
arquivo JSON pequeno, para o programa abrir já com os filtros que
estavam em uso: não é preciso selecionar tudo de novo a cada dia.
"""

import json

from safetech import config


def carregar(arquivo=config.ARQUIVO_PREFERENCIAS):
    """
    Devolve (setor, exigidos) salvos; sem arquivo (ou com arquivo
    inválido), devolve o setor padrão de config.py.
    """

    setor = config.SETOR_PADRAO
    exigidos = list(config.SETORES[config.SETOR_PADRAO])

    try:

        with open(arquivo, "r", encoding="utf-8") as origem:
            dados = json.load(origem)

        setor_salvo = dados["setor"]
        exigidos_salvos = dados["exigidos"]

        # Só aceita o que ainda faz sentido: um EPI removido de
        # config.py depois de salvo é descartado.
        if isinstance(setor_salvo, str) and isinstance(exigidos_salvos, list):
            setor = setor_salvo
            exigidos = [chave for chave in exigidos_salvos if chave in config.EPIS]

    except (OSError, ValueError, KeyError, TypeError):
        # Primeira execução ou arquivo corrompido: usa o padrão
        pass

    return setor, exigidos


def salvar(setor, exigidos, arquivo=config.ARQUIVO_PREFERENCIAS):
    """Grava a seleção atual. Falhar ao gravar não deve travar o programa."""

    try:

        with open(arquivo, "w", encoding="utf-8") as destino:
            json.dump(
                {"setor": setor, "exigidos": list(exigidos)},
                destino,
                ensure_ascii=False,
                indent=4,
            )

    except OSError:
        pass
