"""
Cria o atalho "SafeTech Entry" na área de trabalho (Windows).

Com o atalho, o programa abre com dois cliques, sem terminal e sem
janela preta: ele usa o "pythonw" (o Python sem console) e já abre na
pasta do projeto. O ícone é o escudo do SafeTech.

Rodar uma vez, de dentro da pasta do projeto:

    python instalador\\criar_atalho.py

Também gera o instalador\\safetech.ico, usado pelo atalho e pelo .exe
(veja gerar_exe.ps1). Para só gerar o ícone: --so-icone
"""

import subprocess
import sys
from pathlib import Path


PASTA_PROJETO = Path(__file__).resolve().parent.parent
ARQUIVO_ICONE = Path(__file__).resolve().parent / "safetech.ico"

NOME_ATALHO = "SafeTech Entry"

# Tamanhos guardados dentro do .ico (o Windows escolhe o melhor para cada lugar)
TAMANHOS_ICONE = [(16, 16), (24, 24), (32, 32), (48, 48), (64, 64), (128, 128), (256, 256)]


def gerar_icone():
    """Desenha o escudo do programa e o grava como .ico."""

    sys.path.insert(0, str(PASTA_PROJETO))

    from safetech.interface.tema import desenhar_icone

    desenhar_icone(256).save(ARQUIVO_ICONE, format="ICO", sizes=TAMANHOS_ICONE)

    return ARQUIVO_ICONE


def achar_pythonw():
    """O Python "sem janela preta" ao lado do Python que está rodando este script."""

    pasta = Path(sys.executable).parent

    for nome in ("pythonw.exe", f"pythonw{sys.version_info.major}.{sys.version_info.minor}.exe", "pythonw3.exe"):

        if (pasta / nome).exists():
            return pasta / nome

    # Sem pythonw: o atalho funciona, só que com uma janela de console junto
    return Path(sys.executable)


def criar_atalho():

    icone = gerar_icone()
    pythonw = achar_pythonw()

    # O atalho (.lnk) é criado pelo próprio Windows, via PowerShell. A
    # pasta "Área de trabalho" é perguntada ao Windows (ela pode estar no
    # OneDrive, com outro nome).
    comando = f"""
$area = [Environment]::GetFolderPath('Desktop')
$atalho = (New-Object -ComObject WScript.Shell).CreateShortcut((Join-Path $area '{NOME_ATALHO}.lnk'))
$atalho.TargetPath = '{pythonw}'
$atalho.Arguments = '"{PASTA_PROJETO / "app.py"}"'
$atalho.WorkingDirectory = '{PASTA_PROJETO}'
$atalho.IconLocation = '{icone}'
$atalho.Description = 'Controle de acesso e fiscalização de EPI'
$atalho.Save()
Write-Output (Join-Path $area '{NOME_ATALHO}.lnk')
"""

    resultado = subprocess.run(
        ["powershell", "-NoProfile", "-ExecutionPolicy", "Bypass", "-Command", comando],
        capture_output=True,
        text=True,
        check=False,
    )

    if resultado.returncode != 0:
        print("Não foi possível criar o atalho:")
        print(resultado.stderr)
        return 1

    print("Atalho criado:", resultado.stdout.strip())
    print("Abre com:", pythonw)

    return 0


if __name__ == "__main__":

    if "--so-icone" in sys.argv:
        print("Ícone gerado:", gerar_icone())
        sys.exit(0)

    sys.exit(criar_atalho())
