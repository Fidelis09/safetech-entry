"""
Backup e restauração das configurações num arquivo só.

Tudo o que o operador ajusta na tela fica em preferencias.json: áreas
(câmera, setor, EPIs, modo), câmeras IP, confiança e intervalo, tema e
os ajustes do painel web. O backup é uma cópia disso num arquivo .json
com algumas informações a mais (de que programa é e quando foi feito),
para levar a outro computador ou guardar antes de mexer em tudo.

    salvar    -> grava o backup
    ler       -> abre um backup e confere se é mesmo do SafeTech
    restaurar -> troca as configurações atuais pelas do backup. As atuais
                 NÃO são perdidas: viram preferencias_antes_da_restauracao_<data>.json

O backup NÃO leva a auditoria (eventos e fotos) nem o dataset: só as
configurações. Atenção: o endereço de uma câmera IP pode conter a senha
dela, e vai junto no backup (a senha do painel web vai só como hash).
"""

import json
import logging
import shutil

from safetech import config
from safetech.nucleo import horario


log = logging.getLogger(__name__)


# Marca que identifica um backup do SafeTech (e a versão do formato)
PROGRAMA = "SafeTech Entry"
VERSAO_FORMATO = 1


class BackupInvalido(ValueError):
    """O arquivo escolhido não é um backup do SafeTech (ou está estragado)."""


def salvar(caminho, arquivo_preferencias=None):
    """Grava o backup das configurações em 'caminho'. Pode lançar OSError."""

    arquivo_preferencias = arquivo_preferencias or config.ARQUIVO_PREFERENCIAS

    try:
        preferencias = json.loads(arquivo_preferencias.read_text(encoding="utf-8"))
    except (OSError, ValueError):
        # Nada salvo ainda (ou arquivo estragado): backup das configurações padrão
        preferencias = {}

    conteudo = {
        "programa": PROGRAMA,
        "versao_formato": VERSAO_FORMATO,
        "criado_em": horario.agora_iso(),
        "preferencias": preferencias,
    }

    with open(caminho, "w", encoding="utf-8") as destino:
        json.dump(conteudo, destino, ensure_ascii=False, indent=4)

    log.info("Backup das configurações salvo em %s", caminho)

    return caminho


def ler(caminho):
    """
    Abre um backup e devolve o conteúdo (dicionário).

    Lança BackupInvalido se não for um backup do SafeTech, ou se for de
    um formato mais novo que este programa não conhece.
    """

    try:
        with open(caminho, "r", encoding="utf-8") as origem:
            conteudo = json.load(origem)

    except (OSError, ValueError) as erro:
        raise BackupInvalido(f"Não foi possível ler o arquivo: {erro}") from erro

    if not isinstance(conteudo, dict) or conteudo.get("programa") != PROGRAMA:
        raise BackupInvalido("Este arquivo não é um backup do SafeTech Entry.")

    if not isinstance(conteudo.get("preferencias"), dict):
        raise BackupInvalido("O backup está incompleto (sem as configurações).")

    versao = conteudo.get("versao_formato")

    if not isinstance(versao, int) or versao > VERSAO_FORMATO:
        raise BackupInvalido("O backup foi feito por uma versão mais nova do programa.")

    return conteudo


def restaurar(caminho, arquivo_preferencias=None):
    """
    Troca as configurações atuais pelas do backup.

    Devolve o caminho da cópia das configurações de antes (ou None se
    não havia nenhuma). Lança BackupInvalido ou OSError; nesses casos,
    as configurações atuais continuam como estavam.
    """

    arquivo_preferencias = arquivo_preferencias or config.ARQUIVO_PREFERENCIAS

    conteudo = ler(caminho)

    copia = None

    # As configurações atuais são guardadas, nunca apagadas
    if arquivo_preferencias.exists():

        sufixo = horario.agora().strftime("%Y%m%d_%H%M%S")

        copia = arquivo_preferencias.with_name(f"{arquivo_preferencias.stem}_antes_da_restauracao_{sufixo}.json")

        shutil.copy2(arquivo_preferencias, copia)

    # Grava num arquivo temporário e só depois troca: se algo falhar no
    # meio, o preferencias.json atual continua inteiro
    temporario = arquivo_preferencias.with_suffix(".tmp")

    with open(temporario, "w", encoding="utf-8") as destino:
        json.dump(conteudo["preferencias"], destino, ensure_ascii=False, indent=4)

    temporario.replace(arquivo_preferencias)

    log.info("Configurações restauradas de %s (as de antes ficaram em %s)", caminho, copia)

    return copia
