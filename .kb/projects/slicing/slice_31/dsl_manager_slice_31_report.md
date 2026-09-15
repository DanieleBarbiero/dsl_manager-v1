# Report Slice 31

Stato reale: **completata**.

Attività post-slice: **completate**. La documentazione corrente e il
laboratorio Orione sono allineati ai comandi installati; prompt, report e altre
fonti storiche non sono stati riscritti.

La Slice 31 elimina i tre workaround esterni individuati nel laboratorio
Orione: configurazione dell'allowlist review, propagazione temporale e prova
controllata dello stato `partial` sono ora verticali pubbliche del DSL Manager.
La correzione multi-supporto è nel core e viene consumata da review, merge,
reconciliation, DSL v2, diff e GEXF. Nessuna delle quattro capacità resta
delegata a script del laboratorio.

## Preflight, anti-drift e piano file-per-file

Prima delle modifiche sono stati letti il prompt Slice 31 allegato, `AGENTS.md`,
configurazione Codex, template, project summary, design v01/v02, analisi
tecnica, contratti manifest, manuali, documento di modifica prompt, tutti i
prompt/report Slice 01-30 e i materiali canonici del laboratorio Orione. La
directory `.wb` non è stata consultata.

Stato Git iniziale:

```text
## main...origin/main
```

Il worktree era pulito; non esistevano modifiche utente preesistenti da
preservare o distinguere. Non è stato creato alcun commit.

Il piano dichiarato prima delle patch sostanziali è stato applicato in questo
ordine:

1. `migrations.py`, `temporal.py`, `temporal_consolidation.py`, merge/review/
   reconciliation: v12 e autorità multi-supporto;
2. `review_config.py`, risorsa profilo, `config.py` e handler/parser CLI:
   governance pubblica della configurazione;
3. handler temporal CLI e lifecycle run: propagazione pubblica;
4. worker diagnostico, orchestratore e stato `partial`: scenario controllato;
5. renderer DSL/diff/GEXF: provenienza completa e deterministica;
6. test Slice 31, aspettative storiche di migrazione e golden toccati dal nuovo
   contratto additivo;
7. soltanto dopo installazione, test mirati, suite completa e smoke: questo
   report.

## Implementazione

### Migrazione v12 e invariante multi-supporto

La migrazione append-only `create_temporal_interval_supports` aggiunge:

```text
temporal_interval_supports
  support_id               PK
  interval_id              FK temporal_intervals
  candidate_record_id      FK temporal_candidate_details, UNIQUE
  decision_id              FK review_decisions
  created_at
  UNIQUE(interval_id, candidate_record_id)
```

Sono presenti indice per intervallo e trigger `no_update`/`no_delete`. Il runner
v12 esegue un backfill ordinato da ogni coppia legacy
`temporal_intervals.source_candidate_record_id/decision_id`. Le colonne legacy
restano intatte per compatibilità; nessun record storico viene riscritto.
Applicazione, backfill e registrazione in `schema_migrations` condividono la
stessa transazione. I test coprono upgrade v11→v12 con dati, replay idempotente,
trigger append-only e rollback di una v12 artificialmente fallita.

L'effettività di un intervallo è ora:

```text
esiste almeno un supporto
  il cui candidate è foglia corrente
  e la cui review head corrente è confirmed
```

La conferma di un candidate semanticamente equivalente riusa lo stesso
`temporal_intervals.interval_id` e aggiunge un nuovo supporto. Invalidare un
supporto non cancella storia; l'intervallo resta visibile finché un altro
supporto è effettivo e scompare quando non ne resta nessuno. Merge e
reconciliation verificano la relation v12, non la colonna singolare legacy.

DSL v2 espone sempre `supports`, ordinati per intervallo/candidate, con
`support_id`, candidate ID, decisione di materializzazione, decisione corrente
e review. La trace temporale, il diff e il GEXF dinamico riportano gli stessi
identificatori. Il contratto è additivo: i campi temporali precedenti e le
colonne legacy restano disponibili.

### CLI temporale pubblica

Sintassi canonica scelta:

