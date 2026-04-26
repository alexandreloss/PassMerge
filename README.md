# PassMerge

Consolidador local de credenciais entre Google/Chrome, NordPass, 1Password,
Apple Passwords e Kaspersky Password Manager.

> **Aviso de segurança:** este utilitário lê e grava credenciais em **texto
> plano**. Use exclusivamente em máquina própria e confiável e apague os
> arquivos (CSV/TXT/1PUX de entrada e `vault.json` de saída) assim que terminar
> o merge e a reimportação nos apps. O comando `passmerge wipe` faz isso
> com sobrescrita 3-pass.

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

---

## Comandos

### `init` — Criar um vault vazio

    python -m passmerge init --vault meu_vault.json

Cria `meu_vault.json` com schema canônico vazio (0 itens). Se o arquivo já
existir, o comando encerra com erro sem sobrescrever.

**Exemplo:**

```
python -m passmerge init --vault C:\Senhas\cofre.json
# OK: vault criado em C:\Senhas\cofre.json
#     schema_version = 1.0
#     itens = 0
```

---

### `import` — Importar e mesclar arquivos de senha

Todos os argumentos de fonte são opcionais — informe ao menos um.
O vault é criado automaticamente se ainda não existir.

    python -m passmerge import \
        --chrome      google_export.csv   \
        --nordpass    nordpass_export.csv \
        --onepassword meu_export.1pux     \
        --applesenhas apple_export.csv    \
        --kaspersky   kaspersky_export.txt \
        --vault       meu_vault.json

**Exemplo — importar 3 fontes de uma vez:**

```
python -m passmerge import \
    --nordpass    C:\Senhas\NordPass.csv  \
    --onepassword C:\Senhas\1Password.1pux \
    --chrome      C:\Senhas\Chrome.csv   \
    --vault       C:\Senhas\cofre.json

# OK: vault criado em C:\Senhas\cofre.json
#   nordpass   : 120 itens importados
#   1password  :  85 itens importados
#   chrome     :  42 itens importados
#   merge      : 198 itens únicos (49 duplicatas removidas)
#   conflitos  :   3 (ver cofre.conflicts.json)
```

> **Importante — passe todas as fontes em uma única chamada.**
> O merge e a deduplicação só ocorrem quando ≥2 fontes são fornecidas
> **ao mesmo tempo**. Importar cada fonte separadamente em chamadas
> individuais não dispara o merger — os itens são simplesmente
> concatenados ao vault sem deduplicar, gerando duplicatas entre fontes.
> A ordem dos argumentos não afeta o resultado; a prioridade é sempre
> `nordpass > 1password > chrome > applesenhas > kaspersky`.

**Como obter os arquivos de exportação:**

| Gerenciador | Como exportar |
|---|---|
| Google Chrome | `chrome://password-manager/passwords` → Exportar |
| NordPass | Configurações → Exportar → CSV |
| 1Password | Arquivo → Exportar → Todos os Vaults → formato `.1pux` |
| Apple Passwords | App Senhas → ••• → Exportar Senhas (iOS 18+ / macOS Sequoia+) |
| Kaspersky | Gerenciador de Senhas → Configurações → Exportar |

**Formatos aceitos por gerenciador:**

| Gerenciador | Flag | Formato | Categorias suportadas |
|---|---|---|---|
| Google Chrome | `--chrome` | CSV (5 colunas) | LOGIN |
| NordPass | `--nordpass` | CSV (24 colunas) | LOGIN, CREDIT_CARD, SECURE_NOTE, IDENTITY |
| 1Password | `--onepassword` | `.1pux` (ZIP + JSON) | Todas as 22 categorias¹ |
| Apple Passwords | `--applesenhas` | CSV (6 colunas) | LOGIN |
| Kaspersky | `--kaspersky` | TXT (blocos) | LOGIN, SECURE_NOTE |

