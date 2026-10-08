"""
Escolha do detector de pessoas.

O sistema tem duas formas de encontrar as pessoas na imagem, e o
usuário alterna entre elas na tela:

    modo "rosto" -> detector_rosto.py (YuNet). Rápido. Para catraca:
                    pessoa perto da câmera e de frente.

    modo "corpo" -> detector_corpo.py (YOLOX). Mais lento. Para câmera
                    geral: várias pessoas, de costas, de lado, andando
                    e se cruzando.

Os dois detectores têm a mesma "cara" (o método detectar devolve uma
lista de caixas), então o resto do sistema não precisa saber qual está
em uso.
"""

from safetech import config


def modo_disponivel(modo) -> bool:
    """
    True se o arquivo de modelo do modo existe.

    Não carrega nada: serve para a tela saber, na hora de abrir, quais
    opções pode oferecer.
    """

    if modo == config.MODO_CORPO:
        return config.ARQUIVO_MODELO_CORPO.exists()

    return config.ARQUIVO_MODELO_ROSTO.exists()


def criar_detector(modo):
    """Cria (e carrega) o detector do modo pedido."""

    # Importados aqui para só carregar o que for usado
    if modo == config.MODO_CORPO:

        from safetech.nucleo.detector_corpo import DetectorCorpo

        return DetectorCorpo()

    from safetech.nucleo.detector_rosto import DetectorRosto

    return DetectorRosto()


def criar_detectores() -> dict:
    """
    Cria um detector para cada modo, pronto para a troca na tela ser
    imediata: {modo: detector}.

    O modo rosto sempre entra (sem o arquivo dele, o detector trata a
    cena inteira como uma pessoa). O modo corpo só entra se o modelo
    estiver na pasta.
    """

    detectores = {config.MODO_ROSTO: criar_detector(config.MODO_ROSTO)}

    if modo_disponivel(config.MODO_CORPO):
        detectores[config.MODO_CORPO] = criar_detector(config.MODO_CORPO)

    return detectores