```text
dsl-manager temporal propagate WORKSPACE \
  --source-revision-id REV_ID \
  --target-subject-type fact|relation \
  --target-subject-id SUBJECT_ID \
  --source-subject TYPE:ID [--source-subject TYPE:ID ...] \
  --policy explicit_copy|intersection|aggregation|conflict
```

Non ci sono scostamenti semantici dal prompt. `--source-subject` è ripetibile e
obbligatorio; duplicati, tipi non supportati, ID mancanti, revisione assente,
target invalido e policy invalida falliscono prima di evidence/candidate. La
CLI crea una run `temporal_propagation`, delega l'algoritmo al servizio core,
registra input/output/log/process report e restituisce JSON con candidate e
batch ID. Il JSON stdout dei comandi mutanti include il workspace risolto; gli
artefatti conservano soltanto path workspace-relative.

`explicit_copy`, `intersection` e `aggregation` producono candidati pending.
`conflict` produce un conflitto governato e termina con exit 4.

### Governance pubblica della configurazione review

Sintassi canonica scelta:

```text
dsl-manager config review show WORKSPACE
dsl-manager config review profiles WORKSPACE
dsl-manager config review apply-profile WORKSPACE --profile conservative/1 \
  [--expect-config-hash HASH]
dsl-manager config review set-allowlist WORKSPACE \
  [--policy POLICY ...] [--expect-config-hash HASH]
dsl-manager config validate WORKSPACE [--profile conservative/1]
```

Zero occorrenze di `--policy` sostituiscono l'allowlist con `[]`; l'help lo
dichiara esplicitamente. `--expect-config-hash` è l'estensione motivata per il
controllo lost-update richiesto. L'updater modifica soltanto
`review.automatic_policies`, conserva commenti/chiavi/sezioni estranei, scrive
UTF-8 con file temporaneo nello stesso directory e `os.replace`, e non riscrive
un no-op. La validazione prospettica avviene prima del replace.

`show` espone valore effettivo, origine, ordine canonico, hash config e hash
policy. `profiles` espone ID/versione/descrizione/policy/hash. `validate` esegue
le validazioni tipizzate correnti del progetto e controlla esistenza,
duplicati e flag `automatic_review_allowed` delle policy senza mutare il file.
I comandi producono `result_catalog_v1`, campo human-readable `summary` e log
applicativo.

Il profilo built-in è una risorsa package immutabile:

```text
id: conservative/1
hash: 1fc093f7f59056c195aa4b0deb352f96e42dec42fc1b8b29779441b6b81e7eb6
policy count: 13
```

Policy effettive, in ordine canonico:

```text
explicit_ddl_column_only/1
explicit_ddl_table_only/1
explicit_db_code_unit_only/1
explicit_excel_named_range_only/1
explicit_excel_region_only/1
explicit_excel_sheet_only/1
explicit_excel_table_only/1
explicit_excel_workbook_only/1
explicit_resolved_ddl_fk_only/1
explicit_xml_form_structure_only/1
explicit_xml_operation_only/1
named_explicit_log_policy_required/1
observed_db_code_dependency_only/1
```

La lista coincide esattamente con le policy del catalogo Slice 21 il cui
contratto consente auto-review. `explicit_excel_reference_pending/1` e ogni
policy pending/inferred/ambigua/temporale/AI sono escluse. Il default di un
workspace nuovo resta vuoto.

### Diagnostica di normalizzazione controllata

Forma canonica conservata con il leaf `run`, coerente col lifecycle esplicito:

```text
dsl-manager diagnostics normalization run WORKSPACE \
  --revision REV_ID \
  --scenario controlled_partial_success/1
```

Il parser non espone opzioni worker/module/command/path/shell/payload. Il solo
worker selezionabile è quello package-internal
`controlled_partial_normalization`; non accetta path o comando dall'utente.
Il preflight verifica revisione registrata, esistenza, hash, formato e budget.
Per XLSX applica il preflight OOXML e rifiuta external relationship, macro,
VBA/OLE; `.xlsm` e formati non allowlisted sono rifiutati. Il worker non usa
rete, macro, OLE o dereferenziazione esterna.

La run `normalization_diagnostic` e il worker terminano realmente `partial`
con exit 6. Il retry è limitato a un tentativo e il resume è disabilitato. Gli
artefatti specifici vivono sotto:

