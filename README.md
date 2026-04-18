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
- `core/conflict.py` — `ReviewConflict` / `ConflictLog`: apenas conflitos sem resolução automática, com todos os campos em texto claro para avaliação humana
- `core/merger.py` — merge campo a campo com múltiplos critérios de resolução automática; complementação de campos; preservação de perdedores em `extras["_losers"]`
- `passmerge import` unifica automaticamente ≥2 fontes e grava `vault.conflicts.json` apenas com os conflitos que exigem decisão manual

Fases 1 e 2 mantidas integralmente: 4 importers, schema canônico, vault JSON, wipe seguro.

## Requisitos

- Python 3.10+
- Nenhuma dependência externa (só a stdlib)

## Fluxo de uso

1. Exporte as senhas de cada gerenciador (gera CSV/TXT/1PUX em texto claro).
2. Importe e faça merge com `passmerge import` (múltiplas fontes são unificadas automaticamente).
3. Se houver conflitos não resolvidos automaticamente, revise `vault.conflicts.json`, marque com `[x]` as versões escolhidas e rode `passmerge manual`.
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

### Resolver conflitos manualmente

Após revisar `vault.conflicts.json`, marque a versão escolhida trocando `"escolhido": "[]"` por `"escolhido": "[x]"` em exatamente uma versão de cada conflito:

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
        conflict.py            # ConflictLog, ReviewConflict (JSON formatado, com plaintext para revisão humana)
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
      test_conflict.py           # ConflictLog / ReviewConflict
      test_merger.py             # 11 cenários de merge
      test_manual_cmd.py         # comando passmerge manual

## Testes

    python -m unittest discover -s tests -v

Resultado esperado: **196 testes, todos OK**.

## Merge: como funciona

Quando `passmerge import` recebe ≥2 fontes, o merger:

1. Agrupa itens por `(category, primary_key)` — chave canônica por categoria.
2. **Grupos com 1 item** → passam direto.
3. **Grupos com >1 item** → elege vencedor e resolve campo a campo:

   **Critérios de eleição do vencedor** (ordem decrescente de prioridade):
   - Timestamp mais recente.
   - Tem timestamp vs. não tem.
   - Tem senha preenchida vs. sem senha.
   - Prioridade de fonte: `nordpass > 1password > chrome > kaspersky`.

   **Resolução automática de conflito de campo** (sem gerar entrada no log):
   - Vencedor ou perdedor tem timestamp → timestamp decide.
   - Todos os vaults com senha preenchida têm a mesma senha → prioridade de fonte decide.
   - Vencedor tem senha e todos os perdedores divergentes não têm senha → vencedor decide.
   - Em conflito multi-vault: vaults com senha em branco são excluídos antes da comparação; se restar só um lado com senha → resolvido automaticamente.

   **Conflito genuíno** (vai para `<vault>.conflicts.json`): sem timestamps, múltiplos vaults com senhas diferentes e divergentes.

4. **Complementação:** campos ausentes no vencedor são preenchidos por campos presentes nos perdedores, inclusive os descartados na resolução de conflito.
5. **Preservação:** valores perdedores ficam em `extras["_losers"]` (com SHA-256, sem texto claro).

### Revisar conflitos

O arquivo `<vault>.conflicts.json` contém apenas os conflitos que exigem decisão manual, em JSON formatado e legível:

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

## Critério de aceite (Fases 1–3)

**Atendido:**

- Importers produzem ≥1 `CanonicalItem` por categoria suportada.
- Merger deduplica corretamente em todos os 7 cenários de teste.
- Conflitos resolvidos automaticamente não aparecem no log; apenas os genuínos (senhas diferentes, sem timestamps) vão para `<vault>.conflicts.json`.
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
