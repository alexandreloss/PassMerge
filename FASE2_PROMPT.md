# Prompt para iniciar a Fase 2 do PassMerge em nova sessão

Copie o bloco abaixo e cole como primeira mensagem numa nova sessão do
Claude Code (com `/model sonnet` ativado antes, se ainda não estiver).

O projeto já está em:
`C:\Users\31897\OneDrive - A.C.Camargo Cancer Center\VSCode\PassMerge`

---

## PROMPT (início — copie a partir daqui)

Estou continuando um projeto chamado **PassMerge**: um utilitário Python (CLI,
só stdlib) para consolidar senhas exportadas de Google/Chrome, NordPass,
1Password e Kaspersky Password Manager, fazer merge inteligente com
resolução de conflitos por timestamp, e reexportar em cada formato nativo.

A **Fase 1 (Fundação)** já está pronta e os 19 testes passam. Antes de
começar, por favor **leia estes arquivos na ordem** para entender o estado
atual:

1. `README.md` — visão geral, decisões e uso atual
2. `passmerge/core/canonical.py` — schema canônico (`Vault`, `CanonicalItem`, `Category`)
3. `passmerge/core/categories.py` — tabelas de mapeamento canônico ↔ nativo
4. `passmerge/cli.py` — comandos existentes (`init`, `status`, `verify`, `wipe`)
5. `tests/test_canonical.py` e `tests/test_phase1_acceptance.py` — padrão de testes

**Decisões já tomadas (não reabrir):**

- Vault é JSON UTF-8 em texto claro (sem criptografia; o usuário apaga
  manualmente com `passmerge wipe` após o merge).
- Sem dependências externas — só stdlib Python 3.10+.
- Testes usam `unittest` da stdlib, não `pytest`.
- Fixtures de teste são **sintéticas** (nunca dados reais).

**Objetivo desta sessão: Fase 2 — Importers**

Implementar os 4 importers concretos na ordem:

1. `passmerge/importers/base.py` — classe abstrata `Importer` com
   `parse(path: Path) -> list[CanonicalItem]` e propriedades
   `source_name`, `supported_categories`, `supports_timestamps`.

2. `passmerge/importers/chrome.py` — CSV com 5 colunas
   (`name,url,username,password,note`). Só `Category.LOGIN`. Sem timestamp.

3. `passmerge/importers/kaspersky.py` — TXT proprietário com blocos
   `Websites`, `Applications`, `Notes`. Parser linha-a-linha por rótulo.
   Mapeia Websites/Apps → LOGIN, Notes → SECURE_NOTE.

4. `passmerge/importers/nordpass.py` — CSV multi-categoria com coluna
   `type` (`password`, `credit_card`, `note`, `identity`). Se houver
   `note_date`, usar como `updated_at`.

5. `passmerge/importers/onepassword.py` — `.1pux` é ZIP contendo
   `export.data` (JSON). Tem `createdAt`, `updatedAt`, `favorite`,
   `tags`. Usar `core.categories.ONEPASSWORD_TO_CANONICAL` para
   o `categoryUuid`. Percorrer recursivamente `details.loginFields`
   e `details.sections[].fields[]`.

Também criar:

- `passmerge/core/normalize.py` com `normalize_url()`, `normalize_email()`,
  `normalize_phone()` (só stdlib: `urllib.parse`, `re`). Serão reutilizadas
  pela Fase 3 (matching).

- Comando `passmerge import` no CLI:
  `passmerge import --chrome X.csv --nordpass Y.csv --onepassword Z.1pux
  --kaspersky W.txt --vault out.json` (todos opcionais, ao menos um
  obrigatório). Preencher `SourceFileRef` (source, path, sha256,
  item_count) em cada vault.

Para cada importer, criar fixture sintética em `tests/fixtures/` e um
arquivo de teste `tests/test_importer_<nome>.py` validando:

- contagem correta de itens
- categorias mapeadas corretamente
- campos preservados (incluindo unicode, vírgulas em notas, URLs vazias)
- `SourceRef` anotado em cada item
- `updated_at` preenchido quando a fonte suporta

**Critério de aceite da Fase 2:** cada importer produz ≥1
`CanonicalItem` por categoria que suporta, e todos os testes (Fase 1 +
Fase 2) passam em `python -m unittest discover -s tests -v`.

**Por favor, comece com um TodoWrite detalhado** e implemente **um
importer por vez** — do mais complexo (1Password) ao mais simples
(Chrome). Ao terminar cada importer, rode os testes dele antes de
passar para o próximo.

Fixture do 1Password deve ser gerada programaticamente com `zipfile` +
JSON mínimo — o formato `.1pux` é documentado em
`https://support.1password.com/1pux-format/` (só consulte se precisar
de detalhes que não estão em `core/categories.py`).

## PROMPT (fim — copie até aqui)