```text
artifacts/runs/<RUN_ID>/diagnostics/normalization/
```

Lo scaffold standard della run conserva input/output/process report/log nella
root della run. Il payload pubblico elenca soltanto
`controlled_preview.txt` e `diagnostic_report.json` nel namespace diagnostico.
Snapshot prima/dopo provano invariati `normalized_hash`, manifest workbook,
fragment, chunk, candidate, fact e relation; nessun output viene pubblicato in
`normalized/`.

## Exit code osservati

| Percorso | Condizione osservata | Exit |
|---|---|---:|
| install editable | completata | 0 |
| config show/profiles/apply/set/validate | successo | 0 |
| config mutation | `config_hash_mismatch` | 4 |
| config validation | policy sconosciuta/non automatica/duplicata | 2 |
| temporal propagate | candidate pending creati | 0 |
| temporal propagate | conflitto governato | 4 |
| temporal propagate | source duplicata/invalida | 3 |
| diagnostics normalization | `controlled_partial_success/1` | 6 |
| worker diagnostico | stato `partial` | 6 |
| help/version/smoke/pytest finale | successo | 0 |

## Golden aggiornati e compatibilità

I golden non sono stati corretti per mascherare regressioni. Sono cambiati
soltanto dopo aver stabilito il nuovo contratto richiesto: ogni intervallo DSL
v2 e GEXF temporale deve esporre candidate e decision ID anche con un singolo
supporto. Restano invariati contenuti non temporali, DSL v1, conteggi, parser,
normalizzazione, merge e candidate.

Hash Aurora aggiornati in modo deterministico:

```text
DSL v2:  34a1f5b5854aa388d97fd56883de4a7e008a345a7b571aeb60e8e474b856856e
GEXF:    ad615240db527a6924511718314baacaff0282c9dd94cf8fa62cab10c2b12c2d
```

Il test documentale Slice 29 considera i sette nuovi leaf Slice 31 come
estensione esplicita del catalogo runtime. Durante l'applicazione della slice il
manuale non era stato modificato, come richiesto dal prompt; l'allineamento del
manuale corrente è avvenuto soltanto nella fase post-slice richiesta.

## Tracciabilità requisito → test

| Requisito | Test/verifica | Esito |
|---|---|---|
| v12 backfill/idempotenza/rollback/append-only | `test_slice_31_migration_v12_backfills_atomically_and_is_append_only` | completato |
| reuse semantico e più supporti | `test_slice_31_same_interval_has_multiple_effective_supports` | completato |
| uno/all support invalidati | stesso test + reconciliation | completato |
| DSL/diff/GEXF con candidate/decision ID | stesso test + golden Slice 26/27/Aurora | completato |
| CLI temporal e batch ID | `test_slice_31_public_temporal_propagation_and_prevalidation` | completato |
| conflict exit 4 e prevalidation | stesso test | completato |
| profilo/hash/no-op/preserve/lost-update | `test_slice_31_review_profile_preserves_unrelated_yaml_and_is_noop` | completato |
| clear/validate/help/entry parity | `test_slice_31_config_cli_clear_validate_and_entrypoint_parity` | completato |
| policy unknown/pending/duplicate | `test_slice_31_config_rejects_unknown_pending_and_duplicate_policies` | completato |
| partial reale, isolamento e artefatti | `test_slice_31_controlled_partial_diagnostic_is_bounded_and_non_mutating` | completato |

## Smoke E2E e ID dinamici

Nel workspace isolato del test diagnostico, la revisione è stata letta dal
registry e gli ID successivi dal JSON/process report, senza assumerli nel
comando:

```text
source_revision_id: REV_000001
run_id:             RUN_000001
worker_run_id:      WRK_000001
status:             partial
exit_code:          6
```

Nel smoke temporale, gli ID sono stati letti dal JSON e verificati nel DB:

```text
run_id:               RUN_000003
candidate_record_id:  CREC_000006
candidate_batch_id:   CBATCH_000003
exit_code:            0
```

Gli ID sono valori osservati nelle fixture isolate e non costanti usate per
pilotare i nuovi comandi.

