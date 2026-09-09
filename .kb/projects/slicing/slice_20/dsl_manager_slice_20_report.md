# Report Slice 20

Implementata la Slice 20 end-to-end, nello scope richiesto. Stato finale: **completata**.

La verticalita' verificata e': evidenza DDL persistita -> candidato strutturalmente valido e
pending -> decisione append-only persistita -> foglia confirmed merge-eligible -> fatto
effettivo. Il percorso legacy resta leggibile e i candidati pending, rejected, superseded o
non-leaf non sono materializzati dal nuovo merge.

## Aggiunto

- migrazione append-only v7 con rebuild controllato di `candidate_batches`, backfill legacy,
  review, head, lineage, correzioni, riconciliazione, derivazioni e quattro viste effettive;
- profilo condiviso `canonical_json_v1`/SHA-256 con UTF-8, NFC, chiavi ordinate, numeri
  tipizzati, distinzione null/mancante e LF soltanto negli artifact JSON;
- `CandidateReviewService` con decisioni append-only, optimistic concurrency tramite
  `BEGIN IMMEDIATE`, replay prima del controllo della testa, collision detection e semantic
  no-op;
- review umana con attore stabile da `--actor-id` o `review.default_actor_id`, reason
  obbligatoria per reject/correct, e review automatica limitata a regole deterministiche
  nominate/versionate con policy id/versione;
- correzione atomica in run `candidate_correction`, nuovo batch `human_correction`, nuovo
  candidato, lineage senza branch, testa replacement confirmed e output del batch ID;
- merge mixed/strict con rilettura di testa e foglia nella propria transazione, report
  `result_catalog_v1`, skip distinti e `no_merge_eligible_candidates` con exit 4;
- riconciliazione persistente con retry standalone e chiusura atomica durante il merge del
  replacement;
- blocco di render DSL v1, diff ed export GEXF statico quando esistono riconciliazioni aperte;
- catalogo di derivazione contenente soltanto `ddl_table_fact/1`; l'output attraversa il
  normale importer, crea anche batch vuoti e rimane pending in assenza di review;
- comandi CLI:
  - `candidates review list <workspace> [--outcome ...]`;
  - `candidates review show <workspace> <candidate_record_id>`;
  - `candidates review confirm <workspace> <candidate_record_id> ...`;
  - `candidates review reject <workspace> <candidate_record_id> --reason ...`;
  - `candidates review correct <workspace> <candidate_record_id> --payload ... --reason ...`;
  - `candidates derive <workspace> [--source-revision-id ID] [--rule RULE]`;
  - `facts merge <workspace> --batch ID [--strict-review]`;
  - `facts reconcile <workspace> [--reconciliation-id ID] [--strict]`;
- test Slice 20 per migrazione reale, canonicalizzazione, review, concorrenza, idempotenza,
  correzione/crash/retry, merge, viste, riconciliazione, CLI e DDL end-to-end.

Nessuna nuova dipendenza runtime, ORM, rete o servizio esterno e' stato introdotto. Nessun
golden esistente e' stato modificato.

## Preflight e controllo anti-drift

Sono stati letti integralmente `AGENTS.md`, design v02, design v01, template report, analisi
tecnica, contratti manifest, manuale utente, i tre documenti di supporto candidati e i report
Slice 01-19. Sono stati inoltre ispezionati sorgenti, test, fixture, expected, schema,
migrazioni e help CLI correnti.

Il worktree iniziale era:

```text
## main...origin/main
 M .kb/prompt/prompt_slicing_dsl-manager.md
```

La modifica preesistente a `.kb/prompt/prompt_slicing_dsl-manager.md` non appartiene alla
Slice 20, non e' stata modificata né inclusa nel perimetro del diff della Slice.

Classificazione del gate dipendenze: **pronta**. Non sono emersi difetti bloccanti di Slice
01-19. L'assenza di review/lineage/effective views nello stato v6 era il gap atteso e
proprietario della Slice 20.

