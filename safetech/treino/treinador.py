"""
Treinamento do reconhecedor de EPI.

Técnica: TRANSFER LEARNING. Em vez de treinar uma rede do zero (o que
exigiria milhares de imagens), usamos a MobileNetV2, que já aprendeu a
"enxergar" com milhões de fotos, e treinamos apenas uma pequena camada
final que aprende a diferença entre as nossas classes.

Etapas:

    1) validar o dataset (pastas e quantidade de imagens);
    2) carregar as imagens, separando treino e validação;
    3) montar a rede (MobileNetV2 congelada + camada de classificação);
    4) treinar;
    5) avaliar na validação;
    6) salvar o modelo e a lista de classes.
"""

import json

import tensorflow as tf

from safetech import config


# ============================================================
# 1) VALIDAÇÃO DO DATASET
# ============================================================

def contar_imagens_por_classe(pasta_dataset):
    """Devolve {nome_da_classe: quantidade_de_imagens}, uma entrada por subpasta."""

    contagem = {}

    for pasta in sorted(pasta_dataset.iterdir()):

        if not pasta.is_dir():
            continue

        contagem[pasta.name] = sum(
            1
            for arquivo in pasta.iterdir()
            if arquivo.is_file() and arquivo.suffix.lower() in config.EXTENSOES_IMAGEM
        )

    return contagem


def validar_dataset(pasta_dataset):
    """
    Confere se dá para treinar. Devolve a contagem por classe ou
    interrompe o programa com uma explicação do que está faltando.
    """

    if not pasta_dataset.exists():

        raise SystemExit(
            "ERRO: a pasta 'dataset' não foi encontrada.\n\n"
            "Crie esta estrutura:\n\n"
            "dataset\n"
            "  com_epi\n"
            "  sem_epi"
        )

    contagem = contar_imagens_por_classe(pasta_dataset)

    if len(contagem) < 2:

        raise SystemExit(
            "ERRO: é necessário ter pelo menos DUAS classes "
            "(duas subpastas dentro de 'dataset').\n"
            f"Classes encontradas: {list(contagem)}"
        )

    classes_vazias = [nome for nome, quantidade in contagem.items() if quantidade == 0]

    if classes_vazias:

        raise SystemExit(
            f"ERRO: estas classes não têm imagens válidas: {classes_vazias}\n"
            f"Formatos aceitos: {' '.join(sorted(config.EXTENSOES_IMAGEM))}"
        )

    return contagem


# ============================================================
# 2) CARREGAMENTO DAS IMAGENS
# ============================================================

def carregar_dataset(pasta_dataset):
    """
    Lê as imagens e separa em treino e validação.

    A mesma semente (seed) nas duas chamadas garante que nenhuma
    imagem caia nos dois conjuntos ao mesmo tempo.
    """

    opcoes = dict(
        validation_split=config.FRACAO_VALIDACAO,
        seed=config.SEMENTE_TREINO,
        image_size=config.TAMANHO_IMAGEM,
        batch_size=config.LOTE_TREINO,
    )

    treino = tf.keras.utils.image_dataset_from_directory(
        pasta_dataset, subset="training", **opcoes
    )

    validacao = tf.keras.utils.image_dataset_from_directory(
        pasta_dataset, subset="validation", **opcoes
    )

    # Os nomes das classes vêm dos nomes das subpastas, em ordem alfabética
    classes = treino.class_names

    # prefetch: prepara o próximo lote enquanto a rede treina no atual
    treino = treino.prefetch(buffer_size=tf.data.AUTOTUNE)
    validacao = validacao.prefetch(buffer_size=tf.data.AUTOTUNE)

    return treino, validacao, classes


# ============================================================
# 3) MONTAGEM DA REDE
# ============================================================

