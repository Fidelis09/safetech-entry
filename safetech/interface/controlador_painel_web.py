"""
Ligação entre a janela e o painel web do gerente (somente leitura).

    - sobe o servidor com os ajustes salvos (porta, rede, usuário e hash
      da senha) e o reinicia quando o operador clica em "Aplicar" em
      Configurações > Painel web;
    - entrega ao servidor o que ele mostra: o "ao vivo" (a área que
      comanda a catraca, ou a primeira) e a situação de todas as áreas;
    - mantém o selo do cabeçalho: no ar, desligado, porta em uso, ou
      amarelo quando ainda está com a senha padrão ou sem senha.

O servidor roda em threads próprias; as leituras entregues a ele só
usam o que já é seguro entre threads (câmera e analisador).
"""

import logging
import webbrowser

from safetech.interface.tema import CORES
from safetech.nucleo.tipos import EstadoCena
from safetech.servicos import acesso_web, preferencias
from safetech.web.servidor import ServidorWeb


log = logging.getLogger(__name__)


class ControladorPainelWeb:

    def __init__(self, janela, areas):
        """
        janela -> JanelaPrincipal (auditoria, Configurações e avisos)
        areas  -> ControladorAreas (o que o painel mostra ao vivo)
        """

        self._janela = janela
        self._areas = areas

        self.ajustes = None
        self.servidor = None

        # Endereço em que o painel está no ar (None = fora do ar)
        self.endereco = None

        # Selo do cabeçalho; a janela entrega depois de montar a tela
        self.selo = None

    # ============================================================
    # LIGAR, REINICIAR E PARAR
    # ============================================================

    def iniciar(self):
        """Sobe o painel com os ajustes salvos; se não der, o aplicativo segue normalmente."""

        self.ajustes = preferencias.carregar_painel_web()

        self.ligar()

    def ligar(self):
        """
        Para o servidor que estiver no ar e sobe outro com os ajustes atuais.

        Devolve o texto do erro (ex.: porta em uso) ou None.
        """

        self.parar()

        ajustes = self.ajustes
        configuracoes = self._janela.configuracoes

        senha_padrao = acesso_web.usa_senha_padrao(ajustes)

        if not ajustes.ativo:

            # Clicar no selo leva às Configurações, para ligar
            self.selo.definir("Painel web desligado", CORES["texto_suave"])
            configuracoes.definir_painel_web(ajustes, None, senha_padrao)

            return None

        servidor = ServidorWeb(
            self._janela.auditoria,
            self.ler_ao_vivo,
            fonte_areas=self.ler_areas,
            ajustes=ajustes,
        )

        try:
            servidor.iniciar()

        except OSError:

            # Porta ocupada (outro programa ou outra cópia do aplicativo)
            erro = f"A porta {ajustes.porta} está em uso por outro programa."

            log.warning("Painel web não subiu: porta %d em uso", ajustes.porta)

            self.selo.definir(f"Painel web indisponível (porta {ajustes.porta} em uso)", CORES["perigo"])
            configuracoes.definir_painel_web(ajustes, None, senha_padrao, erro=erro)

            return erro

        self.servidor = servidor
        self.endereco = servidor.endereco()

        log.info("Painel web no ar em %s (login: %s)", self.endereco, "sim" if ajustes.exige_login else "não")

        # Sem login, ou com a senha padrão (pública no repositório): o
        # selo fica amarelo, para lembrar de proteger o painel
        if senha_padrao:
            texto, cor = f"Painel web: {self.endereco}  (troque a senha)", CORES["alerta"]
        elif not ajustes.exige_login:
            texto, cor = f"Painel web: {self.endereco}  (sem senha)", CORES["alerta"]
        else:
            texto, cor = f"Painel web: {self.endereco}", CORES["sucesso"]

        self.selo.definir(texto, cor)
        configuracoes.definir_painel_web(ajustes, self.endereco, senha_padrao)

        return None

    def aplicar(self, **campos):
        """
        Configurações > Painel web > Aplicar.

        Confere o que foi digitado, salva (a senha só como hash) e reinicia
        o servidor com os ajustes novos. Devolve (deu_certo, mensagem)
        para a janela de Configurações mostrar.
        """

        novos, erro = acesso_web.montar_ajustes(self.ajustes, **campos)

        if erro:
            return False, erro

        self.ajustes = novos

        preferencias.salvar_painel_web(novos)

        erro = self.ligar()

        if erro:
            return False, f"{erro} Os ajustes foram salvos: escolha outra porta e aplique de novo."

        if not novos.ativo:
            self._janela.avisar("Painel web desligado.")
            return True, "Painel web desligado."

        self._janela.avisar(f"Painel web no ar em {self.endereco}.", tipo="sucesso")

        return True, f"Painel no ar em {self.endereco}."

    def abrir(self):
        """Clique no selo do painel web: abre no navegador (ou, desligado, as Configurações)."""

        if self.endereco:
            webbrowser.open(self.endereco)
        else:
            self._janela.configuracoes.mostrar("painel")

    def parar(self):

        if self.servidor is not None:
            self.servidor.parar()
            self.servidor = None

        self.endereco = None

    # ============================================================
    # O QUE O PAINEL MOSTRA (chamado pelas threads do servidor)
    # ============================================================

    def ler_ao_vivo(self):
        """Frame e estado do momento: da área que comanda a catraca ou, sem nenhuma, da primeira."""

        areas = list(self._areas.lista)

        if not areas:
            return None, EstadoCena()

        area = self._areas.da_catraca() or areas[0]

        return area.ler_ao_vivo()

    def ler_areas(self):
        """Todas as áreas, para a visão geral do painel: lista de (nome, frame, estado, comanda_catraca)."""

        resultado = []

        for area in list(self._areas.lista):

            frame, estado = area.ler_ao_vivo()

            resultado.append((area.nome, frame, estado, area.dados.controla_catraca))

        return resultado
