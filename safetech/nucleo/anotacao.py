"""
Desenho das caixas e rótulos sobre a imagem.

Usado em dois lugares: no vídeo ao vivo da interface e nas fotos de
evidência da auditoria. Por isso fica no núcleo, e não na interface.

Observação: as fontes do OpenCV não têm acentos, então os textos
desenhados aqui usam apenas caracteres simples.
"""

import cv2

from safetech import config
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

def texto_da_pessoa(pessoa: PessoaObservada) -> str:
    """Ex.: "#3 OK", "#3 FALTA: CAPACETE, LUVAS" ou "#3 Analisando..."."""

    if pessoa.status is StatusPessoa.ANALISANDO:
        return f"#{pessoa.identificador} Analisando..."

    if pessoa.status is StatusPessoa.LIBERADO:
        return f"#{pessoa.identificador} OK"

    # Modelo antigo: não sabe dizer QUAL equipamento falta
    if pessoa.faltando == (config.EPI_CONJUNTO,):
        return f"#{pessoa.identificador} SEM EPI"

    # As CHAVES dos EPIs não têm acento, por isso servem para o vídeo
    faltando = ", ".join(chave.upper() for chave in pessoa.faltando)

    return f"#{pessoa.identificador} FALTA: {faltando}"


# ============================================================
# DESENHO
# ============================================================

def desenhar_pessoas(imagem_bgr, pessoas, escala=1.0):
    """
    Desenha todas as pessoas sobre a imagem (a imagem é alterada).

    escala -> fator entre a imagem recebida e o frame original, usado
              quando a imagem foi redimensionada para caber na tela.
    """

    for pessoa in pessoas:

        caixa = tuple(int(valor * escala) for valor in pessoa.caixa)

        desenhar_caixa(
            imagem_bgr,
            caixa,
            texto_da_pessoa(pessoa),
            CORES_STATUS[pessoa.status],
        )

    return imagem_bgr


def desenhar_caixa(imagem_bgr, caixa, texto, cor):
    """Desenha uma caixa com cantos reforçados e um rótulo acima dela."""

    x1, y1, x2, y2 = caixa

    altura_imagem, largura_imagem = imagem_bgr.shape[:2]

    # Espessuras e fonte proporcionais ao tamanho da imagem, para o
    # desenho ficar igual em qualquer resolução.
    base = max(1, round(largura_imagem / 640))

    espessura_fina = base
    espessura_canto = base * 3

    # ------------------------------------------------------
    # CAIXA: contorno fino + cantos grossos
    # ------------------------------------------------------

    cv2.rectangle(imagem_bgr, (x1, y1), (x2, y2), cor, espessura_fina, cv2.LINE_AA)

    canto = max(10, min(x2 - x1, y2 - y1) // 5)

    for x, y, direcao_x, direcao_y in (
        (x1, y1, 1, 1),
        (x2, y1, -1, 1),
        (x1, y2, 1, -1),
        (x2, y2, -1, -1),
    ):

        cv2.line(imagem_bgr, (x, y), (x + direcao_x * canto, y), cor, espessura_canto, cv2.LINE_AA)
        cv2.line(imagem_bgr, (x, y), (x, y + direcao_y * canto), cor, espessura_canto, cv2.LINE_AA)

    # ------------------------------------------------------
    # RÓTULO: fundo colorido + texto branco
    # ------------------------------------------------------

    tamanho_fonte = 0.5 * max(1.0, largura_imagem / 640)
    espessura_fonte = max(1, base)

    (largura_texto, altura_texto), _ = cv2.getTextSize(
        texto, FONTE, tamanho_fonte, espessura_fonte
    )

    margem = 6

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
