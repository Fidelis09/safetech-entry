"""
Acesso ao painel web: ligar, porta, rede, usuário e senha.

Esses ajustes são feitos na tela (Configurações > Painel web) e ficam
salvos em preferencias.json, que NÃO vai para o repositório. O
config.py só guarda os valores da primeira vez.

A SENHA NUNCA É GUARDADA. Fica guardado só um "hash" dela: um resumo
calculado de um jeito que não tem volta (PBKDF2, a mesma família usada
por sistemas de login de verdade). Para conferir um login, calcula-se o
hash da senha digitada e compara-se com o guardado. Quem abrir o
preferencias.json não descobre a senha.

    "pbkdf2_sha256$200000$<sal>$<hash>"
                   |       |      +-- o resumo da senha
                   |       +--------- texto aleatório, diferente a cada senha:
                   |                  duas pessoas com a mesma senha têm
                   |                  hashes diferentes
                   +----------------- quantas vezes o cálculo é repetido
                                      (de propósito lento para quem tenta
                                      adivinhar senhas)

Este módulo não tem tela: só regras. A janela de Configurações coleta
os campos e chama montar_ajustes(), que valida e devolve o erro em
texto se houver.
"""

import base64
import hashlib
import hmac
import secrets
from dataclasses import dataclass, replace

from safetech import config


ALGORITMO = "pbkdf2_sha256"


# ============================================================
# AJUSTES DO PAINEL
# ============================================================

@dataclass(frozen=True)
class AjustesPainelWeb:

    # Painel no ar?
    ativo: bool

    # True = outros aparelhos da rede acessam (computador do gerente,
    # celular, catraca ESP32 pelo Wi-Fi); False = só este computador
    na_rede: bool

    porta: int

    usuario: str

    # Hash da senha ("" = sem login: qualquer um na rede entra)
    hash_senha: str

    @property
    def host(self) -> str:
        """Endereço em que o servidor escuta."""

        return "0.0.0.0" if self.na_rede else "127.0.0.1"

    @property
    def exige_login(self) -> bool:
        return bool(self.hash_senha)


def ajustes_padrao() -> AjustesPainelWeb:
    """Os valores do config.py, usados até o primeiro "Aplicar" na tela."""

    return AjustesPainelWeb(
        ativo=config.PAINEL_WEB_ATIVO,
        na_rede=config.PAINEL_WEB_HOST == "0.0.0.0",
        porta=config.PAINEL_WEB_PORTA,
        usuario=config.PAINEL_WEB_USUARIO,
        hash_senha=gerar_hash(config.PAINEL_WEB_SENHA) if config.PAINEL_WEB_SENHA else "",
    )


def usa_senha_padrao(ajustes) -> bool:
    """True se a senha ainda é a do config.py (que é pública no repositório)."""

    return bool(config.PAINEL_WEB_SENHA) and senha_confere(config.PAINEL_WEB_SENHA, ajustes.hash_senha)


# ============================================================
# HASH DA SENHA
# ============================================================

def gerar_hash(senha, iteracoes=None) -> str:
    """Hash de uma senha, com sal aleatório, no formato descrito no topo do arquivo."""

    iteracoes = iteracoes or config.ITERACOES_HASH_SENHA

    sal = secrets.token_bytes(16)

    resumo = hashlib.pbkdf2_hmac("sha256", senha.encode("utf-8"), sal, iteracoes)

    return "$".join([ALGORITMO, str(iteracoes), _texto(sal), _texto(resumo)])


def senha_confere(senha, hash_guardado) -> bool:
    """A senha digitada gera o mesmo hash guardado? (False para hash vazio ou estragado)"""

    try:
        algoritmo, iteracoes, sal, resumo = hash_guardado.split("$")

        if algoritmo != ALGORITMO:
            return False

        calculado = hashlib.pbkdf2_hmac("sha256", senha.encode("utf-8"), _bytes(sal), int(iteracoes))

    except (ValueError, AttributeError, TypeError):
        return False

    # compare_digest compara em tempo constante (não "vaza" quantas
    # letras acertou pelo tempo de resposta)
    return hmac.compare_digest(calculado, _bytes(resumo))


def _texto(dados) -> str:
    return base64.b64encode(dados).decode("ascii")


def _bytes(texto) -> bytes:
    return base64.b64decode(texto.encode("ascii"), validate=True)


# ============================================================
# VALIDAÇÃO DO QUE FOI DIGITADO NA TELA
# ============================================================

def montar_ajustes(atuais, ativo, na_rede, porta, exigir_login, usuario, nova_senha, confirmacao):
    """
    Confere os campos da tela e devolve (ajustes_novos, erro).

    erro é um texto para mostrar ao usuário, ou None se estiver tudo
    certo. Senha nova em branco mantém a senha atual.
    """

    try:
        porta = int(str(porta).strip())
    except ValueError:
        return None, "A porta precisa ser um número."

    if not config.PAINEL_WEB_PORTA_MINIMA <= porta <= config.PAINEL_WEB_PORTA_MAXIMA:
        return None, (
            f"Use uma porta entre {config.PAINEL_WEB_PORTA_MINIMA} e {config.PAINEL_WEB_PORTA_MAXIMA} "
            "(as menores são reservadas pelo sistema)."
        )

    usuario = usuario.strip()

    if not exigir_login:
        return replace(atuais, ativo=ativo, na_rede=na_rede, porta=porta, usuario=usuario, hash_senha=""), None

    if not usuario:
        return None, "Informe o usuário do login."

    # O navegador envia "usuario:senha": um ":" no usuário quebraria o login
    if ":" in usuario:
        return None, "O usuário não pode ter \":\"."

    if nova_senha != confirmacao:
        return None, "A senha e a confirmação estão diferentes."

    if nova_senha:

        if len(nova_senha) < config.PAINEL_WEB_SENHA_MINIMA:
            return None, f"A senha precisa ter pelo menos {config.PAINEL_WEB_SENHA_MINIMA} caracteres."

        hash_senha = gerar_hash(nova_senha)

    elif atuais.hash_senha:

        # Em branco: continua a senha de antes
        hash_senha = atuais.hash_senha

    else:
        return None, "Para exigir login, defina uma senha."

    return replace(atuais, ativo=ativo, na_rede=na_rede, porta=porta, usuario=usuario, hash_senha=hash_senha), None
