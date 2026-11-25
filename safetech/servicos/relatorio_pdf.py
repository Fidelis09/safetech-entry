"""
Relatório de indicadores em PDF (para imprimir ou mandar por e-mail).

Página 1: período, os números principais (eventos, conformidade, EPI que
mais falta, horário crítico) e os quatro gráficos dos indicadores.
Páginas seguintes: a lista dos eventos IRREGULARES do período (quem,
onde, quando e o que faltava).

As páginas são desenhadas como imagem (Pillow) e salvas juntas num PDF:
não precisa de nenhuma biblioteca a mais. As cores são as de papel
branco, boas para imprimir, qualquer que seja o tema da tela.

O relatório DIÁRIO é este mesmo relatório com o período de um dia só;
o programa pode gerá-lo sozinho (veja gerar_diario e
config.RELATORIO_DIARIO_AUTOMATICO).
"""

import logging
from datetime import date, timedelta

from PIL import Image, ImageDraw

from safetech import config
from safetech.nucleo import horario
from safetech.servicos import graficos, indicadores as modulo_indicadores


log = logging.getLogger(__name__)


# Cores do papel (claras, boas para imprimir)
CORES_PAPEL = {
    "fundo": "#ffffff",
    "texto": "#111827",
    "texto_suave": "#5b6676",
    "grade": "#e5e9ef",
    "barra": "#2563eb",
    "sucesso": "#16a34a",
    "perigo": "#dc2626",
    "cartao": "#f4f6f9",
    "destaque": "#2563eb",
}

# Tamanho da folha A4 em milímetros
LARGURA_A4_MM = 210
ALTURA_A4_MM = 297
MM_POR_POLEGADA = 25.4


def _tamanho_pagina():

    pontos = config.RESOLUCAO_PDF_DPI / MM_POR_POLEGADA

    return int(LARGURA_A4_MM * pontos), int(ALTURA_A4_MM * pontos)


def _medida(milimetros):
    """Milímetros da folha em pixels da imagem."""

    return int(milimetros * config.RESOLUCAO_PDF_DPI / MM_POR_POLEGADA)


def texto_do_periodo(inicio, fim):

    def br(dia):
        return f"{dia[8:10]}/{dia[5:7]}/{dia[0:4]}"

    if inicio and fim and inicio == fim:
        return f"Dia {br(inicio)}"

    if inicio and fim:
        return f"De {br(inicio)} a {br(fim)}"

    return "Todo o histórico"


# ============================================================
# GERAR
# ============================================================

def gerar(registros, caminho, inicio=None, fim=None, area=None):
    """
    Grava o PDF dos registros do período (e da área, se dada) em 'caminho'.

    Devolve o caminho. Pode lançar OSError (ex.: o PDF está aberto).
    """

    if area:
        registros = [registro for registro in registros if registro.area == area]

    dados = modulo_indicadores.calcular(registros, inicio, fim)

    irregulares = [
        registro
        for registro in registros
        if registro.liberado != "SIM"
        and (inicio is None or horario.data(registro.timestamp) >= inicio)
        and (fim is None or horario.data(registro.timestamp) <= fim)
    ]

    titulo_periodo = texto_do_periodo(inicio, fim) + (f" · Área: {area}" if area else " · Todas as áreas")

    paginas = [_pagina_resumo(dados, titulo_periodo)]
    paginas += _paginas_irregulares(irregulares, titulo_periodo)

    caminho.parent.mkdir(parents=True, exist_ok=True)

    paginas[0].save(
        caminho,
        "PDF",
        resolution=config.RESOLUCAO_PDF_DPI,
        save_all=True,
        append_images=paginas[1:],
        title="Relatório de conformidade de EPI",
        author=config.NOME_PRODUTO,
    )

    log.info("Relatório PDF gerado: %s (%d evento(s))", caminho, dados.total)

    return caminho


def gerar_diario(registros, dia=None, pasta=None):
    """
    Relatório de UM dia (padrão: ontem) em <pasta>/AAAA-MM-DD.pdf.

    Devolve o caminho, ou None se não houve eventos naquele dia (não
    gera um relatório vazio).
    """

    dia = dia or (date.today() - timedelta(days=1)).isoformat()
    pasta = pasta or config.PASTA_RELATORIOS_DIARIOS

    if not any(horario.data(registro.timestamp) == dia for registro in registros):
        return None

    return gerar(registros, pasta / f"{dia}.pdf", inicio=dia, fim=dia)


# ============================================================
# PÁGINAS
# ============================================================

def _pagina_em_branco():

    pagina = Image.new("RGB", _tamanho_pagina(), CORES_PAPEL["fundo"])

    return pagina, ImageDraw.Draw(pagina)


def _cabecalho(pincel, largura, titulo_periodo, numero_pagina=None):
    """Faixa do topo: título, período e quando o relatório foi gerado. Devolve onde ela termina."""

    margem = _medida(15)

    pincel.text((margem, _medida(14)), "Relatório de conformidade de EPI", fill=CORES_PAPEL["texto"], font=graficos.fonte(_medida(7), True))

    pincel.text((margem, _medida(24)), f"{config.NOME_PRODUTO} · {titulo_periodo}", fill=CORES_PAPEL["texto_suave"], font=graficos.fonte(_medida(4)))

    gerado = f"Gerado em {horario.para_relatorio(horario.agora_iso())}"

    if numero_pagina:
        gerado += f" · página {numero_pagina}"

    pincel.text((largura - margem, _medida(25)), gerado, fill=CORES_PAPEL["texto_suave"], font=graficos.fonte(_medida(3)), anchor="ra")

    pincel.line((margem, _medida(33), largura - margem, _medida(33)), fill=CORES_PAPEL["grade"], width=_medida(0.5))

    return _medida(40)


