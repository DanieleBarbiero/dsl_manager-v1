# Report Slice 21

Implementata la Slice 21 end-to-end, solo nello scope richiesto. Stato finale:
**completata**.

Gli output strutturati e persistiti dei parser DDL, XML form, codice database e log sono
trasformati in batch di candidati deterministici, reviewable e pending tramite l'importer
comune della Slice 20. Il percorso non invoca AI o rete e non scrive direttamente fatti o
relazioni.

## Aggiunto

- catalogo tecnico versionato completato con `ddl_column_fact/1`, `ddl_fk_relation/1`,
  `xml_form_structure/1`, `xml_table_usage/1`, `db_code_unit/1`,
  `db_code_dependency/1` e `log_event_observation/1`;
- contratto dichiarativo per ogni regola: parser, schema input, tipo candidato, assertion,
  locator completo, policy automatica consentita e stato review predefinito `pending`;
- derivazione pura con ordinamento stabile per revisione/parser/locator, deduplica per
  identita' deterministica e collision detection;
- risoluzione FK soltanto contro frammenti `ddl_table` attivi; target assenti producono
  `derivation_insufficient_evidence`;
- uso XML `reads_from`/`writes_to` soltanto quando il parser distingue esplicitamente
  l'operazione; una table reference priva di operazione produce evidenza insufficiente;
- unita' procedure/funzioni/trigger e dipendenze database `reads_from`, `writes_to` e
  `calls` ricavate esclusivamente dai segnali osservati del parser;
- eventi log come fact osservazionali, sempre pending per default e senza auto-conferma;
- report `result_catalog_v1` con conteggi per `rule/version`, input, prodotti, deduplicati,
  rifiutati, pending e auto-confermati, payload hash e hash semantico stabile;
- rifiuto nel validator comune di placeholder semantici `${...}`, `{{...}}`,
  `REPLACE_*`, `<<...>>`, `PLACEHOLDER`, `TBD` e `TODO`;
- golden unico della matrice delle sette regole sugli output reali dei quattro parser;
- fixture isolate della Slice 21 per FK non risolta e procedura con dipendenza `CALL`.

La CLI pubblica `candidates derive` conserva `ddl_table_fact/1` come default compatibile e
accetta tutte le regole versionate del catalogo. Non sono state aggiunte dipendenze runtime,
migrazioni o API parallele.

## Preflight e controllo anti-drift

Sono stati letti integralmente, prima del codice: `AGENTS.md`, design v02, design v01,
template report, analisi tecnica, contratti manifest, manuale utente, i tre documenti di
supporto candidati e tutti i report Slice 01-20 in ordine numerico. Sono stati inoltre
ispezionati `src/dsl_mngr`, test, fixture, golden, schema/migrazioni reali, parser e help CLI.

Il worktree iniziale era gia' modificato dalla Slice 20 e da una modifica utente:

```text
## main...origin/main
 M .kb/prompt/prompt_slicing_dsl-manager.md
 M src/dsl_mngr/cli/app.py
 M src/dsl_mngr/cli/commands/candidates.py
 M src/dsl_mngr/cli/commands/dsl.py
 M src/dsl_mngr/cli/commands/facts.py
 M src/dsl_mngr/cli/commands/graph.py
 M src/dsl_mngr/core/ai_inbox.py
 M src/dsl_mngr/core/candidate_import.py
 M src/dsl_mngr/core/config.py
 M src/dsl_mngr/core/database.py
 M src/dsl_mngr/core/dsl_diff.py
 M src/dsl_mngr/core/dsl_renderer.py
 M src/dsl_mngr/core/graph_export.py
 M src/dsl_mngr/core/merge.py
 M src/dsl_mngr/core/migrations.py
 M src/dsl_mngr/core/runs.py
 M tests/test_slice_01_workspace_config_logging.py
 M tests/test_slice_06_fact_merge.py
 M tests/test_slice_07_dsl_render.py
 M tests/test_slice_09_golden_pipeline.py
 M tests/test_slice_13_parse_xml_form.py
 M tests/test_slice_14_parse_db_code_log.py
 M tests/test_slice_16_batch_orchestration.py
 M tests/test_slice_19_local_ui.py
?? .kb/projects/slicing/slice_20/dsl_manager_slice_20_report.md
?? src/dsl_mngr/core/candidate_derivation.py
?? src/dsl_mngr/core/candidate_review.py
?? src/dsl_mngr/core/canonical.py
?? src/dsl_mngr/core/reconciliation.py
?? tests/__init__.py
?? tests/slice_20_test_support.py
?? tests/test_slice_20_candidate_review.py
?? tests/test_slice_20_migration_and_derivation.py
```

