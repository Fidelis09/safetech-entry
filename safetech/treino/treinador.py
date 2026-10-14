"""
Treinamento do reconhecedor de EPI (modelo por equipamento).

Técnica: TRANSFER LEARNING. Em vez de treinar uma rede do zero (o que
exigiria milhares de imagens), usamos a MobileNetV2, que já aprendeu a
"enxergar" com milhões de fotos, e treinamos apenas uma pequena camada
final.

Diferença em relação a um classificador comum: aqui a resposta não é
"uma classe entre várias", e sim VÁRIAS respostas independentes de sim
ou não, uma por equipamento (classificação multirrótulo):

    capacete? 0.97    óculos? 0.12    colete? 0.88    luvas? 0.05

Por isso a camada final usa a função SIGMOID (cada saída vai de 0 a 1
sozinha, sem depender das outras) em vez de softmax.

Etapas:

    1) ler e validar o dataset rotulado;
    2) separar treino e validação;
    3) montar a rede (MobileNetV2 congelada + camada de saída);
    4) treinar;
    5) avaliar, mostrando a acurácia de cada EPI;
    6) salvar o modelo e a lista de EPIs.
"""

import json

import numpy as np
import tensorflow as tf

from safetech import config
from safetech.nucleo.epis import nome_do_epi
from safetech.servicos.dataset import ColetorDataset


# ============================================================
# 1) LEITURA E VALIDAÇÃO DO DATASET
# ============================================================

def ler_dataset(coletor=None):
    """
    Lê a planilha de rótulos.

    Devolve (caminhos, rotulos):
        caminhos -> lista com o caminho de cada imagem
        rotulos  -> matriz [imagem, epi] de 0 e 1, colunas na ordem de config.EPIS
    """

    coletor = coletor or ColetorDataset()

    exemplos = coletor.ler_rotulos()

    caminhos = [str(caminho) for caminho, _ in exemplos]

    rotulos = np.array(
        [rotulos for _, rotulos in exemplos],
        dtype=np.float32,
    ).reshape(len(exemplos), len(config.EPIS))

    return caminhos, rotulos


def validar_dataset(rotulos):
    """
    Confere se dá para treinar.

    Interrompe o programa se faltar o essencial e devolve uma lista de
    avisos (problemas que não impedem o treino, mas pioram o resultado).
    """

    total = len(rotulos)

    if total < config.MINIMO_IMAGENS_TREINO:

        raise SystemExit(
            f"ERRO: há {total} imagens rotuladas, e o mínimo para treinar é "
            f"{config.MINIMO_IMAGENS_TREINO}.\n\n"
            "Abra o aplicativo (python app.py), ligue a câmera e use a área\n"
            "'Coleta de imagens': marque o que a pessoa está usando e salve."
        )

    avisos = []

    for posicao, chave in enumerate(config.EPIS):

        usando = int(rotulos[:, posicao].sum())
        sem_usar = total - usando

        # O modelo só aprende um equipamento se vir os DOIS casos:
        # gente usando e gente sem usar.
        if usando == 0 or sem_usar == 0:

            caso = "usando" if usando == 0 else "sem usar"

            raise SystemExit(
                f"ERRO: não há nenhuma imagem com a pessoa {caso} "
                f"'{nome_do_epi(chave)}'.\n"
                "O modelo precisa de exemplos dos dois casos para cada EPI."
            )

        if min(usando, sem_usar) < config.MINIMO_EXEMPLOS_POR_CASO:

            avisos.append(
                f"{nome_do_epi(chave)}: {usando} usando e {sem_usar} sem usar. "
                f"O ideal é pelo menos {config.MINIMO_EXEMPLOS_POR_CASO} de cada."
            )

    return avisos


# ============================================================
# 2) SEPARAÇÃO EM TREINO E VALIDAÇÃO
# ============================================================

def _ler_imagem(caminho, rotulos):
    """Abre uma imagem do disco e a deixa no tamanho que a rede espera."""

    largura, altura = config.TAMANHO_IMAGEM

    imagem = tf.io.decode_image(
        tf.io.read_file(caminho),
        channels=3,
        expand_animations=False,
    )

    # resize devolve valores de 0 a 255 em ponto flutuante, que é
    # exatamente o que o modelo recebe durante o uso.
    imagem = tf.image.resize(imagem, (altura, largura))

    return imagem, rotulos


