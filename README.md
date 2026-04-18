# PassMerge - Fase 3 (Merger)

Consolidador local de credenciais entre Google/Chrome, NordPass, 1Password e
Kaspersky Password Manager.

> **Aviso de segurança:** este utilitário lê e grava credenciais em **texto
> plano**. Use exclusivamente em máquina própria e confiável e apague os
> arquivos (CSV/TXT/1PUX de entrada e `vault.json` de saída) assim que terminar
> o merge e a reimportação nos apps. O comando `passmerge wipe` faz isso
> com sobrescrita 3-pass.

## Estado desta entrega

Fase 3 da arquitetura — **Merger**:

- `core/matching.py` — chave de deduplicação por categoria (`primary_key`)
- `core/conflict.py` — log de conflitos em JSONL, sem valores em texto claro (só SHA-256)
- `core/merger.py` — merge campo a campo: timestamp → fonte rica → prioridade; complementação; preservação de perdedores em `extras["_losers"]`
- `passmerge import` unifica automaticamente ≥2 fontes e grava `vault.conflicts.jsonl` se houver conflitos

Fases 1 e 2 mantidas integralmente: 4 importers, schema canônico, vault JSON, wipe seguro.

## Requisitos

- Python 3.10+
- Nenhuma dependência externa (só a stdlib)

## Fluxo de uso

1. Exporte as senhas de cada gerenciador (gera CSV/TXT/1PUX em texto claro).
2. Importe e faça merge com `passmerge import` (múltiplas fontes são unificadas automaticamente).
3. Se houver conflitos, revise `vault.conflicts.jsonl` (campos sensíveis nunca aparecem em texto claro).
4. Verifique o vault com `passmerge verify` e revise o resumo com `passmerge status`.
5. *(Fase 4)* Reexporte nos formatos nativos.
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
        --kaspersky   kaspersky_export.txt \
        --vault       meu_vault.json

Se o vault ainda não existir, ele é criado automaticamente. Com ≥2 fontes,
o merger agrupa duplicatas e resolve conflitos automaticamente.

### Como exportar do 1Password

1. Abra o app 1Password
2. Vá em **Arquivo → Exportar → Todos os Vaults**
3. Escolha o formato **1Password (`.1pux`)**
4. Salve o arquivo e passe o caminho para `--onepassword`

### Formatos aceitos por gerenciador

| Gerenciador | Flag | Formato | Categorias suportadas |
| --- | --- | --- | --- |
| Google Chrome | `--chrome` | CSV (5 colunas) | LOGIN |
| NordPass | `--nordpass` | CSV (multi-categoria) | LOGIN, CREDIT_CARD, SECURE_NOTE, IDENTITY |
| 1Password | `--onepassword` | `.1pux` (ZIP + JSON) | LOGIN, CREDIT_CARD, SECURE_NOTE, SERVER, WIRELESS, IDENTITY, DATABASE, SOFTWARE_LICENSE |
| Kaspersky | `--kaspersky` | TXT (blocos) | LOGIN, SECURE_NOTE |

### Exemplo de comando completo

python -m passmerge import --onepassword C:\Users\Alexandre\Senhas\1Password.1pux --kaspersky C:\Users\Alexandre\Senhas\Kaspersky.txt --chrome C:\Users\Alexandre\Senhas\Chrome.csv --vault C:\Users\Alexandre\Senhas\cofre.json


### Ver resumo do vault

    python -m passmerge status --vault meu_vault.json

### Validar integridade do schema

    python -m passmerge verify --vault meu_vault.json

### Apagar um arquivo com sobrescrita segura

    python -m passmerge wipe --file meu_export.1pux --yes

## Estrutura

    passmerge/
      __init__.py
      __main__.py              # habilita 'python -m passmerge'
      cli.py                   # argparse + todos os comandos
      core/
        canonical.py           # Vault, CanonicalItem, Category, SourceRef
        categories.py          # mapeamento canônico ↔ nativo (4 gerenciadores)
        normalize.py           # normalize_url, normalize_email, normalize_phone
        matching.py            # primary_key por categoria (deduplicação)
        conflict.py            # ConflictLog, ConflictEntry (JSONL, sem plaintext)
        merger.py              # merge(), MergeResult, MergeStats
      importers/
        base.py                # classe abstrata Importer
        chrome.py              # Google Chrome CSV
        nordpass.py            # NordPass CSV
        onepassword.py         # 1Password .1pux (ZIP + export.data JSON)
        kaspersky.py           # Kaspersky TXT
      security/
        wipe.py                # sobrescrita segura 3-pass
      exporters/               # (Fase 4)
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
      test_conflict.py           # ConflictLog / ConflictEntry
      test_merger.py             # 7 cenários de merge

## Testes

    python -m unittest discover -s tests -v

Resultado esperado: **182 testes, todos OK**.

## Merge: como funciona

Quando `passmerge import` recebe ≥2 fontes, o merger:

1. Agrupa itens por `(category, primary_key)` — chave canônica por categoria.
2. **Grupos com 1 item** → passam direto.
3. **Grupos com >1 item** → resolve campo a campo:
   - Timestamp mais recente vence.
   - Item com timestamp vence item sem timestamp.
   - Sem timestamp e valores divergem → prioridade (`1password > nordpass > kaspersky > chrome`); conflito marcado `requires_review=True`.
4. **Complementação:** campos vazios no vencedor são preenchidos por outros itens do grupo.
5. **Preservação:** valores perdedores ficam em `extras["_losers"]` (com SHA-256, nunca em texto claro).
6. **Log de conflitos** gravado em `<vault>.conflicts.jsonl`.


### Revisar conflitos

    cat meu_vault.conflicts.jsonl | python -m json.tool

Cada linha tem: `conflict_id`, `item_title`, `field`, `candidates` (com `value_hash` SHA-256),
`auto_resolution`, `requires_review`.

## Critério de aceite (Fases 1–3)

**Atendido:**

- Importers produzem ≥1 `CanonicalItem` por categoria suportada.
- Merger deduplica corretamente em todos os 7 cenários de teste.
- Campos sensíveis (password, etc.) nunca aparecem em texto claro no log.
- Merge é não-destrutivo: nenhum valor é silenciosamente descartado.

## Mudança em relação à arquitetura original

A arquitetura original previa vault criptografado com AES-256-GCM +
scrypt/Argon2id. Após revisão, optou-se por **JSON plano** porque o fluxo
de uso é de curta duração e os arquivos de entrada já estão em texto claro.
O módulo `security/wipe.py` garante o apagamento seguro no passo final.

## Próximos passos (Fase 4)

Implementar os exporters:

- Reexportar vault para CSV Chrome, CSV NordPass, TXT Kaspersky e `.1pux` 1Password
- Comando `passmerge export --target chrome --output saida.csv --vault vault.json`
