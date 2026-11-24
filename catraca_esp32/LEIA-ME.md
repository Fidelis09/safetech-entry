# Catraca de demonstração (ESP32)

Maquete de catraca que obedece ao SafeTech Entry. O ESP32 recebe o status do acesso de **dois jeitos**, que podem ficar ligados ao mesmo tempo:

| Caminho | Como funciona | Quando usar |
|---|---|---|
| **Cabo USB** (principal) | O programa escreve uma linha de texto na porta serial do ESP32, a cada 0,3 s. Não precisa de rede nem de senha. | Sempre que o ESP32 estiver ligado ao computador. Já vem ligado nos dois lados. |
| **Wi-Fi** (opcional) | O ESP32 pergunta, duas vezes por segundo, ao painel web (`/api/ao-vivo`). | Quando o ESP32 ficar longe do computador. Liga com `WIFI_ATIVO true` no `config.h`. |

Enquanto o cabo estiver mandando dados, o Wi-Fi nem é consultado. **Se o cabo sair e o Wi-Fi estiver ligado, o Wi-Fi assume sozinho**, sem regravar nada. Com isso, a catraca:

| Status no programa | Cancela | LEDs | Tela (veja o visual abaixo) | Som |
|---|---|---|---|---|
| Ninguém na câmera | Fechada | Amarelo aceso | `AGUARDANDO` + um "olho" | - |
| Analisando | Fechada | Amarelo piscando | `ANALISANDO` + barra correndo | - |
| **Liberado** | **Abre por 3 s** e fecha | Verde | `LIBERADO` + moldura e "visto" | - |
| **Negado** | Fechada (fecha na hora, se estava aberta) | Vermelho | **Tela inteira acesa, piscando**: `NEGADO` / "Falta: Capacete" | 2 bipes |
| Câmera desligada no programa | Fechada | Amarelo aceso | `CAMERA OFF` | - |
| Sem dados do programa (cabo solto, programa fechado, Wi-Fi fora, senha errada) | **Fechada** | Vermelho piscando | `OFFLINE` + "X" piscando e o motivo | - |
| Programa no **modo Vigilância** | **Fechada** (catraca desligada) | Todos apagados | `VIGILANCIA` + "Catraca desligada" | - |

**Com várias áreas (câmeras), a catraca segue só a área marcada** em Configurações > Área e câmera > "Esta área comanda a catraca física". Sem nenhuma marcada, ela fica desligada (fechada).

**A catraca só obedece no modo Catraca do programa.** No modo Vigilância (fiscalização de uma área, sem acesso a liberar) ela fica desligada, qualquer que seja a situação das pessoas. Ao voltar para o modo Catraca, ela volta a obedecer na hora.

**A tela OLED é monocromática** (não faz vermelho). O destaque do NEGADO vem do contraste: a tela inteira acende e pisca, com as letras pretas por cima. A cor mesmo vem dos LEDs. Para ver todos os visuais sem Wi-Fi nem programa, grave o `teste_tela` (veja "Testes antes do firmware").

**Regra de segurança (a mesma do sistema): na dúvida, nega.** Qualquer falha de comunicação mantém a cancela fechada: 3 s sem nenhuma mensagem válida vão para `OFFLINE`, e um "liberado" sem notícia nova há mais de 1,5 s já volta para "analisando". Mensagem cortada, ruído no cabo ou valor desconhecido são ignorados.

A catraca **só recebe** o status. Ela não manda nada de volta ao programa, e o painel web continua somente leitura.

## Usar pelo cabo (o jeito mais simples)

1. Grave o firmware (veja "Instalação"). O `config.h` vem com `WIFI_ATIVO false`: não precisa de Wi-Fi.
2. Deixe o ESP32 ligado no USB do computador.
3. Abra o SafeTech Entry. Ele acha o ESP32 sozinho e mostra no rodapé da janela **"Catraca: COM3 conectada"**.
4. Ligue a câmera: a catraca já obedece.