Tutte le modifiche preesistenti non pertinenti sono state preservate. La Slice 21 modifica
necessariamente il modulo di derivazione non ancora tracciato della Slice 20 e adegua una
sola sua asserzione di catalogo; il resto dei file Slice 20 non e' stato riscritto.

Classificazione del gate dipendenze:

| Precondizione | Evidenza osservata | Esito |
|---|---|---|
| importer comune | `import_candidate_file` accetta origine `deterministic_derivation` | pronta |
| review e lineage | `CandidateReviewService`, head, lineage e viste v7 presenti | pronta |
| identita' batch | `candidate_record_id` globale; `candidate_id` ripetibile tra batch | pronta |
| parser Slice 12-14 | frammenti strutturati con metadata e locator persistiti | pronta |
| schema/migrazioni | v7 sufficiente per derivazioni e review | pronta; nessuna migrazione necessaria |
| catalogo derivazione | presente la sola regola `ddl_table_fact/1` | gap atteso non bloccante, proprietario Slice 21 |
| placeholder semantici | il validator accettava i template `REPLACE_*` | gap atteso non bloccante, proprietario Slice 21 |
| orchestratore batch | disponibile ma assegnato alla Slice 22 | fuori scope, non modificato |

Non sono emersi conflitti normativi o dipendenze bloccanti.

## Contratto e comportamento delle regole

| Regola | Input persistito | Candidato/assertion | Locator | Policy consentita e default |
|---|---|---|---|---|
| `ddl_column_fact/1` | `ddl_column`: tabella, colonna, tipo | fact `database_column`, explicit | revisione + fragment + path + righe | `explicit_ddl_column_only/1`; pending |
| `ddl_fk_relation/1` | `ddl_constraint` FK con target `ddl_table` attivo | relation `references`, explicit | completo | `explicit_resolved_ddl_fk_only/1`; pending |
| `xml_form_structure/1` | `xml_form`, `xml_field`, `xml_button` | fact tecnici, explicit | completo | `explicit_xml_form_structure_only/1`; pending |
| `xml_table_usage/1` | relazione XML con operazione distinta | relation `reads_from`/`writes_to`, explicit | completo | `explicit_xml_operation_only/1`; pending |
| `db_code_unit/1` | `sql_procedure`, `sql_function`, `sql_trigger` | fact `database_code_unit`, explicit | completo | `explicit_db_code_unit_only/1`; pending |
| `db_code_dependency/1` | liste parser `reads`, `writes`, `calls` | relation tecnica, observed | completo | `observed_db_code_dependency_only/1`; pending |
| `log_event_observation/1` | `log_event` parsato | fact `log_event`, observed | completo | `named_explicit_log_policy_required/1`; pending |

Il parser DB corrente persiste procedure e trigger; il supporto alla forma `sql_function`
e' contrattuale e provato in isolamento senza attribuire semantica di dominio. Parametri di
procedura e pseudo-record `NEW`/`OLD` non sono promossi a dipendenze database. I nomi sono
usati solo come identificatori tecnici espliciti, mai per inferire concetti di dominio.

Conteggi della matrice golden su fixture parser correnti:

