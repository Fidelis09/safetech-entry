"""
Ícones desenhados pelo próprio programa (sem arquivos de imagem).

    desenhar_escudo    -> a marca do SafeTech (escudo com um "visto"):
                          janela, barra de tarefas, atalho, celular
    desenhar_icone_epi -> o desenho de cada EPI (capacete, óculos, colete,
                          luvas): telão, chips da fiscalização, evento
                          selecionado e relatório

Ficam no núcleo porque só desenham (Pillow): a tela, os relatórios e o
painel web usam os mesmos desenhos, e isso dá identidade visual.

Cada ícone é desenhado 4 vezes maior e depois reduzido, para as bordas
ficarem suaves. Um EPI sem desenho próprio (acrescentado depois em
config.EPIS) ganha um círculo com a inicial do nome: nunca fica sem ícone.
"""

from PIL import Image, ImageDraw, ImageFont

from safetech.nucleo.epis import nome_do_epi


# Cores do escudo quando quem chama não escolhe (as do tema escuro)
COR_ESCUDO = "#3b82f6"
COR_ESCUDO_SOMBRA = "#2563eb"


def desenhar_escudo(tamanho=64, cor=COR_ESCUDO, cor_sombra=COR_ESCUDO_SOMBRA, fundo=None):
    """
    A marca do SafeTech: escudo com um "visto" branco (imagem PIL RGBA).

    fundo -> cor de fundo (ex.: para o ícone do celular, que não pode
             ser transparente); None = transparente
    """

    grande = tamanho * 4

    imagem = Image.new("RGBA", (grande, grande), fundo or (0, 0, 0, 0))
    pincel = ImageDraw.Draw(imagem)

    # Com fundo, o escudo fica um pouco menor, com margem em volta
    margem = 0.12 if fundo else 0.0
    escala = 1 - 2 * margem

    def p(x, y):
        return ((margem + x * escala) * grande, (margem + y * escala) * grande)

    escudo = [
        p(0.50, 0.04), p(0.88, 0.17), p(0.88, 0.48),
        p(0.80, 0.70), p(0.50, 0.96), p(0.20, 0.70),
        p(0.12, 0.48), p(0.12, 0.17),
    ]

    pincel.polygon(escudo, fill=cor)

    # Faixa mais escura na metade direita: dá volume ao escudo
    pincel.polygon([p(0.50, 0.04), p(0.88, 0.17), p(0.88, 0.48), p(0.80, 0.70), p(0.50, 0.96)], fill=cor_sombra)

    pincel.line([p(0.31, 0.50), p(0.45, 0.64), p(0.71, 0.36)], fill="white", width=int(grande * 0.09 * escala), joint="curve")

    return imagem.resize((tamanho, tamanho), Image.LANCZOS)


def desenhar_icone_epi(chave, tamanho, cor="white"):
    """Ícone do EPI (imagem PIL RGBA, quadrada, fundo transparente)."""

    grande = tamanho * 4

    imagem = Image.new("RGBA", (grande, grande), (0, 0, 0, 0))
    pincel = ImageDraw.Draw(imagem)

    # Medidas relativas: o desenho é o mesmo em qualquer tamanho
    def p(x, y):
        return (x * grande, y * grande)

    def caixa(x0, y0, x1, y1):
        return (x0 * grande, y0 * grande, x1 * grande, y1 * grande)

    traco = max(2, int(grande * 0.05))

    desenho = DESENHOS.get(chave)

    if desenho is not None:
        desenho(pincel, p, caixa, cor, traco, grande)
    else:
        _generico(pincel, caixa, cor, traco, grande, nome_do_epi(chave))

    return imagem.resize((tamanho, tamanho), Image.LANCZOS)


# ============================================================
# UM DESENHO POR EPI
# ============================================================

