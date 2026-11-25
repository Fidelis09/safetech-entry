"""
Carga da IA em segundo plano: o modelo de EPI e os detectores de pessoa.

Carregar o TensorFlow e o modelo leva alguns segundos. Se isso fosse
feito antes de abrir a janela, o programa pareceria travado. Por isso:

    1) a janela abre na hora, com "Carregando o modelo de IA...";
    2) uma thread carrega a IA (carregar) e deixa o resultado guardado;
    3) a cada ciclo, a janela pergunta se terminou (verificar).

A thread de carga NÃO mexe na tela (o Tkinter só aceita a thread
principal): ela só guarda o resultado, e quem o usa é a janela.
"""

import logging
import threading

from safetech.nucleo import detector
from safetech.servicos.analisador import ClassificadorCompartilhado


log = logging.getLogger(__name__)


class CargaIA:

    def __init__(self, epis_do_modelo):
        """epis_do_modelo -> EPIs que o modelo instalado reconhece (vazio = não há modelo)."""

        self._epis_do_modelo = epis_do_modelo

        # Preenchido pela thread de carga e lido pela janela:
        # None (carregando), ("ok", classificador, detectores) ou ("erro", mensagem)
        self._resultado = None

        # Situação depois de verificar(): pronta ou com erro
        self.pronta = False
        self.erro = None

        # O modelo de EPI é UM só, dividido entre as áreas (com trava)
        self.classificador = None

        # Detectores já carregados na thread de carga: vão para a
        # primeira área (as outras criam os seus, que não são divididos)
        self.detectores_iniciais = None

    # ============================================================
    # CARGA (thread em segundo plano)
    # ============================================================

    def iniciar(self):
        """Começa a carregar em segundo plano. Retorna na hora."""

        threading.Thread(target=self.carregar, name="carga-ia", daemon=True).start()

    def carregar(self):

        try:

            if not self._epis_do_modelo:

                raise FileNotFoundError(
                    "Nenhum modelo encontrado em 'modelos/'. Colete imagens "
                    "rotuladas e execute o treinar.py."
                )

            # Importado aqui, e não no topo do arquivo, porque traz o
            # TensorFlow junto: é o que mais demora no programa.
            from safetech.nucleo.classificador import ClassificadorEPI

            # Os detectores dos dois modos ficam carregados desde já,
            # para a troca entre catraca e vigilância ser imediata.
            self._resultado = ("ok", ClassificadorEPI(), detector.criar_detectores())

            log.info("IA carregada")

        except Exception as erro:

            log.exception("Não foi possível carregar a IA")

            self._resultado = ("erro", str(erro))

    def definir_resultado(self, classificador, detectores):
        """Entrega uma IA já pronta (usado por scripts de demonstração e testes)."""

        self._resultado = ("ok", classificador, detectores)

    # ============================================================
    # VERIFICAÇÃO (thread da interface, a cada ciclo)
    # ============================================================

    def verificar(self):
        """
        Devolve "pronta" ou "erro" UMA vez, no ciclo em que a carga
        termina; nos outros ciclos, None.
        """

        if self._resultado is None or self.pronta or self.erro:
            return None

        if self._resultado[0] == "erro":

            self.erro = self._resultado[1]

            return "erro"

        _, classificador, detectores = self._resultado

        self.classificador = ClassificadorCompartilhado(classificador)
        self.detectores_iniciais = detectores
        self.pronta = True

        return "pronta"

    @property
    def por_epi(self) -> bool:
        """True com o modelo por EPI; False com o modelo antigo (só "conjunto completo")."""

        return bool(self.classificador and self.classificador.por_epi)