¹ LOGIN, CREDIT_CARD, SECURE_NOTE, IDENTITY, PASSWORD, SERVER, SOFTWARE_LICENSE, BANK_ACCOUNT,
DATABASE, DRIVER_LICENCE, OUTDOOR_LICENSE, MEMBERSHIP, PASSPORT, REWARD_PROGRAM, SSN, WIRELESS,
EMAIL_ACCOUNT, API_CREDENTIAL, MEDICAL_RECORD, CRYPTO_WALLET, DOCUMENT, OTHER.

---

### `status` — Ver resumo do vault

    python -m passmerge status --vault meu_vault.json

Exibe contagem de itens por categoria, número de conflitos pendentes e
metadados da última geração.

**Exemplo:**

```
python -m passmerge status --vault C:\Senhas\cofre.json

# schema_version : 1.0
# generated_at   : 2025-11-04T18:32:00+00:00
# itens          : 198
#   login        : 152
#   credit_card  :  12
#   secure_note  :  20
#   identity     :   8
#   server       :   6
# conflitos      :   3
```

---

### `verify` — Validar integridade do schema

    python -m passmerge verify --vault meu_vault.json

Valida a estrutura JSON do vault (versão de schema, IDs únicos, campos
obrigatórios). Encerra com código 1 se encontrar erros.

**Exemplo:**

```
python -m passmerge verify --vault C:\Senhas\cofre.json
# OK: vault valido (198 itens, schema 1.0)

python -m passmerge verify --vault C:\Senhas\cofre_corrompido.json
# ERRO: item[5] (GitHub): campos não esperados para login: ['extra_field']
```

---

### `manual` — Resolver conflitos manualmente

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

**Exemplo:**

```
python -m passmerge manual \
    --vault C:\Senhas\cofre.json \
    --log   C:\Senhas\cofre.conflicts.json

# OK: 3 conflito(s) resolvido(s). Todos resolvidos → cofre.conflicts.json removido.
```

O comando:
- Atualiza os campos conflitantes no vault com os valores da versão marcada.
- Remove do log os conflitos resolvidos.
- Se todos os conflitos forem resolvidos, apaga o arquivo `.conflicts.json`.
- Conflitos sem marcação ou com marcação ambígua (dois `[x]`) permanecem no log.

---

### `export` — Exportar o vault para os formatos nativos

Todos os `--to-*` são opcionais — informe ao menos um.
Itens de categorias não suportadas pelo destino são omitidos e listados
no terminal (motivo: `unsupported_category`).

    python -m passmerge export \
        --vault            meu_vault.json \
        --to-chrome        saida_chrome.csv \
        --to-nordpass      saida_nordpass.csv \
        --to-onepassword   saida_1password.1pux \
        --to-applesenhas   saida_apple.csv \
        --to-kaspersky     saida_kaspersky.txt

**Exemplo — exportar para NordPass e 1Password ao mesmo tempo:**

```
python -m passmerge export \
    --vault          C:\Senhas\cofre.json          \
    --to-nordpass    C:\Senhas\saida_nordpass.csv  \
    --to-onepassword C:\Senhas\saida_1password.1pux

# nordpass   : 198 itens exportados, 0 omitidos
# 1password  : 198 itens exportados, 0 omitidos
```

**Formatos produzidos por gerenciador:**

| Destino | Flag | Formato | Categorias exportadas |
|---|---|---|---|
| Google Chrome | `--to-chrome` | CSV | LOGIN |
| NordPass | `--to-nordpass` | CSV (24 colunas, formato atual) | Todas² |
| 1Password | `--to-onepassword` | `.1pux` (ZIP + JSON) | Todas as 22 categorias |
| Apple Passwords | `--to-applesenhas` | CSV (6 colunas) | LOGIN |
| Kaspersky | `--to-kaspersky` | TXT | LOGIN, SECURE_NOTE |

² Categorias sem mapeamento nativo no NordPass (SERVER, DATABASE, etc.) são
exportadas como LOGIN para evitar perda de dados.

---

### `wipe` — Apagar arquivos com sobrescrita segura

    python -m passmerge wipe --file arquivo.csv --yes

Sobrescreve o arquivo 3 vezes (zeros, uns, aleatório) antes de apagá-lo.
A flag `--yes` confirma a operação sem prompt interativo.

**Exemplo — apagar todos os arquivos sensíveis após o processo:**