def construir_modelo(quantidade_classes):

    largura, altura = config.TAMANHO_IMAGEM

    # ------------------------------------------------------
    # DATA AUGMENTATION
    # ------------------------------------------------------
    #
    # Durante o treino, cada imagem é apresentada com pequenas
    # variações (espelhada, levemente girada, com um pouco de zoom).
    # Isso ajuda a rede a generalizar com poucas fotos. Fora do
    # treino estas camadas não fazem nada.
    # ------------------------------------------------------

    aumento_dados = tf.keras.Sequential([
        tf.keras.layers.RandomFlip("horizontal"),
        tf.keras.layers.RandomRotation(0.10),
        tf.keras.layers.RandomZoom(0.10),
    ])

    # ------------------------------------------------------
    # MOBILENETV2 PRÉ-TREINADA
    # ------------------------------------------------------
    #
    # include_top=False remove a camada final original (que
    # classificava 1000 categorias do ImageNet); a nossa entra no
    # lugar. Na primeira execução os pesos são baixados da internet.
    # ------------------------------------------------------

    modelo_base = tf.keras.applications.MobileNetV2(
        input_shape=(altura, largura, 3),
        include_top=False,
        weights="imagenet",
    )

    # Congela a MobileNetV2: o conhecimento que ela já tem é preservado
    # e só a camada de classificação é treinada.
    modelo_base.trainable = False

    # ------------------------------------------------------
    # LIGAÇÃO DAS CAMADAS
    # ------------------------------------------------------

    entrada = tf.keras.Input(shape=(altura, largura, 3), name="imagem")

    x = aumento_dados(entrada)

    # Normalização exigida pela MobileNetV2. Como ela fica DENTRO do
    # modelo, quem usa o modelo depois não precisa normalizar nada.
    x = tf.keras.applications.mobilenet_v2.preprocess_input(x)

    # Extração de características (training=False mantém as camadas
    # internas da MobileNetV2 em modo de inferência)
    x = modelo_base(x, training=False)

    # Transforma os mapas de características em um único vetor
    x = tf.keras.layers.GlobalAveragePooling2D()(x)

    # Dropout: reduz o risco de a rede "decorar" as imagens de treino
    x = tf.keras.layers.Dropout(config.TAXA_DROPOUT)(x)

    # Um neurônio por classe; softmax converte os valores em probabilidades
    saida = tf.keras.layers.Dense(
        quantidade_classes,
        activation="softmax",
        name="classificacao",
    )(x)

    modelo = tf.keras.Model(inputs=entrada, outputs=saida)

    modelo.compile(
        optimizer=tf.keras.optimizers.Adam(learning_rate=config.TAXA_APRENDIZADO),
        loss="sparse_categorical_crossentropy",
        metrics=["accuracy"],
    )

    return modelo


# ============================================================
# EXECUÇÃO COMPLETA
# ============================================================

def _titulo(texto):

    print()
    print("=" * 52)
    print(texto)
    print("=" * 52)
    print()


def executar():

    _titulo("TREINAMENTO DO RECONHECEDOR DE EPI (SafeTech)")

    print("Dataset:", config.PASTA_DATASET)

    # ------------------------------------------------------
    # 1) VALIDAÇÃO
    # ------------------------------------------------------

    contagem = validar_dataset(config.PASTA_DATASET)

    print()
    print("Classes encontradas:")

    for nome, quantidade in contagem.items():

        print(f"  {nome}: {quantidade} imagens")

        if quantidade < config.MINIMO_IMAGENS_RECOMENDADO:
            print(
                f"    ATENÇÃO: poucas imagens. Para um resultado melhor, coloque "
                f"pelo menos {config.MINIMO_IMAGENS_RECOMENDADO}."
            )

    print(f"  Total: {sum(contagem.values())} imagens")

    # ------------------------------------------------------
    # 2) CARREGAMENTO
    # ------------------------------------------------------

    _titulo("CARREGANDO IMAGENS")

    treino, validacao, classes = carregar_dataset(config.PASTA_DATASET)

    print()
    print("Classes que a IA vai aprender:")

    for numero, classe in enumerate(classes):
        print(f"  {numero} = {classe}")

    # ------------------------------------------------------
    # 3) MODELO
    # ------------------------------------------------------

    _titulo("MONTANDO A REDE (MobileNetV2)")

    print("Na primeira execução pode ser necessário baixar os pesos da rede.")
    print()

    modelo = construir_modelo(len(classes))

    modelo.summary()

    # ------------------------------------------------------
    # 4) TREINAMENTO
    # ------------------------------------------------------

    _titulo(f"TREINANDO ({config.EPOCAS_TREINO} épocas)")

    modelo.fit(treino, validation_data=validacao, epochs=config.EPOCAS_TREINO)

    # ------------------------------------------------------
    # 5) AVALIAÇÃO
    # ------------------------------------------------------

    _titulo("AVALIANDO")

    _, acuracia = modelo.evaluate(validacao, verbose=0)

    print(f"Acurácia na validação: {acuracia * 100:.2f}%")

    # ------------------------------------------------------
    # 6) SALVAMENTO
    # ------------------------------------------------------

    config.PASTA_MODELOS.mkdir(parents=True, exist_ok=True)

    modelo.save(config.ARQUIVO_MODELO)

    with open(config.ARQUIVO_CLASSES, "w", encoding="utf-8") as arquivo:
        json.dump(classes, arquivo, ensure_ascii=False, indent=4)

    _titulo("TREINAMENTO FINALIZADO")

    print("Modelo salvo em: ", config.ARQUIVO_MODELO)
    print("Classes salvas em:", config.ARQUIVO_CLASSES)
    print()
    print("Agora você pode abrir o programa com: python app.py")