O que o rodapé pode dizer:

| Rodapé | Significado |
|---|---|
| `Catraca: COM3 conectada` | Tudo certo: o programa está enviando o status |
| `Catraca: ESP32 nao encontrado no USB` | O ESP32 não está plugado, o cabo é só de carga ou falta o driver (CP210x/CH340) |
| `Catraca: COM3 ocupada ou indisponivel` | Outro programa tem a porta: feche o Monitor Serial e a Arduino IDE |
| `Catraca: cabo desconectado, procurando...` | Puxaram o cabo: ao plugar de novo, volta sozinho |

**Atenção:** enquanto o SafeTech estiver com a porta aberta, a Arduino IDE **não consegue gravar a placa** nem abrir o Monitor Serial. Para gravar, feche o SafeTech ou ponha `CATRACA_SERIAL_ATIVA = False` no `safetech/config.py`.

O formato da mensagem (para quem quiser ver no Monitor Serial): `ST|negado|1|2|Capacete;Oculos`, ou seja, acesso, quantas pessoas estão irregulares, quantas há na imagem e o que falta.

**Uma passagem por liberação:** depois de abrir, a cancela só abre de novo quando o status sair de "liberado" e voltar. Assim ela não fica aberta para sempre com uma pessoa parada na frente, como uma catraca de verdade.

---

## Peças

| Peça | Quantidade | Preço aproximado |
|---|---|---|
| ESP32 DevKit (38 ou 30 pinos) | 1 | R$ 35–50 |
| Servo motor SG90 | 1 | R$ 12–15 |
| Tela OLED 0,96" I2C (SSD1306, 4 pinos) | 1 | R$ 20 |
| LED verde, amarelo e vermelho (5 mm) | 1 de cada | R$ 3 |
| Resistor de 220 Ω | 3 | R$ 1 |
| Buzzer **ativo** 3–5 V | 1 | R$ 4 |
| Módulo relé 5 V (1 canal) | 1 (opcional) | R$ 8 |
| Capacitor eletrolítico 470 µF (10 V ou mais) | 1 (recomendado) | R$ 2 |
| Protoboard + jumpers macho-macho e macho-fêmea | 1 kit | R$ 20 |
| Cabo USB **de dados** (não só de carga) | 1 | - |

Total: cerca de R$ 100 a 130. O braço da cancela pode ser um palito de sorvete ou uma régua de 15 cm colada no braço do servo, e a "catraca" uma caixa de MDF ou papelão.

**Buzzer ativo x passivo:** o ativo apita sozinho quando recebe energia (é o que o código espera). O passivo precisa de uma frequência e fica mudo com este código. Na loja, o ativo costuma ter um adesivo por cima.

---

## Ligações

```
ESP32                 Peça
-----                 ----
GPIO 13  ───────────  Servo: fio LARANJA (sinal)
5V / VIN ───────────  Servo: fio VERMELHO
GND      ───────────  Servo: fio MARROM

3V3      ───────────  OLED: VCC
GND      ───────────  OLED: GND
GPIO 21  ───────────  OLED: SDA
GPIO 22  ───────────  OLED: SCL

GPIO 25  ── 220 Ω ──  LED VERDE    (perna longa) ; perna curta ── GND
GPIO 26  ── 220 Ω ──  LED AMARELO  (perna longa) ; perna curta ── GND
GPIO 27  ── 220 Ω ──  LED VERMELHO (perna longa) ; perna curta ── GND

GPIO 33  ───────────  Buzzer: perna + (a mais longa)
GND      ───────────  Buzzer: perna -

5V / VIN ───────────  Relé: VCC
GND      ───────────  Relé: GND
GPIO 32  ───────────  Relé: IN
```

Cuidados:

