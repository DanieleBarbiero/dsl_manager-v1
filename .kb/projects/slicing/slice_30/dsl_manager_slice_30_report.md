# Report Slice 30

Stato reale: **completata**.

La Slice 30 consegna la verticalità richiesta
`plan → list/explain → package`: selezione locale dichiarativa e deterministica,
piano storico append-only, ispezione read-only e package composto dal worker
esistente con esattamente gli item inclusi. Non sono stati introdotti provider,
modelli, endpoint, embeddings, invii di rete o scritture AI dirette in
facts/relations/DSL.

## Controllo anti-drift e precondizioni

Prima delle modifiche sono stati letti `AGENTS.md`, design v02 emendato, design
v01, template, project summary, analisi tecnica, contratti manifest, manuali,
discussione completa sulla Slice 30, materiali sui candidati deterministici e
report Slice 01–29. Un design v03 non è presente. Sono stati ispezionati schema,
migrazioni v1–v10, codice/test pertinenti e help dei comandi AI/candidate.

Il prompt allegato e quello canonico nel repository hanno lo stesso SHA-256:

```text
A4ED4DE1687AAADF9600FD34263604D41FF94018D2C6E3F079AA318C268B6DE4
```

Stato Git iniziale:

```text
## main...origin/main [ahead 1]
```

Il worktree era pulito; non erano presenti modifiche utente da preservare. Il
design v02 emendato assegna formalmente la v11 alla Slice 30 e non esiste una
fonte successiva in conflitto.

| Precondizione | Evidenza osservata | Classificazione |
|---|---|---|
| AI handoff Slice 15 | `core/ai_package.py`, `cli/commands/ai.py`, worker `build_ai_package.py`, test package/stale | pronta |
| candidate/review/lineage Slice 20 | v7, `candidate_records`, `candidate_lineage`, `review_subject_heads`, decisioni append-only | pronta |
| derivazione Slice 21 | catalogo regole versionate DDL/XML/DB code/log/Excel e batch `deterministic_derivation` | pronta |
| batch Slice 22 | package-batch e consolidamento correnti | pronta; percorso legacy da preservare |
| Excel Slice 23–25 | fragment `excel_region`, manifest e regole Excel versionate | pronta |
| temporalità Slice 26–27 | v9/v10 e candidati temporali | pronta; non modificata dalla selezione |
| documentazione Slice 29 | contratti e manuali presenti | pronta, aggiornata allo stato Slice 30 |
| budget GEXF | gap già documentato dalla Slice 29 | gap non bloccante, fuori scope |
| `result_catalog_v1` uniforme | gap già documentato dalla Slice 29 | gap non bloccante, fuori scope |

Matrice iniziale dato → registry → decisione:

| Dato richiesto | Fonte corrente | Gap | Decisione Slice 30 |
|---|---|---|---|
| tipo/subtipo/autorità/status fonte | `sources` | nessuno | lettura diretta |
| revisione/hash/path/status/corrente | `source_revisions`, `sources.current_revision_id` | nessuno | scope esplicito o tutto l'inventario registrato |
| chunk/status/testo/hash/ordine | `chunks` | producer nei metadata | `chunker`/`chunker_version` da `metadata_json` |
| fragment/type/locator/status/hash/ordine | `source_fragments` | producer nei metadata | `parser`/`parser_version` da `metadata_json` |
| regole applicabili | `ALL_DERIVATION_RULE_CATALOG` | nessuno | matching dichiarato su `input_fragment_type` |
| candidati deterministici | batch origin + candidate row/payload | nessuno | solo origin `deterministic_derivation` pertinente |
| foglia e testa corrente | lineage + review heads/decisions | nessuno | pending/confirmed/rejected/superseded distinti |
| piani storici | assente fino alla v10 | gap assegnato | migrazione append-only v11 |
| package→piano | assente fino alla v10 | gap assegnato | FK nullable, nessun backfill legacy |

## Implementazione

### Motore e persistenza

- Aggiunto `dsl_mngr.core.ai_selection`, servizio condiviso da preview e
  packaging.
- Il motore carica policy locali sotto `configs/ai_selection/`, con nome
  validato, risoluzione confinata alla directory, parser YAML minimale già
  esistente e rifiuto strict di sezioni/chiavi/valori sconosciuti.
- L'inventario conserva inclusi ed esclusi senza copiare il testo nel database,
  nei log o nel report del piano.
- Provenienza chunk: `chunker`/`chunker_version`; provenienza fragment:
  `parser`/`parser_version`. JSON invalido produce
  `invalid_evidence_metadata`, non un'assunzione.
