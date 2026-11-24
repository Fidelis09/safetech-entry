"""
Capturas manuais: o botão "Capturar foto" da câmera de uma área.

Diferente da foto de evidência (que a análise grava sozinha quando a
decisão de alguém muda), a captura é do OPERADOR: ele vê algo na
câmera e quer guardar aquele momento (um incidente, uma situação para
mostrar depois). A captura não entra no log de auditoria.

A imagem salva é o frame do momento com as caixas das pessoas e o
mesmo carimbo das fotos de evidência (data, hora e área), em
config.PASTA_CAPTURAS.
"""

import re
from datetime import datetime

import cv2

from safetech import config
from safetech.nucleo import anotacao


def salvar(frame, estado, nome_area, pasta=None):
    """
    Grava a captura e devolve o caminho do arquivo.

    frame  -> imagem da câmera (não é alterada: desenha-se numa cópia)
    estado -> EstadoCena do momento (as caixas das pessoas)

    Pode lançar OSError (ex.: disco cheio, sem permissão na pasta).
    """

    pasta = pasta or config.PASTA_CAPTURAS
    pasta.mkdir(parents=True, exist_ok=True)

    agora = datetime.now()

    imagem = anotacao.desenhar_pessoas(frame.copy(), estado.pessoas, modo=estado.modo)

    carimbo = f"{config.NOME_PRODUTO} | {agora:%Y-%m-%d %H:%M:%S} | Area: {nome_area} | Captura manual"

    anotacao.carimbar(imagem, anotacao.sem_acentos(carimbo))

    caminho = pasta / f"{agora:%Y%m%d_%H%M%S}_{_nome_para_arquivo(nome_area)}.jpg"

    if not cv2.imwrite(str(caminho), imagem):
        raise OSError(f"não foi possível gravar {caminho}")

    return caminho


def _nome_para_arquivo(texto) -> str:
    """ "Área 2 / Portão" -> "Area_2_Portao": só letras, números e "_"."""

    simples = anotacao.sem_acentos(texto)

    return re.sub(r"[^A-Za-z0-9]+", "_", simples).strip("_") or "area"