- **Todos os GND juntos** (ESP32, servo, tela, LEDs, buzzer e relé), na fileira azul da protoboard.
- **Capacitor de 470 µF entre o 5V e o GND do servo** (perna mais curta, marcada com "-", no GND). O servo puxa um pico de corrente ao se mover; sem o capacitor, o ESP32 pode reiniciar sozinho.
- **O pino 5V/VIN só tem energia com o ESP32 ligado no USB.** Se o servo tremer ou o ESP32 reiniciar mesmo com o capacitor, alimente o servo com uma fonte de 5 V separada (unindo os GND).
- **Relé**: os bornes `COM` e `NO` do módulo são o "contato seco" que abriria uma catraca real. Na maquete ele só faz um "clique" ao abrir, o que já é ótimo para explicar na apresentação.

---

## Instalação (Arduino IDE 2)

1. Instale a **Arduino IDE 2** (arduino.cc/en/software).
2. Placa ESP32: em **Arquivo > Preferências > URLs adicionais**, cole
   `https://espressif.github.io/arduino-esp32/package_esp32_index.json`.
   Depois, em **Ferramentas > Placa > Gerenciador de placas**, instale **esp32** (Espressif Systems).
3. Bibliotecas, em **Ferramentas > Gerenciar bibliotecas**:
   - **ArduinoJson** (Benoit Blanchon), versão 7
   - **ESP32Servo** (Kevin Harrington)
   - **Adafruit SSD1306** (aceite instalar também a **Adafruit GFX**)
4. Nesta pasta, **copie `config_exemplo.h` para `config.h`**.
   - **Só pelo cabo:** não precisa preencher nada. `WIFI_ATIVO` já vem `false`.
   - **Para usar o Wi-Fi também:** troque `WIFI_ATIVO` para `true` e preencha:
     - `WIFI_NOME` e `WIFI_SENHA`: a rede do computador (**2,4 GHz**; o ESP32 não conecta em 5 GHz);
     - `SAFETECH_IP` e `SAFETECH_PORTA`: o endereço que aparece no rodapé do programa ("Painel web: http://192.168.0.15:8080"). O IP muda de rede para rede;
     - `SAFETECH_USUARIO` e `SAFETECH_SENHA`: o login do painel web, definido no programa em **Configurações > Painel web** (trocou lá, troque aqui).

   O `config.h` pode ter senhas e **não vai para o git**.
   Para o cabo funcionar, o programa precisa do **pyserial** (`python -m pip install -r requirements.txt`).
5. Abra `catraca_esp32.ino`, escolha **Ferramentas > Placa > ESP32 Dev Module** e a **porta COM** do ESP32, e clique em **Carregar** (seta).
   - Se ficar em "Connecting....", segure o botão **BOOT** do ESP32 até começar a gravar.
   - Se nenhuma porta COM aparecer: troque o cabo (alguns só carregam) ou instale o driver do chip USB da placa (CP210x ou CH340, escrito na placa).
6. Abra o **Monitor Serial** (115200 baud). Ele mostra cada mudança de situação. (Feche o SafeTech antes: ele toma a porta.)

---

## Testes antes do firmware

Dois sketches prontos, sem Wi-Fi e sem o programa. Cada um é uma pasta com o seu `.ino`; abra o arquivo na Arduino IDE e grave como o firmware.

| Pasta | O que faz |
|---|---|
| `teste_pecas/` | Passa por **todas as peças**, uma por vez: LED verde, amarelo, vermelho, buzzer (2 bipes), cancela (abre e fecha) e relé (pulso). Mostra cada passo na tela e no Monitor Serial, e escreve no Monitor Serial o endereço I2C da tela. Peça que não estiver ligada não atrapalha. |
| `teste_tela/` | Passa pelos **cinco visuais da tela** (aguardando, analisando, liberado, negado, offline), 4 segundos cada, com o LED de cada um. |

Os dois pinos e o endereço da tela (`0x3C`) são os mesmos do firmware. Se um teste funciona, o firmware também deve funcionar com aquela peça.

---

