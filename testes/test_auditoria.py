"""
Serviço de auditoria (safetech/servicos/auditoria.py).

Regra central testada aqui: a auditoria NUNCA é apagada pelo programa.
Zerar arquiva; excluir uma linha move a linha e a foto para "excluidos".
"""

import csv

import numpy as np

from safetech.nucleo.tipos import ResultadoEPI
from safetech.servicos.auditoria import COLUNAS


FOTO = np.zeros((60, 80, 3), np.uint8)

ITENS = (
    ResultadoEPI("capacete", True, 0.95),
    ResultadoEPI("luvas", False, 0.12),
)


def registrar(auditoria, pessoa, liberado=False, foto=FOTO):

    return auditoria.registrar(
        evento="ENTRADA",
        identificador_pessoa=pessoa,
        setor="Canteiro de obras",
        exigidos=("capacete", "luvas"),
        itens=ITENS,
        faltando=() if liberado else ("luvas",),
        liberado=liberado,
        imagem_bgr=foto,
    )


def ler_csv(caminho):

    with open(caminho, newline="", encoding="utf-8") as arquivo:
        return list(csv.reader(arquivo))


# ============================================================
# GRAVAR E LER
# ============================================================

def test_registra_evento_com_foto_e_texto_legivel(auditoria):

    registro = registrar(auditoria, 3)

    assert registro.pessoa == "P003"
    assert registro.exigidos == "Capacete, Luvas"
    assert registro.faltando == "Luvas"
    assert registro.confiancas == "Capacete 95%, Luvas 12%"
    assert registro.liberado == "NAO"
    assert (auditoria.pasta_imagens / registro.imagem).exists()

    assert auditoria.carregar_historico() == [registro]


def test_evento_sem_foto(auditoria):

    registro = registrar(auditoria, 1, foto=None)

    assert registro.imagem == ""
    assert auditoria.carregar_historico() == [registro]


def test_log_de_formato_antigo_e_renomeado_e_nao_apagado(tmp_path):

    from safetech.servicos.auditoria import ServicoAuditoria

    log = tmp_path / "log_auditoria.csv"
    log.write_text("data,resultado\n2026-01-01,ok\n", encoding="utf-8")

    ServicoAuditoria(log, tmp_path / "imagens", tmp_path / "excluidos")

    antigos = list(tmp_path.glob("log_auditoria_formato_antigo_*.csv"))

    assert len(antigos) == 1
    assert "2026-01-01,ok" in antigos[0].read_text(encoding="utf-8")
    assert ler_csv(log) == [COLUNAS]


# ============================================================
# EXCLUIR UMA LINHA
# ============================================================

def test_excluir_move_linha_e_foto_para_excluidos(auditoria, tmp_path):

    registros = [registrar(auditoria, pessoa) for pessoa in (1, 2, 3)]

    assert auditoria.excluir(registros[1]) is True

    # Saiu do log principal...
    assert [r.pessoa for r in auditoria.carregar_historico()] == ["P001", "P003"]
    assert not (auditoria.pasta_imagens / registros[1].imagem).exists()

    # ...mas continua guardado, com a data da exclusão
    linhas = ler_csv(tmp_path / "excluidos" / "log_excluidos.csv")

    assert linhas[0] == COLUNAS + ["excluido_em"]
    assert linhas[1][:-1] == registros[1].como_linha()
    assert (tmp_path / "excluidos" / "imagens" / registros[1].imagem).exists()


def test_excluir_duas_vezes_nao_faz_nada_na_segunda(auditoria):

    registro = registrar(auditoria, 1)

    assert auditoria.excluir(registro) is True
    assert auditoria.excluir(registro) is False


def test_excluir_nao_deixa_arquivo_temporario(auditoria, tmp_path):

    auditoria.excluir(registrar(auditoria, 1))

    assert not list(tmp_path.glob("*.tmp"))


# ============================================================
# ZERAR
# ============================================================

def test_zerar_arquiva_tudo_e_comeca_vazio(auditoria, tmp_path):

    registrar(auditoria, 1)
    registrar(auditoria, 2)

    destino, eventos, fotos = auditoria.zerar()

    assert (eventos, fotos) == (2, 2)
    assert destino.parent == tmp_path / "arquivados"
    assert len(ler_csv(destino / "log_auditoria.csv")) == 3  # cabeçalho + 2
    assert len(list((destino / "imagens").iterdir())) == 2

    assert auditoria.carregar_historico() == []


def test_zerar_duas_vezes_no_mesmo_segundo(auditoria):
    """Bug encontrado por estes testes: a segunda pasta tinha o mesmo nome e dava erro."""

    registrar(auditoria, 1)
    primeira, *_ = auditoria.zerar()

    registrar(auditoria, 2)
    segunda, *_ = auditoria.zerar()

    assert segunda != primeira
    assert (segunda / "log_auditoria.csv").exists()


def test_zerar_vazio_nao_cria_arquivo(auditoria):

    assert auditoria.zerar() == (None, 0, 0)