| Precondizione | Evidenza osservata prima del codice | Esito |
|---|---|---|
| Slice 01-19 disponibili | package `src/dsl_mngr`, CLI, worker e 19 report presenti | pronta |
| Schema reale v6 | `MIGRATIONS` terminava con `create_graph_export_schema` v6 | pronta |
| Import candidati | validation strutturale ed evidence binding gia' persistenti | pronta |
| Merge legacy | merge idempotente su fact/relation ma senza review eligibility | gap atteso Slice 20 |
| Candidate ID | `candidate_record_id` PK; nessun UNIQUE globale su `candidate_id` | pronta |
| Parser DDL | frammenti `ddl_table` attivi con `fragment_id`, locator e metadata | pronta |
| Snapshot legacy | `dsl_snapshots` append-only; renderer/diff/export statici v1 | pronta |
| Baseline test mirata | 39 test pertinenti verdi prima del cambiamento | pronta |

## Migrazione, persistenza e compatibilita'

La migrazione v7 `create_candidate_review_lineage_schema` aggiunge:

- `review_decisions`;
- `review_subject_heads`;
- `review_decision_evidence`;
- `review_audit_notes`;
- `candidate_lineage`;
- `candidate_corrections`;
- `reconciliation_required`;
- `candidate_derivation_runs`;
- `effective_fact_evidence`;
- `effective_relation_evidence`;
- `effective_facts`;
- `effective_relations`.

`candidate_batches` e' ricostruita con `input_path` nullable e con `origin_type`/`origin_ref`.
Il CHECK conserva `input_path` per `file_import` e `ai_import` e lo vieta per
`human_correction` e `deterministic_derivation`, che richiedono `origin_ref`. Durante il solo
rebuild SQLite le foreign key vengono disabilitate fuori transazione, verificate tramite
`PRAGMA foreign_key_check` prima del commit e ripristinate; l'upgrade resta atomico.
`candidate_records.supersedes_candidate_record_id` e il relativo indice unico rendono
esplicito anche sul record il parent della correzione; i trigger ne impongono la coerenza
con `candidate_lineage.parent_candidate_record_id`.

Il backfill crea lineage root per ogni candidato v6. Una decisione sintetica confirmed
`system/migration`, policy `legacy_backfill/1`, viene creata soltanto per supporti
materializzati `active` con assertion `explicit` o `observed`. I candidati inferred,
ambiguous e i supporti `conflicted` non sono confermati. Il test conserva byte e contenuto
di uno snapshot v1 gia' registrato.

Gli import AI sono catalogati come `ai_import`; gli import file ordinari restano
`file_import`. `candidate_id` rimane dichiarativo e ripetibile: soltanto
`candidate_record_id` identifica globalmente il record persistito.

## File della Slice

Nuovi file runtime:

```text
src/dsl_mngr/core/canonical.py
src/dsl_mngr/core/candidate_review.py
src/dsl_mngr/core/candidate_derivation.py
src/dsl_mngr/core/reconciliation.py
```

File runtime modificati:

```text
src/dsl_mngr/cli/app.py
src/dsl_mngr/cli/commands/candidates.py
src/dsl_mngr/cli/commands/dsl.py
src/dsl_mngr/cli/commands/facts.py
src/dsl_mngr/cli/commands/graph.py
src/dsl_mngr/core/ai_inbox.py
src/dsl_mngr/core/candidate_import.py
src/dsl_mngr/core/config.py
src/dsl_mngr/core/database.py
src/dsl_mngr/core/dsl_diff.py
src/dsl_mngr/core/dsl_renderer.py
src/dsl_mngr/core/graph_export.py
src/dsl_mngr/core/merge.py
src/dsl_mngr/core/migrations.py
src/dsl_mngr/core/runs.py
```

Nuovi file test:

```text
tests/__init__.py
tests/slice_20_test_support.py
tests/test_slice_20_candidate_review.py
tests/test_slice_20_migration_and_derivation.py
```

Test legacy adeguati soltanto al nuovo contratto di review/schema:

```text
tests/test_slice_01_workspace_config_logging.py
tests/test_slice_06_fact_merge.py
tests/test_slice_07_dsl_render.py
tests/test_slice_09_golden_pipeline.py
tests/test_slice_13_parse_xml_form.py
tests/test_slice_14_parse_db_code_log.py
tests/test_slice_16_batch_orchestration.py
tests/test_slice_19_local_ui.py
```

Artifact documentale aggiunto:

```text
.kb/projects/slicing/slice_20/dsl_manager_slice_20_report.md
```

## Tracciabilita' Slice 20

