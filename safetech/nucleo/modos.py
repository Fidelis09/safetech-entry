"""
Modos de operação: catraca e vigilância.

A regra de decisão é a mesma nos dois modos (os EPIs exigidos no
setor). O que muda é como o resultado é CHAMADO:

    catraca    -> "Liberado" / "Negado"         (há um acesso a liberar)
    vigilancia -> "Conforme" / "Não conforme"   (só se verifica a área)

Os textos ficam em config.TEXTOS_POR_MODO. Este módulo só os entrega
a quem precisa (tela, auditoria, relatório, vídeo), para ninguém
escrever "Liberado" fixo no código.
"""

from safetech import config


def modo_valido(modo) -> str:
    """
    Devolve o modo, convertendo nomes antigos ("rosto", "corpo").

    Modo vazio ou desconhecido vira "catraca": é como eram tratados os
    registros de antes de existir a vigilância.
    """

    modo = config.MODOS_ANTIGOS.get(modo, modo)

    if modo in config.TEXTOS_POR_MODO:
        return modo

    return config.MODO_CATRACA


def textos(modo) -> dict:
    """Os textos do modo (veja TEXTOS_POR_MODO no config.py)."""

    return config.TEXTOS_POR_MODO[modo_valido(modo)]


def nome_do_modo(modo) -> str:
    """Nome para mostrar: "Catraca" ou "Vigilância"."""

    return config.MODOS_DETECCAO[modo_valido(modo)]


def resultado(modo, conforme) -> str:
    """ "Liberado"/"Negado" na catraca; "Conforme"/"Não conforme" na vigilância."""

    chave = "resultado_ok" if conforme else "resultado_irregular"

    return textos(modo)[chave]


def eh_vigilancia(modo) -> bool:

    return modo_valido(modo) == config.MODO_VIGILANCIA
