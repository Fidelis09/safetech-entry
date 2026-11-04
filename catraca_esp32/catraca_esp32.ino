// ============================================================
// SAFETECH ENTRY - CATRACA DE DEMONSTRAÇÃO (ESP32)
// ============================================================
//
// Uma maquete de catraca que obedece ao SafeTech Entry.
//
// Como funciona:
//
//   1) O ESP32 recebe do programa o status atual do acesso. Há DOIS
//      caminhos, que podem estar ligados ao mesmo tempo:
//
//        CABO USB -> o programa escreve uma linha de texto na porta
//                    serial a cada 0,3 s (linhas "ST|negado|1|2|...").
//                    É o caminho principal: não depende de rede.
//
//        WI-FI    -> (só se WIFI_ATIVO no config.h) duas vezes por
//                    segundo ele pede o status ao painel web, no
//                    endereço /api/ao-vivo (o mesmo que o navegador do
//                    gerente usa). É só LEITURA.
//
//      Enquanto o cabo estiver mandando dados, o Wi-Fi nem é
//      consultado. Se o cabo sair, o Wi-Fi assume sozinho.
//
//   2) Conforme o status, ele move a cancela (servo), acende os
//      LEDs, apita e escreve na tela o que está faltando.
//
//   3) No modo VIGILÂNCIA do programa (fiscalização de uma área, sem
//      acesso a liberar), a catraca fica DESLIGADA: fechada, LEDs
//      apagados, sem bipe, com o aviso na tela. Ela só obedece no modo
//      CATRACA.
//
// Regra de segurança (a mesma do sistema): NA DÚVIDA, NEGA. Se os
// dados pararem de chegar, o programa fechar ou a mensagem vier
// estranha, a cancela fica fechada.
//
// Bibliotecas (instalar pelo Gerenciador de Bibliotecas da IDE):
//   - ArduinoJson        (Benoit Blanchon)  - lê a resposta do programa
//   - ESP32Servo         (Kevin Harrington) - controla o servo
//   - Adafruit SSD1306   (Adafruit)         - tela OLED
//   - Adafruit GFX       (Adafruit)         - desenho na tela
// ============================================================

#include <WiFi.h>
#include <HTTPClient.h>
#include <Wire.h>

#include <ArduinoJson.h>
#include <ESP32Servo.h>
#include <Adafruit_GFX.h>
#include <Adafruit_SSD1306.h>

// O config.h tem as senhas e não vai para o git. Se ele não existir,
// a compilação para com uma mensagem explicando o que fazer.
#if __has_include("config.h")
  #include "config.h"
#else
  #error "Copie o arquivo config_exemplo.h para config.h (na mesma pasta) e preencha o Wi-Fi e o IP do computador."
#endif


// Valores usados se o config.h for de uma versão anterior (que não
// tinha estes ajustes). Veja o significado em config_exemplo.h.
#ifndef WIFI_ATIVO
  #define WIFI_ATIVO true
#endif

#ifndef VELOCIDADE_SERIAL
  #define VELOCIDADE_SERIAL 115200
#endif

#ifndef TEMPO_LIBERADO_VALIDO_MS
  #define TEMPO_LIBERADO_VALIDO_MS 1500
#endif


// ============================================================
// SITUAÇÕES POSSÍVEIS DA CATRACA
// ============================================================
//
// As quatro primeiras vêm do campo "acesso" do programa. As duas
// últimas são da própria catraca: câmera desligada no programa e
// falta de comunicação com ele.
// ============================================================

enum Situacao {
  AGUARDANDO,        // ninguém na frente da câmera
  ANALISANDO,        // tem gente, a IA ainda está decidindo
  LIBERADO,          // todos com os EPIs exigidos
  NEGADO,            // alguém sem EPI exigido
  CAMERA_DESLIGADA,  // o programa está aberto, mas a câmera está parada
  VIGILANCIA,        // o programa está no modo vigilância: catraca desligada
  SEM_CONEXAO        // sem dados do programa (cabo solto, Wi-Fi fora, programa fechado...)
};


// ============================================================
// ESTADO (variáveis globais)
// ============================================================

Servo cancela;

Adafruit_SSD1306 tela(128, 64, &Wire, -1);
bool telaFunciona = false;

// Última situação recebida do programa
Situacao situacao = SEM_CONEXAO;

// Situação do ciclo anterior (para perceber a mudança)
Situacao situacaoAnterior = SEM_CONEXAO;

