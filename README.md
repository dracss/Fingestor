# FinGestor — Contas a Pagar e a Receber (MVP)

App Android **em Python** (Kivy + KivyMD), *offline-first*, para micro/pequenos negócios
e vendedores autônomos gerenciarem clientes, vendas (à vista e parceladas), baixas e
comprovantes. Gera o **APK** automaticamente via **GitHub Actions**.

> Este é o MVP da [especificação técnica](../ESPECIFICACAO_APP_FINANCEIRO.md): cobre a
> Fase 1 (contatos, vendas, baixa, cupom PDF/PNG, dashboard e configurações da empresa).

## O que já funciona

- **Contatos**: cadastro/edição de clientes e fornecedores; arquivamento em vez de exclusão
  quando há vendas vinculadas (integridade preservada); total devedor por contato.
- **Vendas**: à vista ou parceladas (N parcelas mensais), desconto em **R$** ou **%**,
  geração de parcelas com o centavo residual na 1ª parcela.
- **Baixa** (quitação) total ou parcial, registrada como lançamento imutável em `payments`.
- **Status derivado** na leitura: Pendente / Parcial / Pago / **Atrasado**.
- **Cupom** em **PDF e PNG** (renderizado com Pillow) com logo/dados da empresa,
  compartilhável no Android (WhatsApp, e-mail…) via **FileProvider**.
- **Dashboard**: a receber em aberto, vencido/atrasado, recebido no mês e próximos
  vencimentos (7 dias).
- **Configurações**: dados da empresa, moeda e rodapé do cupom.
- **100% offline**: dados em **SQLite** no armazenamento privado do app.

## Estrutura

| Arquivo | Responsabilidade |
|---------|------------------|
| `main.py` | UI KivyMD + navegação (ponto de entrada exigido pelo Buildozer) |
| `db.py` | SQLite + regras de negócio (dinheiro em **centavos**, parcelas, baixa, status). Sem Kivy — testável isolado. |
| `receipt.py` | Cupom PDF/PNG com Pillow + compartilhamento Android (pyjnius/FileProvider) |
| `buildozer.spec` | Configuração do build do APK |
| `.github/workflows/android-build.yml` | Compila o APK na nuvem do GitHub |

## Como gerar o APK (GitHub Actions — recomendado)

1. Crie um repositório no GitHub e envie esta pasta:
   ```bash
   cd FinGestor
   git init && git add -A && git commit -m "FinGestor MVP"
   git branch -M main
   git remote add origin https://github.com/<seu-usuario>/FinGestor.git
   git push -u origin main
   ```
2. O workflow roda automaticamente no push. Acompanhe na aba **Actions**
   (a 1ª compilação leva ~15–25 min; ela baixa SDK/NDK).
3. Ao ficar verde, abra a execução e baixe o artefato **apk** em *Artifacts*.
4. (Opcional) Publique um **Release** para ter um link permanente que abre direto no
   celular:
   ```bash
   gh run download --name apk --dir ./bin
   gh release create v0.1 ./bin/*.apk --title "FinGestor v0.1" --notes "Primeiro build"
   ```

## Instalar no celular

Transfira o `.apk` para o telefone (ou abra o link do Release no navegador do celular),
habilite **"Instalar apps desconhecidos"** para o app que abrirá o arquivo (Arquivos ou
navegador), toque no `.apk` e instale. Builds *debug* são autoassinados — ideais para uso
pessoal; para publicar na Play Store é preciso um build **release** assinado.

## Testar no desktop (iteração rápida)

Kivy roda no PC — teste a lógica e a UI antes de compilar:

```bash
pip install "kivy==2.3.0" "kivymd==1.2.0" pillow
python main.py
```

Chamadas específicas do Android (compartilhamento via `jnius`) são protegidas com
try/except, então no desktop o app apenas **salva** o cupom e informa o caminho.

## Próximos passos (pós-MVP)

Contas a pagar completas, relatórios com exportação em PDF, categorias customizáveis,
notificações de vencimento (WorkManager equivalente), backup/restore e sincronização em
nuvem — detalhados na especificação técnica.
