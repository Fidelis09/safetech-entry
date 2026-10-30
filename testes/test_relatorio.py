"""
Relatório de um evento da auditoria (safetech/servicos/relatorio.py).
"""

import numpy as np

from safetech.nucleo.tipos import ResultadoEPI
from safetech.servicos import relatorio


def registrar(auditoria, pessoa, setor="Canteiro de obras"):

    return auditoria.registrar(
        evento="ENTRADA",
        identificador_pessoa=pessoa,
        setor=setor,
        exigidos=("capacete", "luvas"),
        itens=(ResultadoEPI("capacete", True, 0.95), ResultadoEPI("luvas", False, 0.12)),
        faltando=("luvas",),
        liberado=False,
        imagem_bgr=np.zeros((60, 80, 3), np.uint8),
    )


def test_relatorio_tem_dados_foto_e_marca_exigidos(auditoria, tmp_path):

    registro = registrar(auditoria, 1)

    pasta = relatorio.salvar(registro, auditoria.pasta_imagens, pasta_relatorios=tmp_path / "rel")

    assert pasta.name.endswith("_P001")
    assert (pasta / "evidencia.jpg").exists()

    pagina = (pasta / "relatorio.html").read_text(encoding="utf-8")

    assert "ACESSO NEGADO - P001" in pagina
    assert "Canteiro de obras" in pagina
    assert "Luvas 12%" in pagina and "(exigido)" in pagina
    assert 'src="evidencia.jpg"' in pagina


def test_relatorio_copia_a_foto_sem_mexer_na_auditoria(auditoria, tmp_path):

    registro = registrar(auditoria, 1)

    relatorio.salvar(registro, auditoria.pasta_imagens, pasta_relatorios=tmp_path / "rel")

    assert (auditoria.pasta_imagens / registro.imagem).exists()
    assert auditoria.carregar_historico() == [registro]


def test_relatorio_inclui_outros_eventos_do_mesmo_momento(auditoria, tmp_path):

    principal = registrar(auditoria, 1)
    outro = registrar(auditoria, 2)

    pasta = relatorio.salvar(
        principal, auditoria.pasta_imagens, [outro], pasta_relatorios=tmp_path / "rel"
    )

    pagina = (pasta / "relatorio.html").read_text(encoding="utf-8")

    assert "Outros eventos no mesmo momento" in pagina
    assert "P002" in pagina
    assert (pasta / "outros" / outro.imagem).exists()


def test_texto_do_log_e_escapado_no_html(auditoria, tmp_path):
    """Um "<" no nome do setor não pode virar código HTML na página."""

    registro = registrar(auditoria, 1, setor="<script>alert(1)</script>")

    pasta = relatorio.salvar(registro, auditoria.pasta_imagens, pasta_relatorios=tmp_path / "rel")

    pagina = (pasta / "relatorio.html").read_text(encoding="utf-8")

    assert "<script>" not in pagina
    assert "&lt;script&gt;" in pagina


def test_salvar_duas_vezes_cria_outra_pasta(auditoria, tmp_path):

    registro = registrar(auditoria, 1)

    primeira = relatorio.salvar(registro, auditoria.pasta_imagens, pasta_relatorios=tmp_path / "rel")
    segunda = relatorio.salvar(registro, auditoria.pasta_imagens, pasta_relatorios=tmp_path / "rel")

    assert segunda != primeira
    assert segunda.name == primeira.name + "_2"