// Detalhes para a tela: o que falta (ex.: "Capacete, Luvas"),
// quantas pessoas estão irregulares e o motivo de uma falha
String faltando = "";
int pessoasNegadas = 0;
int totalPessoas = 0;
String motivoFalha = "Aguardando dados...";

// Controle do tempo (millis = milissegundos desde que o ESP32 ligou)
unsigned long ultimaConsulta = 0;
unsigned long ultimaRespostaValida = 0;   // última mensagem válida, de qualquer caminho
unsigned long ultimaSerialValida = 0;      // última mensagem válida pelo CABO
unsigned long liberadoDesde = 0;       // 0 = não está liberado agora
unsigned long cancelaAbertaDesde = 0;
unsigned long releLigadoDesde = 0;

bool cancelaAberta = false;
bool releLigado = false;

// "Rearmada" = pronta para abrir. Depois de abrir uma vez, só rearma
// quando o status sai de "liberado": uma passagem por liberação.
bool rearmada = true;

// Bipe: quantas fases faltam (ligado, desligado, ligado, ...)
int fasesDoBipe = 0;
unsigned long ultimaFaseDoBipe = 0;

// Linha que está chegando pelo cabo, montada letra por letra
String linhaSerial = "";

// O que está desenhado na tela parada agora (para só redesenhar se mudar)
String conteudoDaTela = "";


// ============================================================
// FUNÇÕES AUXILIARES
// ============================================================

// A fonte da tela não tem acentos. Troca as letras acentuadas mais
// comuns do português pela letra sem acento ("Óculos" -> "Oculos").
//
// Em UTF-8, essas letras ocupam DOIS bytes: 0xC3 seguido de um
// segundo byte que diz qual é a letra.
String semAcentos(const String& texto) {

  String resultado = "";

  for (unsigned int i = 0; i < texto.length(); i++) {

    unsigned char letra = texto[i];

    if (letra != 0xC3 || i + 1 >= texto.length()) {
      resultado += (char)letra;
      continue;
    }

    unsigned char segunda = texto[++i];

    if (segunda >= 0x80 && segunda <= 0x85) resultado += 'A';
    else if (segunda == 0x87) resultado += 'C';
    else if (segunda >= 0x88 && segunda <= 0x8B) resultado += 'E';
    else if (segunda >= 0x8C && segunda <= 0x8F) resultado += 'I';
    else if (segunda == 0x91) resultado += 'N';
    else if (segunda >= 0x92 && segunda <= 0x96) resultado += 'O';
    else if (segunda >= 0x99 && segunda <= 0x9C) resultado += 'U';
    else if (segunda >= 0xA0 && segunda <= 0xA5) resultado += 'a';
    else if (segunda == 0xA7) resultado += 'c';
    else if (segunda >= 0xA8 && segunda <= 0xAB) resultado += 'e';
    else if (segunda >= 0xAC && segunda <= 0xAF) resultado += 'i';
    else if (segunda == 0xB1) resultado += 'n';
    else if (segunda >= 0xB2 && segunda <= 0xB6) resultado += 'o';
    else if (segunda >= 0xB9 && segunda <= 0xBC) resultado += 'u';
    else resultado += '?';
  }

  return resultado;
}

const char* nomeDaSituacao(Situacao s) {

  switch (s) {
    case AGUARDANDO:       return "AGUARDANDO";
    case ANALISANDO:       return "ANALISANDO";
    case LIBERADO:         return "LIBERADO";
    case NEGADO:           return "NEGADO";
    case CAMERA_DESLIGADA: return "CAMERA OFF";
    case VIGILANCIA:       return "VIGILANCIA";
    default:               return "SEM CONEXAO";
  }
}

void ligarRele(bool ligar) {

  // Alguns módulos relé ligam com nível BAIXO (veja config.h)
  bool nivel = RELE_LIGA_EM_NIVEL_BAIXO ? !ligar : ligar;

  digitalWrite(PINO_RELE, nivel ? HIGH : LOW);

  releLigado = ligar;
}


// ============================================================
// RECEBER O STATUS PELO CABO USB
// ============================================================
//
// O programa escreve uma linha por mensagem:
//
//   ST|negado|1|2|Capacete;Oculos
//
//   ST               -> começo de uma mensagem válida
//   negado           -> sem_pessoas | analisando | liberado | negado | camera_off | vigilancia
//   1                -> quantas pessoas estão irregulares
//   2                -> quantas pessoas há na imagem
//   Capacete;Oculos  -> o que falta (vazio se nada)
//
// Linha que não começa com "ST|", que está cortada ou tem um acesso
// desconhecido é IGNORADA: ruído no cabo nunca muda a cancela.
// ============================================================

