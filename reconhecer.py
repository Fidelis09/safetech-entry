"""
SafeTech Entry - teste do modelo com uma imagem de arquivo.

Para usar:

    python reconhecer.py                 (abre uma janela para escolher a imagem)
    python reconhecer.py foto.jpg        (analisa a imagem informada)

Faz com a imagem exatamente o que o aplicativo faz com cada frame da
webcam: localiza as pessoas, classifica cada uma e mostra o resultado.
É útil para conferir o modelo depois de um treino, sem precisar da câmera.
"""

import sys

import cv2

from safetech import config
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

    print("Carregando a IA...")

    classificador = ClassificadorEPI()
    detector = DetectorPessoas()

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

    print()
    print("=" * 40)
    print("RESULTADO")
    print("=" * 40)

    for numero, (caixa, probabilidades) in enumerate(zip(caixas, resultados), start=1):

        indice = int(probabilidades.argmax())

        classe = classificador.classes[indice]
        confianca = float(probabilidades[indice])

        liberado = (
            classe == config.CLASSE_LIBERA_ACESSO
            and confianca >= config.LIMIAR_CONFIANCA_PADRAO
        )

        print()
        print(f"Pessoa {numero} (caixa {caixa})")
        print(f"  Classe:    {classe.upper()}")
        print(f"  Confiança: {confianca * 100:.2f}%")
        print(f"  Acesso:    {'LIBERADO' if liberado else 'NEGADO'}")

        for nome, probabilidade in zip(classificador.classes, probabilidades):
            print(f"    {nome}: {probabilidade * 100:.2f}%")


if __name__ == "__main__":
    principal()