def _pagina_resumo(dados, titulo_periodo):

    pagina, pincel = _pagina_em_branco()
    largura, altura = pagina.size

    margem = _medida(15)

    topo = _cabecalho(pincel, largura, titulo_periodo)

    # ---------------- os quatro números ----------------

    taxa = f"{dados.taxa * 100:.0f}%" if dados.taxa is not None else "-"

    mais_falta = dados.epi_que_mais_falta
    hora = dados.hora_critica

    cartoes = [
        ("Eventos", str(dados.total), f"{dados.irregulares} irregular(es)"),
        ("Conformidade", taxa, f"meta: {config.META_CONFORMIDADE * 100:.0f}%"),
        ("EPI que mais falta", mais_falta[0] if mais_falta else "-", f"{mais_falta[1]} vez(es)" if mais_falta else "nenhuma falta"),
        ("Horário crítico", f"{hora}h às {hora + 1}h" if hora is not None else "-", "mais irregulares" if hora is not None else "sem irregulares"),
    ]

    espaco = _medida(4)
    largura_cartao = (largura - 2 * margem - espaco * (len(cartoes) - 1)) / len(cartoes)
    altura_cartao = _medida(26)

    for posicao, (titulo, valor, rodape) in enumerate(cartoes):

        x = margem + posicao * (largura_cartao + espaco)

        pincel.rounded_rectangle((x, topo, x + largura_cartao, topo + altura_cartao), radius=_medida(2), fill=CORES_PAPEL["cartao"])

        pincel.text((x + _medida(4), topo + _medida(3)), titulo, fill=CORES_PAPEL["texto_suave"], font=graficos.fonte(_medida(3.2)))
        pincel.text((x + _medida(4), topo + _medida(8)), valor, fill=CORES_PAPEL["texto"], font=graficos.fonte(_medida(7), True))
        pincel.text((x + _medida(4), topo + _medida(19)), rodape, fill=CORES_PAPEL["texto_suave"], font=graficos.fonte(_medida(3)))

    # ---------------- os quatro gráficos (2 x 2) ----------------

    topo += altura_cartao + _medida(10)

    largura_grafico = int((largura - 2 * margem - espaco) / 2)
    altura_grafico = int((altura - topo - _medida(20)) / 2 - _medida(10))

    imagens = graficos.graficos_dos_indicadores(dados, largura_grafico, altura_grafico, CORES_PAPEL, tamanho_letra=_medida(3.2))

    for posicao, chave in enumerate(graficos.TITULOS_DOS_GRAFICOS):

        linha, coluna = divmod(posicao, 2)

        x = margem + coluna * (largura_grafico + espaco)
        y = topo + linha * (altura_grafico + _medida(14))

        pincel.text((x, y), graficos.TITULOS_DOS_GRAFICOS[chave], fill=CORES_PAPEL["texto"], font=graficos.fonte(_medida(4), True))

        pagina.paste(imagens[chave], (x, y + _medida(7)))

    return pagina


# Colunas da lista de irregulares: (título, como obter do registro, largura em mm)
COLUNAS_IRREGULARES = [
    ("Data e hora", lambda r: horario.para_exibir(r.timestamp), 38),
    ("Área", lambda r: r.area, 32),
    ("Pessoa", lambda r: r.pessoa, 18),
    ("Setor", lambda r: r.setor, 38),
    ("Faltando", lambda r: r.faltando or "-", 54),
]


def _paginas_irregulares(irregulares, titulo_periodo):
    """Uma ou mais páginas com a tabela dos eventos irregulares (nenhuma se não houver)."""

    paginas = []

    por_pagina = config.LINHAS_POR_PAGINA_PDF

    for inicio in range(0, len(irregulares), por_pagina):

        pagina, pincel = _pagina_em_branco()
        largura, _ = pagina.size

        margem = _medida(15)

        y = _cabecalho(pincel, largura, titulo_periodo, numero_pagina=len(paginas) + 2)

        pincel.text((margem, y), f"Eventos irregulares ({len(irregulares)})", fill=CORES_PAPEL["texto"], font=graficos.fonte(_medida(4.5), True))

        y += _medida(10)

        letra = graficos.fonte(_medida(3))
        letra_titulo = graficos.fonte(_medida(3), True)
        altura_linha = _medida(6.5)

        # Títulos das colunas
        x = margem

        for titulo, _, largura_mm in COLUNAS_IRREGULARES:
            pincel.text((x, y), titulo, fill=CORES_PAPEL["texto_suave"], font=letra_titulo)
            x += _medida(largura_mm)

        y += altura_linha

        for posicao, registro in enumerate(irregulares[inicio: inicio + por_pagina]):

            # Listras: o olho segue a linha até o fim
            if posicao % 2 == 0:
                pincel.rectangle((margem - _medida(1), y - _medida(1), largura - margem, y + altura_linha - _medida(1.5)), fill=CORES_PAPEL["cartao"])

            x = margem

            for _, valor, largura_mm in COLUNAS_IRREGULARES:

                texto = graficos._cortar(pincel, str(valor(registro)), letra, _medida(largura_mm - 2))

                pincel.text((x, y), texto, fill=CORES_PAPEL["texto"], font=letra)

                x += _medida(largura_mm)

            y += altura_linha

        paginas.append(pagina)

    return paginas
