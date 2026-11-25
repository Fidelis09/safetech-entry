# ============================================================
# GERA O "SafeTech Entry.exe" (PyInstaller)
# ============================================================
#
# Rodar da pasta do projeto, no PowerShell:
#
#     powershell -ExecutionPolicy Bypass -File instalador\gerar_exe.ps1
#
# Leva vários minutos (o TensorFlow é grande) e o resultado ocupa cerca
# de 1 GB: a pasta dist\SafeTech Entry\. Ela pode ser copiada para
# outro computador Windows, que NÃO precisa ter o Python instalado.
#
# Antes de rodar: o programa precisa estar funcionando com
# "python app.py" (mesmas bibliotecas do requirements.txt), e o modelo
# do corpo (YOLOX) precisa estar em modelos\ se for usar a vigilância.
# ============================================================

$ErrorActionPreference = "Stop"

# O mesmo Python que roda o projeto (o da Microsoft Store, neste computador)
$python = "python"

Write-Host "1/3 Instalando o PyInstaller (versao fixa, como o resto do projeto)..."
& $python -m pip install "pyinstaller==6.11.1"

Write-Host "2/3 Gerando o icone..."
& $python instalador\criar_atalho.py --so-icone

Write-Host "3/3 Montando a pasta do programa (demora)..."
& $python -m PyInstaller instalador\safetech.spec --noconfirm --distpath dist --workpath build

Write-Host ""
Write-Host "Pronto: dist\SafeTech Entry\SafeTech Entry.exe"