```
python -m passmerge wipe --file C:\Senhas\NordPass.csv     --yes
python -m passmerge wipe --file C:\Senhas\1Password.1pux   --yes
python -m passmerge wipe --file C:\Senhas\Chrome.csv       --yes
python -m passmerge wipe --file C:\Senhas\cofre.json       --yes
```

---

## Formatos NordPass em detalhe

### Estrutura do CSV (formato atual)

```
name, url, additional_urls, username, password, note,
cardholdername, cardnumber, cvc, pin, expirydate, zipcode,
folder, shared_folder, full_name, phone_number, email,
address1, address2, city, country, state,
type, custom_fields
```

### Campo `type`

| Valor em `type` | Categoria canônica |
|---|---|
| `password` | LOGIN |
| `credit_card` | CREDIT_CARD |
| `note` | SECURE_NOTE |
| `identity` | IDENTITY |
| `folder` | — ignorado na importação |
| ausente/vazio | inferido pelo conteúdo das colunas |

### Campo `custom_fields`

Campos extras do NordPass são armazenados como JSON na coluna `custom_fields`.
O importer parseia esse JSON e salva cada campo em `extras`:

**CSV recebido:**
```
custom_fields: [{"type":"hidden","label":"Chave de Segurança","value":"IBH"},{"type":"text","label":"Token","value":"abc123"}]
```

**Estrutura canônica resultante:**
```json
{
  "extras": {
    "Chave de Segurança": "IBH",
    "Token": "abc123"
  }
}
```

O exporter reverte esse processo: se o item canônico tiver `extras` preenchido,
eles são serializados de volta para `custom_fields` no formato:
```
[{"Chave de Segurança":"IBH","Token":"abc123"}]
```

### Campo `folder` no export

Em todos os exporters que suportam o conceito de pasta (NordPass), o campo
`folder` é preenchido com a **primeira tag** do item (`item.tags[0]`).
Se o item não tiver tags, usa o `item.folder` original; se também estiver
vazio, `folder` fica em branco.

```
tags: ["Mercantil do Brasil", "VLI"]  →  folder: "Mercantil do Brasil"
tags: []  +  folder: "Work"           →  folder: "Work"
tags: []  +  folder: null             →  folder: ""
```

---

## Merge: como funciona

Quando `passmerge import` recebe ≥2 fontes, o merger executa 4 etapas:

### 1. Agrupamento (deduplicação)

Itens de todas as fontes são agrupados pela chave `(categoria, primary_key)`.
A `primary_key` é calculada por categoria a partir dos campos canônicos,
sempre normalizados (lowercase, strip, colapso de espaços internos):

| Categoria | Chave primária | Observação |
|---|---|---|
| LOGIN | `origin(url)` + `username` | origin = `scheme://host` sem path/query; `www.` removido¹ |
| CREDIT_CARD | `número completo` + `cardholder` | fallback: `extras["número"]` / `extras["titular"]` |
| SERVER | `hostname` + `username` | porta ignorada; fallback: `extras["url"]`/`extras["servidor"]` + `extras["nome de usuário"]` |
| SECURE_NOTE | `title` + `hash(body[:256])` | |
| IDENTITY | `email` — ou `first_name` + `last_name` + `phone` | |
| SOFTWARE_LICENSE | `product` + `license_key` | |
| DATABASE | `hostname` + `database` + `username` | fallback: `extras["servidor"]` + `extras["tipo"]` + `extras["nome de usuário"]` |
| WIRELESS | `ssid` | fallback: `extras["nome da rede"]` |
| demais / OTHER | `title` | PASSWORD, BANK_ACCOUNT, MEMBERSHIP, PASSPORT, etc. |

¹ Exemplos de normalização de URL para LOGIN:
- `https://prd-aa1.lg.com.br/Autoatendimento/index.html?id=1` → `https://prd-aa1.lg.com.br`
- `https://www.aa.com/homePage.do` → `https://aa.com`
- `http://visabenefits.force.com/webportal/` → `http://visabenefits.force.com`