## File modificati

Runtime e risorse:

```text
pyproject.toml
src/dsl_mngr/cli/app.py
src/dsl_mngr/cli/commands/candidates.py
src/dsl_mngr/cli/commands/config.py                         nuovo
src/dsl_mngr/cli/commands/diagnostics.py                    nuovo
src/dsl_mngr/cli/commands/temporal.py                       nuovo
src/dsl_mngr/core/candidate_review.py
src/dsl_mngr/core/config.py
src/dsl_mngr/core/dsl_diff.py
src/dsl_mngr/core/dsl_renderer.py
src/dsl_mngr/core/graph_export.py
src/dsl_mngr/core/merge.py
src/dsl_mngr/core/migrations.py
src/dsl_mngr/core/normalization_diagnostics.py              nuovo
src/dsl_mngr/core/reconciliation.py
src/dsl_mngr/core/review_config.py                          nuovo
src/dsl_mngr/core/runs.py
src/dsl_mngr/core/temporal.py
src/dsl_mngr/core/temporal_consolidation.py
src/dsl_mngr/core/worker_runner.py
src/dsl_mngr/resources/review_profiles/__init__.py          nuovo
src/dsl_mngr/resources/review_profiles/conservative_1.json  nuovo
src/dsl_mngr/workers/controlled_partial_normalization.py    nuovo
```

Test e golden:

```text
tests/expected/expected_slice_26_dsl_v2.json
tests/expected/expected_slice_27_temporal_spells.json
tests/expected/expected_slice_28_aurora_e2e.json
tests/test_slice_26_dsl_v2.py
tests/test_slice_26_temporal_core.py
tests/test_slice_27_evidence_concordance.py
tests/test_slice_29_documentation.py
tests/test_slice_30_ai_evidence_selection.py
tests/test_slice_31_diagnostics.py                         nuovo
tests/test_slice_31_public_governance.py                   nuovo
tests/test_slice_31_temporal_supports.py                   nuovo
.kb/projects/slicing/slice_31/dsl_manager_slice_31_report.md nuovo
```

Nella fase di implementazione non era stato modificato alcun file Orione,
manuale, corpus, design, project summary, prompt o template.

Prima del report, lo stat dei 23 file tracciati era:

```text
23 files changed, 745 insertions(+), 106 deletions(-)
```

Gli undici file nuovi contavano 1.462 righe. Il report è stato creato soltanto
dopo il collaudo e non era incluso in quei conteggi.

File aggiornati nella fase post-slice:

```text
.kb/documenti/project_summary.md
.kb/documenti/documenti di design/run 2/design_document_v_02.md
.kb/documenti/documenti tecnici/analisi_tecnica_dsl_manager.md
.kb/documenti/documenti tecnici/contratti_manifest_dsl_manager.md
.kb/documenti/manuali/manuale_utente_dsl_manager.md
.kb/documenti/manuali/outline_dsl_manager_flow_from_input_to_output_completo.md
.kb/documenti/manuali/outline_dsl_manager_flow_from_input_to_output_riassunto.md
.kb/projects/laboratorio_orione_assistenza/corpus_mock_orione_assistenza/leggimi_prima.md
.kb/projects/laboratorio_orione_assistenza/corpus_mock_orione_assistenza/materiale_di_supporto/checklist_risultati_attesi.md
.kb/projects/laboratorio_orione_assistenza/corpus_mock_orione_assistenza/materiale_di_supporto/diario_tecnico_validazione.md
.kb/projects/laboratorio_orione_assistenza/corpus_mock_orione_assistenza/materiale_di_supporto/guida_dsl_manager_cmd_v_01.md
.kb/projects/laboratorio_orione_assistenza/corpus_mock_orione_assistenza/materiale_di_supporto/guida_dsl_manager_powershell_v_01.md
.kb/projects/laboratorio_orione_assistenza/corpus_mock_orione_assistenza/materiale_di_supporto/laboratorio_orione_assistenza_interattivo_v_01.ps1
.kb/projects/laboratorio_orione_assistenza/corpus_mock_orione_assistenza/materiale_di_supporto/limitazioni_intenzionali.md
.kb/projects/laboratorio_orione_assistenza/corpus_mock_orione_assistenza/materiale_di_supporto/matrice_fixture_attesi.md
tests/test_slice_29_documentation.py
.kb/projects/slicing/slice_31/dsl_manager_slice_31_report.md
```

