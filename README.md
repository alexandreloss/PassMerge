# PassMerge - Fase 4 (Exporters)

Consolidador local de credenciais entre Google/Chrome, NordPass, 1Password e
Kaspersky Password Manager.

> **Aviso de segurança:** este utilitário lê e grava credenciais em **texto
> plano**. Use exclusivamente em máquina própria e confiável e apague os
> arquivos (CSV/TXT/1PUX de entrada e `vault.json` de saída) assim que terminar
> o merge e a reimportação nos apps. O comando `passmerge wipe` faz isso
> com sobrescrita 3-pass.

## Estado desta entrega

Fase 4 da arquitetura — **Exporters** + suporte ao Apple Passwords:

- `exporters/base.py` — `Exporter` (ABC) + `ExportReport` (contagem, skipped, truncated, warnings)
- `exporters/chrome.py` — CSV Google Chrome (LOGIN)
- `exporters/nordpass.py` — CSV NordPass (template oficial de importação)
- `exporters/kaspersky.py` — TXT Kaspersky (LOGIN → bloco `Websites`, SECURE_NOTE → bloco `Notes`)
- `exporters/onepassword.py` — ZIP `.1pux` 1Password (todas as 22 categorias)
- `exporters/apple.py` — CSV Apple Passwords / iPhone (LOGIN)
- `passmerge export` — CLI para exportar o vault para 1–5 formatos simultaneamente

Fases 1–3 mantidas integralmente: 5 importers, schema canônico com 22 categorias, vault JSON, merge com resolução de conflitos, comando `manual`.

## Requisitos

- Python 3.10+
- Nenhuma dependência externa (só a stdlib)

## Fluxo de uso

1. Exporte as senhas de cada gerenciador (gera CSV/TXT/1PUX em texto claro).
2. Importe e faça merge com `passmerge import` (múltiplas fontes são unificadas automaticamente).
3. Se houver conflitos não resolvidos automaticamente, revise `vault.conflicts.json`, marque com `[x]` as versões escolhidas e rode `passmerge manual`.
4. Verifique o vault com `passmerge verify` e revise o resumo com `passmerge status`.
5. Reexporte nos formatos nativos com `passmerge export`.
6. Apague todos os arquivos intermediários com `passmerge wipe`.

## Uso

### Criar um vault vazio

    python -m passmerge init --vault meu_vault.json

### Importar arquivos de senha

Todos os argumentos de fonte são opcionais — informe ao menos um:

    python -m passmerge import \
        --chrome      google_export.csv   \
        --nordpass    nordpass_export.csv \
        --onepassword meu_export.1pux     \
        --applesenhas apple_export.csv    \
        --kaspersky   kaspersky_export.txt \
        --vault       meu_vault.json

Se o vault ainda não existir, ele é criado automaticamente.

> **Importante — passe todas as fontes em uma única chamada.**
> O merge e a deduplicação só ocorrem quando ≥2 fontes são fornecidas
> **ao mesmo tempo**. Importar cada fonte separadamente em chamadas
> individuais não dispara o merger — os itens são simplesmente
> concatenados ao vault sem deduplicar, gerando duplicatas entre fontes.
> A ordem dos argumentos não afeta o resultado; a prioridade é sempre
> `nordpass > 1password > chrome > applesenhas > kaspersky`.

### Como exportar do Apple Passwords (iPhone/macOS)

1. Abra o app **Senhas** no iPhone (iOS 18+) ou em **Ajustes → Senhas** (macOS Sequoia+)
2. Toque em ••• (menu) → **Exportar Senhas**
3. Confirme a autenticação e salve o arquivo `.csv`
4. Passe o caminho para `--applesenhas`

### Como exportar do 1Password

1. Abra o app 1Password
2. Vá em **Arquivo → Exportar → Todos os Vaults**
3. Escolha o formato **1Password (`.1pux`)**
4. Salve o arquivo e passe o caminho para `--onepassword`

### Formatos aceitos por gerenciador (import)