## Antes da apresentação: teste em 3 passos

**Pelo cabo:** abra o SafeTech com o ESP32 no USB e confira no rodapé "Catraca: COM3 conectada". Ligue a câmera e fique na frente dela, sem e depois com o capacete: a catraca deve negar e liberar.

**Pelo Wi-Fi** (só se `WIFI_ATIVO true`):

1. **O programa está acessível na rede?** No celular, conectado ao mesmo Wi-Fi, abra `http://<IP do computador>:8080`. Se o painel web abrir, a catraca também vai conseguir. Se não abrir, permita o Python no firewall do Windows (redes privadas) e confira se **Permitir acesso pela rede** está marcado em Configurações > Painel web.
2. **A resposta está certa?** No navegador, abra `http://<IP>:8080/api/ao-vivo`. Deve aparecer algo como `"acesso": "negado"` e `"faltando": ["Capacete"]`.
3. **A catraca reage?** Com o ESP32 ligado, fique na frente da câmera, sem e depois com o capacete.

Monte primeiro **só o ESP32 e o Monitor Serial**, sem as peças: dá para ver as mensagens `Situacao: NEGADO` e `Cancela ABERTA` antes de ligar qualquer fio.

---

## Roteiro sugerido para a apresentação

1. Ninguém na câmera: catraca em `AGUARDANDO` (amarelo).
2. Uma pessoa entra **sem capacete**: `NEGADO`, LED vermelho, dois bipes, a tela mostra "Falta: Capacete".
3. A pessoa coloca o capacete: cerca de 1 s depois, `LIBERADO`, a cancela abre e o relé estala.
4. No programa, troque o setor (ex.: para "Laboratório"): a exigência muda na hora e a catraca acompanha.
5. Mostre a auditoria com a foto de cada decisão e gere o relatório de uma linha.
6. Feche o programa (ou puxe o cabo): a catraca vai para `OFFLINE` em até 3 s e **fica fechada** ("na dúvida, nega").

Dicas: leve **uma rede própria** (roteador do notebook ou do celular, em 2,4 GHz), e treine o modelo com fotos das pessoas e EPIs que vão aparecer, **no local e com a mesma luz** da apresentação.

---

## Problemas comuns

| Tela / sintoma | Causa provável e solução |
|---|---|
| `OFFLINE` / "Sem dados do cabo USB" | O programa está fechado, o cabo saiu ou o rodapé do programa não mostra "Catraca: ... conectada". Veja a tabela do rodapé acima. |
| `OFFLINE` / "Sem Wi-Fi" | Nome ou senha da rede errados, ou rede de 5 GHz. Use 2,4 GHz. |
| `OFFLINE` / "Programa fora do ar" | O programa está fechado, o IP mudou (confira no rodapé do programa) ou o firewall bloqueou. Faça o teste 1 acima. |
| `OFFLINE` / "Login recusado" | Usuário ou senha diferentes dos do painel web. |
| `CAMERA OFF` | O programa está aberto, mas a câmera está parada: clique em "Iniciar câmera". |
| ESP32 reinicia quando o servo mexe | Falta o capacitor, ou a USB não aguenta o servo. Veja "Cuidados" acima. |
| Cancela abre para o lado errado | Troque `ANGULO_FECHADA` e `ANGULO_ABERTA` no `config.h`. |
| Relé fica ligado o tempo todo | Troque `RELE_LIGA_EM_NIVEL_BAIXO` no `config.h`. |
| Tela apagada | Confira SDA/SCL; tente `OLED_ENDERECO_I2C 0x3D`. A catraca funciona sem a tela. |
| Erro "Copie o arquivo config_exemplo.h para config.h" ao compilar | Falta o passo 4 da instalação. |

O formato da resposta do programa que a catraca usa é verificado pelo teste `testes/test_contrato_catraca.py`: se alguém mudar o `/api/ao-vivo`, o teste avisa antes de a catraca parar de funcionar.