Il prompt storico Orione continua a referenziare l'adapter temporale originale.
Poiché la richiesta vieta di alterare la documentazione storica, il file è
stato conservato; tutor e guide correnti non lo caricano né lo invocano.

## Test e comandi eseguiti

Interprete determinato esclusivamente da `.codex/config.toml`:
`.venv\Scripts\python.exe`, Python `3.12.10`.

Installazione editable prima delle modifiche:

```powershell
& '.\.venv\Scripts\python.exe' -m pip install -e '.[dev]'
```

Esito: exit 0, `dsl_mngr 1.1.0` installato editable.

Baseline mirata pre-modifica:

```powershell
& '.\.venv\Scripts\python.exe' -m pytest <suite Slice 20/21/23/26/27/30>
```

Esito: `79 passed in 203.76s`, exit 0.

Matrice finale mirata Slice 31 + regressioni critiche:

```powershell
& '.\.venv\Scripts\python.exe' -m pytest \
  tests/test_slice_31_temporal_supports.py \
  tests/test_slice_31_public_governance.py \
  tests/test_slice_31_diagnostics.py \
  tests/test_slice_23_excel_ingest.py::test_slice_23_partial_is_distinct_and_atomic \
  tests/test_slice_28_aurora_e2e.py::test_slice_28_aurora_e2e \
  tests/test_slice_29_documentation.py::test_slice_29_manual_command_catalog_matches_parser
```

Esito: `10 passed in 24.48s`, exit 0.

Verifica finale DSL/diff/GEXF/golden multi-supporto:

```powershell
& '.\.venv\Scripts\python.exe' -m pytest \
  tests/test_slice_26_dsl_v2.py \
  tests/test_slice_26_gexf_offline.py \
  tests/test_slice_27_spells_bounds.py \
  tests/test_slice_28_aurora_e2e.py::test_slice_28_aurora_e2e \
  tests/test_slice_31_temporal_supports.py
```

Esito: `24 passed in 27.53s`, exit 0.

Suite completa definitiva:

```powershell
& '.\.venv\Scripts\python.exe' -m pytest
```

Esito: **`204 passed in 328.17s (0:05:28)`**, exit 0; nessun skipped,
xfailed o warning pytest.

Smoke esplicito:

```powershell
& '.\.venv\Scripts\python.exe' -m pytest tests/test_smoke.py
```

Esito: `1 passed in 0.89s`, exit 0.

Versione dei due entry point:

```text
python -m dsl_mngr: dsl-manager 1.1.0
dsl-manager.exe:     dsl-manager 1.1.0
```

I sette help leaf Slice 31 sono stati eseguiti su entrambi gli entry point:
exit 0 e output identico.

### Verifica post-slice

Installazione editable ripetuta con lo stesso interprete:

```powershell
& '.\.venv\Scripts\python.exe' -m pip install -e '.[dev]'
```

Esito: exit 0.

Test mirati Slice 31 e documentazione aggiornata:

```powershell
& '.\.venv\Scripts\python.exe' -m pytest `
  tests/test_slice_31_temporal_supports.py `
  tests/test_slice_31_public_governance.py `
  tests/test_slice_31_diagnostics.py `
  tests/test_slice_29_documentation.py
```

Esito: **`13 passed in 6.66s`**, exit 0.

Suite completa post-slice:

```powershell
& '.\.venv\Scripts\python.exe' -m pytest
```

Esito: **`204 passed in 333.51s (0:05:33)`**, exit 0.

Smoke esplicito post-slice:

```powershell
& '.\.venv\Scripts\python.exe' -m pytest tests/test_smoke.py
```

Esito: **`1 passed in 0.79s`**, exit 0.

Sono stati confrontati `--help` radice e i sette leaf Slice 31 fra
`python -m dsl_mngr` e `dsl-manager.exe`: 8 confronti, output byte-identico ed
exit 0 per entrambe le entry point.