| Gerenciador | Flag | Formato | Categorias suportadas |
|---|---|---|---|
| Google Chrome | `--chrome` | CSV (5 colunas) | LOGIN |
| NordPass | `--nordpass` | CSV | LOGIN, CREDIT_CARD, SECURE_NOTE, IDENTITY |
| 1Password | `--onepassword` | `.1pux` (ZIP + JSON) | Todas as 22 categorias¹ |
| Apple Passwords | `--applesenhas` | CSV (6 colunas) | LOGIN |
| Kaspersky | `--kaspersky` | TXT (blocos) | LOGIN, SECURE_NOTE |

¹ LOGIN, CREDIT_CARD, SECURE_NOTE, IDENTITY, PASSWORD, SERVER, SOFTWARE_LICENSE, BANK_ACCOUNT,
DATABASE, DRIVER_LICENCE, OUTDOOR_LICENSE, MEMBERSHIP, PASSPORT, REWARD_PROGRAM, SSN, WIRELESS,
EMAIL_ACCOUNT, API_CREDENTIAL, MEDICAL_RECORD, CRYPTO_WALLET, DOCUMENT, OTHER.

> **Nota NordPass:** o importer suporta dois layouts — o CSV exportado pelo próprio NordPass
> (com coluna `type`) e o template oficial de importação (sem `type`, com `cardholdername`/
> `totp`/`shared_folder`). Quando `type` está ausente, a categoria é inferida pelo conteúdo.

> **Nota 1Password:** itens com `state = "archived"` são ignorados na importação.

###  de comando completo

    python -m passmerge import \
        --onepassword C:\Senhas\1Password.1pux  \
        --nordpass    C:\Senhas\NordPass.csv    \
        --chrome      C:\Senhas\Chrome.csv      \
        --applesenhas C:\Senhas\Apple.csv       \
        --kaspersky   C:\Senhas\Kaspersky.txt   \
        --vault       C:\Senhas\cofre.json

### Ver resumo do vault

    python -m passmerge status --vault meu_vault.json

### Validar integridade do schema

    python -m passmerge verify --vault meu_vault.json

### Resolver conflitos manualmente

Após revisar `vault.conflicts.json`, marque a versão escolhida trocando
`"escolhido": "[]"` por `"escolhido": "[x]"` em exatamente uma versão de
cada conflito:

```json
{
  "source": "nordpass",
  "updated_at": null,
  "escolhido": "[x]",
  "fields": { "username": "alice", "password": "minha_senha" }
}
```

Depois aplique as escolhas ao vault:

    python -m passmerge manual --vault meu_vault.json --log meu_vault.conflicts.json

O comando:
- Atualiza os campos conflitantes no vault com os valores da versão marcada.
- Remove do log os conflitos resolvidos.
- Se todos os conflitos forem resolvidos, apaga o arquivo `.conflicts.json`.
- Conflitos sem marcação ou com marcação ambígua (dois `[x]`) permanecem no log.

### Exportar o vault para os formatos nativos

Todos os `--to-*` são opcionais — informe ao menos um:

    python -m passmerge export \
        --vault            meu_vault.json \
        --to-chrome        saida_chrome.csv \
        --to-nordpass      saida_nordpass.csv \
        --to-onepassword   saida_1password.1pux \
        --to-applesenhas   saida_apple.csv \
        --to-kaspersky     saida_kaspersky.txt

Itens de categorias não suportadas pelo formato de destino são omitidos e
listados no terminal (motivo: `unsupported_category`).

| Destino | Flag | Formato | Categorias exportadas |
|---|---|---|---|
| Google Chrome | `--to-chrome` | CSV | LOGIN |
| NordPass | `--to-nordpass` | CSV (template oficial) | Todas (sem mapeamento nativo → exportado como LOGIN) |
| 1Password | `--to-onepassword` | `.1pux` (ZIP + JSON) | Todas as 22 categorias |
| Apple Passwords | `--to-applesenhas` | CSV (6 colunas) | LOGIN |
| Kaspersky | `--to-kaspersky` | TXT | LOGIN, SECURE_NOTE |

