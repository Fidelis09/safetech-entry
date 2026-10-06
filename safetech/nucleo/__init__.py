"""
Núcleo do SafeTech Entry: a parte "inteligente" do sistema.

    tipos.py          -> estruturas de dados trocadas entre os módulos
    detector.py       -> acha as pessoas no frame (detector de rosto YuNet)
    rastreador.py     -> mantém a identidade de cada pessoa entre os frames
    classificador.py  -> modelo de EPI (MobileNetV2): com_epi / sem_epi
    decisao.py        -> regras que transformam classificações em liberado/negado
    anotacao.py       -> desenha caixas e rótulos sobre a imagem

Nada aqui conhece a interface gráfica nem a câmera: são peças que
recebem imagens/dados e devolvem resultados, fáceis de testar isoladas.
"""
