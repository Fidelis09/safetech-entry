// ============================================================
// TESTE DE TODAS AS PEÇAS DA CATRACA (sem Wi-Fi, sem o programa)
// ============================================================
//
// Grave este sketch ANTES do firmware completo, só para conferir se
// as peças estão ligadas certo. Ele repete sem parar, um passo de
// cada vez, e escreve o passo na tela OLED e no Monitor Serial
// (115200 baud):
//
//   1) LED verde aceso
//   2) LED amarelo aceso
//   3) LED vermelho aceso
//   4) Buzzer: dois bipes
//   5) Cancela (servo) abre e fecha
//   6) Relé: um pulso (você ouve o "clique")
//
// Peça que não estiver ligada não atrapalha: o teste segue com as
// outras. Na partida ele mostra no Monitor Serial quais dispositivos
// I2C achou (a tela OLED costuma ser 0x3C ou 0x3D).
//
// Bibliotecas necessárias: ESP32Servo, Adafruit SSD1306, Adafruit GFX.
// ============================================================

#include <Wire.h>
#include <ESP32Servo.h>
#include <Adafruit_GFX.h>
#include <Adafruit_SSD1306.h>


// ============================================================
// PINOS E AJUSTES
// ============================================================
//
// Os mesmos pinos do firmware completo (config_exemplo.h). Se você
// ligou em outros pinos, troque aqui E no config.h depois.
// ============================================================

#define PINO_SERVO         13
#define PINO_LED_VERDE     25
#define PINO_LED_AMARELO   26
#define PINO_LED_VERMELHO  27
#define PINO_BUZZER        33
#define PINO_RELE          32

// A tela usa o I2C padrão do ESP32: SDA no pino 21, SCL no 22.
// O endereço é procurado sozinho entre estes dois.
#define OLED_ENDERECO_A    0x3C
#define OLED_ENDERECO_B    0x3D

#define ANGULO_FECHADA     0
#define ANGULO_ABERTA      90

// Muitos módulos relé ligam com o pino em nível BAIXO (LOW).
// Mesmo ajuste do config.h da catraca.
#define RELE_LIGA_EM_NIVEL_BAIXO  true

// Quanto tempo cada passo do teste dura
#define TEMPO_PASSO_MS     1000

// Bipe: duração de cada apito e da pausa entre eles
#define TEMPO_BIPE_MS      150

// Duração do pulso no relé
#define TEMPO_PULSO_RELE_MS 500


Servo cancela;

Adafruit_SSD1306 tela(128, 64, &Wire, -1);
bool telaFunciona = false;


// ============================================================
// FUNÇÕES AUXILIARES
// ============================================================

// Escreve na tela (duas linhas: título grande e detalhe pequeno)
void mostrarNaTela(const char* titulo, const char* detalhe) {

  if (!telaFunciona) return;

  tela.clearDisplay();
  tela.setTextColor(SSD1306_WHITE);

  tela.setTextSize(2);
  tela.setCursor(0, 0);
  tela.println(titulo);

  tela.setTextSize(1);
  tela.setCursor(0, 28);
  tela.println(detalhe);

  tela.display();
}

// Acende só um LED (ou nenhum, com pino -1)
void acenderSo(int pino) {

  digitalWrite(PINO_LED_VERDE, pino == PINO_LED_VERDE ? HIGH : LOW);
  digitalWrite(PINO_LED_AMARELO, pino == PINO_LED_AMARELO ? HIGH : LOW);
  digitalWrite(PINO_LED_VERMELHO, pino == PINO_LED_VERMELHO ? HIGH : LOW);
}

void ligarRele(bool ligar) {

  bool nivel = RELE_LIGA_EM_NIVEL_BAIXO ? !ligar : ligar;

  digitalWrite(PINO_RELE, nivel ? HIGH : LOW);
}

// Faz um passo do teste: escreve na tela e no Monitor Serial
void anunciar(const char* titulo, const char* detalhe) {

  Serial.print(titulo);
  Serial.print(" - ");
  Serial.println(detalhe);

  mostrarNaTela(titulo, detalhe);
}

