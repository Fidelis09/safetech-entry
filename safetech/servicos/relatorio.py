"""
Relatório de um evento da auditoria (botão "Salvar relatório").

O usuário seleciona uma linha na tabela de auditoria e o programa monta
um relatório COMPLETO daquele momento: quem era a pessoa, o setor, o
que era exigido, o que faltava, a confiança de cada EPI, a decisão e a
foto de evidência. Os outros eventos registrados no mesmo instante
também entram, para mostrar o momento inteiro.

Cada relatório vira uma pasta própria em auditoria/relatorios/:

    2026-10-28_14-30-05_P003/
        relatorio.html   -> o relatório, para abrir no navegador
        evidencia.jpg    -> cópia da foto de evidência do evento
        outros/...       -> fotos dos outros eventos do mesmo momento

O HTML usa só caminhos relativos para as fotos: a pasta inteira pode
ser copiada ou enviada (compactada) e continua abrindo. A foto é
COPIADA, não movida: o log de auditoria continua intacto.
"""

import html
import shutil
from datetime import datetime

from safetech import config
from safetech.nucleo import modos


NOME_EVENTO = {
    "ENTRADA": "Primeira decisão sobre a pessoa",
    "MUDANCA": "Mudança de decisão",
}


# ============================================================
# GRAVAÇÃO
# ============================================================

def salvar(registro, pasta_imagens, outros_do_momento=(), pasta_relatorios=None):
    """
    Grava o relatório de um evento e devolve a pasta criada.

    registro          -> RegistroAuditoria da linha selecionada
    pasta_imagens     -> onde estão as fotos de evidência da auditoria
    outros_do_momento -> outros RegistroAuditoria do mesmo instante
    """

    # Lido aqui, e não como valor padrão do parâmetro, para os testes
    # poderem apontar config.PASTA_RELATORIOS para uma pasta temporária.
    if pasta_relatorios is None:
        pasta_relatorios = config.PASTA_RELATORIOS

    pasta = _pasta_nova(pasta_relatorios, registro)

    pasta.mkdir(parents=True)

    foto = _copiar_foto(registro, pasta_imagens, pasta, "evidencia.jpg")

    # Fotos dos outros eventos do mesmo momento, numa subpasta
    fotos_outros = []

    for outro in outros_do_momento:

        # Mesmo nome da foto original: dois eventos nunca coincidem
        fotos_outros.append(_copiar_foto(outro, pasta_imagens, pasta, f"outros/{outro.imagem}"))

    conteudo = _montar_html(registro, foto, list(zip(outros_do_momento, fotos_outros)))

    (pasta / "relatorio.html").write_text(conteudo, encoding="utf-8")

    return pasta


def _pasta_nova(pasta_relatorios, registro):
    """
    Pasta com a data e hora do EVENTO e a pessoa, ex.: 2026-10-28_14-30-05_P003.
    Se já existir (relatório salvo duas vezes), ganha um número.
    """

    momento = datetime.strptime(registro.timestamp, "%Y-%m-%d %H:%M:%S")

    base = f"{momento.strftime('%Y-%m-%d_%H-%M-%S')}_{registro.pessoa}"

    pasta = pasta_relatorios / base
    numero = 2

    while pasta.exists():
        pasta = pasta_relatorios / f"{base}_{numero}"
        numero += 1

    return pasta


def _copiar_foto(registro, pasta_imagens, pasta, relativo):
    """
    Copia a foto de evidência do evento para pasta/relativo.
    Devolve o caminho relativo (usado no HTML), ou None se não há foto.
    """

    if not registro.imagem:
        return None

    origem = pasta_imagens / registro.imagem

    if not origem.exists():
        return None

    destino = pasta / relativo

    destino.parent.mkdir(parents=True, exist_ok=True)

    shutil.copy2(origem, destino)

    return relativo


# ============================================================
# HTML
# ============================================================

def _resultado(registro):
    """
    (texto, classe CSS) da decisão do evento.

    O texto depende do modo em que o evento aconteceu: "ACESSO
    LIBERADO" / "ACESSO NEGADO" na catraca; "EM CONFORMIDADE" /
    "NÃO CONFORME" na vigilância.
    """

    textos = modos.textos(registro.modo)

    if registro.liberado == "SIM":
        return textos["faixa_ok"], "ok"

    return textos["faixa_irregular"], "negado"


def _lista_confiancas(registro) -> str:
    """
    A confiança de cada EPI, um por linha.

    No CSV ela vem como texto: "Capacete 97%, Luvas 12%". Os EPIs
    exigidos ganham a marca "(exigido)".
    """

    e = html.escape

    exigidos = {nome.strip() for nome in registro.exigidos.split(",") if nome.strip()}

    itens = []

    for parte in registro.confiancas.split(","):

        parte = parte.strip()

        if not parte:
            continue

        nome = parte.rsplit(" ", 1)[0]

        marca = ' <span class="exigido">(exigido)</span>' if nome in exigidos else ""

        itens.append(f"<div>{e(parte)}{marca}</div>")

    return "\n".join(itens) or "-"