// Interpreta uma linha. Devolve true se ela era uma mensagem válida
// (e, nesse caso, já atualizou a situação e os detalhes da tela).
bool processarLinhaSerial(String linha) {

  linha.trim();

  if (!linha.startsWith("ST|")) return false;

  int fimAcesso = linha.indexOf('|', 3);
  int fimNegadas = linha.indexOf('|', fimAcesso + 1);
  int fimTotal = linha.indexOf('|', fimNegadas + 1);

  if (fimAcesso < 0 || fimNegadas < 0 || fimTotal < 0) return false;

  String acesso = linha.substring(3, fimAcesso);

  Situacao nova;

  if (acesso == "liberado") nova = LIBERADO;
  else if (acesso == "negado") nova = NEGADO;
  else if (acesso == "analisando") nova = ANALISANDO;
  else if (acesso == "sem_pessoas") nova = AGUARDANDO;
  else if (acesso == "camera_off") nova = CAMERA_DESLIGADA;
  else if (acesso == "vigilancia") nova = VIGILANCIA;
  else return false;   // acesso desconhecido: na dúvida, ignora

  // Só depois de tudo conferido é que as variáveis mudam
  pessoasNegadas = linha.substring(fimAcesso + 1, fimNegadas).toInt();
  totalPessoas = linha.substring(fimNegadas + 1, fimTotal).toInt();

  // "Capacete;Oculos" -> "Capacete, Oculos" (sem acento, para a tela)
  String lista = semAcentos(linha.substring(fimTotal + 1));
  lista.replace(";", ", ");
  faltando = lista;

  situacao = nova;

  return true;
}

// Lê o que chegou pelo cabo, sem esperar: monta a linha letra por
// letra e só a interpreta quando chega o fim dela ("\n").
void lerSerial(unsigned long agora) {

  while (Serial.available()) {

    char letra = Serial.read();

    if (letra == '\n') {

      if (processarLinhaSerial(linhaSerial)) {
        ultimaSerialValida = agora;
        ultimaRespostaValida = agora;
      }

      linhaSerial = "";

    } else if (letra != '\r') {

      linhaSerial += letra;

      // Ruído sem fim de linha não pode crescer para sempre
      if (linhaSerial.length() > 160) linhaSerial = "";
    }
  }
}


// ============================================================
// CONSULTA AO SAFETECH ENTRY (PELO WI-FI)
// ============================================================
//
// Pede o status a /api/ao-vivo e preenche as variáveis globais.
// Devolve true se a resposta veio certa.
//
// Resposta do programa (só os campos usados aqui):
//
//   {
//     "camera_ativa": true,
//     "acesso": "negado",          // sem_pessoas | analisando | liberado | negado
//     "pessoas": [
//       { "status": "negado", "faltando": ["Capacete"] },
//       { "status": "liberado", "faltando": [] }
//     ]
//   }
// ============================================================