| Requisito sezione 17 | Implementazione | Test/esito finale |
|---|---|---|
| validita' != merge eligibility | `merge.py`: testa confirmed + foglia corrente | `test_slice_20_pending_not_mergeable` - passed |
| review append-only | tabelle/head e trigger v7; `CandidateReviewService` | `test_slice_20_decision_chain` - passed |
| concorrenza ottimistica | `BEGIN IMMEDIATE`, expected head incluso null | `test_slice_20_stale_head_atomic` - passed |
| idempotenza | lookup chiave/hash prima della testa, collisione e no-op | `test_slice_20_review_idempotency` - passed |
| correzione | transazione unica, batch/candidato/lineage/replacement head | `test_slice_20_correction_atomic` - passed |
| attore umano stabile | flag/config; nessun lookup OS; reason validate | `test_slice_20_actor_required` - passed |
| viste effettive | quattro viste v7 governate da head e leaf | `test_slice_20_effective_support_and_simple_reconcile` - passed |
| legacy migration | rebuild reale v6, backfill selettivo e FK check | `test_slice_20_migrate_real_v6` - passed |
| primo candidato DDL | catalogo/regola `ddl_table_fact/1`, importer normale | `test_slice_20_ddl_table_candidate` - passed |
| snapshot storici immutabili | nessun UPDATE snapshot/file durante v7 | coperto in `test_slice_20_migrate_real_v6` - passed |

Coperture obbligatorie ulteriori nello stesso modulo test:

- same-subject e ciclo dei decision link, testa unica e append-only;
- due writer con testa stantia e assenza di mutazioni;
- replay prima del head check, collisione chiave e semantic no-op;
- correzione con fault injection, rollback, retry, replay e no-branch;
- mixed merge, strict rollback e nessun eleggibile;
- supporti fact multipli e supporto relation effettivo;
- riconciliazione semplice, strict, replacement pending, retry e chiusura al merge;
- blocco render/diff/export con exit 4 e senza traceback;
- canonical hash per Unicode composto/decomposto, emoji, key order, null/mancante,
  interi grandi, decimali, zero negativo, liste e rifiuto float binari;
- due derive DDL con payload candidati canonici identici.

## Diff/status

Prima dell'aggiunta dei nuovi file non tracciati e del presente report, il diff tracciato
della sola Slice (esclusa la modifica utente preesistente) risultava:

```text
23 files changed, 1336 insertions(+), 50 deletions(-)
```

I file nuovi aggiungono i quattro moduli core, quattro file test/supporto e questo report.
Lo stato finale conserva separatamente la modifica utente preesistente come indicato nel
preflight.

## Test

Interprete usato: `.venv/Scripts/python.exe` / Python `3.12.10`.

Install editable eseguita prima del codice:

```powershell
.\.venv\Scripts\python.exe -m pip install -e ".[dev]"
```

Risultato: completato con exit 0; `dsl_mngr==0.1.0` installato editable e dipendenze dev
soddisfatte.

Baseline mirata pre-modifica:

```powershell
.\.venv\Scripts\python.exe -m pytest tests\test_slice_02_database_migrations.py tests\test_slice_05_candidate_validation.py tests\test_slice_06_fact_merge.py tests\test_slice_07_dsl_render.py tests\test_slice_08_dsl_diff.py tests\test_slice_12_parse_ddl.py tests\test_slice_13_parse_xml_form.py tests\test_slice_14_parse_db_code_log.py tests\test_slice_16_batch_orchestration.py tests\test_slice_17_graph_export.py
```

```text
39 passed in 77.14s
```

Test mirati finali:

```powershell
.\.venv\Scripts\python.exe -m pytest tests\test_slice_20_candidate_review.py tests\test_slice_20_migration_and_derivation.py tests\test_slice_02_database_migrations.py -q
```

```text
21 passed in 37.27s
```

Suite completa finale, eseguita dopo l'ultima modifica al codice:

```powershell
.\.venv\Scripts\python.exe -m pytest
```

```text
86 passed in 170.59s (0:02:50)
```

Non risultano skipped, xfail o failure nel run finale.

### Run intermedi e failure risolte