- La copertura distingue `no_rule_applicable`, `applicable_no_candidate`,
  `pending`, `confirmed`, `rejected` e `superseded_non_leaf`. Solo una foglia
  con testa corrente `confirmed` è copertura positiva.
- Ranking basato esclusivamente sulle preferenze ordinate della policy; tie-break
  finale `(source_revision_id, evidence_kind, sequence, evidence_id)`.
- Budget default: 100.000 esaminati, 10.000 selezionati e 10.000.000 caratteri;
  hard maximum: 1.000.000, 100.000 e 100.000.000. Il primo fallisce prima di
  creare una run/piano; gli altri producono esclusioni ordinate.
- Il conteggio caratteri è `len` del testo dopo CRLF/CR→LF, limitato per singola
  evidenza da `ai_package.max_evidence_chars`; coincide quindi col massimo testo
  destinabile a `content.md`.

### Migrazione v11

`create_ai_evidence_selection_schema` aggiunge:

- `ai_evidence_selection_plans`: run, policy/route/profile versionati, config e
  state hash, scope/config/state canonici, contatori, reason summary, report e
  stato completed;
- `ai_evidence_selection_items`: evidence kind/ID/revisione/sequence,
  included|excluded, rank, caratteri, coverage, reason, criteri matched,
  riferimenti e sort key;
- `ai_packages.selection_plan_id` nullable con FK e indice;
- indici di outcome/rank e trigger che impediscono update/delete di piani/item.

Gli ID usano `AISEL_<NNNNNN>`. Il test esegue un upgrade reale v10→v11,
idempotenza, rollback di una v11 artificialmente fallita e assenza di tabella/FK
parziale dopo rollback. Le aspettative storiche dei test v9/v10 sono state
aggiornate per includere la nuova migrazione successiva, senza cambiare le
migrazioni v1–v10.

### CLI e policy

Comandi aggiunti:

```text
dsl-manager ai evidence plan <workspace> --policy NAME [--revision REV]... [--profile PROFILE]
dsl-manager ai evidence list <workspace> --plan AISEL_ID [--outcome included|excluded]
dsl-manager ai evidence explain <workspace> --plan AISEL_ID <evidence_id>
dsl-manager ai package <workspace> --selection-policy NAME [--revision REV]... [--profile PROFILE]
dsl-manager ai package <workspace> --selection-plan AISEL_ID [--profile PROFILE]
```

`plan` crea una run `ai_evidence_selection`, record/item e
`selection_plan_report.json`, ma nessun `AIPKG_*` o `ai_packages`. `list` e
`explain` leggono soltanto lo snapshot persistito. Gli ID mancanti/ambigui e gli
errori previsti sono mostrati su stderr senza traceback.

Il workspace iniziale contiene due policy versionate:

- `technical_extraction/1`: frammenti tecnici con locator completo; esclude
  coverage `confirmed`;
- `domain_interpretation/1`: chunk e frammenti; conserva anche evidence già
  coperta per consentire una route interpretativa diversa.

Le liste vuote significano esplicitamente `no_restriction`. Policy e profilo
restano configurazioni separate. Un profilo che disabilita un evidence kind
ammesso o non coincide col profilo snapshot produce
`selection_profile_conflict`.

Catalogo reason v1 per item:

```text
included_by_policy
not_current_revision
inactive_source
inactive_evidence
invalid_evidence_metadata
evidence_kind_excluded
source_type_excluded
source_subtype_excluded
extension_excluded
authority_level_excluded
fragment_type_excluded
producer_excluded
producer_version_excluded
incomplete_locator
deterministic_coverage_excluded
coverage_state_excluded
lower_rank
selection_item_budget_exceeded
selection_char_budget_exceeded
```

Reason operative catalogate: `selection_plan_stale`,
`no_ai_eligible_evidence`, `invalid_selection_policy` e
`selection_profile_conflict`.

### Hash, snapshot e stale detection

Tutti gli hash nuovi usano `canonical_json_v1`/`canonical_sha256_v1`.

```text
resolved_config_hash
  = hash(policy risolta + profilo risolto + semantica caratteri/reason)

relevant_state_hash
  = hash(scope + fonti/revisioni + status/hash/metadata/locator evidence
         + regole applicabili + candidati deterministici pertinenti
         + lineage + sole teste review osservate)

selection_plan_hash
  = hash(route/policy/profile versionati + config risolta + scope
         + proiezione ordinata di tutti gli item
         + relevant_state_hash)
```