bool consultarSafeTech() {

  if (WiFi.status() != WL_CONNECTED) {
    motivoFalha = "Sem Wi-Fi";
    return false;
  }

  HTTPClient http;

  String endereco = String("http://") + SAFETECH_IP + ":" + SAFETECH_PORTA + "/api/ao-vivo";

  http.setConnectTimeout(TEMPO_LIMITE_HTTP_MS);
  http.setTimeout(TEMPO_LIMITE_HTTP_MS);

  if (!http.begin(endereco)) {
    motivoFalha = "Endereco invalido";
    return false;
  }

  // Mesmo login do painel web do gerente
  http.setAuthorization(SAFETECH_USUARIO, SAFETECH_SENHA);

  int codigo = http.GET();

  if (codigo != 200) {

    if (codigo == 401) motivoFalha = "Login recusado";
    else if (codigo < 0) motivoFalha = "Programa fora do ar";
    else motivoFalha = String("Erro HTTP ") + codigo;

    http.end();
    return false;
  }

  String corpo = http.getString();
  http.end();

  // O filtro faz a ArduinoJson guardar só os campos que a catraca
  // usa, economizando memória do ESP32.
  JsonDocument filtro;
  filtro["camera_ativa"] = true;
  filtro["acesso"] = true;
  filtro["modo"] = true;
  filtro["pessoas"][0]["status"] = true;
  filtro["pessoas"][0]["faltando"] = true;

  JsonDocument dados;

  DeserializationError erro = deserializeJson(dados, corpo, DeserializationOption::Filter(filtro));

  if (erro) {
    motivoFalha = "Resposta invalida";
    return false;
  }

  // --------------------------------------------------------
  // Situação geral
  // --------------------------------------------------------

  String acesso = dados["acesso"] | "";
  String modo = dados["modo"] | "";

  // Modo vigilância vale mais que tudo: a catraca fica desligada
  if (modo == "vigilancia") situacao = VIGILANCIA;
  else if (!(dados["camera_ativa"] | false)) situacao = CAMERA_DESLIGADA;
  else if (acesso == "liberado") situacao = LIBERADO;
  else if (acesso == "negado") situacao = NEGADO;
  else if (acesso == "analisando") situacao = ANALISANDO;
  else if (acesso == "sem_pessoas") situacao = AGUARDANDO;
  else {
    // Valor desconhecido: na dúvida, nega
    motivoFalha = "Status desconhecido";
    return false;
  }

  // --------------------------------------------------------
  // O que está faltando (juntando todas as pessoas negadas)
  // --------------------------------------------------------

  faltando = "";
  pessoasNegadas = 0;
  totalPessoas = 0;

  for (JsonObject pessoa : dados["pessoas"].as<JsonArray>()) {

    totalPessoas++;

    if (String(pessoa["status"] | "") != "negado") continue;

    pessoasNegadas++;

    for (JsonVariant epi : pessoa["faltando"].as<JsonArray>()) {

      String nome = semAcentos(epi.as<String>());

      // Cada EPI aparece uma vez só, mesmo faltando em várias pessoas
      if (faltando.indexOf(nome) >= 0) continue;

      if (faltando.length() > 0) faltando += ", ";
      faltando += nome;
    }
  }

  return true;
}


// ============================================================
// CANCELA (servo e relé)
// ============================================================

void abrirCancela(unsigned long agora) {

  cancela.write(ANGULO_ABERTA);

  cancelaAberta = true;
  cancelaAbertaDesde = agora;
  rearmada = false;

  // Pulso no relé: é o sinal que abriria uma catraca de verdade
  ligarRele(true);
  releLigadoDesde = agora;

  Serial.println("Cancela ABERTA");
}

void fecharCancela() {

  cancela.write(ANGULO_FECHADA);

  cancelaAberta = false;

  Serial.println("Cancela FECHADA");
}

void atualizarCancela(unsigned long agora) {

  bool liberado = (situacao == LIBERADO);

  // Saiu de "liberado": a catraca rearma para a próxima pessoa
  if (!liberado) {
    liberadoDesde = 0;
    rearmada = true;
  } else if (liberadoDesde == 0) {
    liberadoDesde = agora;
  }

  if (cancelaAberta) {

    // Fecha NA HORA se deixou de estar liberado (ex.: entrou alguém
    // sem EPI), ou quando o tempo de passagem acabou
    if (!liberado || agora - cancelaAbertaDesde >= TEMPO_CANCELA_ABERTA_MS) {
      fecharCancela();
    }

  } else if (liberado && rearmada && agora - liberadoDesde >= TEMPO_CONFIRMA_LIBERADO_MS) {

    abrirCancela(agora);
  }

  // Fim do pulso do relé
  if (releLigado && agora - releLigadoDesde >= TEMPO_PULSO_RELE_MS) {
    ligarRele(false);
  }
}


// ============================================================
// LEDS E BIPE
// ============================================================

void iniciarBipes(int quantidade) {

  // Cada bipe tem duas fases: ligado e desligado
  fasesDoBipe = quantidade * 2;
  ultimaFaseDoBipe = 0;
}

void atualizarBipe(unsigned long agora) {

  if (fasesDoBipe == 0) return;

  if (ultimaFaseDoBipe != 0 && agora - ultimaFaseDoBipe < TEMPO_BIPE_MS) return;

  // Fases pares ligam o buzzer, ímpares desligam (termina desligado)
  digitalWrite(PINO_BUZZER, (fasesDoBipe % 2 == 0) ? HIGH : LOW);

  fasesDoBipe--;
  ultimaFaseDoBipe = agora;
}