### Smoke Orione post-slice

È stato creato un workspace nuovo sotto `%TEMP%`; il path assoluto non viene
pubblicato. Comandi e risultati osservati:

| Passaggio | Risultato | Exit |
|---|---|---:|
| `init` / `db init` | workspace nuovo, 12 migrazioni | 0 / 0 |
| `config review show` | allowlist iniziale vuota | 0 |
| `config review profiles` | `conservative/1`, 13 policy, hash `1fc093f7…7eb6` | 0 |
| `config review apply-profile` / `config validate` | 13 policy effettive, configurazione valida | 0 / 0 |
| doppio `corpus scan` | 15 added, poi 15 unchanged | 0 / 0 |
| `batch consolidate --reconcile` | 25 parse, 117 candidati, 86 auto-confirmed, 31 temporali pending, 78 fatti, 8 relazioni | 0 |
| review/merge intervalli sorgente | due correnti e uno storico confermati/materializzati | 0 |
| sei `temporal propagate` | cinque `explicit_copy`, una `aggregation`; sei candidati pending | 0 |
| review/merge candidati propagati | prima 4/4, poi 2/2 | 0 |
| `dsl render --schema-version 2` | `DSL_000003`, 3 fatti e 1 relazione temporali | 0 |
| `graph export --dynamic --timeformat date --temporal-output-mode strict` | 2 spell nodo, 4 spell arco | 0 |
| `diagnostics normalization run` | run/worker partial, stato produzione invariato | 6 |
| `run status` diagnostico | run `normalization_diagnostic` partial | 0 |

I quattro candidati correnti `CREC_000118`–`CREC_000121` e i due storici
`CREC_000122`/`CREC_000123` sono stati osservati nella lista pending prima
della review. Gli intervalli finali erano 2023-01-01/2025-02-28 e
2026-03-01/aperto; DSL v2 conteneva quattro intervalli fact e due relation.
Il GEXF strict ha prodotto 2 `<spell>` di nodo e 4 di arco.

La diagnostica su una revisione `.txt` registrata ha prodotto `RUN_000074`,
`controlled_simulation: true`, exit worker/CLI 6 e i soli artefatti:

```text
artifacts/runs/RUN_000074/diagnostics/normalization/controlled_preview.txt
artifacts/runs/RUN_000074/diagnostics/normalization/diagnostic_report.json
```

Gli hash dello stato di produzione prima e dopo coincidevano.

### Esecuzioni intermedie fallite e classificazione

- Il primo mirato dopo la v12 mostrava cinque failure: due aspettative di
  migrazione ferme a v11, due golden temporali ancora privi di supporti e una
  restrizione core eccessiva sul target/run. Tutte erano introdotte dalla
  Slice 31 e sono state corrette preservando la compatibilità degli internal
  caller.
- La prima suite completa ha dato `202 passed, 2 failed`: un call site GEXF
  interno non aggiornato e il catalogo manuale Slice 29. Il call site è stato
  corretto; il test documentale ora aggiunge esplicitamente i sette leaf senza
  modificare il manuale congelato.
- Dopo il contratto always-additive, un run completo ha dato
  `203 passed, 1 failed`: `PermissionError [WinError 5]` nel preesistente
  `worker_runner._atomic_write_text` durante Slice 15. È un lock Windows
  transitorio già osservato storicamente, non correlato alla Slice 31. Il caso
  isolato è passato (`1 passed in 1.72s`) senza modifica runtime; il run completo
  successivo è il definitivo verde da 204 test.

### Hardening filesystem condiviso post-slice

La classificazione precedente descrive lo stato al termine dell'implementazione
originaria della Slice 31. In un intervento successivo il lock non è stato più
lasciato alla sola mitigazione ambientale: è stata introdotta
`dsl_mngr.core.filesystem`, che centralizza retry e backoff delle operazioni
filesystem soggette ai lock transitori di Windows.

La policy comune esegue al massimo 10 tentativi, con backoff da 0,05 s fino a
0,5 s, esclusivamente per `PermissionError`. Riusa lo stesso file temporaneo,
non intercetta gli altri `OSError`, propaga l'errore dopo l'ultimo tentativo e
permette ai chiamanti di pulire il temporaneo senza mascherare l'errore
principale. Sono stati instradati attraverso la utility condivisa:

