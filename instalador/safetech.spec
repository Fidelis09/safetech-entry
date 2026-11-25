# ============================================================
# RECEITA DO PYINSTALLER PARA O SAFETECH ENTRY
# ============================================================
#
# Gera uma PASTA (dist/SafeTech Entry/) com o SafeTech Entry.exe e tudo
# de que ele precisa (Python, TensorFlow, OpenCV, os modelos). Essa
# pasta pode ser copiada para outro computador Windows, sem instalar o
# Python. Não use diretamente: rode o instalador/gerar_exe.ps1.
#
# Pasta (e não um .exe único) de propósito: com o TensorFlow, um .exe
# único teria mais de 1 GB e levaria muito tempo para abrir (ele se
# descompacta a cada abertura).
#
# Os dados que o programa grava (auditoria, logs, preferencias.json)
# ficam DENTRO da pasta gerada: copie-a para um lugar em que o usuário
# possa escrever (ex.: Documentos), não para "Arquivos de Programas".
# ============================================================

from pathlib import Path

PROJETO = Path(SPECPATH).parent

analise = Analysis(
    [str(PROJETO / "app.py")],
    pathex=[str(PROJETO)],
    datas=[
        # Os modelos (EPI, rosto, corpo) e a página do painel web
        (str(PROJETO / "modelos"), "modelos"),
        (str(PROJETO / "safetech" / "web" / "painel.html"), "safetech/web"),
    ],
    # Módulos que o PyInstaller não acha sozinho (importados dentro de funções)
    hiddenimports=["safetech.nucleo.classificador", "serial.tools.list_ports"],
    excludes=["pytest", "matplotlib"],
    noarchive=False,
)

pacote = PYZ(analise.pure)

executavel = EXE(
    pacote,
    analise.scripts,
    [],
    exclude_binaries=True,
    name="SafeTech Entry",
    icon=str(PROJETO / "instalador" / "safetech.ico"),
    # Sem janela preta de console
    console=False,
)

pasta = COLLECT(
    executavel,
    analise.binaries,
    analise.datas,
    name="SafeTech Entry",
)