void atualizarLeds(unsigned long agora) {

  bool piscaLigado = (agora / INTERVALO_PISCA_MS) % 2 == 0;

  bool verde = (situacao == LIBERADO);
  bool vermelho = (situacao == NEGADO) || (situacao == SEM_CONEXAO && piscaLigado);
  bool amarelo = (situacao == AGUARDANDO) || (situacao == CAMERA_DESLIGADA) ||
                 (situacao == ANALISANDO && piscaLigado);

  digitalWrite(PINO_LED_VERDE, verde ? HIGH : LOW);
  digitalWrite(PINO_LED_VERMELHO, vermelho ? HIGH : LOW);
  digitalWrite(PINO_LED_AMARELO, amarelo ? HIGH : LOW);
}


// ============================================================
// TELA OLED
// ============================================================
//
// Cada situação tem o seu visual (o mesmo de teste_tela.ino):
//
//   AGUARDANDO   -> um "olho" no centro
//   ANALISANDO   -> barra de progresso correndo
//   LIBERADO     -> moldura dupla e um "visto"
//   NEGADO       -> TELA INTEIRA ACESA, piscando, com o que falta
//   OFFLINE      -> um "X" piscando e o motivo da falha
//   CAMERA OFF   -> aviso para ligar a câmera no programa
//
// A tela OLED é monocromática (não faz vermelho). O destaque do
// NEGADO vem do contraste: a tela inteira acende e as letras ficam
// pretas por cima. Quem dá a cor são os LEDs.
// ============================================================

// Escreve um texto centralizado na horizontal, na altura y.
// "cor" é a cor da letra (WHITE em fundo preto, BLACK em fundo aceso).
void textoCentralizado(const String& texto, int y, int tamanho, uint16_t cor) {

  int16_t x1, y1;
  uint16_t largura, altura;

  tela.setTextSize(tamanho);
  tela.setTextColor(cor);
  tela.getTextBounds(texto.c_str(), 0, 0, &x1, &y1, &largura, &altura);

  tela.setCursor((128 - (int)largura) / 2, y);
  tela.print(texto);
}

// Título grande de cada situação. Cabe em 128 px com letra de tamanho 2
// (12 px por letra: no máximo 10 letras).
const char* tituloDaTela(Situacao s) {

  switch (s) {
    case AGUARDANDO:       return "AGUARDANDO";
    case ANALISANDO:       return "ANALISANDO";
    case LIBERADO:         return "LIBERADO";
    case NEGADO:           return "NEGADO";
    case CAMERA_DESLIGADA: return "CAMERA OFF";
    case VIGILANCIA:       return "VIGILANCIA";
    default:               return "OFFLINE";
  }
}

void desenharAguardando(unsigned long agora) {

  textoCentralizado(tituloDaTela(AGUARDANDO), 4, 2, WHITE);

  // Um "olho" que pisca de vez em quando
  bool aberto = (agora / 1200) % 4 != 0;

  tela.drawCircle(64, 38, 14, WHITE);

  if (aberto) tela.fillCircle(64, 38, 6, WHITE);
  else tela.drawLine(52, 38, 76, 38, WHITE);

  textoCentralizado("Aproxime-se da camera", 56, 1, WHITE);
}

void desenharAnalisando(unsigned long agora) {

  textoCentralizado(tituloDaTela(ANALISANDO), 4, 2, WHITE);

  // Barra de progresso: um bloco que corre da esquerda para a direita
  tela.drawRect(8, 32, 112, 14, WHITE);

  int bloco = 28;
  int posicao = (agora / 20) % (112 - bloco);

  tela.fillRect(10 + posicao, 34, bloco, 10, WHITE);

  textoCentralizado("Verificando EPIs...", 54, 1, WHITE);
}

void desenharLiberado() {

  // Moldura dupla
  tela.drawRect(0, 0, 128, 64, WHITE);
  tela.drawRect(3, 3, 122, 58, WHITE);

  textoCentralizado(tituloDaTela(LIBERADO), 8, 2, WHITE);

  // "Visto" grosso (várias linhas lado a lado)
  for (int i = -1; i <= 1; i++) {
    tela.drawLine(50, 34 + i, 59, 43 + i, WHITE);
    tela.drawLine(59, 43 + i, 80, 24 + i, WHITE);
  }

  textoCentralizado(cancelaAberta ? "Pode passar" : "Acesso liberado", 50, 1, WHITE);
}