def separar_dataset(caminhos, rotulos):
    """
    Embaralha e divide as imagens: a maior parte para treinar e uma
    parte guardada para validar (imagens que a rede não vê no treino).

    A semente fixa faz a divisão ser sempre a mesma.
    """

    ordem = np.random.default_rng(config.SEMENTE_TREINO).permutation(len(caminhos))

    quantidade_validacao = max(1, int(len(caminhos) * config.FRACAO_VALIDACAO))

    indices_validacao = ordem[:quantidade_validacao]
    indices_treino = ordem[quantidade_validacao:]

    def montar(indices, embaralhar):

        conjunto = tf.data.Dataset.from_tensor_slices(
            ([caminhos[indice] for indice in indices], rotulos[indices])
        )

        if embaralhar:
            # Ordem diferente a cada época ajuda a rede a generalizar
            conjunto = conjunto.shuffle(len(indices), seed=config.SEMENTE_TREINO)

        return (
            conjunto
            .map(_ler_imagem, num_parallel_calls=tf.data.AUTOTUNE)
            .batch(config.LOTE_TREINO)
            # prefetch: prepara o próximo lote enquanto a rede treina no atual
            .prefetch(tf.data.AUTOTUNE)
        )

    return montar(indices_treino, True), montar(indices_validacao, False)


# ============================================================
# 3) MONTAGEM DA REDE
# ============================================================

def calcular_pesos_das_classes(rotulos):
    """
    Devolve (peso_usando, peso_sem_usar): um peso por EPI para cada caso.

    O caso menos frequente recebe o peso maior, de modo que "usando" e
    "sem usar" contribuam igual para o erro de cada EPI. Um EPI com
    metade das imagens em cada caso fica com peso 1 nos dois.
    """

    total = len(rotulos)

    usando = rotulos.sum(axis=0)
    sem_usar = total - usando

    return total / (2 * usando), total / (2 * sem_usar)


def criar_perda_ponderada(peso_usando, peso_sem_usar):
    """
    Entropia cruzada binária em que cada caso de cada EPI tem seu peso.

    O class_weight do Keras não atende saídas multirrótulo (uma por EPI),
    por isso o peso é aplicado aqui, dentro da própria perda.
    """

    peso_usando = tf.constant(peso_usando, dtype=tf.float32)
    peso_sem_usar = tf.constant(peso_sem_usar, dtype=tf.float32)

    def perda_ponderada(esperado, previsto):

        esperado = tf.cast(esperado, tf.float32)

        # Evita log(0)
        previsto = tf.clip_by_value(previsto, 1e-7, 1 - 1e-7)

        erro = -(
            peso_usando * esperado * tf.math.log(previsto)
            + peso_sem_usar * (1 - esperado) * tf.math.log(1 - previsto)
        )

        return tf.reduce_mean(erro, axis=-1)

    return perda_ponderada


def construir_modelo(quantidade_epis, pesos_das_classes=None):
    """
    pesos_das_classes -> (peso_usando, peso_sem_usar) de
                         calcular_pesos_das_classes; None = sem balanceamento.
    """

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
    # e só a camada de saída é treinada.
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

    # Um neurônio por EPI. SIGMOID faz cada saída ser uma probabilidade
    # independente: a pessoa pode estar com vários EPIs, com um ou com
    # nenhum. (Softmax obrigaria as saídas a somarem 1, o que só serve
    # quando existe uma única resposta certa.)
    saida = tf.keras.layers.Dense(
        quantidade_epis,
        activation="sigmoid",
        name="epis",
    )(x)

    modelo = tf.keras.Model(inputs=entrada, outputs=saida)

    # binary_crossentropy trata cada saída como uma pergunta de sim ou
    # não separada, que é exatamente o nosso caso
    if pesos_das_classes is None:
        perda = "binary_crossentropy"
    else:
        perda = criar_perda_ponderada(*pesos_das_classes)

    modelo.compile(
        optimizer=tf.keras.optimizers.Adam(learning_rate=config.TAXA_APRENDIZADO),
        loss=perda,
        metrics=["binary_accuracy"],
    )

    return modelo


# ============================================================
# 5) AVALIAÇÃO POR EPI
# ============================================================

