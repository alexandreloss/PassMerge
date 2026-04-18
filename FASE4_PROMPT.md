# Prompt para iniciar a Fase 4 do PassMerge em nova sessão

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

As **Fases 1 a 3** já estão prontas. Antes de começar, **leia estes
arquivos na ordem** para entender o estado atual:

1. `README.md` — visão geral e decisões
2. `passmerge/core/canonical.py` — `Vault`, `CanonicalItem`, `Category`
3. `passmerge/core/categories.py` — tabelas `CANONICAL_TO_*` (usadas pelos exporters)
4. `passmerge/importers/` — todos os importers (para entender os campos que cada formato espera)
5. `passmerge/core/merger.py` — `MergeResult`, `MergeStats`
6. `passmerge/cli.py` — comandos `init`, `status`, `verify`, `wipe`, `import`
7. Pelo menos `tests/test_merger.py` para ver como os itens merged ficam na prática

**Decisões já tomadas (não reabrir):**

- Vault é JSON UTF-8 em texto claro (sem criptografia).
- Sem dependências externas — só stdlib Python 3.10+.
- Testes usam `unittest`, fixtures são sintéticas.
- Os importers da F2 são a referência dos formatos nativos de cada app.
  Os exporters devem produzir arquivos que os importers correspondentes
  consigam reler com fidelidade (round-trip).

**Objetivo desta sessão: Fase 4 — Exporters**

Implementar os 4 exporters concretos que convertem `list[CanonicalItem]`
de volta ao formato nativo de cada gerenciador, para reimportação nos apps.

### 1. `passmerge/exporters/base.py` — Interface abstrata

```python
@dataclass
class ExportReport:
    target: str                         # "chrome", "1password", etc.
    exported_count: int
    skipped_items: list[dict]           # [{id, title, category, reason}]
    truncated_fields: list[dict]        # [{id, title, field, original_len, max_len}]
    warnings: list[str]

class Exporter(ABC):
    target_name: str
    supported_categories: set[Category]

    @abstractmethod
    def export(self, items: list[CanonicalItem], out_path: Path) -> ExportReport: ...
```

Itens de categorias não suportadas pelo alvo: **omitir** e registrar em
`ExportReport.skipped_items` com `reason="unsupported_category"`.

### 2. `passmerge/exporters/chrome.py` — CSV Chrome

Formato de saída: CSV UTF-8 com colunas `name,url,username,password,note`.

- Apenas `Category.LOGIN`. Todo o resto é skipped.
- `name` = `item.title`
- `url` = `item.fields["url"]` (se vazio, usar string vazia)
- `username` = `item.fields["username"]`
- `password` = `item.fields["password"]`
- `note` = `item.notes` (preservar quebras de linha `\n`)
- Usar `csv.writer` com `quoting=csv.QUOTE_ALL` para segurança.

### 3. `passmerge/exporters/kaspersky.py` — TXT Kaspersky

Formato de saída: TXT proprietário com blocos separados por categoria.

```
Websites

Website name: GitHub
Website URL: https://github.com
Login name: alex
Login: alex@example.com
Password: ****
Comment:

---

Notes

Note name: Backup Codes
Text: chave1 chave2 chave3

---
```

- `Category.LOGIN` → bloco `Websites` (mapear campos conforme rótulos)
- `Category.SECURE_NOTE` → bloco `Notes`
- Demais categorias → skipped
- Separador entre blocos: `---` em linha isolada
- Separador entre entradas dentro do bloco: linha em branco

### 4. `passmerge/exporters/nordpass.py` — CSV NordPass

Formato de saída: CSV UTF-8, colunas variam por tipo. Usar as mesmas
colunas que o importer NordPass leu na F2.

Cabeçalho completo (todas as colunas mesmo que vazias):
`name,url,username,password,note,cardholdername,cardnumber,cvc,
expirydate,zipcode,folder,full_name,phone_number,email,address1,
address2,city,country,state,type`

- `Category.LOGIN` → `type=password`
- `Category.CREDIT_CARD` → `type=credit_card`, preencher colunas de cartão
- `Category.SECURE_NOTE` → `type=note`
- `Category.IDENTITY` → `type=identity`, preencher colunas de identidade
- Demais categorias → skipped
- Usar `csv.DictWriter` com `extrasaction='ignore'`.

### 5. `passmerge/exporters/onepassword.py` — .1pux (ZIP + JSON)

