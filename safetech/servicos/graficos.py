"""
Gráficos de barras desenhados como imagem (Pillow).

Os mesmos gráficos aparecem em dois lugares: na janela de Indicadores e
no relatório em PDF. Desenhá-los como imagem, aqui, garante que os dois
fiquem iguais, e não precisa de nenhuma biblioteca a mais.

Quem chama escolhe as cores (o tema escuro ou claro da janela, ou um
papel branco para o PDF) por um dicionário com as chaves:

    fundo, texto, texto_suave, grade, barra
"""

import os
from pathlib import Path

from PIL import Image, ImageDraw, ImageFont


# Fontes do Windows (as mesmas da janela). Fora do Windows, ou sem elas,
# usa a fonte embutida do Pillow.
PASTA_FONTES = Path(os.environ.get("WINDIR", "C:/Windows")) / "Fonts"
ARQUIVO_FONTE = "segoeui.ttf"
ARQUIVO_FONTE_NEGRITO = "segoeuib.ttf"

_fontes = {}


def fonte(tamanho, negrito=False):
    """Fonte no tamanho pedido (em pixels), guardada para não abrir o arquivo toda vez."""

    chave = (int(tamanho), negrito)

    if chave not in _fontes:

        arquivo = PASTA_FONTES / (ARQUIVO_FONTE_NEGRITO if negrito else ARQUIVO_FONTE)

        try:
            _fontes[chave] = ImageFont.truetype(str(arquivo), chave[0])
        except OSError:
            _fontes[chave] = ImageFont.load_default(size=chave[0])

    return _fontes[chave]


def _largura_texto(pincel, texto, letra):

    caixa = pincel.textbbox((0, 0), texto, font=letra)

    return caixa[2] - caixa[0]


def _cortar(pincel, texto, letra, largura_maxima):
    """Encurta o texto com "…" até caber na largura."""

    if _largura_texto(pincel, texto, letra) <= largura_maxima:
        return texto

    while texto and _largura_texto(pincel, texto + "…", letra) > largura_maxima:
        texto = texto[:-1]

    return texto + "…"


def vazio(largura, altura, cores, texto, tamanho_letra=14):
    """Quadro com uma mensagem no meio (ex.: "Nenhum evento no período")."""

    imagem = Image.new("RGB", (max(1, largura), max(1, altura)), cores["fundo"])
    pincel = ImageDraw.Draw(imagem)

    letra = fonte(tamanho_letra)

    pincel.text((largura / 2, altura / 2), texto, fill=cores["texto_suave"], font=letra, anchor="mm")

    return imagem