`selection_plan_hash` esclude selection plan/run/package ID, timestamp, report e
path operativi. La proiezione include outcome, rank, reason, matched criteria,
coverage, sort key e conteggio package. Due piani sullo stesso stato hanno hash
e proiezione semantica uguali pur avendo ID/run differenti.

Prima del package lo stato rilevante viene ricalcolato senza modificare il
piano. Cambi di revisione, evidence status/hash/metadata/locator, regola
applicabile, candidate/lineage o review head producono
`selection_plan_stale`, exit code 4 e nessun outbox.

### Rafforzamento del packager esistente

Non esiste un secondo packager. `prepare_ai_package_input` accetta in modo
additivo lo snapshot risolto; `cli/commands/ai.py` orchestra stale check e
worker; `workers/build_ai_package.py` continua a renderizzare istruzioni,
contenuto, schema, template e manifest con gli helper di `core/ai_package.py`.

Il worker resta senza accesso SQLite e riceve `evidence_order` più il piano già
risolto. Il package policy-driven aggiunge `selection_plan.json`, incluso nella
mappa file e nel `package_hash`. I due manifest contengono
`selection_plan_id/hash`, `policy_id/version`, `route_id/version`,
`config_hash`, `relevant_state_hash`, contatori, reason summary e ordine. La
persistenza ricontrolla artifact, manifest, hash e record di piano prima della
FK package→piano. Un failure rimuove esclusivamente la directory outbox esatta
del package policy-driven rimasta incompleta.

Senza le nuove opzioni, il ramo legacy non riceve `evidence_order`,
`selection_plan.json` o metadata selection. I file, filtri revision/profile,
manifest, rendering e `package-batch` restano quelli della Slice 15/16.

## Matrice route/policy/evidenza

| Route/policy | Evidenza | Coverage osservata | Rank | Outcome/reason | Test |
|---|---|---|---:|---|---|
| `technical_extraction/1` | chunk documentale | `no_rule_applicable` | — | excluded / `evidence_kind_excluded` | `test_plan_is_persisted_deterministic_explainable_and_policy_specific` |
| `domain_interpretation/1` | stesso chunk | `no_rule_applicable` | 1 | included / `included_by_policy` | stesso test, terzo piano |
| `technical_extraction/1` | DDL senza candidate | `applicable_no_candidate` | 1 | included / `included_by_policy` | stesso test |
| `technical_extraction/1` | DDL candidate pending | `pending` | 1 | included / `included_by_policy` | `test_coverage_heads_and_budgets_change_declared_outcomes` |
| `technical_extraction/1` | DDL current confirmed | `confirmed` | — | excluded / `deterministic_coverage_excluded` | stesso test |
| `technical_extraction/1` | DDL current rejected | `rejected` | 1 | included / `included_by_policy` | stesso test |
| `technical_extraction/1` | DDL root non-leaf + replacement pending | `superseded_non_leaf` | 1 | included / `included_by_policy` | stesso test |
| `domain_interpretation/1` | DDL/XML/DB code/log/Excel | regola applicabile, nessun candidate | deterministico | included / producer/version matched | `test_registry_provenance_for_supported_fragment_producers` |
| policy `limited/1` | secondo item eleggibile | pertinente | — | excluded / `lower_rank`, `selection_item_budget_exceeded` | test coverage/budget |

## Tracciabilità requisito → file/test → esito

| Requisito | Implementazione | Test/verifica | Esito |
|---|---|---|---|
| policy/route locali versionate e safe | `workspace.py`, `ai_selection.load_selection_policy` | unsafe path, unknown key/value | completato |
| criteri registry/provenance/locator/status | `ai_selection._load_evidence`, `_eligibility` | fixture chunk + DDL/XML/DB/log/Excel | completato |
| coverage completa | `_load_coverage` | no rule/no candidate/pending/confirmed/rejected/non-leaf | completato |
| ranking/tie-break dichiarati | `_ranking_key`, sort key persistita | determinismo due piani, ordine canonico | completato |
| budget e char accounting | config + `_select_items` | hard examined, item budget, newline/cap nei dati persistiti | completato |
| plan senza package | `create_selection_plan` | zero record/package/outbox dopo plan | completato |
| list/explain read-only | query v11 | run count invariato, output storico | completato |
| package esatto dal piano | `prepare_selection_package`, packager/worker esistenti | content/ordine/contatori/FK/hash | completato |
| package da policy | orchestrazione CLI | piano creato + package con relativo ID | completato |
| stale fail-closed | relevant state recompute | status evidence e review head cambiati | completato |
| zero inclusi/profile conflict/failure atomic | errori catalogati + cleanup mirato | exit 4/2, nessun `ai_packages`/outbox | completato |
| v10→v11, idempotenza, rollback | `migrations.py` | test migrazione reale e failing migration | completato |
| compatibilità package/batch legacy | ramo opzionale assente per default | Slice 15/16 mirati e suite completa | completato |
| entry point/help/stdout/stderr | parser e handler CLI | modulo/console help identici, exit 0 | completato |
| nessuna rete/AI reale | nessun client runtime | monkeypatch socket/urllib + ricerca statica | completato |

