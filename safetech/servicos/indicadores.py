"""
Indicadores da auditoria: os números que o gerente quer ver de relance.

A partir dos eventos do log, calcula:

    - totais e taxa de conformidade do período;
    - o EPI que mais falta (e quantas vezes faltou cada um);
    - a conformidade de cada área;
    - a conformidade dia a dia;
    - os horários críticos (em que hora do dia há mais irregulares).

Só faz contas: não desenha nada. A janela de Indicadores e o relatório
em PDF usam este mesmo resultado, para mostrarem sempre os mesmos números.
"""

from collections import Counter
from dataclasses import dataclass
from datetime import date, timedelta

from safetech import config
from safetech.nucleo import horario


@dataclass(frozen=True)
class Indicadores:

    # Período considerado (datas "AAAA-MM-DD"; None = desde o começo / até hoje)
    inicio: str
    fim: str

    total: int
    conformes: int
    irregulares: int

    # (nome do EPI, vezes que faltou), do que mais falta para o que menos falta
    faltas_por_epi: tuple

    # (área, eventos, conformes), da área com mais eventos para a com menos
    por_area: tuple

    # (data "AAAA-MM-DD", eventos, conformes), um por dia, do mais antigo ao mais novo
    por_dia: tuple

    # 24 posições (0h a 23h): (eventos, irregulares)
    por_hora: tuple

    @property
    def taxa(self):
        """Conformidade de 0 a 1 (None sem eventos)."""

        return self.conformes / self.total if self.total else None

    @property
    def epi_que_mais_falta(self):
        """(nome, vezes) ou None se nada faltou."""

        return self.faltas_por_epi[0] if self.faltas_por_epi else None

    @property
    def hora_critica(self):
        """Hora do dia (0 a 23) com mais irregulares, ou None se não houve nenhum."""

        irregulares = [quantidade for _, quantidade in self.por_hora]

        if not any(irregulares):
            return None

        return irregulares.index(max(irregulares))


def calcular(registros, inicio=None, fim=None, dias_no_grafico=None):
    """
    Indicadores dos registros entre as datas 'inicio' e 'fim' (inclusive).

    inicio, fim     -> "AAAA-MM-DD" ou None (sem limite)
    dias_no_grafico -> quantos dias mostrar no gráfico dia a dia (dias
                       sem eventos aparecem com zero, para o gráfico não
                       "pular" dias)
    """

    dias_no_grafico = dias_no_grafico or config.DIAS_NO_GRAFICO_INDICADORES

    escolhidos = [
        registro
        for registro in registros
        if (inicio is None or horario.data(registro.timestamp) >= inicio)
        and (fim is None or horario.data(registro.timestamp) <= fim)
    ]

    conformes = sum(1 for registro in escolhidos if registro.liberado == "SIM")

    # ---------------- EPI que mais falta ----------------

    faltas = Counter()

    for registro in escolhidos:

        for nome in registro.faltando.split(","):

            if nome.strip():
                faltas[nome.strip()] += 1

    # ---------------- por área ----------------

    areas = {}

    for registro in escolhidos:

        eventos, ok = areas.get(registro.area, (0, 0))

        areas[registro.area] = (eventos + 1, ok + (registro.liberado == "SIM"))

    por_area = sorted(((nome, eventos, ok) for nome, (eventos, ok) in areas.items()), key=lambda item: -item[1])

    # ---------------- por dia (os últimos dias_no_grafico do período) ----------------

    ultimo = date.fromisoformat(fim) if fim else date.today()

    contagem_dia = {}

    for registro in escolhidos:

        dia = horario.data(registro.timestamp)

        eventos, ok = contagem_dia.get(dia, (0, 0))

        contagem_dia[dia] = (eventos + 1, ok + (registro.liberado == "SIM"))

    dias = [(ultimo - timedelta(days=atras)).isoformat() for atras in range(dias_no_grafico - 1, -1, -1)]

    # Um período mais curto que o gráfico (ex.: "Hoje") não mostra dias de fora dele
    if inicio:
        dias = [dia for dia in dias if dia >= inicio]

    por_dia = tuple((dia, *contagem_dia.get(dia, (0, 0))) for dia in dias)

    # ---------------- por hora do dia ----------------

    horas = [[0, 0] for _ in range(24)]

    for registro in escolhidos:

        hora = horario.hora(registro.timestamp)

        if hora is None:
            continue

        horas[hora][0] += 1

        if registro.liberado != "SIM":
            horas[hora][1] += 1

    return Indicadores(
        inicio=inicio,
        fim=fim,
        total=len(escolhidos),
        conformes=conformes,
        irregulares=len(escolhidos) - conformes,
        faltas_por_epi=tuple(faltas.most_common()),
        por_area=tuple(por_area),
        por_dia=por_dia,
        por_hora=tuple(tuple(hora) for hora in horas),
    )


def periodo(nome_do_periodo, hoje=None):
    """
    (inicio, fim) de um período de config.PERIODOS_AUDITORIA, ex.:
    "Últimos 7 dias" -> ("2026-11-19", "2026-11-25"). "Todo o histórico" -> (None, None).
    """

    hoje = hoje or date.today()

    dias = config.PERIODOS_AUDITORIA.get(nome_do_periodo)

    if dias is None:
        return None, None

    return (hoje - timedelta(days=dias)).isoformat(), hoje.isoformat()
