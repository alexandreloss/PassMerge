# PassMerge - Fase 2 (Importers)

Consolidador local de credenciais entre Google/Chrome, NordPass, 1Password e
Kaspersky Password Manager.

> **Aviso de segurança:** este utilitário lê e grava credenciais em **texto
> plano**. Use exclusivamente em máquina própria e confiável e apague os
> arquivos (CSV/TXT/1PUX de entrada e `vault.json` de saída) assim que terminar
> o merge e a reimportação nos apps. O comando `passmerge wipe` faz isso
> com sobrescrita 3-pass.

## Estado desta entrega

Fase 2 da arquitetura — **Importers**:

- 4 importers concretos: Chrome (CSV), NordPass (CSV), 1Password (`.1pux`), Kaspersky (TXT)
- Classe abstrata `Importer` com interface uniforme (`parse`, `source_name`, `supported_categories`, `supports_timestamps`)
- Normalização de campos reutilizável (`normalize_url`, `normalize_email`, `normalize_phone`)
- Comando `passmerge import` com suporte a múltiplas fontes simultâneas
- `SourceFileRef` gravado no vault (sha256, contagem de itens, caminho)
- Suíte de testes com **120 casos** (unittest, sem dependências externas)

Fase 1 mantida integralmente: schema canônico, mapeamento nativo, vault JSON, wipe seguro.

## Requisitos

- Python 3.10+
- Nenhuma dependência externa (só a stdlib)

## Fluxo de uso

1. Exporte as senhas de cada gerenciador (gera CSV/TXT/1PUX em texto claro).
2. Importe tudo para um vault unificado com `passmerge import`.
3. Verifique o vault com `passmerge verify` e revise com `passmerge status`.
4. *(Fase 3)* Resolva conflitos; *(Fase 4)* reexporte nos formatos nativos.
5. Apague todos os arquivos intermediários com `passmerge wipe`.

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

Se o vault ainda não existir, ele é criado automaticamente. Se já existir,
os novos itens são acrescentados (sem deduplicação — isso é tarefa da Fase 3).

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

## Testes

    python -m unittest discover -s tests -v

Resultado esperado: **120 testes, todos OK**.

## Critério de aceite (Fase 2)

**Atendido** — cada importer:

- Produz ≥ 1 `CanonicalItem` por categoria que suporta.
- Anota `SourceRef` (source + imported_at) em todos os itens.
- Preenche `updated_at` quando a fonte suporta timestamps (1Password, NordPass).
- Preserva unicode, vírgulas em notas e URLs vazias sem truncar.

## Mudança em relação à arquitetura original

A arquitetura original previa vault criptografado com AES-256-GCM +
scrypt/Argon2id. Após revisão, optou-se por **JSON plano** porque o fluxo
de uso é de curta duração e os arquivos de entrada já estão em texto claro.
O módulo `security/wipe.py` garante o apagamento seguro no passo final.

## Próximos passos (Fase 3)

Implementar o merge inteligente:

- Deduplicação por `normalize_url` + `normalize_email`
- Resolução de conflitos por `updated_at` (timestamp mais recente vence)
- Comando `passmerge resolve` para casos ambíguos
