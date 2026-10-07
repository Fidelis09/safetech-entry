"""
SafeTech Entry - teste do modelo com uma imagem de arquivo.

Para usar:

    python reconhecer.py                 (abre uma janela para escolher a imagem)
    python reconhecer.py foto.jpg        (analisa a imagem informada)

Faz com a imagem exatamente o que o aplicativo faz com cada frame da
webcam: localiza as pessoas, avalia cada EPI de cada uma e mostra o
resultado. É útil para conferir o modelo depois de um treino, sem
precisar da câmera.
"""

import sys

import cv2

from safetech import config
from safetech.nucleo import epis
from safetech.nucleo.classificador import ClassificadorEPI
from safetech.nucleo.detector import DetectorPessoas


def escolher_imagem():
    """Abre a janela de seleção de arquivo; devolve o caminho ou None."""

    from tkinter import Tk
    from tkinter.filedialog import askopenfilename

    janela = Tk()
    janela.withdraw()
    janela.attributes("-topmost", True)

    caminho = askopenfilename(
        title="Escolha uma imagem",
        filetypes=[
            ("Imagens", "*.jpg *.jpeg *.png *.bmp"),
            ("Todos os arquivos", "*.*"),
        ],
    )

    janela.destroy()

    return caminho or None


def principal():

    caminho = sys.argv[1] if len(sys.argv) > 1 else escolher_imagem()

    if not caminho:
        print("Nenhuma imagem selecionada.")
        return

    imagem = cv2.imread(caminho)

    if imagem is None:
        print(f"Não foi possível abrir a imagem: {caminho}")
        return

    if not epis.epis_do_modelo():
        print("Nenhum modelo encontrado em 'modelos/'. Execute o treinar.py primeiro.")
        return

    print("Carregando a IA...")

    classificador = ClassificadorEPI()
    detector = DetectorPessoas()

    if not classificador.por_epi:
        print("Aviso: usando o modelo antigo, que só avalia o conjunto completo.")

    # ------------------------------------------------------
    # Mesma sequência do aplicativo: detectar -> recortar -> classificar
    # ------------------------------------------------------

    caixas = detector.detectar(imagem)

    if not caixas:
        print("Nenhuma pessoa encontrada: analisando a imagem inteira.")
        altura, largura = imagem.shape[:2]
        caixas = [(0, 0, largura, altura)]

    recortes = [imagem[y1:y2, x1:x2] for x1, y1, x2, y2 in caixas]

    resultados = classificador.classificar_lote(recortes)

    limiar = config.LIMIAR_CONFIANCA_PADRAO

    print()
    print("=" * 44)
    print(f"RESULTADO (limiar de confiança: {limiar * 100:.0f}%)")
    print("=" * 44)

    for numero, (caixa, probabilidades) in enumerate(zip(caixas, resultados), start=1):

        print()
        print(f"Pessoa {numero} (caixa {caixa})")

        for chave, probabilidade in zip(classificador.epis, probabilidades):

            situacao = "USANDO" if probabilidade >= limiar else "sem usar"

            print(f"  {epis.nome_do_epi(chave):<14} {probabilidade * 100:6.2f}%   {situacao}")


if __name__ == "__main__":
    principal()
