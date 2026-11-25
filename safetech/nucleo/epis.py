"""
Informações sobre os EPIs que o modelo instalado sabe reconhecer.

Fica num módulo separado (e sem TensorFlow) para que a interface possa
montar a tela na hora, antes de o modelo terminar de carregar.

Existem dois tipos de modelo:

    POR EPI  -> responde separadamente para cada equipamento
                (modelos/modelo_epis.keras + modelos/epis.json)

    ANTIGO   -> só diz se a pessoa está com o conjunto completo
                (modelos/modelo_epi.keras + modelos/classes.json)

O modelo por EPI tem prioridade; o antigo só é usado se ele não existir.
"""

import json

from safetech import config


def ler_lista(caminho) -> list[str]:
    """Lê uma lista de textos de um arquivo JSON."""

    with open(caminho, "r", encoding="utf-8") as arquivo:
        return json.load(arquivo)


def modelo_por_epi_disponivel() -> bool:
    """True se o modelo que distingue os equipamentos já foi treinado."""

    return config.ARQUIVO_MODELO_EPIS.exists() and config.ARQUIVO_EPIS.exists()


def modelo_antigo_disponivel() -> bool:

    return config.ARQUIVO_MODELO_LEGADO.exists() and config.ARQUIVO_CLASSES_LEGADO.exists()


def epis_do_modelo() -> list[str]:
    """
    Chaves dos EPIs que o modelo instalado reconhece, na ordem das
    saídas dele. Com o modelo antigo, é só o "EPI" fictício do conjunto.
    Sem modelo nenhum, lista vazia.
    """

    if modelo_por_epi_disponivel():
        return ler_lista(config.ARQUIVO_EPIS)

    if modelo_antigo_disponivel():
        return [config.EPI_CONJUNTO]

    return []


def nome_do_epi(chave) -> str:
    """Nome para mostrar na tela (ex.: "oculos" -> "Óculos")."""

    if chave == config.EPI_CONJUNTO:
        return config.NOME_EPI_CONJUNTO

    return config.EPIS.get(chave, chave)


def chave_do_epi(nome):
    """O contrário de nome_do_epi: "Óculos" -> "oculos" (None se não for um EPI conhecido)."""

    for chave, nome_conhecido in config.EPIS.items():

        if nome_conhecido.lower() == str(nome).strip().lower():
            return chave

    return None


def ler_confiancas(texto):
    """
    "Capacete 97%, Luvas 12%" (como fica no log) -> [("Capacete", 0.97), ("Luvas", 0.12)].

    Partes estranhas (sem número no fim) são ignoradas.
    """

    resultado = []

    for parte in str(texto).split(","):

        nome, _, valor = parte.strip().rpartition(" ")

        try:
            resultado.append((nome, float(valor.rstrip("%")) / 100))
        except ValueError:
            continue

    return resultado


def nomes_dos_epis(chaves) -> str:
    """Vários nomes em um texto só (ex.: "Capacete, Luvas")."""

    return ", ".join(nome_do_epi(chave) for chave in chaves)
