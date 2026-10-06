"""
Interface gráfica do SafeTech Entry (Tkinter).

    tema.py                  -> cores, fontes e estilos (visual centralizado)
    painel_monitoramento.py  -> vídeo, status, controles e coleta de dataset
    painel_auditoria.py      -> indicadores, filtros, tabela e foto de evidência
    janela_principal.py      -> monta a janela e liga a interface aos serviços

Os painéis só cuidam de MOSTRAR coisas e avisar a janela principal
quando o usuário faz algo (por meio de funções recebidas no construtor).
Eles não conhecem câmera, modelo nem auditoria.
"""
