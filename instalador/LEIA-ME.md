# Instalar o SafeTech Entry sem terminal

Há dois jeitos, do mais simples ao mais completo.

## 1. Atalho na área de trabalho (recomendado neste computador)

Para abrir o programa com dois cliques, sem terminal e sem janela preta. Precisa do Python e das bibliotecas já instaladas (veja o README).

Na pasta do projeto, rode uma vez:

```powershell
python instalador\criar_atalho.py
```

Aparece o atalho **SafeTech Entry** na área de trabalho, com o ícone do escudo. Ele abre o `app.py` com o `pythonw` (o Python sem console), já na pasta do projeto. Se a pasta do projeto mudar de lugar, rode o script de novo.

## 2. Programa completo (.exe) para outro computador

Para levar o SafeTech a um computador **sem Python**. Gera a pasta `dist\SafeTech Entry\` com o `SafeTech Entry.exe` e tudo de que ele precisa (cerca de 1 GB, por causa do TensorFlow).

```powershell
powershell -ExecutionPolicy Bypass -File instalador\gerar_exe.ps1
```

- Leva vários minutos. A receita está em `instalador\safetech.spec`.
- Copie a pasta inteira para um lugar em que o usuário possa escrever (ex.: `Documentos`), não para "Arquivos de Programas": a auditoria, os logs e as preferências ficam dentro dela.
- Nesse computador, crie um atalho para o `.exe` (botão direito > Enviar para > Área de trabalho).
- A primeira vez que o `.exe` abrir, o Windows pode avisar que o programa não é conhecido ("O Windows protegeu o computador"). É porque o `.exe` não tem assinatura digital: clique em "Mais informações" > "Executar assim mesmo".

O ícone (`instalador\safetech.ico`) é gerado pelos dois scripts e não vai para o git.
