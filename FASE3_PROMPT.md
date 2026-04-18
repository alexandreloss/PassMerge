# Prompt para iniciar a Fase 3 do PassMerge em nova sessão

Copie o bloco abaixo e cole como primeira mensagem numa nova sessão do
Claude Code (com `/model sonnet` ativado).

O projeto já está em:
`C:\Users\31897\OneDrive - A.C.Camargo Cancer Center\VSCode\PassMerge`

---

## PROMPT (início — copie a partir daqui)

Estou continuando um projeto chamado **PassMerge**: um utilitário Python (CLI,
só stdlib) para consolidar senhas exportadas de Google/Chrome, NordPass,
1Password e Kaspersky Password Manager, fazer merge inteligente com
resolução de conflitos por timestamp, e reexportar em cada formato nativo.

As **Fases 1 e 2** já estão prontas. Antes de começar, **leia estes
arquivos na ordem** para entender o estado atual:

1. `README.md` — visão geral e decisões
2. `passmerge/core/canonical.py` — `Vault`, `CanonicalItem`, `Category`, `SourceRef`
3. `passmerge/core/categories.py` — tabelas de mapeamento canônico ↔ nativo
4. `passmerge/core/normalize.py` — `normalize_url()`, `normalize_email()`, etc. (criado na F2)
5. `passmerge/importers/base.py` — interface `Importer`
6. Pelo menos um importer concreto (ex.: `importers/onepassword.py`) para entender como `CanonicalItem` é preenchido na prática
7. `passmerge/cli.py` — comandos existentes incluindo `import`
8. `tests/` — padrão de testes e fixtures existentes

**Decisões já tomadas (não reabrir):**

- Vault é JSON UTF-8 em texto claro (sem criptografia).
- Sem dependências externas — só stdlib Python 3.10+.
- Testes usam `unittest`, não `pytest`. Fixtures são sintéticas.
- O merge acontece dentro do comando `import`: quando há múltiplas fontes,
  os importers produzem listas separadas de `CanonicalItem` e o merger
  as unifica antes de gravar o vault.

**Objetivo desta sessão: Fase 3 — Merger**

Implementar a lógica de merge e deduplicação de itens vindos de múltiplos
importers. A Fase 3 é o coração do sistema. Criar os seguintes módulos:

### 1. `passmerge/core/matching.py` — Chaves de deduplicação

Cada categoria tem uma chave primária para agrupar itens duplicados:

| Categoria       | Chave primária                                     |
|-----------------|----------------------------------------------------|
| `LOGIN`         | `normalize_url(url)` (domínio) + `username` lower  |
| `CREDIT_CARD`   | últimos 4 dígitos de `number` + `cardholder` lower  |
| `SERVER`        | `hostname` lower + `username` lower + `port`        |
| `SECURE_NOTE`   | `title` normalizado + `hashlib.sha256(body[:256])`  |
| `IDENTITY`      | `email` lower OU (`first_name` + `last_name` + `phone`) |
| `SOFTWARE_LICENSE` | `product` lower + `license_key` lower             |
| `DATABASE`      | `hostname` lower + `database` lower + `username`   |
| `WIRELESS`      | `ssid` lower                                        |
| `OTHER`         | `title` normalizado                                 |

Interface: `def primary_key(item: CanonicalItem) -> str` retornando uma
string canônica hashável. Itens com mesmo `(category, primary_key)` são
candidatos a merge.

Normalizar antes da comparação: lowercase, strip, collapse whitespace.
Para URLs, usar `normalize_url()` do `core/normalize.py` (extrair domínio).
Para campos opcionais ausentes, usar string vazia (nunca `None` na chave).

### 2. `passmerge/core/conflict.py` — Log de conflitos

Dataclass `ConflictEntry`:

```python
@dataclass
class ConflictEntry:
    conflict_id: str          # uuid
    item_title: str
    category: str
    field: str                # "password", "username", etc.
    candidates: list[dict]    # [{source, value_hash (sha256), updated_at}]
    auto_resolution: str      # "1password (timestamp)" ou "priority"
    requires_review: bool     # True se sem timestamp e valores divergem
```

SEGURANÇA: o log **nunca** registra o valor do campo sensível em texto
claro. Apenas o SHA-256 do valor (`hashlib.sha256(value.encode()).hexdigest()`).