## File modificati

Runtime e test:

```text
src/dsl_mngr/core/ai_selection.py                         nuovo
src/dsl_mngr/core/ai_package.py                           estensione additiva
src/dsl_mngr/core/migrations.py                           migrazione v11
src/dsl_mngr/core/config.py                               budget/hard maxima
src/dsl_mngr/core/workspace.py                            directory e due policy
src/dsl_mngr/core/runs.py                                 nuovo run type
src/dsl_mngr/cli/app.py                                   parser CLI
src/dsl_mngr/cli/commands/ai.py                           orchestration/handler
src/dsl_mngr/workers/build_ai_package.py                  artifact/manifest selection
tests/test_slice_30_ai_evidence_selection.py              nuovo
tests/test_slice_26_temporal_core.py                      aspettativa MIGRATIONS +v11
tests/test_slice_27_evidence_concordance.py               aspettativa MIGRATIONS +v11
```

Documentazione aggiornata:

```text
.kb/documenti/project_summary.md
.kb/documenti/documenti tecnici/analisi_tecnica_dsl_manager.md
.kb/documenti/documenti tecnici/contratti_manifest_dsl_manager.md
.kb/documenti/manuali/manuale_utente_dsl_manager.md
.kb/documenti/manuali/outline_dsl_manager_flow_from_input_to_output_riassunto.md
.kb/projects/slicing/slice_30/dsl_manager_slice_30_report.md
```

Prima del report, `git diff --stat` sui file già tracciati riportava:

```text
15 files changed, 786 insertions(+), 91 deletions(-)
```

I due file nuovi non tracciati contavano 1.498 righe core e 689 righe test. Il
report è anch'esso nuovo e quindi non compare nello stat Git standard finché non
viene aggiunto all'indice.

Stato Git finale (nessun commit creato):

```text
## main...origin/main [ahead 1]
 M ".kb/documenti/documenti tecnici/analisi_tecnica_dsl_manager.md"
 M ".kb/documenti/documenti tecnici/contratti_manifest_dsl_manager.md"
 M .kb/documenti/manuali/manuale_utente_dsl_manager.md
 M .kb/documenti/manuali/outline_dsl_manager_flow_from_input_to_output_riassunto.md
 M .kb/documenti/project_summary.md
 M src/dsl_mngr/cli/app.py
 M src/dsl_mngr/cli/commands/ai.py
 M src/dsl_mngr/core/ai_package.py
 M src/dsl_mngr/core/config.py
 M src/dsl_mngr/core/migrations.py
 M src/dsl_mngr/core/runs.py
 M src/dsl_mngr/core/workspace.py
 M src/dsl_mngr/workers/build_ai_package.py
 M tests/test_slice_26_temporal_core.py
 M tests/test_slice_27_evidence_concordance.py
?? .kb/projects/slicing/slice_30/dsl_manager_slice_30_report.md
?? src/dsl_mngr/core/ai_selection.py
?? tests/test_slice_30_ai_evidence_selection.py
```

## Test e verifiche

Interprete determinato esclusivamente da `.codex/config.toml` secondo
`AGENTS.md`: `.venv\Scripts\python.exe`, Python `3.12.10`.

Installazione editable prima delle modifiche:

```powershell
& '.\.venv\Scripts\python.exe' -m pip install -e '.[dev]'
```

Esito: exit 0, `dsl_mngr 1.1.0` installato editable.

Baseline mirata prima delle modifiche:

```powershell
& '.\.venv\Scripts\python.exe' -m pytest -q tests\test_slice_15_ai_package.py tests\test_slice_20_candidate_review.py tests\test_slice_20_migration_and_derivation.py tests\test_slice_21_deterministic_derivation.py
```

Esito: `21 passed in 42.34s`, exit 0.

Regressione finale Slice 15/16/20/21 + Slice 30:

```powershell
& '.\.venv\Scripts\python.exe' -m pytest -q tests/test_slice_15_ai_package.py tests/test_slice_16_batch_orchestration.py tests/test_slice_20_candidate_review.py tests/test_slice_20_migration_and_derivation.py tests/test_slice_21_deterministic_derivation.py tests/test_slice_30_ai_evidence_selection.py
```