- output e file di capture dei worker in `worker_runner`;
- `batch_checkpoint.tmp` → `batch_checkpoint.json` in
  `batch_consolidation`, già colpito storicamente da `WinError 5`;
- pubblicazione da staging, output e report del worker Docling;
- aggiornamento atomico della configurazione review introdotto dalla Slice 31.

La centralizzazione era quindi possibile anche per la Slice 31. Il suo helper
mantiene localmente le garanzie specifiche `mkstemp`, `flush` e `fsync`, mentre
delega alla utility soltanto replace, retry e cleanup: non è stato indebolito il
contratto di durabilità e non è stato introdotto un accoppiamento con
`worker_runner`. Il mini report `.wb/mini_report_docling_windows.md` è stato
consultato come evidenza workbench non canonica del rilascio tardivo degli
handle sul confine di processo Docling; non è una dipendenza del runtime né una
fonte canonica del progetto.

I test deterministici monkeypatchano `os.replace` e `time.sleep` e verificano
tentativi, sequenza del backoff, riuso del temporaneo, contenuto finale, cleanup
e propagazione. Il mirato complessivo ha dato `15 passed in 8.42s`; la suite
completa successiva ha dato `210 passed in 610.23s (0:10:10)`, exit 0.

Nessuna failure resta aperta.

## Diff/status e verifiche tecniche

- `git diff --check`: exit 0, nessun whitespace error; soltanto warning
  informativi LF→CRLF del worktree Windows.
- Decodifica UTF-8 strict: verificata su tutti i file modificati/nuovi.
- Ricerca di path macchina in runtime/test: nessun path assoluto specifico
  trovato.
- Tutti gli artifact path pubblici verificati sono workspace-relative.
- Lo stato iniziale dell'implementazione era pulito. All'ingresso della fase
  post-slice erano presenti le 23 modifiche tracciate e i 12 file nuovi della
  Slice 31, incluso questo report; sono stati preservati e completati senza
  ripristini o sovrascritture.

Verifica post-slice finale:

```text
git diff --stat: 37 file tracciati, 1280 inserimenti, 248 eliminazioni
file modificati o nuovi verificati UTF-8 strict: 49
file nuovi non tracciati: 12
link relativi non risolti nei Markdown modificati/nuovi: 0
path macchina assoluti nei Markdown modificati/nuovi: 0
errori di parsing del tutor PowerShell: 0
git diff --check: exit 0
```

Il controllo esteso di trailing whitespace sull'intero contenuto dei file
toccati rileva il design v02 per spazi finali già presenti nelle righe di
metadata Markdown; `git diff --check` conferma che il diff non introduce nuovi
errori. I warning LF→CRLF sono informativi e coerenti col worktree Windows.

## Limiti residui e post-slice

- Il catalogo built-in contiene soltanto `conservative/1`; profili custom o un
  marketplace di profili non sono parte della Slice 31.
- L'editor preservativo opera sul formato YAML semplice già supportato dal
  progetto; non è stato introdotto un parser YAML general-purpose.
- La diagnostica espone intenzionalmente un solo scenario, un tentativo e
  nessun resume; ampliare scenario/formati richiede una nuova policy/versione.
- I candidati prodotti dalla propagazione restano pending finché i normali
  comandi review non li confermano o rifiutano.
- Le colonne singolari legacy in `temporal_intervals` restano per compatibilità;
  una loro eventuale deprecazione richiede una migrazione futura separata.
- Gli errori dei leaf `config` correnti usano stderr ed exit 2/4 ma non
  restituiscono un envelope JSON `result_catalog_v1` su stdout; i successi sono
  strutturati.
- L'adapter Orione non fa più parte del flusso corrente, ma resta nel repository
  perché il prompt storico immutabile lo referenzia. La rimozione richiederebbe
  prima una decisione esplicita su come preservare quel riferimento storico.

Questi limiti non aggirano le capacità consegnate: configurazione,
propagazione, review esistente e diagnostica partial sono tutte invocabili
direttamente dal DSL Manager pubblico.