Classe `ConflictLog`:
- `.add(entry: ConflictEntry)`
- `.to_jsonl() -> str` — uma linha JSON por conflito
- `.save(path: Path)` — grava `conflicts.jsonl`
- `.summary() -> dict` — contagem de conflitos por tipo, quantos requerem review

### 3. `passmerge/core/merger.py` — Algoritmo de merge

Função principal:

```python
def merge(item_groups: list[list[CanonicalItem]],
          priority: list[str] | None = None) -> MergeResult:
```

Onde `item_groups` são as listas produzidas por cada importer e `priority`
é a ordem de prioridade por fonte (default: `["1password", "nordpass",
"kaspersky", "chrome"]`).

**Algoritmo (seção 6 da arquitetura aprovada):**

1. **Agrupar** todos os itens de todas as listas por `(category, primary_key)`.

2. **Grupos com 1 item** → passa direto (sem conflito).

3. **Grupos com >1 item** → resolver campo a campo:
   a. **Timestamp:** se ambos têm `updated_at`, vence o mais recente.
   b. **Fonte rica:** se apenas um tem `updated_at`, ele vence.
   c. **Prioridade:** se nenhum tem timestamp e valores divergem,
      usa prioridade configurada. Registra conflito com
      `requires_review=True`.

4. **Complementação:** campo a campo — se o vencedor tem campo X vazio
   e outro item do grupo tem X preenchido, adota o valor.
   Se múltiplos não-vencedores divergem em X, adota o de maior prioridade
   e registra conflito.

5. **Preservação:** valores perdedores vão em
   `item.extras["_losers"] = [{source, field, value_hash, reason}]`.
   Merge é **não-destrutivo** — nenhum dado é silenciosamente descartado.

6. **SourceRef:** o item merged acumula os `SourceRef` de todos os itens
   do grupo.

`MergeResult`:
```python
@dataclass
class MergeResult:
    items: list[CanonicalItem]
    conflict_log: ConflictLog
    stats: MergeStats  # total_input, total_output, groups_merged, fields_complemented
```

### 4. Integrar merge no CLI `import`

Alterar o comando `passmerge import` existente para, quando há ≥2 fontes:
1. Rodar cada importer individualmente (já feito na F2).
2. Chamar `merge()` passando as listas.
3. Gravar o `MergeResult.items` no vault.
4. Gravar `conflicts.jsonl` ao lado do vault (se houver conflitos).
5. Imprimir resumo no terminal: itens por fonte, grupos merged,
   conflitos requerendo revisão.

Quando há apenas 1 fonte: pular merge (sem sentido), gravar direto.

### 5. Testes

Criar `tests/test_matching.py`:
- Dois logins com mesma URL (variantes: `https://github.com/login` vs
  `http://www.github.com`) e mesmo username → mesma chave primária.
- Login com username diferente → chave diferente.
- Cartão com mesmos últimos 4 dígitos + cardholder → mesma chave.
- Nota segura com mesmo título e body → mesma chave.

Criar `tests/test_merger.py`:
- **Cenário 1:** 2 logins do GitHub de fontes diferentes, ambos com
  timestamp. Vence o mais recente. Campos exclusivos complementados.
- **Cenário 2:** 2 logins, apenas 1 com timestamp. Vence o que tem
  timestamp.
- **Cenário 3:** 2 logins, nenhum com timestamp, passwords diferentes.
  Vence por prioridade. `requires_review=True` no conflito. Perdedor em
  `extras._losers`.
- **Cenário 4:** 3 fontes para o mesmo item. Resolução em cascata.
- **Cenário 5:** itens sem duplicata (de categorias diferentes ou chaves
  diferentes). Passam direto sem merge. Contagem preservada.
- **Cenário 6:** complementação — vencedor tem OTP vazio, perdedor tem
  OTP preenchido → merged herda o OTP.
- **Cenário 7:** campos sensíveis (password) nunca aparecem em texto claro
  no conflict log — só sha256.

Criar `tests/test_conflict.py`:
- `ConflictLog` serializa para JSONL corretamente.
- `.summary()` conta corretamente.
- `value_hash` é sha256 e não contém o valor original.

**Critério de aceite da Fase 3:** todos os cenários de teste acima passam,
inclusive os testes das Fases 1 e 2. O comando `passmerge import` com 2+
fontes sintéticas produz um vault com itens merged e um `conflicts.jsonl`.

**Comece com um TodoWrite detalhado.** Implemente na ordem:
matching → conflict → merger → CLI integration → testes.
Rode os testes após cada módulo.

## PROMPT (fim — copie até aqui)