### Apagar um arquivo com sobrescrita segura

    python -m passmerge wipe --file meu_export.1pux --yes

## Estrutura

    passmerge/
      __init__.py
      __main__.py              # habilita 'python -m passmerge'
      cli.py                   # argparse + todos os comandos
      core/
        canonical.py           # Vault, CanonicalItem, Category (22 valores), SourceRef
        categories.py          # mapeamento canônico ↔ nativo (4 gerenciadores)
        normalize.py           # normalize_url, normalize_email, normalize_phone
        matching.py            # primary_key por categoria (deduplicação)
        conflict.py            # ConflictLog, ReviewConflict (JSON formatado para revisão humana)
        merger.py              # merge(), MergeResult, MergeStats
      importers/
        base.py                # Importer (ABC)
        chrome.py              # Google Chrome CSV
        nordpass.py            # NordPass CSV (dois layouts)
        onepassword.py         # 1Password .1pux (ZIP + export.data JSON)
        apple.py               # Apple Passwords CSV (iPhone/macOS)
        kaspersky.py           # Kaspersky TXT
      exporters/
        base.py                # Exporter (ABC) + ExportReport
        chrome.py              # Google Chrome CSV
        nordpass.py            # NordPass CSV (template oficial)
        onepassword.py         # 1Password .1pux (ZIP + export.data JSON)
        apple.py               # Apple Passwords CSV (iPhone/macOS)
        kaspersky.py           # Kaspersky TXT
      security/
        wipe.py                # sobrescrita segura 3-pass
      report/                  # (Fase 5)
    tests/
      fixtures/
        chrome_test.csv
        nordpass_test.csv
        onepassword_test.1pux
        kaspersky_test.txt
        make_onepassword_fixture.py   # gerador da fixture .1pux
      test_canonical.py
      test_phase1_acceptance.py
      test_importer_chrome.py
      test_importer_nordpass.py
      test_importer_onepassword.py
      test_importer_kaspersky.py
      test_matching.py           # chaves de deduplicação por categoria
      test_conflict.py           # ConflictLog / ReviewConflict
      test_merger.py             # cenários de merge
      test_manual_cmd.py         # comando passmerge manual
      test_exporter_chrome.py    # ChromeExporter
      test_exporter_nordpass.py  # NordPassExporter
      test_exporter_kaspersky.py # KasperskyExporter
      test_exporter_onepassword.py # OnePasswordExporter
      test_importer_apple.py     # ApplePasswordsImporter
      test_exporter_apple.py     # ApplePasswordsExporter
      test_roundtrip.py          # round-trip: export → reimport → comparação (todos os formatos)

## Testes

    python -m unittest discover -s tests -v

Resultado esperado: **273 testes, todos OK**.

## Merge: como funciona

Quando `passmerge import` recebe ≥2 fontes, o merger executa 4 etapas:

### 1. Agrupamento (deduplicação)

Itens de todas as fontes são agrupados pela chave `(categoria, primary_key)`.
A `primary_key` é calculada por categoria a partir dos campos canônicos,
sempre normalizados (lowercase, strip, colapso de espaços internos):

| Categoria | Chave primária |
|---|---|
| LOGIN | `domínio_da_url` + `username` |
| CREDIT_CARD | `últimos 4 dígitos` + `cardholder` |
| SERVER | `hostname` + `username` + `port` |
| SECURE_NOTE | `title` + `hash(body[:256])` |
| IDENTITY | `email` — ou `first_name` + `last_name` + `phone` |
| SOFTWARE_LICENSE | `product` + `license_key` |
| DATABASE | `hostname` + `database` + `username` |
| WIRELESS | `ssid` |
| demais / OTHER | `title` |

> Itens de categorias diferentes nunca colidem mesmo que os campos coincidam.
> URLs são normalizadas extraindo apenas o netloc (`www.` removido).

### 2. Eleição do vencedor

Dentro de cada grupo, os itens são ordenados por uma chave composta de 4 critérios
(**menor = melhor**):