Esito: `33 passed in 63.73s`, exit 0.

Test Slice 30 finale, inclusa interdizione rete:

```powershell
& '.\.venv\Scripts\python.exe' -m pytest -q tests/test_slice_30_ai_evidence_selection.py
```

Esito: `9 passed in 5.95s`, exit 0.

Verifica finale test documentali Slice 29 e verticalità Slice 30, dopo la
creazione del presente report canonico:

```powershell
& '.\.venv\Scripts\python.exe' -m pytest -q tests/test_slice_29_documentation.py tests/test_slice_30_ai_evidence_selection.py
```

Esito: `15 passed in 5.30s`, exit 0.

Suite completa finale:

```powershell
& '.\.venv\Scripts\python.exe' -m pytest
```

Esito: **`193 passed in 315.83s (0:05:15)`**, exit 0; nessun skipped,
xfailed o warning pytest.

Verifica help per entrambi gli entry point:

```text
ai evidence --help
ai evidence plan --help
ai evidence list --help
ai evidence explain --help
ai package --help
ai package-batch --help
ai inbox scan --help
candidates derive --help
candidates review --help
```

Per ogni comando `python -m dsl_mngr` e `dsl-manager.exe` hanno restituito exit
0 e output identico.

`git diff --check`: exit 0, nessun whitespace error; presenti soltanto warning
informativi LF→CRLF di Git per il worktree Windows. La ricerca statica sui tre
moduli selection/package/worker non trova client o URL di rete.

### Esecuzioni fallite e classificazione

Il primo run completo dopo l'implementazione ha prodotto:

```text
3 failed, 189 passed in 1114.27s (0:18:34)
```

- Due failure attendevano ancora che `MIGRATIONS` terminasse a v10
  (`[9,10]` e `[10]`). Classificazione: **introdotte dalla Slice 30 nei test
  storici**, non errore della migrazione; le sole aspettative sono state
  aggiornate a `[9,10,11]` e `[10,11]`, con skipped count 11.
- Una failure Aurora era `PermissionError [WinError 5]` durante `os.replace` di
  un artifact di worker. Classificazione: **lock Windows transitorio
  preesistente/ambientale**, già documentato storicamente, fuori dal runtime
  Slice 30. Il rerun isolato dei tre casi ha dato `3 passed in 52.73s`.

Dopo le correzioni, una suite completa ha dato `192 passed in 343.74s`; dopo
l'aggiunta del test esplicito no-network, il run finale da 193 test è verde come
riportato sopra. Nessuna failure resta aperta.

## Compatibilità, failure mode e fuori scope

- `--selection-policy` e `--selection-plan` sono mutuamente esclusivi;
  `--revision` non può alterare lo scope di un piano esistente.
- Un piano con zero inclusi resta uno snapshot completo e valido, ma il package
  termina non-zero e non viene pubblicato.
- Un piano storico non viene aggiornato per superare stale o profile conflict;
  `list`/`explain` continuano a mostrarlo.
- Package legacy e package-batch non acquisiscono nuove semantiche né nuovi file.
- Nessuna nuova dipendenza runtime, ORM, servizio, server o parser YAML.
- Nessuna modifica a facts, relations, decisioni, viste effettive, DSL o
  temporalità da parte del motore.
- Provider AI, selezione modello/endpoint, invio package, vector DB,
  classificazione probabilistica, scheduler e UI selection restano fuori scope.
- I gap GEXF budget e result catalog della Slice 29 restano documentati e non
  sono stati usati come pretesto per refactor laterali.

## Autoverifica finale

- Scope: sola verticalità Slice 30 e aggiornamenti minimi di compatibilità/docs.
- Determinismo: stessa config/stato produce stesso ordine e selection plan hash.
- Auditabilità: tutti gli item hanno outcome, reason, criteri e coverage
  persistiti; nessun testo lungo nel piano DB/report.
- Immutabilità: trigger append-only e stale check senza rewrite.
- Sicurezza/privacy: path policy confinati, hard budget fail-closed, path
  artifact relativi, nessuna rete o AI reale.
- Packaging: worker esistente DB-isolato, selezione risolta dall'orchestratore,
  artifact e hash ricostruibili.
- Compatibilità: percorsi Slice 15/16 verdi senza opt-in.
- Definition of Done: migrazione, CLI, policy, artifact, test, documentazione e
  report presenti; suite completa verde.