def _montar_html(registro, foto, outros):

    e = html.escape

    texto_resultado, classe = _resultado(registro)

    momento = datetime.strptime(registro.timestamp, "%Y-%m-%d %H:%M:%S")

    dados = [
        ("Data e hora", momento.strftime("%d/%m/%Y %H:%M:%S")),
        ("Pessoa", registro.pessoa),
        ("Evento", NOME_EVENTO.get(registro.evento, registro.evento)),
        ("Setor", registro.setor or "-"),
        ("EPIs exigidos", registro.exigidos or "nenhum"),
        ("Faltando", registro.faltando or "nada"),
        ("Modo", modos.nome_do_modo(registro.modo)),
        ("Resultado", modos.resultado(registro.modo, registro.liberado == "SIM")),
        ("Arquivo da foto", registro.imagem or "-"),
    ]

    # Todo texto vindo do CSV passa por html.escape: assim um "<" num
    # nome de setor não quebra a página.
    linhas_dados = "\n".join(
        f"<tr><th>{e(titulo)}</th><td>{e(valor)}</td></tr>" for titulo, valor in dados
    )

    if foto:
        bloco_foto = f'<img class="foto" src="{e(foto)}" alt="Foto de evidência">'
    else:
        bloco_foto = '<p class="sub">Este evento não tem foto de evidência.</p>'

    if outros:

        linhas_outros = "\n".join(_linha_outro(outro, foto_outro) for outro, foto_outro in outros)

        bloco_outros = f"""
<h2>Outros eventos no mesmo momento</h2>
<table class="outros">
<tr><th>Foto</th><th>Pessoa</th><th>Resultado</th><th>Faltando</th><th>Confiança</th></tr>
{linhas_outros}
</table>"""

    else:
        bloco_outros = ""

    return f"""<!doctype html>
<html lang="pt-BR">
<head>
<meta charset="utf-8">
<title>Relatório SafeTech - {e(registro.pessoa)} - {e(momento.strftime("%d/%m/%Y %H:%M:%S"))}</title>
<style>
  body {{ font-family: Segoe UI, Arial, sans-serif; color: #1f2937; margin: 24px; max-width: {config.LARGURA_FOTO_RELATORIO}px; }}
  h1 {{ margin: 0 0 4px; font-size: 22px; }}
  h2 {{ margin: 28px 0 10px; font-size: 17px; }}
  .sub {{ color: #6b7280; margin: 0 0 18px; }}
  .faixa {{ padding: 12px 16px; border-radius: 6px; color: white; font-weight: 600; font-size: 18px; }}
  .faixa.ok {{ background: #16a34a; }}
  .faixa.negado {{ background: #dc2626; }}
  table {{ border-collapse: collapse; width: 100%; }}
  th, td {{ border-bottom: 1px solid #e5e7eb; padding: 8px; text-align: left; vertical-align: top; }}
  .dados th {{ width: 180px; color: #6b7280; font-weight: normal; }}
  .outros th {{ background: #f3f4f6; }}
  .foto {{ width: 100%; border: 1px solid #e5e7eb; }}
  .miniatura {{ max-width: 160px; border: 1px solid #e5e7eb; }}
  .ok {{ color: #15803d; font-weight: 600; }}
  .negado {{ color: #b91c1c; font-weight: 600; }}
  .exigido {{ font-size: 11px; color: #6b7280; }}
  footer {{ margin-top: 28px; color: #9ca3af; font-size: 12px; }}
</style>
</head>
<body>

<h1>Relatório de reconhecimento</h1>
<p class="sub">SafeTech Entry - evento da auditoria e o momento em que ele aconteceu</p>

<div class="faixa {classe}">{texto_resultado} - {e(registro.pessoa)}</div>

<h2>Dados do evento</h2>
<table class="dados">
{linhas_dados}
</table>

<h2>Confiança de cada EPI</h2>
{_lista_confiancas(registro)}

<h2>Foto de evidência</h2>
{bloco_foto}
{bloco_outros}

<footer>
  "Confiança" é a certeza do modelo de que a pessoa ESTÁ usando o equipamento
  (mediana das últimas classificações). Acima da confiança mínima, o EPI conta como presente.
  Relatório gerado em {datetime.now().strftime("%d/%m/%Y %H:%M:%S")}.
</footer>

</body>
</html>
"""


def _linha_outro(registro, foto) -> str:
    """Uma linha da tabela de outros eventos do mesmo momento."""

    e = html.escape

    texto, classe = _resultado(registro)

    miniatura = f'<img class="miniatura" src="{e(foto)}" alt="{e(registro.pessoa)}">' if foto else "-"

    return (
        f"<tr><td>{miniatura}</td>"
        f"<td><b>{e(registro.pessoa)}</b></td>"
        f'<td class="{classe}">{e(modos.resultado(registro.modo, registro.liberado == "SIM"))}</td>'
        f"<td>{e(registro.faltando or 'nada')}</td>"
        f"<td>{_lista_confiancas(registro)}</td></tr>"
    )