| Prioridade | Critério |
|---|---|
| 1 | Tem `updated_at` (itens com timestamp antes de itens sem) |
| 2 | Timestamp mais recente (epoch decrescente) |
| 3 | Tem `password` preenchida |
| 4 | Rank de fonte: `nordpass(0) > 1password(1) > chrome(2) > applesenhas(3) > kaspersky(4)` |

O primeiro item após essa ordenação é o **vencedor**; os demais são **perdedores**.

### 3. Resolução campo a campo

Para cada campo presente em qualquer item do grupo:

**a) Complementação** — o vencedor não tem valor para o campo:
- Se um único valor é encontrado nos perdedores → adotado diretamente.
- Se múltiplos valores divergem → o de melhor rank de fonte é adotado.
- O campo é marcado como `fields_complemented` nas estatísticas.

**b) Acordo** — o vencedor tem valor e todos os perdedores com valor concordam →
nenhuma ação, valor do vencedor mantido.

**c) Divergência — resolução automática** (sem entrada no log):
- **Timestamp:** vencedor ou algum perdedor divergente tem `updated_at` →
  a ordenação da etapa 2 já elegeu o mais recente; resolvido.
- **Senha igual:** múltiplos vaults têm senhas preenchidas e todas são iguais →
  prioridade de fonte decide; resolvido.
- **Vencedor tem senha, perdedores divergentes não têm:** o critério de senha
  da eleição já resolveu; resolvido.

**d) Conflito genuíno** → registrado em `<vault>.conflicts.json`:
sem timestamps, múltiplas fontes com senhas diferentes e divergentes.
Requer decisão manual via `passmerge manual`.

### 4. Merge de metadados e preservação

| Campo | Regra |
|---|---|
| `tags` | União de todas as tags de todos os itens do grupo |
| `favorite` | OR — basta um item ser favorito para o resultado ser favorito |
| `trashed` | AND — só marcado como lixeira se **todos** os itens estiverem na lixeira |
| `notes` | Nota do vencedor; se vazia, usa a primeira nota não-vazia de um perdedor |
| `sources` | Acumula todos os `SourceRef` do grupo (rastreabilidade completa) |
| `extras["_losers"]` | Valores divergentes descartados ficam registrados com `source`, `field` e `sha256(value)` (sem texto claro) |

### Revisar conflitos

O arquivo `<vault>.conflicts.json` contém apenas os conflitos que exigem
decisão manual, em JSON formatado e legível:

```json
[
  {
    "conflict_id": "...",
    "item_title": "GitHub",
    "category": "login",
    "conflicting_fields": ["password"],
    "versions": [
      { "source": "1password", "updated_at": null, "fields": { "username": "alice", "password": "pass1" } },
      { "source": "nordpass",  "updated_at": null, "fields": { "username": "alice", "password": "pass2" } }
    ]
  }
]
```

> **Atenção:** este arquivo contém senhas em texto claro. Apague-o após a revisão.

## Critério de aceite (Fases 1–4)

**Atendido:**

- Importers produzem ≥1 `CanonicalItem` por categoria suportada.
- Merger deduplica corretamente em todos os cenários de teste.
- Conflitos resolvidos automaticamente não aparecem no log; apenas os genuínos vão para `<vault>.conflicts.json`.
- Merge é não-destrutivo: nenhum valor é silenciosamente descartado.
- Exporters produzem arquivos que os importers correspondentes conseguem reler com fidelidade (round-trip).
- Itens de categorias não suportadas pelo destino são omitidos e registrados em `ExportReport.skipped_items`.

## Mudança em relação à arquitetura original

A arquitetura original previa vault criptografado com AES-256-GCM +
scrypt/Argon2id. Após revisão, optou-se por **JSON plano** porque o fluxo
de uso é de curta duração e os arquivos de entrada já estão em texto claro.
O módulo `security/wipe.py` garante o apagamento seguro no passo final.

## Próximos passos (Fase 5)

- Relatório de diferenças pré/pós-merge (`report/`)
- Estatísticas detalhadas por fonte e categoria