void desenharNegado(unsigned long agora) {

  // A cada pisca, a tela inteira alterna entre ACESA e normal.
  // É o efeito de "tela vermelha" possível numa tela monocromática.
  bool acesa = (agora / INTERVALO_PISCA_MS) % 2 == 0;

  uint16_t fundo = acesa ? WHITE : BLACK;
  uint16_t letra = acesa ? BLACK : WHITE;

  tela.fillRect(0, 0, 128, 64, fundo);

  textoCentralizado(tituloDaTela(NEGADO), 4, 3, letra);

  // O que falta pode ter até duas linhas (21 letras por linha)
  tela.setTextSize(1);
  tela.setTextColor(letra);
  tela.setTextWrap(true);
  tela.setCursor(2, 32);
  tela.print(String("Falta: ") + faltando);
  tela.setTextWrap(false);

  textoCentralizado(String(pessoasNegadas) + " de " + String(totalPessoas) + " pessoa(s)", 55, 1, letra);
}

void desenharSemConexao(unsigned long agora) {

  textoCentralizado(tituloDaTela(SEM_CONEXAO), 4, 2, WHITE);

  // "X" que pisca
  if ((agora / INTERVALO_PISCA_MS) % 2 == 0) {

    for (int i = -1; i <= 1; i++) {
      tela.drawLine(56 + i, 22, 72 + i, 38, WHITE);
      tela.drawLine(72 + i, 22, 56 + i, 38, WHITE);
    }
  }

  textoCentralizado(motivoFalha, 43, 1, WHITE);
  // Onde a catraca está esperando os dados
  textoCentralizado(WIFI_ATIVO ? String(SAFETECH_IP) + ":" + String(SAFETECH_PORTA) : String("Cabo USB"), 54, 1, WHITE);
}

void desenharVigilancia() {

  textoCentralizado(tituloDaTela(VIGILANCIA), 4, 2, WHITE);

  // Uma "câmera" desenhada: corpo, lente e um ponto de gravação
  tela.drawRoundRect(46, 24, 30, 18, 3, WHITE);
  tela.drawCircle(61, 33, 5, WHITE);
  tela.fillTriangle(76, 30, 84, 26, 84, 40, WHITE);
  tela.fillCircle(50, 27, 1, WHITE);

  textoCentralizado("Catraca desligada", 48, 1, WHITE);
  textoCentralizado("(so registro de EPIs)", 57, 1, WHITE);
}

void desenharCameraDesligada() {

  textoCentralizado(tituloDaTela(CAMERA_DESLIGADA), 4, 2, WHITE);
  textoCentralizado("Ligue a camera", 34, 1, WHITE);
  textoCentralizado("no programa", 46, 1, WHITE);
}

// Desenha a tela da situação atual. Chamada em todo ciclo, mas só
// redesenha no ritmo de INTERVALO_QUADRO_TELA_MS. As telas paradas
// (liberado e câmera desligada) só redesenham quando algo muda,
// para não ocupar a comunicação I2C à toa.
unsigned long ultimoQuadroDaTela = 0;

void atualizarTela(unsigned long agora) {

  if (!telaFunciona) return;

  if (agora - ultimoQuadroDaTela < INTERVALO_QUADRO_TELA_MS) return;

  ultimoQuadroDaTela = agora;

  bool animada = (situacao != LIBERADO && situacao != CAMERA_DESLIGADA && situacao != VIGILANCIA);

  if (!animada) {

    String conteudo = String(situacao) + "|" + (cancelaAberta ? "1" : "0");

    if (conteudo == conteudoDaTela) return;

    conteudoDaTela = conteudo;
  }

  tela.clearDisplay();

  switch (situacao) {
    case AGUARDANDO:       desenharAguardando(agora); break;
    case ANALISANDO:       desenharAnalisando(agora); break;
    case LIBERADO:         desenharLiberado(); break;
    case NEGADO:           desenharNegado(agora); break;
    case CAMERA_DESLIGADA: desenharCameraDesligada(); break;
    case VIGILANCIA:       desenharVigilancia(); break;
    default:               desenharSemConexao(agora); break;
  }

  tela.display();
}


// ============================================================
// SETUP: roda uma vez, ao ligar
// ============================================================

