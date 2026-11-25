"""
Data e hora dos eventos, com o fuso horário (padrão ISO 8601).

Antes, a auditoria gravava só "2026-11-24 14:10:32". Sem o fuso, não dá
para saber a que horário real isso corresponde quando o log é levado
para outro computador, comparado com outro sistema ou usado num
relatório para outra cidade. Agora cada evento é gravado assim:

    2026-11-25T09:18:51-03:00
    |          |        +-- fuso: 3 horas a menos que o horário universal (UTC)
    |          +----------- hora local
    +---------------------- data

Na TELA continua aparecendo do jeito fácil de ler ("2026-11-25 09:18:51")
e o fuso aparece onde faz diferença (relatório e planilha exportada).

Logs gravados antes, SEM fuso, continuam valendo: todas as funções
daqui aceitam os dois formatos.
"""

from datetime import datetime


# Jeito de mostrar na tela e nas planilhas (sem o "T" e sem o fuso)
FORMATO_TELA = "%Y-%m-%d %H:%M:%S"

# Jeito de mostrar no relatório (dia/mês/ano, como se lê no Brasil)
FORMATO_BRASILEIRO = "%d/%m/%Y %H:%M:%S"


def agora():
    """Data e hora de agora, já com o fuso horário deste computador."""

    return datetime.now().astimezone()


def agora_iso() -> str:
    """Agora no padrão ISO 8601 com fuso, ex.: "2026-11-25T09:18:51-03:00"."""

    return agora().isoformat(timespec="seconds")


def ler(texto):
    """
    Converte o texto gravado em datetime (com fuso, se o texto tiver).

    Aceita o formato novo ("2026-11-25T09:18:51-03:00") e o antigo
    ("2026-11-24 14:10:32"). Devolve None se o texto não for uma data.
    """

    try:
        return datetime.fromisoformat(texto)
    except (TypeError, ValueError):
        return None


def para_exibir(texto) -> str:
    """ "2026-11-25T09:18:51-03:00" -> "2026-11-25 09:18:51" (como foi visto no local)."""

    momento = ler(texto)

    return momento.strftime(FORMATO_TELA) if momento else str(texto)


def fuso(texto) -> str:
    """ "2026-11-25T09:18:51-03:00" -> "-03:00"; formato antigo (sem fuso) -> ""."""

    momento = ler(texto)

    if momento is None or momento.utcoffset() is None:
        return ""

    minutos = int(momento.utcoffset().total_seconds() // 60)

    sinal = "-" if minutos < 0 else "+"

    horas, resto = divmod(abs(minutos), 60)

    return f"{sinal}{horas:02d}:{resto:02d}"


def para_relatorio(texto) -> str:
    """ "25/11/2026 09:18:51 (UTC-03:00)"; sem fuso, só a data e a hora."""

    momento = ler(texto)

    if momento is None:
        return str(texto)

    deslocamento = fuso(texto)

    legivel = momento.strftime(FORMATO_BRASILEIRO)

    return f"{legivel} (UTC{deslocamento})" if deslocamento else legivel


def data(texto) -> str:
    """ "2026-11-25" do evento (os 10 primeiros caracteres valem nos dois formatos)."""

    return str(texto)[:10]


def hora(texto):
    """Hora do dia (0 a 23) do evento, ou None se o texto não for uma data."""

    momento = ler(texto)

    return momento.hour if momento else None


def ler_data_digitada(texto):
    """
    Data escrita por uma pessoa -> "AAAA-MM-DD", ou None se não for uma data.

    Aceita "25/11/2026", "25-11-2026", "25.11.2026" e "2026-11-25".
    """

    texto = str(texto).strip()

    for formato in ("%d/%m/%Y", "%d-%m-%Y", "%d.%m.%Y", "%Y-%m-%d"):

        try:
            return datetime.strptime(texto, formato).date().isoformat()
        except ValueError:
            continue

    return None