def acuracia_por_epi(modelo, validacao):
    """
    Devolve {chave: acurácia} na validação, um valor por EPI.

    A acurácia geral pode esconder um EPI que a rede não aprendeu;
    olhando um por um dá para saber qual precisa de mais imagens.
    """

    esperado = np.concatenate([rotulos.numpy() for _, rotulos in validacao])

    previsto = modelo.predict(validacao, verbose=0) >= 0.5

    acertos = (previsto == (esperado >= 0.5)).mean(axis=0)

    return {chave: float(acertos[posicao]) for posicao, chave in enumerate(config.EPIS)}


# ============================================================
# EXECUÇÃO COMPLETA
# ============================================================

def _titulo(texto):

    print()
    print("=" * 56)
    print(texto)
    print("=" * 56)
    print()


def executar():

    _titulo("TREINAMENTO DO RECONHECEDOR DE EPI (SafeTech)")

    print("Imagens: ", config.PASTA_IMAGENS_DATASET)
    print("Rótulos: ", config.ARQUIVO_ROTULOS)

    # ------------------------------------------------------
    # 1) LEITURA E VALIDAÇÃO
    # ------------------------------------------------------

    caminhos, rotulos = ler_dataset()

    avisos = validar_dataset(rotulos)

    print()
    print(f"Imagens rotuladas: {len(caminhos)}")
    print()

    for posicao, chave in enumerate(config.EPIS):

        usando = int(rotulos[:, posicao].sum())

        print(f"  {nome_do_epi(chave):<10} {usando:>4} usando   {len(caminhos) - usando:>4} sem usar")

    if avisos:

        print()
        print("ATENÇÃO, poucos exemplos (o treino continua, mas pode errar mais):")

        for aviso in avisos:
            print("  -", aviso)

    # ------------------------------------------------------
    # 2) SEPARAÇÃO
    # ------------------------------------------------------

    treino, validacao = separar_dataset(caminhos, rotulos)

    # ------------------------------------------------------
    # 3) MODELO
    # ------------------------------------------------------

    _titulo("MONTANDO A REDE (MobileNetV2)")

    print("Na primeira execução pode ser necessário baixar os pesos da rede.")
    print()

    pesos = calcular_pesos_das_classes(rotulos) if config.BALANCEAR_CLASSES else None

    modelo = construir_modelo(len(config.EPIS), pesos)

    modelo.summary()

    # ------------------------------------------------------
    # 4) TREINAMENTO
    # ------------------------------------------------------

    _titulo(f"TREINANDO (até {config.EPOCAS_TREINO} épocas)")

    # Para quando o erro na validação para de melhorar e devolve o
    # modelo ao melhor momento, não ao da última época.
    parada_antecipada = tf.keras.callbacks.EarlyStopping(
        monitor="val_loss",
        patience=config.PACIENCIA_TREINO,
        restore_best_weights=True,
    )

    modelo.fit(
        treino,
        validation_data=validacao,
        epochs=config.EPOCAS_TREINO,
        callbacks=[parada_antecipada],
    )

    # ------------------------------------------------------
    # 5) AVALIAÇÃO
    # ------------------------------------------------------

    _titulo("AVALIANDO (imagens que a rede não viu no treino)")

    for chave, acuracia in acuracia_por_epi(modelo, validacao).items():
        print(f"  {nome_do_epi(chave):<10} {acuracia * 100:6.2f}% de acerto")

    # ------------------------------------------------------
    # 6) SALVAMENTO
    # ------------------------------------------------------

    config.PASTA_MODELOS.mkdir(parents=True, exist_ok=True)

    modelo.save(config.ARQUIVO_MODELO_EPIS)

    # A ordem das saídas do modelo é a ordem desta lista. O aplicativo
    # lê daqui, e não do config.py, para nunca trocar um EPI por outro.
    with open(config.ARQUIVO_EPIS, "w", encoding="utf-8") as arquivo:
        json.dump(list(config.EPIS), arquivo, ensure_ascii=False, indent=4)

    _titulo("TREINAMENTO FINALIZADO")

    print("Modelo salvo em:", config.ARQUIVO_MODELO_EPIS)
    print("EPIs salvos em: ", config.ARQUIVO_EPIS)
    print()
    print("Agora você pode abrir o programa com: python app.py")
