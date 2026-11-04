// ============================================================
// TESTE VISUAL DA TELA DA CATRACA (sem Wi-Fi, sem o programa)
// ============================================================
//
// Mostra, um depois do outro, como a tela vai ficar em cada situação
// da catraca, junto com o LED correspondente:
//
//   AGUARDANDO   -> texto pequeno e um "olho" no centro   | LED amarelo
//   ANALISANDO   -> barra de progresso correndo           | LED amarelo piscando
//   LIBERADO     -> moldura dupla e um "visto" (check)    | LED verde
//   NEGADO       -> TELA INTEIRA ACESA, piscando          | LED vermelho
//   OFFLINE      -> um "X" piscando                       | LED vermelho piscando
//
// A tela OLED é monocromática (não faz vermelho). O destaque do
// NEGADO vem do contraste: a tela inteira acende e as letras ficam
// pretas por cima. Quem dá a cor são os LEDs.
//
// Bibliotecas necessárias: Adafruit SSD1306 e Adafruit GFX.
// ============================================================

#include <Wire.h>
#include <Adafruit_GFX.h>
#include <Adafruit_SSD1306.h>


// ============================================================
// PINOS E AJUSTES
// ============================================================

#define PINO_LED_VERDE     25
#define PINO_LED_AMARELO   26
#define PINO_LED_VERMELHO  27

// Endereço I2C da tela (a maioria dos módulos de 0,96" usa 0x3C)
#define OLED_ENDERECO_I2C  0x3C

// Quanto tempo cada situação fica na tela
#define TEMPO_SITUACAO_MS  4000

// Velocidade do pisca-pisca (NEGADO, SEM CONEXAO, LED)
#define INTERVALO_PISCA_MS 350

// Redesenha a tela neste intervalo (para as animações)
#define INTERVALO_QUADRO_MS 80


Adafruit_SSD1306 tela(128, 64, &Wire, -1);

// As situações, na ordem em que são mostradas
enum Situacao { AGUARDANDO, ANALISANDO, LIBERADO, NEGADO, SEM_CONEXAO, TOTAL_DE_SITUACOES };


// ============================================================
// FUNÇÕES DE DESENHO
// ============================================================

// Escreve um texto centralizado na horizontal, na altura y.
// "cor" é a cor da letra (WHITE em fundo preto, BLACK em fundo aceso).
void textoCentralizado(const char* texto, int y, int tamanho, uint16_t cor) {

  int16_t x1, y1;
  uint16_t largura, altura;

  tela.setTextSize(tamanho);
  tela.setTextColor(cor);
  tela.getTextBounds(texto, 0, 0, &x1, &y1, &largura, &altura);

  tela.setCursor((128 - largura) / 2, y);
  tela.print(texto);
}

void desenharAguardando(unsigned long agora) {

  tela.clearDisplay();

  textoCentralizado("AGUARDANDO", 4, 2, WHITE);

  // Um "olho" que pisca de vez em quando
  bool aberto = (agora / 1200) % 4 != 0;

  tela.drawCircle(64, 42, 14, WHITE);

  if (aberto) tela.fillCircle(64, 42, 6, WHITE);
  else tela.drawLine(52, 42, 76, 42, WHITE);

  tela.setTextSize(1);
  textoCentralizado("Aproxime-se da camera", 57, 1, WHITE);
}

void desenharAnalisando(unsigned long agora) {

  tela.clearDisplay();

  textoCentralizado("ANALISANDO", 4, 2, WHITE);

  // Barra de progresso: um bloco que corre da esquerda para a direita
  tela.drawRect(8, 32, 112, 14, WHITE);

  int bloco = 28;
  int posicao = (agora / 20) % (112 - bloco);

  tela.fillRect(10 + posicao, 34, bloco, 10, WHITE);

  textoCentralizado("Verificando EPIs...", 54, 1, WHITE);
}

void desenharLiberado() {

  tela.clearDisplay();

  // Moldura dupla
  tela.drawRect(0, 0, 128, 64, WHITE);
  tela.drawRect(3, 3, 122, 58, WHITE);

  textoCentralizado("LIBERADO", 10, 2, WHITE);

  // "Visto" grosso (várias linhas lado a lado)
  for (int i = -1; i <= 1; i++) {
    tela.drawLine(50, 40 + i, 59, 49 + i, WHITE);
    tela.drawLine(59, 49 + i, 80, 30 + i, WHITE);
  }
}

