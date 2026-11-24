# SafeTech Entry

Catraca inteligente com reconhecimento de EPI por visão computacional.

O programa usa a câmera (webcam ou câmera IP) para verificar, **equipamento por equipamento** (capacete, óculos, colete e luvas), o que cada pessoa na frente da câmera está usando. Você escolhe o setor que está sendo fiscalizado e o sistema cobra apenas os EPIs exigidos nele: num setor que só exige luvas, quem está de luvas passa. O acesso só é liberado quando todas as pessoas na imagem estão em conformidade, e cada decisão fica registrada em um log de auditoria, com foto de evidência.

Projeto acadêmico (desafio de segurança do trabalho). Esta etapa cobre apenas a parte de visão computacional; a confirmação por voz da Ordem de Serviço fica para uma etapa futura.

---

## Sumário

1. [Funcionalidades](#funcionalidades)
2. [Instalação](#instalação)
3. [Como usar](#como-usar)
4. [Painel web do gerente](#painel-web-do-gerente)
5. [Como funciona](#como-funciona)
6. [Estrutura do projeto](#estrutura-do-projeto)
7. [Coleta de imagens e re-treino](#coleta-de-imagens-e-re-treino)
8. [Auditoria](#auditoria)
9. [Configuração](#configuração)
10. [Desempenho](#desempenho)
11. [Testes](#testes)
12. [Solução de problemas](#solução-de-problemas)
13. [Limitações e próximos passos](#limitações-e-próximos-passos)

---

## Funcionalidades

- **Vídeo ao vivo** da webcam, fluido e ajustado ao tamanho da janela.
- **Câmera IP**: câmeras de segurança (`rtsp://`) ou o celular (`http://`) adicionadas pela própria tela, com reconexão automática quando a rede cai. A webcam USB também se reabre sozinha se o cabo falhar.
- **Legendas sobre o vídeo**, como num monitor de segurança: "● AO VIVO", nome da área, data e hora, resolução real, quadros por segundo, análises por segundo e pessoas na imagem.
- **Visão geral**: com duas áreas ou mais, todas lado a lado, cada uma com a sua situação colorida; clicar num quadro abre a aba da área.
- **Fotos de evidência carimbadas**: data e hora, área, pessoa e resultado gravados na própria foto.
- **Bipe de acesso negado** no modo Catraca (pode ser desligado no `config.py`).
- **Tema escuro e tema claro**, no programa (botão no cabeçalho, troca na hora e fica salvo) e no painel web (botão próprio, guardado no navegador).
- **Capturar foto**: guarda o momento de uma câmera (com caixas e carimbo) em `auditoria/capturas/`, fora do log.
- **EPIs reconhecidos separadamente**: o modelo dá uma resposta independente para cada equipamento.
- **Fiscalização por setor**: perfis prontos (cada setor com seus EPIs obrigatórios) e caixas de seleção para ajustar na hora. A última seleção é lembrada ao reabrir o programa.
- **Várias pessoas ao mesmo tempo** (fila): cada uma recebe uma caixa que a acompanha, com número e o que está faltando.
- **Decisão estável**: usa a mediana das últimas classificações de cada pessoa, então o status não fica piscando.
- **Uma foto de evidência por pessoa**: outra só é gravada quando a situação dela muda ou quando é outra pessoa.
- **Dois modos de operação**: **Catraca** (libera ou nega o acesso, e a catraca física obedece) e **Vigilância** (verifica se todos numa área estão em conformidade e registra, sem liberar nada).
- **Status em destaque**: na catraca, liberado (verde) ou negado (vermelho); na vigilância, em conformidade ou não conforme; e analisando (laranja) ou aguardando.
- **Confiança mínima e intervalo de análise** ajustáveis na tela, com efeito imediato.
- **Auditoria na mesma tela**: indicadores, filtros (resultado, **período** e busca), ordenação por coluna e foto de evidência do evento selecionado. Cada evento guarda o setor, o que era exigido e o que faltava.
- **Exportar CSV**: o que está filtrado vai para uma planilha que o Excel em português abre direto (também pelo painel web).
- **Relatório de um evento**: um clique gera uma página com todos os dados do momento da linha selecionada, a foto e os outros eventos do mesmo instante.
- **Excluir linha sem perder o registro**: o evento sai da tabela, mas vai para uma pasta de excluídos, com a data da exclusão.
- **Catraca de demonstração com ESP32**: maquete com cancela (servo), LEDs, bipe e tela que obedece ao sistema pelo Wi-Fi (pasta `catraca_esp32/`).
- **Várias câmeras (áreas)**: cada área abre numa aba, com a sua própria câmera, setor, EPIs e modo. A auditoria continua uma só, com a área de cada evento.
- **Testes automatizados**: 195 testes cobrindo regras de decisão, auditoria, câmera IP, painel web e a janela.
- **Coleta de dataset rotulada**: marque o que a pessoa está usando e salve, por botão ou atalho de teclado.
- **Painel web ajustado na tela**: ligar, porta, acesso pela rede, usuário e senha em **Configurações > Painel web**. A senha fica guardada só como hash.
- **Painel web do gerente**, somente leitura: status ao vivo, indicadores, gráfico e fotos pelo navegador, inclusive no celular.
- **Abertura imediata**: a janela aparece na hora e o modelo de IA carrega em segundo plano.

---

## Instalação

### Requisitos

- Windows 10 ou 11
- Python 3.10 ou superior (testado com 3.13)
- Webcam ou câmera IP na mesma rede

### Passo a passo

1. Instale as dependências:

   ```bash
   python -m pip install -r requirements.txt
   ```

   As versões estão fixas no arquivo: são as mesmas com que o projeto foi testado.

2. Confira a pasta `modelos/`:

   | Arquivo | Para que serve | Origem |
   |---|---|---|
   | `face_detection_yunet_2023mar.onnx` | Localiza as pessoas pelo rosto (modo catraca) | Baixado uma vez (já vem no repositório) |
   | `object_detection_yolox_2022nov.onnx` | Localiza as pessoas pelo corpo inteiro (modo vigilância) | **Não vem no repositório** (35 MB). Veja [Modo de operação](#modo-de-operação-catraca-ou-vigilância) |
   | `modelo_epis.keras` e `epis.json` | Modelo **por EPI** | Já vêm no repositório (treinado com um dataset pequeno); gerados de novo pelo `treinar.py` |
   | `modelo_epi.keras` e `classes.json` | Modelo **antigo** (só "com EPI" / "sem EPI") | Já vêm no repositório |

   > **Importante:** o repositório já traz um modelo por EPI, mas treinado com poucas imagens (49): ele funciona para demonstração e erra bastante. Para um resultado confiável, colete mais imagens e treine de novo (veja [Coleta de imagens e re-treino](#coleta-de-imagens-e-re-treino)). Sem o modelo por EPI, o programa usa o modelo antigo, que **não distingue os equipamentos** (a área de fiscalização fica desativada, com um aviso).

   Se o detector de rosto estiver faltando, baixe com (PowerShell, na pasta do projeto):

   ```powershell
   Invoke-WebRequest -Uri "https://github.com/opencv/opencv_zoo/raw/main/models/face_detection_yunet/face_detection_yunet_2023mar.onnx" -OutFile "modelos/face_detection_yunet_2023mar.onnx"
   ```

3. Para melhorar o reconhecimento, colete mais imagens e treine (veja [Coleta de imagens e re-treino](#coleta-de-imagens-e-re-treino)).

---

## Como usar

### Abrir o programa

```bash
python app.py
```

A janela abre na hora, com a mensagem "Carregando o modelo de IA". Quando o botão mudar para **Iniciar câmera**, o programa está pronto.

### A tela

A tela principal tem só o que se usa durante a operação. Em cima, a marca, os **selos de situação** e o botão do **tema**; à esquerda, a **barra de áreas** e a página da área escolhida; à direita, a auditoria de todas as áreas. O resto fica no botão **Configurações**, no canto de cima.

| Área | O que faz |
|---|---|
| **Cabeçalho** | Selos com ponto colorido: **IA** (carregando, pronta com quantos EPIs, ou com erro), **Painel web** (clique abre no navegador) e **Catraca** (conectada ou procurando). Botão **Tema claro / Tema escuro** (troca na hora; a escolha fica salva). À direita, data e hora. |
| **Barra de áreas** | **Visão geral** (todas as câmeras lado a lado, com 2 áreas ou mais), uma **pílula por área** com um ponto na cor da situação dela agora (verde, vermelho, amarelo, cinza) e **+ Nova área**. A área que comanda a catraca tem "· catraca" no nome. |
| **Câmera da área** | Em cima do vídeo: qual câmera a área usa e os botões **Trocar câmera** (abre as Configurações já na área), **Capturar foto** e **▶ Iniciar / ■ Parar câmera**. Com a câmera desligada, o vídeo dá lugar a uma tela de espera com o botão de ligar no meio. |
| **Vídeo** | Imagem da câmera com um contorno fino por pessoa e uma única palavra: verde `OK`, vermelho `NEGADO`, cinza `...` (ainda analisando). O contorno é discreto de propósito, para não cobrir ninguém quando há muita gente. Em cima, as legendas: "● AO VIVO", área, data e hora à esquerda; resolução, fps, análises/s e pessoas à direita. |
| **Faixa de status** | Símbolo (✔ ✖ ◔ ●) e decisão geral, quantas pessoas estão irregulares, em quantas falta cada EPI e o que o setor exige. Liberado, negado e analisando enchem a faixa de cor (para ver de longe); aguardando e câmera desligada ficam num cartão discreto. O detalhe por pessoa fica na auditoria. |
| **Visão geral** | Todas as câmeras lado a lado, cada uma com a sua situação e a borda na cor dela. Passar o mouse destaca o quadro; clicar abre a página da área (a pílula **Visão geral** volta para cá). Câmera desligada tem o botão **Ligar câmera** no próprio quadro. |
| **Fiscalização (abaixo do vídeo)** | **Setor**, **Modo** (Catraca ou Vigilância) e os **EPIs exigidos** como botões que ligam e desligam (azul com ✓ = exigido). Valem só para aquela área. |
| **Configurações** | Botão no topo do monitoramento: abre a janela com o resto (veja abaixo). |
| **Auditoria** | Acompanha a esquerda: com uma área aberta, mostra **só os eventos dela** (o título diz "Auditoria · Portaria"); na **Visão geral**, os de **todas as áreas**. Cartões, tabela e exportação seguem junto. Indicadores do período, filtros (Todos / Conformes / Irregulares, período e busca) e tabela de eventos, atualizados ao vivo. Clique em um evento para ver a foto, o que era exigido e a confiança de cada EPI; duplo clique abre a foto em tamanho real. Clique no título de uma coluna para ordenar. No cabeçalho: **Exportar CSV**, **Abrir pasta** e **Zerar**. No cartão **Evento selecionado**, embaixo: **Salvar relatório** e **Excluir**. |

### Configurações

O botão **Configurações** abre uma janela com abas. Tudo vale na hora e fica salvo para a próxima vez. Fechar a janela só a esconde: o que estiver marcado continua valendo.

| Aba | O que tem |
|---|---|
| **Área e câmera** | Vale para a **área aberta**: renomear, remover, **"Esta área comanda a catraca física"**, qual câmera ela usa, **Adicionar câmera IP...**, **Remover câmera IP** e **+ Nova área...** |
| **Painel web** | **Ligar o painel**, **acesso pela rede** (ou só este computador), **porta**, **exigir usuário e senha**, **usuário** e **nova senha** (com confirmação e "Mostrar senha"). Vale ao clicar em **Aplicar**: o painel reinicia na hora e o resultado aparece embaixo (ex.: "porta em uso"). Avisa se ainda é a senha padrão ou se está sem senha. **Abrir no navegador** abre o painel |
| **Análise** | **Confiança mínima** (mais alto = mais rigoroso) e **intervalo de análise** (de quanto em quanto tempo cada pessoa é verificada de novo), com **Voltar aos valores padrão**. Valem para todas as áreas |
| **Coleta de imagens** | O que a pessoa na câmera está usando, **Salvar imagem da câmera**, **Enviar arquivo...** e o resumo do dataset |

### Várias câmeras: áreas

Cada **área** é uma câmera com a sua própria fiscalização, numa aba da tela principal. Por exemplo: "Portaria" no modo Catraca, exigindo capacete e colete, e "Laboratório" no modo Vigilância, exigindo óculos e luvas.

- **Criar:** clique na aba **+ Nova área** (ou em Configurações > Área e câmera > **+ Nova área...**), dê um nome e escolha a câmera.
- **Renomear, remover e trocar a câmera:** em **Configurações > Área e câmera**, que vale para a aba aberta. A última área não pode ser removida.
- **Catraca física:** só uma área a comanda. Marque **"Esta área comanda a catraca física"** na área certa; a aba dela ganha "· catraca" no nome. Sem nenhuma marcada, a catraca fica fechada.
- **Auditoria:** uma só para todas. Cada evento guarda a **Área** de onde veio (coluna na tabela, no relatório e no painel web).
- **Análise:** todas as áreas analisam ao mesmo tempo, mesmo as que não estão à vista. Só a aba aberta é desenhada na tela.

Limites: uma webcam só funciona em uma área de cada vez (câmeras IP podem se repetir). Cada área é uma câmera e uma análise rodando juntas, então o computador fica mais lento a cada área; o máximo é `MAXIMO_AREAS` (6). Se ficar lento, aumente o intervalo de análise.

O modelo de EPI é carregado uma vez e atende uma área por vez. Os detectores de pessoa são um por área.

### Fiscalização por setor

Cada setor da empresa pode exigir EPIs diferentes. Na aba da área:

1. Escolha o **setor** na lista abaixo do vídeo. Os EPIs obrigatórios dele são marcados de uma vez.
2. Se precisar, **marque ou desmarque** cada EPI à mão, na linha **EPIs exigidos**. Se a combinação não corresponder a nenhum setor pronto, o setor aparece como "Personalizado".

A mudança vale na hora, sem reiniciar nada. O sistema continua enxergando todos os equipamentos; a seleção define apenas **quais deles contam** para liberar ou negar. A última seleção fica salva e é restaurada quando o programa é aberto de novo.

Os setores prontos ficam em `safetech/config.py`, no dicionário `SETORES`. Para criar o seu, acrescente uma linha:

```python
SETORES = {
    "Acesso geral": ["capacete", "oculos", "colete", "luvas"],
    "Manuseio de materiais": ["luvas"],
    "Almoxarifado": ["colete", "luvas"],   # setor novo
}
```

O divisor entre os dois painéis pode ser arrastado para dar mais espaço ao vídeo ou à auditoria.

### Modo de operação: catraca ou vigilância

Abaixo do vídeo de cada área, o seletor **Modo** escolhe como aquela área trabalha. A troca vale na hora, sem reiniciar o programa nem a câmera, e a escolha fica salva.

| | **Catraca** | **Vigilância** |
|---|---|---|
| Para quê | Controle de **acesso**: uma pessoa por vez, perto da câmera e de frente | Fiscalização de uma **área**: câmera geral, várias pessoas de costas, de lado, abaixadas, andando e se cruzando |
| Como acha a pessoa | Pelo **rosto**; o recorte cobre cabeça, tronco e mãos | Pelo **corpo inteiro**, em qualquer posição |
| Resultado mostrado | **ACESSO LIBERADO** / **ACESSO NEGADO** | **EM CONFORMIDADE** / **NÃO CONFORME** (não há acesso a liberar) |
| Palavra no vídeo | `OK` / `NEGADO` | `OK` / `SEM EPI` |
| Catraca física (ESP32) | **Obedece**: abre quando libera | **Desligada**: fechada, LEDs apagados, tela "VIGILANCIA" |
| Auditoria | Registra cada decisão com foto | Registra igual, com o resultado "Conforme" / "Não conforme" |
| Velocidade | Rápido (cerca de 12 análises por segundo) | Mais lento (cerca de 8 análises por segundo) |

A regra de decisão é a mesma nos dois modos: os EPIs exigidos no setor. Cada evento da auditoria guarda o modo em que aconteceu, então a tabela, o relatório e o painel web mostram o texto certo para cada linha.

Numa foto real de um canteiro de obras, a detecção pelo rosto encontrou 5 pessoas e a pelo corpo, as 7 que estavam visíveis.

O que muda ao trocar de modo:

- **As pessoas são esquecidas e recomeçam.** A caixa de um rosto e a de um corpo inteiro não se correspondem, então quem está na imagem passa a contar como pessoa nova (com um novo evento de entrada na auditoria).
- **O recorte entregue ao modelo de EPI muda** (cabeça e tronco num modo, corpo inteiro no outro). Para o reconhecimento funcionar bem nos dois, o dataset precisa ter imagens coletadas **nos dois modos**. A coleta e a importação salvam o recorte do modo que estiver selecionado.

O modo vigilância depende do arquivo `modelos/object_detection_yolox_2022nov.onnx` (35 MB), que não vai para o repositório. Sem ele, a opção **Vigilância** fica desativada. Para baixar (PowerShell, na pasta do projeto):

```powershell
Invoke-WebRequest -Uri "https://github.com/opencv/opencv_zoo/raw/main/models/object_detection_yolox/object_detection_yolox_2022nov.onnx" -OutFile "modelos/object_detection_yolox_2022nov.onnx"
```

### Câmera IP

Além da webcam, o programa abre câmeras pela rede: câmeras de segurança (endereço `rtsp://`) e câmeras simples ou o celular (endereço `http://`).

1. Abra a aba da área e, em **Configurações > Área e câmera**, clique em **Adicionar câmera IP...**.
2. Preencha o **nome** (ex.: "Portaria"), o **endereço do vídeo** e, se a câmera pedir, **usuário** e **senha**.
3. Clique em **Adicionar**. A câmera entra na lista como "Portaria (IP)", liga na hora e fica salva para as próximas vezes.

Com uma câmera IP selecionada, o botão **Remover câmera IP**, na mesma aba, tira a câmera do cadastro; as áreas que a usavam voltam para a última webcam usada.

| Câmera | Endereço típico |
|---|---|
| Intelbras | `rtsp://192.168.0.50:554/cam/realmonitor?channel=1&subtype=1` |
| Hikvision | `rtsp://192.168.0.50:554/Streaming/Channels/102` |
| Celular Android (app **IP Webcam**) | `http://192.168.0.20:8080/video` |

Dicas:

- **Use o stream de qualidade menor** (substream: `subtype=1` na Intelbras, canal `102` na Hikvision). A IA não precisa de 4K e a análise fica mais rápida.
- **Para testar sem câmera**, instale o app gratuito **IP Webcam** no celular, toque em "Iniciar servidor" e use o endereço que ele mostrar. Celular e computador precisam estar no mesmo Wi-Fi.
- **Se a rede cair**, a faixa de status mostra `RECONECTANDO` e o programa tenta voltar sozinho, a cada `INTERVALO_RECONEXAO_IP_SEG` segundos.
- **A senha da câmera não aparece na tela**: só o nome. O endereço completo fica no `preferencias.json`, que não vai para o repositório.

### Atalhos de teclado

| Tecla | Ação |
|---|---|
| `Espaço` | Liga ou desliga a câmera |
| `S` | Salva uma imagem da câmera com os rótulos marcados em **Configurações > Coleta de imagens** (funciona com a janela fechada) |
| `Ctrl+V` | Cola no dataset uma imagem copiada (ou arquivos de imagem copiados), com os rótulos marcados |
| `F11` | Tela cheia (monitor da portaria, apresentação) |
| `Esc` | Sai da tela cheia; fora dela, limpa a busca da auditoria |
| `Delete` | Exclui a linha selecionada na tabela de auditoria (com confirmação) |

Os atalhos ficam desativados enquanto você digita no campo de busca.

### Testar o modelo com uma foto

```bash
python reconhecer.py
```

Abre uma janela para escolher a imagem e mostra, para cada pessoa encontrada, a confiança de cada EPI e se ele conta como "usando". Também aceita o caminho direto: `python reconhecer.py foto.jpg`.

---

## Painel web do gerente

Página de acompanhamento pelo navegador, **somente leitura**: o gerente vê os dados e as imagens, mas não consegue alterar nenhuma configuração, ligar ou desligar a câmera, nem apagar registros.

### Como acessar

1. Abra o aplicativo (`python app.py`). O painel web sobe junto.
2. O endereço aparece no selo do cabeçalho da janela, por exemplo `Painel web: http://192.168.0.15:8080`. Clicar nele abre o navegador. Selo amarelo = ainda com a senha padrão ou sem senha; "Painel web desligado" = clique para ir às Configurações.
3. No computador do gerente (ou no celular), na **mesma rede**, digite esse endereço.
4. Informe o login definido em **Configurações > Painel web**. Até a primeira troca, vale o do `safetech/config.py` (usuário `gerente`); **troque a senha antes de usar de verdade**, porque a padrão está no repositório.

Na primeira vez, o Windows pode perguntar se o Python pode aceitar conexões da rede. É preciso permitir para que outros aparelhos acessem.

### O que o painel mostra

| Área | Conteúdo |
|---|---|
| **Áreas** | Com duas câmeras ou mais: um cartão por área, com a imagem atual, a situação (cor e símbolo), o modo, o setor e quantas pessoas estão irregulares. Atualiza a cada 2 segundos. |
| **Ao vivo** | Imagem atual da câmera com as caixas, o setor em fiscalização e o que ele exige, status da catraca e o que falta para cada pessoa. Atualiza a cada segundo. |
| **Hoje** | Eventos, conformes, irregulares e taxa de conformidade do dia, com o total do histórico abaixo de cada número. "Conforme" é quem foi liberado (catraca) ou estava com os EPIs (vigilância). |
| **Eventos por hora** | Gráfico de barras do dia. Passar o mouse numa hora mostra os números. |
| **Eventos de auditoria** | Os eventos mais recentes, com miniatura da foto, setor, EPIs exigidos e o que faltava, além de filtros e busca. Clicar numa linha abre a foto em tamanho grande. **Exportar CSV** baixa o histórico inteiro numa planilha (só leitura: é um download). |

O gerente **vê** qual setor está sendo fiscalizado, mas não consegue mudá-lo: a escolha do setor é feita só no aplicativo.

A página funciona em celular e não depende de internet (não carrega nada de fora). O botão **Tema claro / Tema escuro** do cabeçalho muda só a aparência naquele navegador (a escolha fica guardada nele); sem escolha, a página segue o tema do sistema do aparelho.

### Catraca de demonstração (ESP32)

A pasta `catraca_esp32/` tem o programa e o guia de montagem de uma maquete de catraca: um ESP32 com servo (a cancela), LEDs, buzzer, tela OLED e um relé. Ela abre a cancela quando o acesso é liberado e recebe o status de dois jeitos, que podem ficar ligados juntos:

- **Cabo USB** (principal): o programa escreve o status na porta serial do ESP32. É só ligar o ESP32 no computador; o rodapé da janela mostra "Catraca: COM3 conectada". Precisa do `pyserial` (já está no `requirements.txt`).
- **Wi-Fi** (opcional): o ESP32 lê o status em `/api/ao-vivo`, com o login do painel. Se o cabo sair, o Wi-Fi assume sozinho.

Nos dois casos o ESP32 só **recebe**: o painel continua somente leitura. Com o cabo, a Arduino IDE não consegue gravar a placa enquanto o programa estiver aberto. Peças, ligações e passo a passo em [`catraca_esp32/LEIA-ME.md`](catraca_esp32/LEIA-ME.md).

### Só o histórico, sem abrir a catraca

```bash
python painel_web.py
```

Sobe o mesmo painel sem câmera: indicadores, gráfico, eventos e fotos. Não abra junto com o aplicativo, pois os dois usam a mesma porta.

### Segurança

- **Somente leitura de verdade**: o servidor só responde a pedidos de leitura (GET). Qualquer tentativa de envio ou alteração é recusada, e não existe rota que mude o sistema.
- **Login obrigatório**: o painel mostra fotos de pessoas, então pede usuário e senha. **Troque a senha padrão** em Configurações > Painel web antes de usar fora de testes.
- **A senha não fica guardada**: o `preferencias.json` (fora do git) guarda só um hash PBKDF2 com sal aleatório. Quem abrir o arquivo não descobre a senha. Conferir uma senha é lento de propósito (~0,1 s); o servidor lembra dos logins já conferidos para não repetir o cálculo a cada pedido.
- **Só as fotos de evidência são servidas**: pedidos que tentam alcançar outros arquivos do computador são recusados.
- **Limite conhecido**: a conexão é HTTP simples, sem criptografia. Use apenas em rede local de confiança, nunca exposto à internet.

Para restringir o painel a este computador, desmarque **Permitir acesso pela rede**; para desligar, desmarque **Ligar o painel web** (Configurações > Painel web). O `painel_web.py` usa os mesmos ajustes.

---

## Como funciona

### As duas redes neurais

O sistema combina dois modelos, cada um com uma função:

1. **Detector de pessoas**: encontra ONDE estão as pessoas. Há dois, e o usuário alterna entre eles na tela:
   - **Rosto (YuNet)**: acha cada rosto e monta uma caixa maior cobrindo cabeça, tronco e mãos, que é onde ficam o capacete, os óculos, o colete e as luvas.
   - **Corpo (YOLOX)**: uma rede de detecção de objetos, da qual só interessa a classe "pessoa". Acha o corpo inteiro em qualquer posição.
2. **Classificador de EPI (MobileNetV2)**: recebe o recorte de cada pessoa e devolve **uma probabilidade por equipamento**, cada uma independente das outras:

   ```
   capacete 0.97    óculos 0.12    colete 0.88    luvas 0.05
   ```

   Isso se chama classificação *multirrótulo*: em vez de escolher uma classe entre várias, a rede responde várias perguntas de sim ou não. Por isso a camada final usa a função *sigmoid* (cada saída vai de 0 a 1 sozinha) em vez de *softmax* (que obrigaria as saídas a somarem 1). O treino é por *transfer learning*: a MobileNetV2 já vem treinada com milhões de imagens e só a camada final é treinada com as fotos do projeto.

### Detectar é diferente de exigir

Esta é a ideia central da fiscalização por setor. O modelo **sempre avalia todos os EPIs** que conhece. Quais deles são obrigatórios é uma decisão separada, tomada depois, com base no setor escolhido:

| A pessoa está usando | Setor exige | Resultado |
|---|---|---|
| Capacete, colete | Capacete, colete | Liberado |
| Capacete, colete | Luvas | Negado (falta: luvas) |
| Só luvas | Luvas | Liberado |
| Nada | Nenhum EPI | Liberado |

Como a classificação não depende do setor, trocar de setor tem efeito imediato: basta refazer a comparação, sem analisar a imagem de novo.

### A linha de análise

Para cada frame da câmera:

```
 frame ──> DETECTAR ──> RASTREAR ──> CLASSIFICAR ──> DECIDIR ──> AUDITAR
           onde estão    quem é      quais EPIs      compara com  grava se a
           as pessoas    quem        cada um usa?    o setor      decisão mudou
```

- **Detectar**: o YuNet roda em duas cópias reduzidas do frame (640 e 320 px de largura) e os resultados são unidos. A maior acha rostos pequenos de uma câmera geral; a menor acha um rosto grande e próximo, como numa catraca. Cada uma sozinha perde o caso da outra.
- **Rastrear**: cada caixa é ligada à pessoa do frame anterior pela sobreposição entre as caixas (IoU) ou pela proximidade dos centros. Quem some por alguns segundos (virou o rosto, passou atrás de algo) continua **lembrado**: se reaparecer perto de onde estava, é reconhecido como a mesma pessoa, com o mesmo histórico e a mesma decisão.
- **Classificar**: todas as pessoas são classificadas numa única chamada ao modelo. Isso acontece no intervalo configurado, e mais rápido quando aparece alguém novo.
- **Decidir**: para cada EPI, usa a **mediana** das últimas 5 classificações (o valor do meio). O EPI conta como "usando" se a mediana passar da confiança mínima. A mediana ignora um resultado isolado fora da curva, que na média bastaria para virar a decisão. A pessoa é liberada se estiver usando todos os EPIs exigidos no setor.
- **Auditar**: um evento, com **uma** foto de evidência, é gravado em apenas dois casos: na primeira decisão sobre uma pessoa nova, e quando a decisão dela muda de fato (liberado para negado ou o contrário, inclusive por troca de setor). A mudança só é gravada depois de se repetir em 3 classificações seguidas. Enquanto a pessoa continua na mesma situação, nada é gravado.

### Regra da catraca

| Situação | Status |
|---|---|
| Ninguém na imagem | Aguardando |
| Alguém ainda sem decisão | Analisando |
| Pelo menos uma pessoa sem algum EPI exigido | **Acesso negado** |
| Todas as pessoas com os EPIs exigidos | **Acesso liberado** |

Um EPI exigido que o modelo não sabe reconhecer conta como faltando: na dúvida, o sistema nega.

### Por que a tela não trava

O programa usa três threads, cada uma com um trabalho:

| Thread | Trabalho |
|---|---|
| **Câmera** | Captura os frames e guarda sempre o mais recente. |
| **Analisador** | Executa a linha de análise e publica o resultado. |
| **Interface** | Desenha a tela cerca de 30 vezes por segundo, usando o frame e o resultado mais recentes. |

A interface nunca espera pela câmera nem pela IA, então o vídeo continua fluido mesmo durante a análise.

---

## Estrutura do projeto

```
Tech_day_26.2/
├── app.py                  Abre o aplicativo
├── treinar.py              Treina o modelo
├── reconhecer.py           Testa o modelo com uma foto
├── painel_web.py           Painel web só com o histórico (sem abrir a catraca)
├── requirements.txt        Dependências (versões fixas)
├── requirements-dev.txt    Dependências só para desenvolver (pytest)
├── pytest.ini              Configuração dos testes
├── README.md
├── .github/workflows/      Testes automáticos no GitHub (Actions)
├── testes/                 Testes automatizados (python -m pytest)
├── catraca_esp32/          Catraca de demonstração (ESP32): firmware e guia de montagem
│
├── safetech/               Código do projeto
│   ├── config.py           Todas as configurações (caminhos e ajustes)
│   │
│   ├── nucleo/             A "inteligência" (sem tela e sem câmera)
│   │   ├── tipos.py            Estruturas de dados trocadas entre os módulos
│   │   ├── epis.py             Quais EPIs o modelo instalado reconhece
│   │   ├── modos.py            Textos de cada modo (catraca / vigilância)
│   │   ├── detector.py         Escolhe o detector conforme o modo (catraca = rosto, vigilância = corpo)
│   │   ├── detector_rosto.py   Encontra as pessoas pelo rosto (YuNet)
│   │   ├── detector_corpo.py   Encontra as pessoas pelo corpo inteiro (YOLOX)
│   │   ├── rastreador.py       Mantém a identidade de cada pessoa
│   │   ├── classificador.py    Modelo de EPI: uma probabilidade por equipamento
│   │   ├── decisao.py          Compara o que a pessoa usa com o que o setor exige
│   │   └── anotacao.py         Desenha caixas e rótulos na imagem
│   │
│   ├── servicos/           O que acontece ao redor do núcleo
│   │   ├── camera.py           Captura da webcam ou câmera IP em thread própria
│   │   ├── analisador.py       Linha de análise em thread própria
│   │   ├── auditoria.py        Log em CSV e fotos de evidência
│   │   ├── relatorio.py        Relatório HTML de um evento da auditoria
│   │   ├── catraca_serial.py   Envia o status à catraca ESP32 pelo cabo USB
│   │   ├── dataset.py          Salva imagens de treino com os rótulos
│   │   ├── importacao.py       Abre imagens de arquivo ou da área de transferência
│   │   └── preferencias.py     Lembra setor, EPIs, câmera e câmeras IP
│   │
│   ├── interface/          A janela (Tkinter)
│   │   ├── tema.py                  Cores, fontes e estilos
│   │   ├── area_monitorada.py       Uma área: câmera + análise + aba (e o desenho dela)
│   │   ├── painel_visao_geral.py    Visão geral: todas as áreas lado a lado
│   │   ├── componentes.py           Selos do cabeçalho e barra de áreas (pílulas)
│   │   ├── painel_monitoramento.py  A aba de uma área: vídeo, status, setor, modo, EPIs e câmera
│   │   ├── dialogo_area.py          Janela "Nova área" / "Renomear área"
│   │   ├── painel_auditoria.py      Indicadores, filtros, tabela e evidência
│   │   ├── janela_configuracoes.py  Janela de Configurações (área e câmera, análise, coleta)
│   │   ├── dialogo_camera_ip.py     Janela "Adicionar câmera IP"
│   │   └── janela_principal.py      Monta a tela e liga tudo
│   │
│   ├── web/                Painel web do gerente (somente leitura)
│   │   ├── servidor.py         Servidor HTTP: página, dados e imagens
│   │   └── painel.html         A página do painel
│   │
│   └── treino/
│       └── treinador.py        Valida o dataset, monta a rede, treina e salva
│
├── modelos/                Modelos usados pelo programa
├── dataset/                Dados de treino (não vão para o repositório)
│   ├── epis/               Imagens coletadas pelo aplicativo
│   └── rotulos.csv         Quais EPIs aparecem em cada imagem
├── preferencias.json       Seleções e câmeras IP (gerado pelo programa)
└── auditoria/              Gerada pelo programa
    ├── log_auditoria.csv
    ├── arquivados/         Logs e fotos anteriores, movidos pelo botão Zerar
    ├── excluidos/          Linhas e fotos tiradas pelo botão Excluir linha
    ├── relatorios/         Relatórios gerados pelo botão Salvar relatório
    └── imagens/            Fotos de evidência
```

### Princípios da organização

- **Camadas com direção única**: a interface usa os serviços, os serviços usam o núcleo. O núcleo não conhece ninguém acima dele, por isso pode ser testado sem câmera e sem janela.
- **Configuração em um lugar só**: nenhum módulo tem número fixo espalhado; tudo vem de `safetech/config.py`.
- **EPIs vindos do arquivo**: quais EPIs o modelo reconhece, e em que ordem, é lido de `epis.json`, gravado junto com o modelo no treino. Assim o aplicativo nunca troca um equipamento por outro.
- **Detectar separado de exigir**: o classificador não sabe nada de setores, e a regra de decisão não sabe nada de imagens.
- **Painéis sem lógica**: os painéis apenas exibem dados e avisam a janela principal quando o usuário faz algo.

---

## Coleta de imagens e re-treino

Para o modelo reconhecer cada equipamento separadamente, ele precisa de imagens **rotuladas item a item**: para cada foto, quais EPIs a pessoa está usando. O próprio aplicativo faz isso.

### Passo a passo

1. Abra o programa e ligue a câmera.
2. Em **Configurações > Coleta de imagens**, marque o que a pessoa na câmera **está usando agora**. Por exemplo, se ela está só de capacete e luvas, marque `Capacete` e `Luvas`.
3. Pressione `S` (ou clique em **Salvar imagem da câmera**) várias vezes, variando posição, distância, ângulo e iluminação.
4. Troque os equipamentos, **atualize as caixas marcadas** e repita. O aviso no rodapé repete os rótulos de cada imagem salva: confira, porque um rótulo errado ensina o modelo errado.
5. Feche o programa e treine:

   ```bash
   python treinar.py
   ```

6. Abra o programa novamente. O modelo por EPI passa a ser usado automaticamente e a escolha de setor e EPIs é ativada.

### Usar imagens que já existem

Além da câmera, a coleta aceita imagens prontas. Elas recebem os rótulos que estiverem marcados no momento, então **marque primeiro, importe depois**.

| Forma | Como |
|---|---|
| **Enviar arquivo...** | Botão em **Configurações > Coleta de imagens**. Dá para escolher várias imagens de uma vez (todas recebem os mesmos rótulos). |
| **Colar (`Ctrl+V`)** | Copie uma imagem (captura de tela, "copiar imagem" do navegador) ou copie arquivos de imagem no Explorador de Arquivos, e pressione `Ctrl+V` na janela do programa. |

A importação funciona com a câmera desligada. Cada imagem passa pelo mesmo tratamento da câmera: o detector acha as pessoas e o que é salvo é o recorte de cada uma; se ninguém for encontrado, a imagem inteira é salva. O aviso no rodapé informa quantas imagens entraram, quantos recortes geraram e com quais rótulos. Arquivos que não são imagens são ignorados.

Ao importar imagens da internet, lembre que só servem as que mostram claramente o que a pessoa está ou não usando, e que precisam ser rotuladas com o mesmo cuidado das fotos da câmera.

### Como montar um bom dataset

- **Cada EPI precisa dos dois casos**: imagens com a pessoa usando e imagens sem usar. O treino se recusa a começar se algum EPI tiver só um dos casos.
- **Varie as combinações.** Se o capacete e o colete aparecem sempre juntos, o modelo não aprende a separá-los: ele aprende "capacete e colete" como uma coisa só. Colete também só capacete, só colete, só luvas, tudo junto e nada.
- **As mãos precisam aparecer** nas imagens com luvas (e nas sem luvas também). Mãos fora da imagem não ensinam nada sobre luvas.
- **Inclua casos que confundem**: boné no lugar do capacete, óculos de grau no lugar dos óculos de proteção, camiseta de cor forte no lugar do colete.
- **Varie pessoas, fundos e iluminação.**
- **Quantidade**: o treino exige pelo menos 20 imagens e avisa quando um EPI tem menos de 10 exemplos de cada caso. Para um resultado confiável, pense em 100 ou mais imagens de cada caso por EPI.
- Colete com **uma pessoa por vez**: todas as pessoas da imagem recebem os mesmos rótulos.

O resumo ao lado do título da coleta mostra o total de imagens e em quantas delas cada EPI aparece em uso.

### Onde os dados ficam

| Arquivo | Conteúdo |
|---|---|
| `dataset/epis/` | As imagens: o **recorte de cada pessoa**, que é exatamente o que o modelo recebe durante o uso |
| `dataset/rotulos.csv` | Uma linha por imagem: `arquivo, capacete, oculos, colete, luvas` (1 = usando, 0 = sem usar) |

A planilha pode ser aberta e corrigida em qualquer editor de planilhas. Se uma imagem for apagada, a linha dela é ignorada no treino.

Ao final, o treino mostra a **taxa de acerto de cada EPI** nas imagens de validação. É assim que se descobre qual equipamento precisa de mais imagens.

### Mudar a lista de EPIs

Os equipamentos fiscalizados ficam em `EPIS`, no `safetech/config.py`. O modelo aprende exatamente essa lista, então, ao acrescentar ou remover um EPI, é preciso **coletar as imagens de novo** (rotulando também o EPI novo) e treinar. A planilha antiga é renomeada, não apagada.

### Sobre o treinamento

- Rede base: MobileNetV2 pré-treinada (ImageNet), congelada.
- Camada treinada: média global, dropout de 20% e uma camada densa com uma saída *sigmoid* por EPI.
- Função de perda: *binary crossentropy*, que trata cada saída como uma pergunta de sim ou não separada.
- *Data augmentation*: espelhamento horizontal, rotação e zoom leves.
- 80% das imagens para treino e 20% para validação; 15 épocas; otimizador Adam.
- A normalização da MobileNetV2 fica dentro do modelo: quem usa o modelo entrega a imagem RGB 224x224 sem normalizar.

---

## Auditoria

O log fica em `auditoria/log_auditoria.csv`, e as fotos em `auditoria/imagens/`.

| Coluna | Conteúdo |
|---|---|
| `timestamp` | Data e hora do evento |
| `evento` | `ENTRADA` (primeira decisão da pessoa) ou `MUDANCA` (a decisão mudou) |
| `pessoa` | Identificação da pessoa na sessão, ex.: `P003` |
| `setor` | Setor que estava sendo fiscalizado |
| `exigidos` | EPIs obrigatórios naquele setor, ex.: `Capacete, Luvas` |
| `faltando` | EPIs exigidos que a pessoa não estava usando (vazio se nenhum) |
| `confiancas` | Confiança de cada EPI, ex.: `Capacete 97%, Luvas 12%` |
| `liberado` | `SIM` ou `NAO`: a pessoa estava com todos os EPIs exigidos? (na catraca, liberado; na vigilância, conforme) |
| `imagem` | Arquivo da foto de evidência |
| `modo` | `catraca` ou `vigilancia`: diz como ler o resultado |
| `area` | Nome da área (câmera) onde o evento aconteceu |

Logs de versões anteriores, sem a coluna `modo`, são convertidos ao abrir o programa: os eventos ganham o modo `catraca` e o arquivo original fica guardado como `log_auditoria_formato_antigo_<data>.csv`.

As fotos do botão **Capturar foto** (da câmera de uma área) ficam em `auditoria/capturas/`, com as caixas e o mesmo carimbo, mas **não** entram no log: são registros avulsos do operador.

Cada evento tem uma foto do frame inteiro, com a pessoa em questão destacada e um **carimbo** no rodapé (ex.: `SafeTech Entry | 2026-11-24 14:10:32 | Area: Portaria | P003 | Negado`). Assim a foto continua dizendo de quando e de onde é, mesmo copiada para fora do sistema. Desligue com `CARIMBAR_EVIDENCIA = False`.

### Exportar para planilha

**Exportar CSV**, no cabeçalho da auditoria, grava numa planilha **o que está filtrado na tela** (área aberta, período, resultado e busca). Para exportar todas as áreas juntas, abra a **Visão geral** antes. Os cabeçalhos saem por extenso ("Data e hora", "Área", "Resultado"...), o resultado no texto do modo ("Liberado", "Não conforme") e o arquivo usa `;` e a marca UTF-8 que o Excel em português precisa para abrir direto, com acentos. O log de auditoria não muda.

O **período** (Hoje, Últimos 7 dias, Últimos 30 dias, Todo o histórico) vale para os cartões de totais, a tabela e a exportação. Os períodos ficam em `PERIODOS_AUDITORIA`, no `config.py`.

### Zerar a auditoria

O botão **Zerar**, no cabeçalho do painel de auditoria, recomeça tudo do zero: esvazia a tabela, os indicadores, o log e a pasta de fotos, e faz as pessoas que estão na câmera contarem como novas (a numeração volta a `P001`). O painel web também passa a mostrar zero.

O programa pede confirmação antes. E **nada é apagado**: o log e as fotos são movidos para `auditoria/arquivados/<data e hora>/`. Para liberar espaço em disco de verdade, exclua essa pasta à mão.

### Salvar o relatório de um evento

Selecione uma linha e clique em **Salvar relatório**. O programa cria a pasta `auditoria/relatorios/<data e hora do evento>_<pessoa>/` e abre o relatório no navegador:

| Arquivo | Conteúdo |
|---|---|
| `relatorio.html` | Resultado, pessoa, data e hora, tipo de evento, setor, EPIs exigidos, o que faltava, confiança de cada EPI (com os exigidos marcados) e a foto |
| `evidencia.jpg` | Cópia da foto de evidência |
| `outros/` | Fotos dos outros eventos registrados no mesmo segundo, que também aparecem no relatório |

As fotos são **copiadas**: o log e a foto original não mudam. A pasta pode ser compactada e enviada, porque o relatório só usa caminhos relativos.

### Excluir uma linha

Selecione a linha e clique em **Excluir**, no cartão do evento selecionado (ou pressione `Delete`). Depois da confirmação, o evento sai da tabela, do log e do painel web.

Como no Zerar, **nada é apagado**: a linha vai para `auditoria/excluidos/log_excluidos.csv`, com uma coluna a mais (`excluido_em`, a data da exclusão), e a foto vai para `auditoria/excluidos/imagens/`.

### Quando uma foto é gravada

| Situação | Grava? |
|---|---|
| Primeira decisão sobre uma pessoa nova | Sim (`ENTRADA`) |
| A pessoa continua na imagem, na mesma situação | Não |
| A pessoa some por alguns segundos e volta ao mesmo lugar | Não: é reconhecida como a mesma |
| Uma classificação isolada diferente das outras | Não: é tratada como oscilação |
| A situação da pessoa muda de fato (colocou ou tirou um EPI exigido, ou o setor mudou) | Sim (`MUDANCA`) |
| Outra pessoa aparece | Sim (`ENTRADA`) |

O reconhecimento de "mesma pessoa" é por **posição**, não por identidade. Se alguém some por mais de `TEMPO_MEMORIA_PESSOA_SEG` segundos, ou reaparece longe de onde estava, conta como pessoa nova. E, se duas pessoas se cruzam enquanto uma delas não está sendo detectada, o sistema pode trocar uma pela outra.

O número da pessoa (`P001`, `P002`...) vale enquanto ela permanece na imagem e recomeça a cada vez que o programa é aberto. Não é uma identificação de quem a pessoa é.

Logs de versões anteriores do programa, que tinham outras colunas, não são apagados: são renomeados para `log_auditoria_formato_antigo_<data>.csv`.

---

## Configuração

Os ajustes ficam em `safetech/config.py`. Os mais úteis:

| Constante | Padrão | Efeito |
|---|---|---|
| `EPIS` | capacete, óculos, colete, luvas | Equipamentos fiscalizados. Mudar exige coletar e treinar de novo |
| `SETORES` | 5 setores de exemplo | Perfis prontos: nome do setor e os EPIs obrigatórios nele |
| `SETOR_PADRAO` | `"Acesso geral"` | Setor selecionado na primeira vez que o programa abre |
| `LIMIAR_CONFIANCA_PADRAO` | `0.80` | Confiança mínima para considerar que a pessoa usa um EPI (valor da primeira abertura e do botão "Voltar aos valores padrão"; depois vale o escolhido em Configurações, que fica salvo) |
| `INTERVALO_CLASSIFICACAO_PADRAO_SEG` | `1.0` | Intervalo de reclassificação (mesma regra da confiança) |
| `LIMIAR_CONFIANCA_MINIMO` / `_MAXIMO` | `0.50` / `0.99` | Faixa do controle de confiança |
| `INTERVALO_CLASSIFICACAO_MINIMO_SEG` / `_MAXIMO_SEG` | `0.3` / `5.0` | Faixa do controle de intervalo |
| `TAMANHO_HISTORICO_DECISAO` | `5` | Quantas classificações entram na mediana da decisão |
| `CONFIRMACOES_PARA_MUDANCA` | `3` | Classificações seguidas necessárias para registrar uma mudança de decisão (com foto nova) |
| `AMOSTRAS_MINIMAS_DECISAO` | `2` | Classificações necessárias antes da primeira decisão |
| `INDICE_CAMERA` | `1` | Webcam usada na primeira abertura (depois vale a escolhida na tela). Num computador com uma webcam só, use `0` |
| `TEMPO_LIMITE_CONEXAO_IP_MS` | `8000` | Tempo máximo esperando uma câmera IP responder ao conectar |
| `TEMPO_LIMITE_LEITURA_IP_MS` | `5000` | Sem imagem por esse tempo, a conexão com a câmera IP é considerada perdida |
| `INTERVALO_RECONEXAO_IP_SEG` | `3.0` | Espera entre tentativas de reconectar à câmera IP |
| `RTSP_POR_TCP` | `True` | Vídeo RTSP por TCP: um pouco mais de atraso, sem imagem cinza quando a rede perde pacotes |
| `LARGURA_CAPTURA` / `ALTURA_CAPTURA` | `1280` / `720` | Resolução pedida à câmera. Alta para câmera geral, com várias pessoas pequenas na imagem |
| `MODO_DETECCAO_PADRAO` | `"catraca"` | Modo de operação na primeira vez que o programa abre |
| `TEXTOS_POR_MODO` | - | Os textos de cada modo: "Liberado"/"Negado", "Conforme"/"Não conforme", títulos da faixa e palavra no vídeo |
| `LARGURAS_DETECCAO` | `(640, 320)` | Larguras das cópias usadas na detecção de rosto. A maior acha rostos pequenos, a menor acha rostos grandes e próximos |
| `LARGURA_DETECCAO_CORPO` | `512` | Largura da cópia usada na detecção de corpo. Maior acha pessoas menores, mais lento |
| `CONFIANCA_MINIMA_CORPO` | `0.5` | Confiança mínima para aceitar uma pessoa no modo vigilância |
| `TEMPO_MAXIMO_PREVISAO_SEG` | `1.0` | Por quanto tempo o rastreador prevê a posição de quem está andando. `0` desliga |
| `MAXIMO_CANDIDATOS_ROSTO` | `5000` | Candidatos mantidos pelo detector. Valor baixo faz parte das pessoas não ser detectada |
| `CONFIANCA_MINIMA_ROSTO` | `0.7` | Confiança mínima para aceitar um rosto |
| `MARGEM_*_ROSTO` | - | Quanto a caixa do rosto é expandida para cobrir tronco e mãos |
| `TEMPO_MAXIMO_AUSENTE_SEG` | `1.0` | Por quanto tempo a caixa fica na tela depois que a pessoa deixa de ser detectada |
| `TEMPO_MEMORIA_PESSOA_SEG` | `8.0` | Por quanto tempo quem sumiu continua lembrado. Maior = menos fotos repetidas, mais risco de confundir duas pessoas |
| `DISTANCIA_*_RASTREIO` | - | Até que distância de onde sumiu a pessoa ainda é reconhecida como a mesma |
| `EPOCAS_TREINO` | `15` | Épocas do treinamento |
| `PAINEL_WEB_ATIVO` | `True` | Liga ou desliga o painel web (só até o primeiro "Aplicar" em Configurações > Painel web) |
| `PAINEL_WEB_HOST` | `"0.0.0.0"` | `"0.0.0.0"` = acessível na rede; `"127.0.0.1"` = só neste computador (idem) |
| `PAINEL_WEB_PORTA` | `8080` | Porta do painel web (idem) |
| `PAINEL_WEB_USUARIO` / `PAINEL_WEB_SENHA` | `gerente` / (veja o arquivo) | Login inicial do painel (idem). Troque pela tela |
| `PAINEL_WEB_SENHA_MINIMA` | `6` | Tamanho mínimo de uma senha nova |
| `ITERACOES_HASH_SENHA` | `200000` | Repetições do hash da senha (mais = mais difícil de adivinhar) |

---

## Desempenho

Medições feitas em CPU (sem placa de vídeo), no computador de desenvolvimento:

| Etapa | Tempo |
|---|---|
| Detecção de rosto por frame (duas escalas) | cerca de 30 ms |
| Detecção de corpo por frame (entrada de 512 px) | cerca de 77 ms |
| Classificação de 1 pessoa | cerca de 24 ms |
| Classificação de 3 pessoas (uma chamada) | cerca de 50 ms |
| Mesma classificação com `modelo.predict()` | cerca de 224 ms |

O que deixa o programa rápido:

- captura, análise e tela em threads separadas;
- inferência compilada em grafo (`tf.function`) e em lote, no lugar de `modelo.predict()` por pessoa;
- detecção de rosto em imagem reduzida;
- classificação apenas no intervalo configurado, não a cada frame;
- tabela de auditoria atualizada por inserção, sem reler o CSV;
- a imagem do vídeo é reaproveitada entre os quadros, em vez de recriada.

O tempo de abertura do modelo depende do TensorFlow: alguns segundos normalmente, e mais de um minuto na primeira execução depois de ligar o computador. A janela fica utilizável durante esse tempo.

---

## Testes

O projeto tem testes automatizados na pasta `testes/`. Para rodar:

```bash
python -m pip install -r requirements-dev.txt
python -m pytest
```

Saída esperada: `195 passed` em menos de um minuto.

| Arquivo | O que testa |
|---|---|
| `test_decisao.py` | Regras de liberação: setor, limiar, mediana, EPI desconhecido, decisão da catraca |
| `test_auditoria.py` | Gravar, ler, excluir linha, zerar e log de formato antigo (nada é apagado) |
| `test_relatorio.py` | Relatório de um evento: conteúdo, foto copiada, outros eventos, texto escapado no HTML |
| `test_preferencias.py` | Preferências salvas, arquivo corrompido, câmeras IP |
| `test_camera.py` | Câmera IP: conexão, queda e reconexão, endereço errado, senha escondida; webcam que cai e reabre sozinha |
| `test_analisador.py` | Linha de análise completa: decisão, uma foto por pessoa, troca de setor |
| `test_painel_web.py` | Painel web: login, somente leitura, proteção das pastas, situação de cada área, imagem por área, download da planilha |
| `test_acesso_web.py` | Painel web ajustado na tela: hash da senha, validação dos campos, ajustes salvos sem a senha, servidor aceitando a senha nova, "Aplicar" reiniciando o painel e porta em uso |
| `test_temas.py` | Tema escuro e claro: paletas compatíveis, troca com o programa aberto, preferência salva |
| `test_exportacao.py` | Planilha de exportação (cabeçalhos, `;`, acentos para o Excel) e carimbo das fotos de evidência |
| `test_contrato_catraca.py` | O formato de `/api/ao-vivo` de que a catraca ESP32 depende (Wi-Fi) |
| `test_catraca_serial.py` | Envio do status pelo cabo USB (porta falsa): formato da linha, reconexão, porta ocupada, e se o firmware entende tudo o que é enviado |
| `test_areas.py` | Várias áreas: áreas salvas e conversão das versões antigas, coluna Área na auditoria, modelo atendendo uma área por vez, duas análises na mesma auditoria |
| `test_modos.py` | Modos Catraca e Vigilância: textos de cada modo, conversão de nomes e logs antigos, e o modo chegando à tela, auditoria, relatório, painel web e catraca |
| `test_janela.py` | Botões da janela: excluir linha, salvar relatório, adicionar e remover câmera IP, visão geral, barra de áreas, tela de espera da câmera, chips dos EPIs, capturar foto, período, exportar, legendas do vídeo, selo da IA e bipe |

Os testes seguem três regras:

- **Nunca tocam nos dados reais**: auditoria, dataset e preferências vão para uma pasta temporária (veja `testes/conftest.py`).
- **Nunca ligam a webcam nem mostram janelas**: usam câmera, detector e classificador falsos (`testes/falsos.py`) e a janela fica escondida.
- **Não precisam do TensorFlow**: o classificador é falso. Por isso também rodam no GitHub sem baixar a biblioteca.

A câmera IP é testada com um servidor de vídeo falso, que roda no próprio computador e é desligado e religado para simular a queda da rede.

No GitHub, os testes rodam sozinhos a cada envio de código (arquivo `.github/workflows/testes.yml`).

---

## Solução de problemas

| Problema | Solução |
|---|---|
| **"Nenhum modelo encontrado em 'modelos/'"** | Recupere os arquivos de `modelos/` do repositório, ou colete imagens e rode `python treinar.py`. |
| **A escolha de setor e EPIs está cinza** | O programa está usando o modelo antigo, que não distingue os EPIs. Colete imagens rotuladas e rode `python treinar.py`. |
| **Um EPI específico erra muito** | Veja a taxa de acerto dele no fim do treino e colete mais imagens desse EPI, nos dois casos (usando e sem usar) e em combinações variadas. |
| **O treino diz que falta um caso** | Algum EPI só tem imagens "usando" ou só "sem usar". Colete o caso que falta. |
| **Luvas nunca são reconhecidas** | As mãos precisam aparecer dentro da caixa da pessoa. Afaste-se um pouco da câmera ou aumente `MARGEM_INFERIOR_ROSTO`. |
| **"Não foi possível acessar a webcam"** | Feche outros programas que usem a câmera (Teams, Zoom, navegador). Se houver mais de uma câmera, mude `INDICE_CAMERA`. |
| **"Não foi possível conectar à câmera IP"** | Confira o endereço, o usuário e a senha (abra o mesmo endereço no VLC, em Mídia > Abrir fluxo de rede, para testar fora do programa). A câmera precisa estar ligada e na mesma rede. |
| **Câmera IP com atraso ou lenta** | Use o substream da câmera (resolução menor). |
| **Imagem da câmera IP cinza ou borrada** | Perda de pacotes na rede. Deixe `RTSP_POR_TCP = True` e, se possível, use cabo em vez de Wi-Fi. |
| **Aviso "Detector de rosto não encontrado"** | Baixe o arquivo `.onnx` (veja [Instalação](#instalação)). Sem ele o programa funciona, mas trata a cena inteira como uma pessoa. |
| **Vídeo lento** | Reduza `LARGURA_CAPTURA`/`ALTURA_CAPTURA` para 640 e 480 e aumente o intervalo de análise na tela. |
| **Nem todas as pessoas são detectadas** | Se elas estão de costas, de lado ou se cruzando, mude para o modo **Vigilância**. No modo catraca, o rosto precisa estar visível e não muito pequeno: acrescente uma escala maior em `LARGURAS_DETECCAO` (por exemplo, `(960, 640, 320)`) ou aproxime a câmera. |
| **Fotos de evidência repetidas da mesma pessoa** | O detector está perdendo a pessoa por mais tempo do que a memória do rastreador. Aumente `TEMPO_MEMORIA_PESSOA_SEG`. |
| **Duas pessoas diferentes contadas como uma** | O contrário: diminua `TEMPO_MEMORIA_PESSOA_SEG` ou `DISTANCIA_MAXIMA_RASTREIO`. |
| **A caixa não aparece** | O detector precisa ver o rosto. Fique de frente para a câmera, com boa iluminação. |
| **Status errado com frequência** | O dataset é pequeno. Colete mais imagens e treine de novo. |
| **"Painel web indisponível (porta 8080 em uso)"** | Outro programa usa a porta, ou o `painel_web.py` está aberto. Feche-o ou troque a porta em Configurações > Painel web. |
| **O painel web não abre em outro aparelho** | Os dois precisam estar na mesma rede, e o Windows precisa ter permitido o Python no firewall (redes privadas). |
| **`No module named 'tensorflow.python'`** ao instalar | Caminhos longos desativados no Windows. Em um PowerShell de administrador: `New-ItemProperty -Path "HKLM:\SYSTEM\CurrentControlSet\Control\FileSystem" -Name "LongPathsEnabled" -Value 1 -PropertyType DWORD -Force`, reinicie o computador e reinstale com `pip install --force-reinstall tensorflow`. |
| **`Could not find the DLL(s) 'msvcp140.dll'`** | Instale o Microsoft Visual C++ Redistributable: `winget install --id Microsoft.VCRedist.2015+.x64 -e`. |

---

## Limitações e próximos passos

Limitações conhecidas:

- **No modo catraca, a pessoa é localizada pelo rosto.** De costas ou com o rosto muito coberto, ela não é detectada; para isso existe o modo vigilância.
- **No modo vigilância, quem está quase todo encoberto por outra pessoa pode não ser detectado**, e a análise é mais lenta.
- **O modelo de EPI precisa de imagens dos dois modos** para funcionar bem em ambos, porque o recorte de cada um é diferente.
- **O modelo por EPI que vem no repositório foi treinado com poucas imagens.** Ele serve para demonstração; para uso real, é preciso coletar um dataset maior e treinar de novo.
- **O modelo olha o recorte inteiro da pessoa, reduzido para 224x224.** Itens pequenos, como óculos e luvas, são os mais difíceis e os que mais dependem de um dataset grande e variado.
- **As mãos precisam estar visíveis** para as luvas serem avaliadas. Mãos fora da imagem ou atrás do corpo contam como "sem luvas".
- **Pessoas muito próximas** podem ter as caixas sobrepostas, e o equipamento de uma influenciar o resultado da outra.
- **O número de imagens necessárias é alto.** Com poucas dezenas de imagens, o modelo erra em pessoas, fundos e iluminações que não viu no treino.
- **O número da pessoa não é identidade.** Quem sai da imagem e volta recebe um número novo.

Próximos passos possíveis:

- Confirmação por voz da Ordem de Serviço (etapa futura do desafio).
- Um detector de objetos (que localiza cada equipamento na imagem), mais preciso para itens pequenos como óculos e luvas.
- Edição dos setores pela própria tela, sem mexer no `config.py`.
- Integração com uma catraca real: a maquete ESP32 já aciona um relé, que é o mesmo sinal de contato seco usado por muitas catracas.
- Relatórios da auditoria por período (dia, semana), além do relatório por evento que já existe.