Este é o exporter mais complexo. O formato `.1pux` é um ZIP contendo
`export.data` (JSON). Estrutura mínima do JSON:

```json
{
  "accounts": [{
    "attrs": {"accountName": "PassMerge Export", "name": "PassMerge",
              "email": "", "uuid": "<uuid>", "domain": ""},
    "vaults": [{
      "attrs": {"uuid": "<uuid>", "name": "Primary"},
      "items": [
        {
          "uuid": "<item.id>",
          "favIndex": 0 ou 1,
          "createdAt": <epoch>,
          "updatedAt": <epoch>,
          "trashed": false,
          "categoryUuid": "001",
          "overview": {
            "title": "...",
            "url": "...",
            "urls": [{"primary": true, "url": "..."}],
            "tags": ["..."]
          },
          "details": {
            "loginFields": [
              {"designation": "username", "value": "..."},
              {"designation": "password", "value": "..."}
            ],
            "notesPlain": "...",
            "sections": []
          }
        }
      ]
    }]
  }]
}
```

- Converter `Category` para `categoryUuid` via `CANONICAL_TO_ONEPASSWORD`
  de `core/categories.py`.
- `createdAt`/`updatedAt`: converter ISO-8601 para epoch (int). Se `None`,
  usar epoch=0.
- Para `LOGIN`: campos em `details.loginFields` com `designation`.
- Para `CREDIT_CARD`: campos em `details.sections[0].fields[]` com
  `title` e `value`.
- Para `SERVER`: similar ao credit card, com `hostname`, `port`, etc.
  nos sections.
- Para `SECURE_NOTE`: apenas `details.notesPlain`.
- Gerar o ZIP com `zipfile.ZipFile` contendo `export.data`.

Consultar o importer `importers/onepassword.py` para reverter exatamente
o mapeamento de campos (o exporter é o inverso do importer).

### 6. Comando `passmerge export` no CLI

```
passmerge export --vault vault.json \
  --to-chrome out/chrome.csv \
  --to-nordpass out/nordpass.csv \
  --to-onepassword out/1p.1pux \
  --to-kaspersky out/kaspersky.txt
```

Todos os `--to-*` são opcionais (ao menos um obrigatório). Para cada
formato solicitado:

1. Ler o vault.
2. Instanciar o exporter.
3. Chamar `.export(vault.items, path)`.
4. Imprimir o `ExportReport` no terminal: itens exportados, skipped
   (com motivo), truncados.

### 7. Testes

**Testes por exporter** em `tests/test_exporter_<nome>.py`:

- Exportar N itens sintéticos. Verificar que o arquivo de saída existe,
  não está vazio, e é válido (CSV parseable, ZIP legível, TXT com blocos).
- Itens de categoria não suportada → aparecem em `ExportReport.skipped`.
- Campos com unicode, vírgulas, quebras de linha → preservados.

**Testes de round-trip** em `tests/test_roundtrip.py` (os mais
importantes):

- Cenário por formato: criar N `CanonicalItem` sintéticos → exportar →
  reimportar com o importer correspondente → comparar campo a campo.
  Os campos que o formato suporta devem casar. Os que não suporta devem
  ser silenciosamente perdidos (e registrados no ExportReport).

  ```python
  def test_chrome_roundtrip(self):
      items = [make_login("GitHub", "alex", "pass123", "https://github.com")]
      report = ChromeExporter().export(items, tmp / "chrome.csv")
      reimported = ChromeImporter().parse(tmp / "chrome.csv")
      self.assertEqual(reimported[0].fields["username"], "alex")
      self.assertEqual(reimported[0].fields["password"], "pass123")
  ```

- **Round-trip NordPass:** login + cartão de crédito + nota.
- **Round-trip Kaspersky:** login + nota.
- **Round-trip 1Password:** login + cartão + nota + server (se suportado).
- **Round-trip com itens não suportados:** exportar login + server para
  Chrome → `ExportReport` lista server como skipped, reimportação traz
  só o login.

**Critério de aceite da Fase 4:** todos os round-trip tests passam —
`import → export → reimport` preserva campos suportados. E todos os testes
das Fases anteriores continuam passando em
`python -m unittest discover -s tests -v`.

**Comece com um TodoWrite detalhado.** Implemente na ordem:
base → 1Password (mais complexo) → NordPass → Kaspersky → Chrome →
CLI integration → round-trip tests.
Rode os testes após cada exporter.

## PROMPT (fim — copie até aqui)