def barras_horizontais(itens, largura, altura, cores, texto_do_valor=str, maximo=None, tamanho_letra=14):
    """
    Uma barra deitada por item, com o rótulo à esquerda e o valor no fim.

    itens          -> lista de (rótulo, valor, cor da barra ou None = cores["barra"])
    texto_do_valor -> como escrever o valor (ex.: lambda v: f"{v:.0f}%")
    maximo         -> valor da barra cheia (None = o maior valor)
    """

    if not itens:
        return vazio(largura, altura, cores, "Sem dados no período", tamanho_letra)

    imagem = Image.new("RGB", (max(1, largura), max(1, altura)), cores["fundo"])
    pincel = ImageDraw.Draw(imagem)

    letra = fonte(tamanho_letra)
    letra_valor = fonte(tamanho_letra, negrito=True)

    maximo = maximo or max(valor for _, valor, _ in itens) or 1

    # Coluna dos rótulos: um terço da largura, no máximo
    coluna_rotulo = min(int(largura * 0.34), max(_largura_texto(pincel, rotulo, letra) for rotulo, _, _ in itens) + 24)
    coluna_valor = max(_largura_texto(pincel, texto_do_valor(valor), letra_valor) for _, valor, _ in itens) + 12

    espaco_barra = max(10, largura - coluna_rotulo - coluna_valor - 8)

    # Com poucos itens, as barras não se espalham pela altura toda
    altura_linha = min(altura / len(itens), tamanho_letra * 3.2)
    grossura = max(6, min(int(altura_linha * 0.55), tamanho_letra * 2))

    for posicao, (rotulo, valor, cor) in enumerate(itens):

        meio = int(altura_linha * (posicao + 0.5))

        pincel.text(
            (coluna_rotulo - 10, meio),
            _cortar(pincel, rotulo, letra, coluna_rotulo - 12),
            fill=cores["texto"],
            font=letra,
            anchor="rm",
        )

        # Trilho (o fundo da barra) e a barra em si
        x0 = coluna_rotulo
        x1 = x0 + espaco_barra

        pincel.rounded_rectangle((x0, meio - grossura // 2, x1, meio + grossura // 2), radius=grossura // 3, fill=cores["grade"])

        comprimento = int(espaco_barra * min(1.0, valor / maximo)) if maximo else 0

        if comprimento > 0:
            pincel.rounded_rectangle(
                (x0, meio - grossura // 2, x0 + max(comprimento, grossura // 2), meio + grossura // 2),
                radius=grossura // 3,
                fill=cor or cores["barra"],
            )

        pincel.text((x1 + 8, meio), texto_do_valor(valor), fill=cores["texto"], font=letra_valor, anchor="lm")

    return imagem


def barras_verticais(itens, largura, altura, cores, rotulo_a_cada=1, tamanho_letra=13):
    """
    Uma barra em pé por item, com linhas de grade e o rótulo embaixo.

    itens         -> lista de (rótulo, valor, cor da barra ou None)
    rotulo_a_cada -> escreve o rótulo de 1 em 1, de 3 em 3... (para não amontoar)
    """

    if not itens or not any(valor for _, valor, _ in itens):
        return vazio(largura, altura, cores, "Sem dados no período", tamanho_letra)

    imagem = Image.new("RGB", (max(1, largura), max(1, altura)), cores["fundo"])
    pincel = ImageDraw.Draw(imagem)

    letra = fonte(tamanho_letra)

    maior = max(valor for _, valor, _ in itens)

    # Topo do eixo: um número "redondo" acima do maior valor
    degrau = max(1, -(-maior // 4))
    topo = degrau * -(-maior // degrau)

    margem_esquerda = _largura_texto(pincel, str(topo), letra) + 12
    margem_baixo = tamanho_letra + 12
    margem_cima = tamanho_letra // 2 + 4

    altura_util = altura - margem_baixo - margem_cima
    largura_util = largura - margem_esquerda - 4

    def y(valor):
        return margem_cima + altura_util * (1 - valor / topo)

    # Linhas de grade e números do eixo
    for valor in range(0, topo + 1, degrau):

        pincel.line((margem_esquerda, y(valor), largura - 4, y(valor)), fill=cores["grade"], width=1)
        pincel.text((margem_esquerda - 6, y(valor)), str(valor), fill=cores["texto_suave"], font=letra, anchor="rm")

    passo = largura_util / len(itens)
    grossura = max(2, min(int(passo * 0.65), 48))

    for posicao, (rotulo, valor, cor) in enumerate(itens):

        centro = margem_esquerda + passo * (posicao + 0.5)

        if valor:
            pincel.rounded_rectangle(
                (centro - grossura / 2, y(valor), centro + grossura / 2, y(0)),
                radius=min(4, grossura // 3),
                fill=cor or cores["barra"],
            )

        if posicao % rotulo_a_cada == 0:
            pincel.text((centro, altura - 4), rotulo, fill=cores["texto_suave"], font=letra, anchor="mb")

    return imagem


# ============================================================
# OS QUATRO GRÁFICOS DOS INDICADORES
# ============================================================

TITULOS_DOS_GRAFICOS = {
    "faltas": "EPIs que mais faltam",
    "areas": "Conformidade por área",
    "dias": "Irregulares por dia",
    "horas": "Irregulares por hora do dia",
}


def graficos_dos_indicadores(indicadores, largura, altura, cores, tamanho_letra=13):
    """
    Desenha os quatro gráficos dos indicadores, cada um com largura x altura.

    cores também precisa de "sucesso" e "perigo": a conformidade de uma
    área fica verde se atingir config.META_CONFORMIDADE, vermelha se não.

    Devolve {chave: imagem}, com as chaves de TITULOS_DOS_GRAFICOS.
    """

    from safetech import config

    faltas = [(nome, vezes, cores["perigo"]) for nome, vezes in indicadores.faltas_por_epi]

    areas = [
        (
            nome,
            ok / eventos * 100,
            cores["sucesso"] if ok / eventos >= config.META_CONFORMIDADE else cores["perigo"],
        )
        for nome, eventos, ok in indicadores.por_area
    ]

    # "25/11" é o bastante embaixo de cada dia
    dias = [(f"{dia[8:10]}/{dia[5:7]}", eventos - ok, cores["perigo"]) for dia, eventos, ok in indicadores.por_dia]

    horas = [(f"{hora}h", irregulares, cores["perigo"]) for hora, (_, irregulares) in enumerate(indicadores.por_hora)]

    rotulo_dias = max(1, -(-len(dias) // 8))

    return {
        "faltas": barras_horizontais(faltas, largura, altura, cores, tamanho_letra=tamanho_letra),
        "areas": barras_horizontais(
            areas, largura, altura, cores, texto_do_valor=lambda valor: f"{valor:.0f}%", maximo=100, tamanho_letra=tamanho_letra
        ),
        "dias": barras_verticais(dias, largura, altura, cores, rotulo_a_cada=rotulo_dias, tamanho_letra=tamanho_letra),
        "horas": barras_verticais(horas, largura, altura, cores, rotulo_a_cada=3, tamanho_letra=tamanho_letra),
    }