| Comando/insieme | Esito | Classificazione e risoluzione |
|---|---:|---|
| migration Slice 02 dopo prima v7 | 8 passed | verifica incrementale verde |
| Slice 02+05 | 12 passed | verifica importer/migrazioni verde |
| Slice 06 prima dell'adeguamento | 3 failed | atteso cambio contratto: fixture pending; aggiunta review esplicita nei test legacy |
| Slice 06 dopo adeguamento | 3 passed | risolto |
| primo run review Slice 20 | 6 passed, 2 failed | test usava run FK fittizio; ordine merge/reconcile esponeva conflitto fisico; entrambi corretti |
| secondo run review Slice 20 | 7 passed, 1 failed | replacement confrontato prima della compensazione; merge riordinato nella stessa transazione |
| run review successivo | 8 passed | risolto |
| primo upgrade v6 realistico | 2 passed, 1 failed | difetto prodotto: rebuild con FK attive; introdotti disable/check/restore atomici |
| rerun singolo upgrade | 1 failed | sola asserzione test `sqlite3.Row` vs tuple; corretta senza cambiare contratto |
| Slice 20 combinata | 11 passed, poi 12 passed | coperture incrementali verdi |
| prima suite completa | 82 passed, 3 failed in 270.68s | due fixture legacy: secondo batch non reviewed e INSERT UI schema v6; adeguate |
| Slice 16/19 mirate | 4 passed | regressioni risolte |
| Slice 15+20 | 15 passed | origine AI e Slice 20 verdi |
| contratto CLI subprocess | 1 passed | console script e modulo, help/exit/stdout/stderr |
| configurazione+actor CLI | 7 passed | default tipizzati e attore da config verdi |
| seconda suite completa | 86 passed in 175.54s | verde |
| gate finale mirato | 21 passed in 37.27s | verde |
| suite finale | 86 passed in 170.59s | verde |

Le failure intermedie erano tutte riproducibili e sono state risolte. Non rimangono failure
note, test disabilitati o scostamenti mascherati da fixture/golden.

## Verifiche aggiuntive

- `dsl-manager` e `python -m dsl_mngr` verificati tramite subprocess;
- help verificato con exit 0 e stderr vuoto per review list/show/confirm/reject/correct,
  derive, merge strict e reconcile;
- successi review/reconcile verificati come JSON `result_catalog_v1` su stdout;
- attore assente verificato con exit 2, stdout vuoto, reason stabile e nessun traceback;
- stale head, collisione idempotency, strict merge e reconciliation required verificati con
  exit/reason 4;
- due derive DDL producono gli stessi payload/hash semantici ordinati;
- `git diff --check`: exit 0; soli warning informativi Git sulla futura conversione LF/CRLF,
  nessun whitespace error;
- ricerca anti-scope: nessuna regola oltre `ddl_table_fact/1`, nessuna implementazione Excel
  o temporale, nessun `allow-incomplete`.

## Scostamenti e note

- Nessuno scostamento funzionale noto dal nucleo v02 e dalla sezione 17 assegnata alla
  Slice 20.
- I test legacy che invocavano direttamente il merge sono stati aggiornati esclusivamente
  per creare la nuova precondizione confirmed; i golden semantici esistenti restano
  invariati e la golden pipeline e' verde.
- Il renderer/diff/GEXF v1 continua a leggere lo stato fisico legacy. La Slice 20 aggiunge il
  gate di riconciliazione; non introduce anticipatamente DSL v2 o export dinamico.
- `review_audit_notes` e' disponibile nello schema; la creazione della nota per semantic
  no-op resta opzionale come previsto e non e' usata per alterare hash semantici.
- `review.automatic_policies` e' tipizzato e validato, ma non viene applicata alcuna policy
  automatica dalla derivazione: il batch orchestrator che applichera' policy abilitate e'
  responsabilita' della Slice 22. Il servizio richiede comunque policy id/versione e una
  regola deterministica nominata/versionata.

## Fuori scope / note

- non implementate le altre regole DDL, XML, codice DB o log della Slice 21;
- non implementato il consolidamento batch/auto-policy della Slice 22;
- non implementati Excel/OOXML, temporalita', DSL schema 2 o GEXF dinamico;
- nessuna opzione `--allow-incomplete` aggiunta: soltanto un futuro percorso schema 2 potra'
  introdurla;
- nessuna mutazione di candidati o decisioni esistenti, nessun username/hostname macchina,
  nessuna unicita' globale su `candidate_id`;
- nessun candidato inferred, ambiguous, conflicted o pending viene auto-confermato dal
  backfill o dalla regola DDL della Slice 20.