| Rule/version | Input pertinenti | Prodotti | Ragioni stabili |
|---|---:|---:|---:|
| `ddl_column_fact/1` | 12 | 12 | 0 |
| `ddl_fk_relation/1` | 5 constraint (2 FK) | 2 | 0 |
| `xml_form_structure/1` | 5 | 5 | 0 |
| `xml_table_usage/1` | 1 | 1 | 0 |
| `db_code_unit/1` | 2 | 2 | 0 |
| `db_code_dependency/1` | 2 | 6 | 0 |
| `log_event_observation/1` | 4 | 4 | 0 |

La fixture FK non risolta produce zero candidati e una ragione
`derivation_insufficient_evidence`, identica su due run.

## File della Slice

File runtime modificati:

```text
src/dsl_mngr/core/candidate_derivation.py
src/dsl_mngr/core/candidate_validation.py
src/dsl_mngr/cli/app.py
```

Compatibilita' test adeguata al nuovo contratto:

```text
tests/test_slice_15_ai_package.py
tests/test_slice_20_migration_and_derivation.py
```

Nuovi test, golden e fixture:

```text
tests/test_slice_21_deterministic_derivation.py
tests/expected/expected_slice_21_rule_matrix.json
tests/fixtures/slice_21/schema_fk_unresolved.sql
tests/fixtures/slice_21/procedura_dipendenze.sql
```

Artifact documentale:

```text
.kb/projects/slicing/slice_21/dsl_manager_slice_21_report.md
```

## Tracciabilita' Slice 21

| Requisito sezione 17 | Implementazione finale | Test/esito finale |
|---|---|---|
| regole DDL/XML/code/log | catalogo e produttori in `candidate_derivation.py`; importer comune; golden parser | `test_slice_21_rule_matrix` - passed |
| placeholder proibiti | controllo ricorsivo dei soli campi semantici nel validator comune | `test_slice_21_unresolved_template_rejected` - passed |

Coperture obbligatorie aggiuntive nello stesso modulo:

- golden per ciascuna delle sette regole e per i parser DDL/XML/DB code/log;
- FK risolta e non risolta, con ragione stabile su due run;
- XML read/write espliciti e table reference ambigua;
- procedure, funzione, trigger e dipendenze read/write/call;
- log osservazionali pending, nessuna review head e zero auto-conferme;
- locator mancante e metadata incompleto come evidenza insufficiente;
- placeholder comuni ed equivalenti respinti prima dell'import;
- stessi `candidate_id` e payload hash in batch distinti, ma `candidate_record_id` distinti;
- input invertito e duplicato con output ordinato/deduplicato identico;
- due run con payload, candidate ID, payload hash e hash semantico del report identici;
- monkeypatch di accessi rete e ispezione runtime: nessuna chiamata rete/AI;
- conteggio invariato di `facts` e `relations` durante tutte le derivazioni.

## Diff/status

Il worktree globale continua a includere le modifiche preesistenti della Slice 20 elencate
nel preflight. Il perimetro Slice 21 e' circoscritto ai dieci file elencati sopra; nessuna
modifica e' entrata in migrazioni, orchestratore batch, merge, renderer o parser.

Dimensione dei principali file nuovi/correnti al termine del codice:

```text
src/dsl_mngr/core/candidate_derivation.py                    984 righe
tests/test_slice_21_deterministic_derivation.py              446 righe
tests/expected/expected_slice_21_rule_matrix.json             48 righe
tests/fixtures/slice_21/                                      13 righe
```

`git diff --check` ha restituito exit 0; sono presenti soltanto warning informativi LF/CRLF
su file gia' nel worktree Windows.

## Test

Interprete usato per installazione, comandi e test:
`.venv/Scripts/python.exe` / Python `3.12.10`.

Install editable eseguita prima del codice:

```powershell
.venv/Scripts/python.exe -m pip install -e ".[dev]"
```

Risultato: exit 0, package `dsl_mngr==0.1.0` installato editable e dipendenze dev
soddisfatte.

Baseline mirata pre-modifica:

