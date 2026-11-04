"""
Desenho das caixas e rótulos sobre a imagem.

Usado em dois lugares: no vídeo ao vivo da interface e nas fotos de
evidência da auditoria. Por isso fica no núcleo, e não na interface.

Observação: as fontes do OpenCV não têm acentos, então os textos
desenhados aqui usam apenas caracteres simples.
"""

import cv2

from safetech import config
from safetech.nucleo import modos
from safetech.nucleo.tipos import PessoaObservada, StatusPessoa


# Cores no formato do OpenCV: (azul, verde, vermelho)
CORES_STATUS = {
    StatusPessoa.LIBERADO: (94, 197, 34),
    StatusPessoa.NEGADO: (68, 68, 239),
    StatusPessoa.ANALISANDO: (175, 163, 148),
}

COR_TEXTO = (255, 255, 255)

FONTE = cv2.FONT_HERSHEY_SIMPLEX


# ============================================================
# TEXTO DO RÓTULO
# ============================================================

# Uma única palavra por pessoa. Com muitas pessoas na imagem, um
# rótulo comprido cobre o vizinho; o detalhe (quais EPIs faltam) fica
# na faixa de status, no log de auditoria e no painel web.
#
# A palavra depende do modo (config.TEXTOS_POR_MODO): na catraca,
# "OK" / "NEGADO"; na vigilância, "OK" / "SEM EPI".
PALAVRA_ANALISANDO = "..."


def texto_da_pessoa(pessoa: PessoaObservada, modo=config.MODO_CATRACA) -> str:
    """A palavra desenhada junto da caixa (ex.: "OK", "NEGADO", "SEM EPI" ou "...")."""

    if pessoa.status is StatusPessoa.ANALISANDO:
        return PALAVRA_ANALISANDO

    textos = modos.textos(modo)

    return textos["palavra_ok"] if pessoa.status is StatusPessoa.LIBERADO else textos["palavra_irregular"]


# ============================================================
# DESENHO
# ============================================================

def desenhar_pessoas(imagem_bgr, pessoas, escala=1.0, modo=config.MODO_CATRACA):
    """
    Desenha todas as pessoas sobre a imagem (a imagem é alterada).

    escala -> fator entre a imagem recebida e o frame original, usado
              quando a imagem foi redimensionada para caber na tela.
    modo   -> modo de operação; define a palavra junto da caixa.
    """

    for pessoa in pessoas:

        caixa = tuple(int(valor * escala) for valor in pessoa.caixa)

        desenhar_caixa(
            imagem_bgr,
            caixa,
            texto_da_pessoa(pessoa, modo),
            CORES_STATUS[pessoa.status],
        )

    return imagem_bgr


def desenhar_caixa(imagem_bgr, caixa, texto, cor):
    """Desenha um contorno fino e uma palavra pequena acima dele."""

    x1, y1, x2, y2 = caixa

    altura_imagem, largura_imagem = imagem_bgr.shape[:2]

    # Medidas proporcionais ao tamanho da imagem, para o desenho ficar
    # igual em qualquer resolução. O contorno é sempre o mais fino
    # possível nessa proporção: com muitas pessoas, linhas grossas e
    # cantos reforçados escondem quem está atrás.
    base = max(1, round(largura_imagem / 1000))

    # ------------------------------------------------------
    # CONTORNO
    # ------------------------------------------------------

    cv2.rectangle(imagem_bgr, (x1, y1), (x2, y2), cor, base, cv2.LINE_AA)

    # ------------------------------------------------------
    # RÓTULO: fundo colorido + palavra em branco
    # ------------------------------------------------------

    tamanho_fonte = 0.4 * max(1.0, largura_imagem / 800)
    espessura_fonte = base

    (largura_texto, altura_texto), _ = cv2.getTextSize(
        texto, FONTE, tamanho_fonte, espessura_fonte
    )

    margem = 3 * base

    altura_rotulo = altura_texto + 2 * margem
    largura_rotulo = largura_texto + 2 * margem

    # Acima da caixa; se não couber (pessoa no topo da imagem), dentro
    topo_rotulo = y1 - altura_rotulo if y1 - altura_rotulo >= 0 else y1

    # Não deixa o rótulo sair pela direita da imagem
    esquerda_rotulo = max(0, min(x1, largura_imagem - largura_rotulo))

    cv2.rectangle(
        imagem_bgr,
        (esquerda_rotulo, topo_rotulo),
        (esquerda_rotulo + largura_rotulo, topo_rotulo + altura_rotulo),
        cor,
        cv2.FILLED,
    )

    cv2.putText(
        imagem_bgr,
        texto,
        (esquerda_rotulo + margem, topo_rotulo + margem + altura_texto),
        FONTE,
        tamanho_fonte,
        COR_TEXTO,
        espessura_fonte,
        cv2.LINE_AA,
    )