def _capacete(pincel, p, caixa, cor, traco, grande):

    # Cúpula (meia elipse) e a aba larga embaixo
    pincel.pieslice(caixa(0.16, 0.22, 0.84, 0.86), 180, 360, fill=cor)
    pincel.rounded_rectangle(caixa(0.06, 0.52, 0.94, 0.64), radius=grande * 0.04, fill=cor)

    # Friso no meio da cúpula (recortado: transparente)
    pincel.rounded_rectangle(caixa(0.45, 0.18, 0.55, 0.52), radius=grande * 0.03, fill=(0, 0, 0, 0))
    pincel.rounded_rectangle(caixa(0.47, 0.2, 0.53, 0.5), radius=grande * 0.02, fill=cor)


def _oculos(pincel, p, caixa, cor, traco, grande):

    # Duas lentes, a ponte entre elas e as hastes
    pincel.rounded_rectangle(caixa(0.08, 0.36, 0.44, 0.66), radius=grande * 0.08, outline=cor, width=traco)
    pincel.rounded_rectangle(caixa(0.56, 0.36, 0.92, 0.66), radius=grande * 0.08, outline=cor, width=traco)

    pincel.arc(caixa(0.42, 0.38, 0.58, 0.52), 200, 340, fill=cor, width=traco)

    pincel.line([p(0.08, 0.44), p(0.02, 0.38)], fill=cor, width=traco)
    pincel.line([p(0.92, 0.44), p(0.98, 0.38)], fill=cor, width=traco)


def _colete(pincel, p, caixa, cor, traco, grande):

    # Corpo do colete com a gola em V e as cavas dos braços
    pincel.polygon(
        [
            p(0.3, 0.1), p(0.42, 0.1), p(0.5, 0.36), p(0.58, 0.1), p(0.7, 0.1),
            p(0.84, 0.3), p(0.84, 0.92), p(0.16, 0.92), p(0.16, 0.3),
        ],
        fill=cor,
    )

    # Faixas refletivas (recortadas: transparentes)
    for y in (0.56, 0.74):
        pincel.rectangle(caixa(0.16, y, 0.84, y + 0.06), fill=(0, 0, 0, 0))

    # Divisão das duas metades (o fecho)
    pincel.line([p(0.5, 0.38), p(0.5, 0.92)], fill=(0, 0, 0, 0), width=max(2, traco // 2))


def _luvas(pincel, p, caixa, cor, traco, grande):

    # Palma e punho
    pincel.rounded_rectangle(caixa(0.28, 0.42, 0.74, 0.8), radius=grande * 0.1, fill=cor)
    pincel.rounded_rectangle(caixa(0.3, 0.78, 0.72, 0.94), radius=grande * 0.03, fill=cor)
    pincel.line([p(0.3, 0.79), p(0.72, 0.79)], fill=(0, 0, 0, 0), width=max(2, traco // 2))

    # Quatro dedos
    for x0, topo in ((0.28, 0.2), (0.4, 0.1), (0.52, 0.12), (0.64, 0.22)):
        pincel.rounded_rectangle(caixa(x0, topo, x0 + 0.1, 0.55), radius=grande * 0.05, fill=cor)

    # Polegar, inclinado para fora
    pincel.polygon([p(0.3, 0.52), p(0.12, 0.38), p(0.07, 0.44), p(0.26, 0.68)], fill=cor)
    pincel.ellipse(caixa(0.05, 0.34, 0.16, 0.46), fill=cor)


def _generico(pincel, caixa, cor, traco, grande, nome):
    """EPI sem desenho próprio: círculo com a inicial do nome."""

    pincel.ellipse(caixa(0.08, 0.08, 0.92, 0.92), outline=cor, width=traco)

    try:
        letra = ImageFont.truetype("segoeuib.ttf", int(grande * 0.5))
    except OSError:
        letra = ImageFont.load_default(size=int(grande * 0.5))

    pincel.text((grande / 2, grande / 2), (nome or "?")[0].upper(), fill=cor, font=letra, anchor="mm")


# Chave do EPI (como em config.EPIS) -> função que o desenha
DESENHOS = {
    "capacete": _capacete,
    "oculos": _oculos,
    "colete": _colete,
    "luvas": _luvas,
}