// Procura dispositivos I2C e escreve o endereço de cada um.
// Devolve o endereço da tela, ou 0 se não achou.
uint8_t procurarTela() {

  uint8_t encontrada = 0;
  int total = 0;

  for (uint8_t endereco = 1; endereco < 127; endereco++) {

    Wire.beginTransmission(endereco);

    if (Wire.endTransmission() == 0) {

      Serial.printf("I2C: dispositivo em 0x%02X\n", endereco);
      total++;

      if (endereco == OLED_ENDERECO_A || endereco == OLED_ENDERECO_B) {
        encontrada = endereco;
      }
    }
  }

  if (total == 0) {
    Serial.println("I2C: nenhum dispositivo. Confira SDA (21), SCL (22), VCC e GND da tela.");
  }

  return encontrada;
}


// ============================================================
// SETUP E LOOP
// ============================================================

void setup() {

  Serial.begin(115200);
  delay(500);

  Serial.println();
  Serial.println("=== Teste de todas as pecas da catraca ===");

  pinMode(PINO_LED_VERDE, OUTPUT);
  pinMode(PINO_LED_AMARELO, OUTPUT);
  pinMode(PINO_LED_VERMELHO, OUTPUT);
  pinMode(PINO_BUZZER, OUTPUT);
  pinMode(PINO_RELE, OUTPUT);

  digitalWrite(PINO_BUZZER, LOW);
  ligarRele(false);

  cancela.setPeriodHertz(50);              // servos comuns usam 50 Hz
  cancela.attach(PINO_SERVO, 500, 2400);   // pulso mínimo e máximo do SG90 (microssegundos)
  cancela.write(ANGULO_FECHADA);

  // Tela: procura o endereço e inicia
  Wire.begin();

  uint8_t endereco = procurarTela();

  if (endereco != 0) {

    telaFunciona = tela.begin(SSD1306_SWITCHCAPVCC, endereco);

    Serial.printf("Tela OLED: %s (endereco 0x%02X)\n", telaFunciona ? "OK" : "falhou ao iniciar", endereco);

  } else {
    Serial.println("Tela OLED: nao encontrada (o teste segue sem ela)");
  }

  mostrarNaTela("TESTE", "Pecas da catraca");
  delay(1500);
}

void loop() {

  // Aqui o delay não atrapalha: é só um teste, um passo de cada vez

  anunciar("LED VERDE", "Passo 1 de 6");
  acenderSo(PINO_LED_VERDE);
  delay(TEMPO_PASSO_MS);

  anunciar("LED AMARELO", "Passo 2 de 6");
  acenderSo(PINO_LED_AMARELO);
  delay(TEMPO_PASSO_MS);

  anunciar("LED VERMELHO", "Passo 3 de 6");
  acenderSo(PINO_LED_VERMELHO);
  delay(TEMPO_PASSO_MS);

  acenderSo(-1);

  anunciar("BUZZER", "Passo 4 de 6: 2 bipes");

  for (int i = 0; i < 2; i++) {
    digitalWrite(PINO_BUZZER, HIGH);
    delay(TEMPO_BIPE_MS);
    digitalWrite(PINO_BUZZER, LOW);
    delay(TEMPO_BIPE_MS);
  }

  delay(TEMPO_PASSO_MS);

  anunciar("CANCELA", "Passo 5 de 6: abrindo");
  cancela.write(ANGULO_ABERTA);
  delay(TEMPO_PASSO_MS);

  mostrarNaTela("CANCELA", "Passo 5 de 6: fechando");
  Serial.println("CANCELA - fechando");
  cancela.write(ANGULO_FECHADA);
  delay(TEMPO_PASSO_MS);

  anunciar("RELE", "Passo 6 de 6: pulso");
  ligarRele(true);
  delay(TEMPO_PULSO_RELE_MS);
  ligarRele(false);
  delay(TEMPO_PASSO_MS);
}
