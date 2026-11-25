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

    tamanho_fonte = config.ESCALA_FONTE_ROTULO * max(1.0, largura_imagem / 800)
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


# ============================================================
# CARIMBO DAS FOTOS DE EVIDÊNCIA
# ============================================================
#
# Uma faixa escura embaixo da foto com o texto do evento (data e hora,
# área, pessoa, resultado). Fica gravado nos pixels: a foto continua
# se explicando mesmo copiada para fora do sistema, sem o CSV junto.
# ============================================================

COR_FAIXA_CARIMBO = (20, 15, 11)

# Opacidade da faixa (0 = invisível, 1 = cobre a foto por completo)
OPACIDADE_CARIMBO = 0.72


def carimbar(imagem_bgr, texto):
    """
    Escreve o texto numa faixa no rodapé da imagem (a imagem é alterada).

    Só caracteres simples (sem acentos): a fonte do OpenCV não os tem.
    """

    altura_imagem, largura_imagem = imagem_bgr.shape[:2]

    base = max(1, round(largura_imagem / 1000))
    tamanho_fonte = config.ESCALA_FONTE_ROTULO * max(1.0, largura_imagem / 800)

    (_, altura_texto), _ = cv2.getTextSize(texto, FONTE, tamanho_fonte, base)

    margem = 6 * base
    altura_faixa = min(altura_imagem, altura_texto + 2 * margem)
    topo = altura_imagem - altura_faixa

    # Faixa semitransparente: mistura a cor da faixa com a foto embaixo
    trecho = imagem_bgr[topo:, :]
    faixa = trecho.copy()
    faixa[:] = COR_FAIXA_CARIMBO

    cv2.addWeighted(faixa, OPACIDADE_CARIMBO, trecho, 1 - OPACIDADE_CARIMBO, 0, dst=trecho)

    cv2.putText(
        imagem_bgr,
        texto,
        (margem, altura_imagem - margem),
        FONTE,
        tamanho_fonte,
        COR_TEXTO,
        base,
        cv2.LINE_AA,
    )

    return imagem_bgr


def sem_acentos(texto) -> str:
    """ "Área Laboratório" -> "Area Laboratorio" (para desenhar com a fonte do OpenCV)."""

    import unicodedata

    decomposto = unicodedata.normalize("NFKD", texto)

    return "".join(letra for letra in decomposto if not unicodedata.combining(letra))


# ============================================================
# MODO CALIBRAÇÃO: A CONFIANÇA DE CADA EPI SOBRE A PESSOA
# ============================================================
#
# Para ajustar a "confiança mínima" vendo o efeito na hora: embaixo da
# caixa de cada pessoa aparece uma barra por EPI, cheia até a confiança
# do modelo, com um risco branco na altura do limiar.
#
#   verde  -> passou do limiar (conta como "usando")
#   vermelho -> não passou
#   cinza  -> EPI que o setor não exige (o modelo avalia, mas não conta)
# ============================================================

COR_BARRA_OK = (94, 197, 34)
COR_BARRA_FALTA = (68, 68, 239)
COR_BARRA_NAO_EXIGIDO = (150, 150, 150)
COR_TRILHO = (40, 40, 40)
COR_LIMIAR = (255, 255, 255)


def sigla_do_epi(chave) -> str:
    """ "capacete" -> "CAP", "oculos" -> "OCU" (sem acento: a fonte do OpenCV não tem)."""

    from safetech.nucleo.epis import nome_do_epi

    return sem_acentos(nome_do_epi(chave))[:3].upper()


def desenhar_confiancas(imagem_bgr, pessoas, escala, limiar, exigidos):
    """
    Barras de confiança de cada EPI embaixo de cada pessoa (a imagem é alterada).

    escala   -> fator entre a imagem e o frame original (como em desenhar_pessoas)
    limiar   -> confiança mínima (0 a 1): onde fica o risco branco
    exigidos -> chaves dos EPIs que o setor exige
    """

    altura_imagem, largura_imagem = imagem_bgr.shape[:2]

    base = max(1, round(largura_imagem / 1000))
    tamanho_fonte = config.ESCALA_FONTE_ROTULO * max(1.0, largura_imagem / 800) * 0.85

    (_, altura_texto), _ = cv2.getTextSize("CAP 100%", FONTE, tamanho_fonte, base)

    altura_linha = altura_texto + 6 * base
    largura_sigla = cv2.getTextSize("CAP ", FONTE, tamanho_fonte, base)[0][0]
    largura_valor = cv2.getTextSize(" 100%", FONTE, tamanho_fonte, base)[0][0]

    for pessoa in pessoas:

        if not pessoa.itens:
            continue

        x1, _, x2, y2 = (int(valor * escala) for valor in pessoa.caixa)

        # Painel no mínimo largo o bastante para a sigla, a barra e o número
        largura_painel = max(x2 - x1, largura_sigla + largura_valor + 40 * base)
        altura_painel = altura_linha * len(pessoa.itens) + 4 * base

        # Embaixo da caixa; sem espaço (pessoa no pé da imagem), por dentro
        topo = y2 + 2 * base if y2 + altura_painel < altura_imagem else max(0, y2 - altura_painel)
        esquerda = max(0, min(x1, largura_imagem - largura_painel))

        # Fundo escuro meio transparente, para ler em cima de qualquer imagem
        trecho = imagem_bgr[topo: topo + altura_painel, esquerda: esquerda + largura_painel]

        if trecho.size:
            escuro = trecho.copy()
            escuro[:] = COR_FAIXA_CARIMBO
            cv2.addWeighted(escuro, OPACIDADE_CARIMBO, trecho, 1 - OPACIDADE_CARIMBO, 0, dst=trecho)

        inicio_barra = esquerda + 3 * base + largura_sigla
        fim_barra = esquerda + largura_painel - largura_valor - 3 * base

        for posicao, item in enumerate(pessoa.itens):

            y = topo + 2 * base + posicao * altura_linha
            meio = y + altura_linha // 2

            if item.chave not in exigidos:
                cor = COR_BARRA_NAO_EXIGIDO
            else:
                cor = COR_BARRA_OK if item.confianca >= limiar else COR_BARRA_FALTA

            cv2.putText(imagem_bgr, sigla_do_epi(item.chave), (esquerda + 3 * base, meio + altura_texto // 2), FONTE, tamanho_fonte, COR_TEXTO, base, cv2.LINE_AA)

            # Trilho, a barra até a confiança e o risco do limiar
            grossura = max(3, altura_texto // 2)

            cv2.rectangle(imagem_bgr, (inicio_barra, meio - grossura // 2), (fim_barra, meio + grossura // 2), COR_TRILHO, cv2.FILLED)

            ponta = inicio_barra + int((fim_barra - inicio_barra) * max(0.0, min(1.0, item.confianca)))

            cv2.rectangle(imagem_bgr, (inicio_barra, meio - grossura // 2), (ponta, meio + grossura // 2), cor, cv2.FILLED)

            x_limiar = inicio_barra + int((fim_barra - inicio_barra) * limiar)

            cv2.line(imagem_bgr, (x_limiar, meio - grossura), (x_limiar, meio + grossura), COR_LIMIAR, max(1, base))

            cv2.putText(
                imagem_bgr, f"{item.confianca * 100:.0f}%", (fim_barra + 2 * base, meio + altura_texto // 2),
                FONTE, tamanho_fonte, COR_TEXTO, base, cv2.LINE_AA,
            )

    return imagem_bgr
