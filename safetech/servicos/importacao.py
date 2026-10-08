"""
Importação de imagens para o dataset de treino.

Além de capturar pela câmera, dá para aproveitar imagens que já
existem: arquivos salvos no computador ou uma imagem copiada (Ctrl+C
numa foto, captura de tela, "copiar imagem" do navegador).

Este módulo só ABRE as imagens e as entrega no formato do OpenCV
(matriz BGR). Recortar as pessoas e gravar com os rótulos continua
sendo feito pelos mesmos módulos usados na captura pela câmera.
"""

import numpy as np
from PIL import Image, ImageGrab, ImageOps


# Extensões oferecidas na janela de escolha de arquivo
EXTENSOES = "*.jpg *.jpeg *.png *.bmp *.webp *.avif *.gif"


def _para_bgr(imagem_pil):
    """Converte uma imagem do Pillow para a matriz BGR usada pelo OpenCV."""

    # Fotos de celular guardam a rotação num campo à parte (EXIF);
    # sem aplicar, a imagem entraria deitada no dataset.
    imagem_pil = ImageOps.exif_transpose(imagem_pil)

    rgb = np.array(imagem_pil.convert("RGB"))

    # Inverte a ordem dos canais (RGB -> BGR). A cópia garante uma
    # matriz contínua na memória, que é o que o OpenCV espera.
    return rgb[:, :, ::-1].copy()


def abrir_arquivo(caminho):
    """
    Abre um arquivo de imagem. Devolve a matriz BGR, ou None se o
    arquivo não for uma imagem que o programa consiga ler.

    Usa o Pillow (e não cv2.imread) porque ele lida com acentos no
    caminho do arquivo e com mais formatos.
    """

    try:

        with Image.open(caminho) as imagem:
            return _para_bgr(imagem)

    except (OSError, ValueError, SyntaxError):
        return None


def ler_area_de_transferencia():
    """
    Lê o que foi copiado (Ctrl+C) e devolve (imagens, falhas):

        imagens -> lista de matrizes BGR
        falhas  -> quantos itens copiados não puderam ser lidos

    Aceita os dois casos comuns: uma IMAGEM copiada (captura de tela,
    "copiar imagem") e ARQUIVOS copiados no Explorador de Arquivos.
    Sem nada aproveitável, devolve ([], 0).
    """

    try:
        conteudo = ImageGrab.grabclipboard()

    except (OSError, NotImplementedError):
        return [], 0

    # Imagem copiada diretamente
    if isinstance(conteudo, Image.Image):
        return [_para_bgr(conteudo)], 0

    # Lista de arquivos copiados
    if isinstance(conteudo, list):

        imagens = [abrir_arquivo(caminho) for caminho in conteudo]

        lidas = [imagem for imagem in imagens if imagem is not None]

        return lidas, len(imagens) - len(lidas)

    return [], 0