> Itens de categorias diferentes nunca colidem mesmo que os campos coincidam.
> Campos não mapeados pelo importer (ex.: nomes de campos em português no .1pux)
> são armazenados em `extras` e usados como fallback na chave primária.

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
      { "source": "1password", "updated_at": null, "escolhido": "[]", "fields": { "username": "alice", "password": "pass1" } },
      { "source": "nordpass",  "updated_at": null, "escolhido": "[]", "fields": { "username": "alice", "password": "pass2" } }
    ]
  }
]
```

> **Atenção:** este arquivo contém senhas em texto claro. Apague-o após a revisão.

---

## Estrutura do projeto

    passmerge/
      __init__.py
      __main__.py              # habilita 'python -m passmerge'
      cli.py                   # argparse + todos os comandos
      core/
        canonical.py           # Vault, CanonicalItem, Category (22 valores), SourceRef
        categories.py          # mapeamento canônico ↔ nativo (5 gerenciadores)
        normalize.py           # normalize_url, normalize_email, normalize_phone
        matching.py            # primary_key por categoria (deduplicação)
        conflict.py            # ConflictLog, ReviewConflict (JSON formatado para revisão humana)
        merger.py              # merge(), MergeResult, MergeStats
      importers/
        base.py                # Importer (ABC)
        chrome.py              # Google Chrome CSV
        nordpass.py            # NordPass CSV (24 colunas; legado também suportado)
        onepassword.py         # 1Password .1pux (ZIP + export.data JSON)
        apple.py               # Apple Passwords CSV (iPhone/macOS)
        kaspersky.py           # Kaspersky TXT
      exporters/
        base.py                # Exporter (ABC) + ExportReport
        chrome.py              # Google Chrome CSV
        nordpass.py            # NordPass CSV (24 colunas, formato atual)
        onepassword.py         # 1Password .1pux (ZIP + export.data JSON)
        apple.py               # Apple Passwords CSV (iPhone/macOS)
        kaspersky.py           # Kaspersky TXT
      security/
        wipe.py                # sobrescrita segura 3-pass
    tests/
      fixtures/
        chrome_test.csv
        nordpass_test.csv
        onepassword_test.1pux
        kaspersky_test.txt
        apple_test.csv
        make_onepassword_fixture.py   # gerador da fixture .1pux
      test_canonical.py
      test_phase1_acceptance.py
      test_importer_chrome.py
      test_importer_nordpass.py
      test_importer_onepassword.py
      test_importer_kaspersky.py
      test_importer_apple.py
      test_matching.py           # chaves de deduplicação por categoria
      test_conflict.py           # ConflictLog / ReviewConflict
      test_merger.py             # cenários de merge
      test_manual_cmd.py         # comando passmerge manual
      test_exporter_chrome.py
      test_exporter_nordpass.py
      test_exporter_kaspersky.py
      test_exporter_onepassword.py
      test_exporter_apple.py
      test_roundtrip.py          # round-trip: export → reimport → comparação (todos os formatos)

## Testes

    python -m unittest discover -s tests -v

Resultado esperado: **308 testes, todos OK**.

---

## Critério de aceite

- Importers produzem ≥1 `CanonicalItem` por categoria suportada.
- Merger deduplica corretamente em todos os cenários de teste.
- Conflitos resolvidos automaticamente não aparecem no log; apenas os genuínos vão para `<vault>.conflicts.json`.
- Merge é não-destrutivo: nenhum valor é silenciosamente descartado.
- Exporters produzem arquivos que os importers correspondentes conseguem reler com fidelidade (round-trip).
- Itens de categorias não suportadas pelo destino são omitidos e registrados em `ExportReport.skipped_items`.

## Notas de arquitetura

A arquitetura original previa vault criptografado com AES-256-GCM +
scrypt/Argon2id. Após revisão, optou-se por **JSON plano** porque o fluxo
de uso é de curta duração e os arquivos de entrada já estão em texto claro.
O módulo `security/wipe.py` garante o apagamento seguro no passo final.

## Próximos passos (Fase 5)

- Relatório de diferenças pré/pós-merge (`report/`)
- Estatísticas detalhadas por fonte e categoria
