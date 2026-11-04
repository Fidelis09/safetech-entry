// ============================================================
// CONFIGURAÇÃO DA CATRACA (ESP32) - MODELO
// ============================================================
//
// COMO USAR: copie este arquivo para "config.h", na mesma pasta, e
// preencha o Wi-Fi e o endereço do computador.
//
// O "config.h" fica FORA do git (está no .gitignore), porque guarda a
// senha do Wi-Fi e a do painel web. Este modelo vai para o git sem
// nenhuma senha de verdade.
//
// É o equivalente ao safetech/config.py: nenhum número fica solto no
// código da catraca; todo ajuste está aqui, com o efeito explicado.
// ============================================================

#pragma once


// ============================================================
// COMO A CATRACA RECEBE O STATUS
// ============================================================
//
// CABO USB (principal): o SafeTech Entry escreve o status na porta
// serial do ESP32, a cada 0,3 s. Não precisa de rede nem de senha.
// No programa, é CATRACA_SERIAL_ATIVA no safetech/config.py (já vem
// ligado) e o ESP32 é achado sozinho.
//
// WI-FI (opcional): o ESP32 pergunta ao painel web. Só é usado se
// WIFI_ATIVO for true E o cabo não estiver mandando dados. Os dois
// podem ficar ligados: o cabo tem prioridade, e se ele sair o Wi-Fi
// assume sozinho.
//
// Para usar só o cabo, deixe WIFI_ATIVO false e ignore as seções de
// Wi-Fi e de endereço do computador logo abaixo.
// ============================================================

#define WIFI_ATIVO  false

// Velocidade do cabo. Precisa ser igual a CATRACA_VELOCIDADE_SERIAL
// no safetech/config.py.
#define VELOCIDADE_SERIAL  115200


// ============================================================
// REDE WI-FI
// ============================================================
//
// Use a MESMA rede do computador que roda o SafeTech Entry.
// Em apresentação, prefira uma rede própria (roteador do notebook ou
// do celular): o Wi-Fi de eventos costuma falhar.
//
// O ESP32 só conecta em redes de 2,4 GHz (não em 5 GHz).
// ============================================================

#define WIFI_NOME   "nome_da_rede"
#define WIFI_SENHA  "senha_da_rede"


// ============================================================
// PROGRAMA SAFETECH (no computador)
// ============================================================
//
// O endereço aparece no rodapé da janela do programa, por exemplo
// "Painel web: http://192.168.0.15:8080". Copie só o IP e a porta.
//
// No config.py do programa, PAINEL_WEB_HOST precisa ser "0.0.0.0"
// (o padrão), senão o painel só aceita o próprio computador.
//
// Usuário e senha: os mesmos do painel web (PAINEL_WEB_USUARIO e
// PAINEL_WEB_SENHA no config.py). A catraca só LÊ o status, pelo
// mesmo caminho que o navegador do gerente usa.
// ============================================================

#define SAFETECH_IP       "192.168.0.15"
#define SAFETECH_PORTA    8080
#define SAFETECH_USUARIO  "gerente"
#define SAFETECH_SENHA    "senha_do_painel"


// ============================================================
// PINOS (veja o desenho de ligação no LEIA-ME.md)
// ============================================================

#define PINO_SERVO          13   // sinal (fio laranja) do servo SG90
#define PINO_LED_VERDE      25
#define PINO_LED_AMARELO    26
#define PINO_LED_VERMELHO   27
#define PINO_BUZZER         33   // buzzer ATIVO (apita sozinho com 3,3 V)
#define PINO_RELE           32   // módulo relé (simula a catraca real)

// A tela OLED usa o I2C padrão do ESP32: SDA no pino 21, SCL no 22
#define OLED_ENDERECO_I2C   0x3C // a maioria das telas 0,96" usa 0x3C (algumas, 0x3D)

// Muitos módulos relé ligam com o pino em nível BAIXO (LOW).
// Se o relé ficar ligado o tempo todo e desligar ao abrir, troque
// para false.
#define RELE_LIGA_EM_NIVEL_BAIXO  true


// ============================================================
// CANCELA (servo)
// ============================================================

// Ângulos do braço. Ajuste conforme a montagem: o braço deve ficar
// na horizontal fechado e na vertical aberto.
#define ANGULO_FECHADA   0
#define ANGULO_ABERTA    90


// ============================================================
// TEMPOS (em milissegundos)
// ============================================================

// De quanto em quanto tempo a catraca pergunta o status ao programa.
// 500 ms = duas vezes por segundo: rápido o bastante para a
// demonstração e leve para o computador.
#define INTERVALO_CONSULTA_MS        500

// Tempo máximo esperando a resposta do programa em cada consulta.
#define TEMPO_LIMITE_HTTP_MS         1500

// Sem nenhuma resposta válida por esse tempo, a catraca considera que
// perdeu o programa: FECHA e mostra "SEM CONEXAO". É a regra do
// sistema: na dúvida, nega.
#define TEMPO_SEM_RESPOSTA_MS        3000

// Um "liberado" só vale por esse tempo depois da última mensagem do
// programa. Passou disso sem notícia nova, a catraca volta para
// "analisando" (cancela fechada) em vez de confiar num dado antigo.
#define TEMPO_LIBERADO_VALIDO_MS     1500

// "Liberado" precisa se manter por esse tempo antes de a cancela
// abrir. Evita abrir por um instante de oscilação da IA.
#define TEMPO_CONFIRMA_LIBERADO_MS   800

// Quanto tempo a cancela fica aberta. Depois fecha sozinha e só abre
// de novo quando o status sair de "liberado" e voltar (uma passagem
// por liberação, como numa catraca de verdade).
#define TEMPO_CANCELA_ABERTA_MS      3000

// Duração do pulso no relé. Catracas reais costumam abrir com um
// pulso curto num contato seco; meio segundo é um valor comum.
#define TEMPO_PULSO_RELE_MS          500

// Bipe de "negado": dois apitos deste tamanho, com a mesma pausa.
#define TEMPO_BIPE_MS                120

// Pisca-pisca do LED amarelo enquanto a IA analisa.
#define INTERVALO_PISCA_MS           300

// Redesenha a tela neste intervalo, para as animações (olho, barra de
// progresso, pisca do NEGADO). 80 ms = cerca de 12 quadros por segundo.
#define INTERVALO_QUADRO_TELA_MS     80