void desenharNegado(unsigned long agora) {

  // A cada pisca, a tela inteira alterna entre ACESA e normal.
  // É o efeito de "tela vermelha" possível numa tela monocromática.
  bool acesa = (agora / INTERVALO_PISCA_MS) % 2 == 0;

  uint16_t fundo = acesa ? WHITE : BLACK;
  uint16_t letra = acesa ? BLACK : WHITE;

  tela.clearDisplay();
  tela.fillRect(0, 0, 128, 64, fundo);

  textoCentralizado("NEGADO", 6, 3, letra);

  textoCentralizado("Falta: Capacete", 40, 1, letra);
  textoCentralizado("1 de 2 pessoa(s)", 52, 1, letra);
}

void desenharSemConexao(unsigned long agora) {

  tela.clearDisplay();

  textoCentralizado("OFFLINE", 4, 2, WHITE);

  // "X" grande que pisca
  if ((agora / INTERVALO_PISCA_MS) % 2 == 0) {

    for (int i = -1; i <= 1; i++) {
      tela.drawLine(52 + i, 28, 76 + i, 52, WHITE);
      tela.drawLine(76 + i, 28, 52 + i, 52, WHITE);
    }
  }
}


// ============================================================
// LEDS
// ============================================================

void atualizarLeds(Situacao situacao, unsigned long agora) {

  bool pisca = (agora / INTERVALO_PISCA_MS) % 2 == 0;

  bool verde = (situacao == LIBERADO);
  bool vermelho = (situacao == NEGADO) || (situacao == SEM_CONEXAO && pisca);
  bool amarelo = (situacao == AGUARDANDO) || (situacao == ANALISANDO && pisca);

  digitalWrite(PINO_LED_VERDE, verde ? HIGH : LOW);
  digitalWrite(PINO_LED_AMARELO, amarelo ? HIGH : LOW);
  digitalWrite(PINO_LED_VERMELHO, vermelho ? HIGH : LOW);
}

const char* nomeDaSituacao(Situacao situacao) {

  switch (situacao) {
    case AGUARDANDO:  return "AGUARDANDO";
    case ANALISANDO:  return "ANALISANDO";
    case LIBERADO:    return "LIBERADO";
    case NEGADO:      return "NEGADO";
    default:          return "SEM CONEXAO";
  }
}


// ============================================================
// SETUP E LOOP
// ============================================================

Situacao situacaoAtual = TOTAL_DE_SITUACOES;   // força o aviso da primeira
unsigned long inicioDaSituacao = 0;
unsigned long ultimoQuadro = 0;

void setup() {

  Serial.begin(115200);
  delay(500);

  Serial.println();
  Serial.println("=== Teste visual da tela ===");

  pinMode(PINO_LED_VERDE, OUTPUT);
  pinMode(PINO_LED_AMARELO, OUTPUT);
  pinMode(PINO_LED_VERMELHO, OUTPUT);

  if (!tela.begin(SSD1306_SWITCHCAPVCC, OLED_ENDERECO_I2C)) {

    Serial.println("Tela OLED nao encontrada. Confira SDA (21), SCL (22), VCC (3V3) e GND.");

    // Sem tela, pisca o LED vermelho para avisar
    while (true) {
      digitalWrite(PINO_LED_VERMELHO, HIGH);
      delay(200);
      digitalWrite(PINO_LED_VERMELHO, LOW);
      delay(200);
    }
  }

  Serial.println("Tela OLED: OK");
}

void loop() {

  unsigned long agora = millis();

  // Passa para a próxima situação a cada TEMPO_SITUACAO_MS
  Situacao esperada = (Situacao)((agora / TEMPO_SITUACAO_MS) % TOTAL_DE_SITUACOES);

  if (esperada != situacaoAtual) {

    situacaoAtual = esperada;
    inicioDaSituacao = agora;

    Serial.printf("Situacao: %s\n", nomeDaSituacao(situacaoAtual));
  }

  atualizarLeds(situacaoAtual, agora);

  if (agora - ultimoQuadro < INTERVALO_QUADRO_MS) return;

  ultimoQuadro = agora;

  switch (situacaoAtual) {
    case AGUARDANDO:  desenharAguardando(agora); break;
    case ANALISANDO:  desenharAnalisando(agora); break;
    case LIBERADO:    desenharLiberado(); break;
    case NEGADO:      desenharNegado(agora); break;
    default:          desenharSemConexao(agora); break;
  }

  tela.display();
}