```powershell
.venv/Scripts/python.exe -m pytest tests/test_slice_05_candidate_validation.py tests/test_slice_12_parse_ddl.py tests/test_slice_13_parse_xml_form.py tests/test_slice_14_parse_db_code_log.py tests/test_slice_20_candidate_review.py tests/test_slice_20_migration_and_derivation.py -q
```

```text
28 passed in 87.55s
```

Test mirati finali Slice 21:

```powershell
.venv/Scripts/python.exe -m pytest tests/test_slice_21_deterministic_derivation.py -q
```

```text
5 passed in 6.23s
```

Regressione mirata estesa:

```powershell
.venv/Scripts/python.exe -m pytest tests/test_slice_05_candidate_validation.py tests/test_slice_12_parse_ddl.py tests/test_slice_13_parse_xml_form.py tests/test_slice_14_parse_db_code_log.py tests/test_slice_15_ai_package.py tests/test_slice_20_candidate_review.py tests/test_slice_20_migration_and_derivation.py tests/test_slice_21_deterministic_derivation.py -q
```

```text
36 passed in 36.93s
```

Suite completa finale, eseguita dopo l'ultima modifica al codice:

```powershell
.venv/Scripts/python.exe -m pytest
```

```text
91 passed in 120.46s (0:02:00)
```

Nessun test skipped, xfail, interrotto o fallito nel run finale.

### Run intermedi e failure risolte

- `test_slice_20_ddl_table_candidate` ha inizialmente fallito con
  `sqlite3.OperationalError: no such column: sr.parser_kind`: regressione introdotta dalla
  Slice 21 durante l'ordinamento. Corretto usando il parser dichiarato dalla regola e le
  colonne reali dello schema; il test e' poi passato.
- il primo run del golden Slice 21 ha fallito per assenza intenzionale del file expected
  durante la sua costruzione; classificazione: scaffolding test introdotto dalla Slice.
  Il payload osservato e' stato revisionato e salvato nel golden; il test finale passa.
- la prima regressione estesa ha ottenuto `35 passed, 1 failed`: la fixture DB aggiunta nella
  directory condivisa alterava il conteggio storico della Slice 14. Classificazione:
  regressione introdotta dalla Slice. Le fixture sono state spostate nella directory
  isolata `tests/fixtures/slice_21`; il rerun ha ottenuto 36 passed.
- `python -m ruff` non era eseguibile (`No module named ruff`): limite ambiente, non test e
  tool non dichiarato negli extra dev. Verifiche alternative eseguite con `py_compile`,
  parsing AST, `git diff --check`, test mirati e suite completa; nessun impatto sulla DoD.

## Verifiche aggiuntive

- `dsl-manager candidates derive --help`: exit 0;
- `.venv/Scripts/python.exe -m dsl_mngr candidates derive --help`: exit 0, help equivalente;
- regola sconosciuta su entrambi gli entry point: exit 2, messaggio stabile su stderr,
  nessun traceback;
- AST dei tre file Python principali Slice 21 valido;
- ricerca statica nel runtime di derivazione: nessun client rete/AI, nessun INSERT/UPDATE
  verso `facts` o `relations`, import assoluti da `dsl_mngr`;
- report di due run identico nei campi semantici e hash, escludendo run ID, derivation ID,
  batch ID e path artifact operativi.

## Fuori scope / note

- l'orchestratore batch non e' stato modificato: il consolidamento e' proprietario della
  Slice 22;
- nessuna migrazione nuova: lo schema v7 della Slice 20 e' sufficiente;
- nessuna scrittura diretta di fact/relation, auto-confirm o semantica di dominio da nomi;
- nessun fallback parser, algoritmo, formato o dipendenza aggiuntiva;
- non sono state create sottoslice e non sono state anticipate feature delle Slice 22+;
- i warning LF/CRLF dipendono dal worktree Windows e non rappresentano errori diff;
- le modifiche preesistenti non correlate sono rimaste preservate.

Autoverifica finale: perimetro, non-obiettivi, invarianti, failure mode, compatibilita'
legacy, determinismo, tracciabilita' e Definition of Done risultano soddisfatti.