void setup() {

  Serial.begin(VELOCIDADE_SERIAL);
  Serial.println();
  Serial.println("SafeTech Entry - catraca de demonstracao");

  // Saídas
  pinMode(PINO_LED_VERDE, OUTPUT);
  pinMode(PINO_LED_AMARELO, OUTPUT);
  pinMode(PINO_LED_VERMELHO, OUTPUT);
  pinMode(PINO_BUZZER, OUTPUT);
  pinMode(PINO_RELE, OUTPUT);

  digitalWrite(PINO_BUZZER, LOW);
  ligarRele(false);

  // Cancela começa FECHADA
  cancela.setPeriodHertz(50);              // servos comuns usam 50 Hz
  cancela.attach(PINO_SERVO, 500, 2400);   // pulso mínimo e máximo do SG90 (microssegundos)
  cancela.write(ANGULO_FECHADA);

  // Tela (se não estiver ligada, a catraca funciona sem ela)
  telaFunciona = tela.begin(SSD1306_SWITCHCAPVCC, OLED_ENDERECO_I2C);

  if (!telaFunciona) {
    Serial.println("Tela OLED nao encontrada: seguindo sem ela");
  }

  atualizarTela(millis());

  // Wi-Fi (opcional): a conexão acontece em segundo plano. Sem ele, a
  // catraca só obedece ao cabo USB.
  if (WIFI_ATIVO) {

    WiFi.mode(WIFI_STA);
    WiFi.setAutoReconnect(true);
    WiFi.begin(WIFI_NOME, WIFI_SENHA);

    motivoFalha = "Conectando Wi-Fi...";

    Serial.printf("Conectando ao Wi-Fi \"%s\"...\n", WIFI_NOME);

  } else {

    motivoFalha = "Sem dados do cabo USB";

    Serial.println("Wi-Fi desligado (WIFI_ATIVO): esperando dados pelo cabo USB");
  }
}


// ============================================================
// LOOP: roda sem parar
// ============================================================
//
// Nada aqui espera parado (sem delay): cada parte olha o relógio e
// decide se é hora de agir. Assim os LEDs piscam, o bipe toca e a
// cancela fecha no tempo certo, ao mesmo tempo.
// ============================================================

void loop() {

  unsigned long agora = millis();

  // ----------------------------------------------------------
  // 1) Dados pelo CABO USB
  // ----------------------------------------------------------

  lerSerial(agora);

  // O cabo está "vivo" enquanto mandou algo válido há pouco tempo
  bool caboVivo = ultimaSerialValida != 0 && agora - ultimaSerialValida < TEMPO_SEM_RESPOSTA_MS;

  // ----------------------------------------------------------
  // 2) Dados pelo WI-FI (só se ligado, e só se o cabo não estiver
  //    mandando nada)
  // ----------------------------------------------------------

  if (WIFI_ATIVO && !caboVivo && agora - ultimaConsulta >= INTERVALO_CONSULTA_MS) {

    ultimaConsulta = agora;

    if (consultarSafeTech()) {
      ultimaRespostaValida = agora;
    }

    // A consulta demora um pouco: relê o relógio
    agora = millis();
  }

  // ----------------------------------------------------------
  // 3) Os dados estão em dia?
  // ----------------------------------------------------------

  bool semDados = ultimaRespostaValida == 0 || agora - ultimaRespostaValida >= TEMPO_SEM_RESPOSTA_MS;

  if (semDados) {

    // Nada chegando (por nenhum caminho): fecha e avisa
    situacao = SEM_CONEXAO;

    if (!WIFI_ATIVO) motivoFalha = "Sem dados do cabo USB";

  } else if (situacao == LIBERADO && agora - ultimaRespostaValida >= TEMPO_LIBERADO_VALIDO_MS) {

    // Um "liberado" antigo não pode abrir (ou manter aberta) a
    // cancela sem confirmação recente. Na dúvida, nega.
    situacao = ANALISANDO;
  }

  // ----------------------------------------------------------
  // 4) A situação mudou?
  // ----------------------------------------------------------

  if (situacao != situacaoAnterior) {

    Serial.printf("Situacao: %s\n", nomeDaSituacao(situacao));

    // Acabou de negar: dois bipes
    if (situacao == NEGADO) iniciarBipes(2);

    situacaoAnterior = situacao;
  }

  // ----------------------------------------------------------
  // 5) Cancela, LEDs, bipe e tela
  // ----------------------------------------------------------

  atualizarCancela(agora);
  atualizarLeds(agora);
  atualizarBipe(agora);
  atualizarTela(agora);
}
