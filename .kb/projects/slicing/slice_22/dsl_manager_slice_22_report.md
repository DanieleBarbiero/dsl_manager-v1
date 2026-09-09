# Report Slice 22

Implementata la Slice 22 end-to-end, solo nello scope richiesto. Stato finale:
**completata**.

Una singola esecuzione `batch consolidate` orchestra scan/parser strutturali, derivazione
deterministica, review automatica autorizzata, merge degli eleggibili e reconcile finale
opzionale. Ogni fase ha checkpoint persistito; crash e retry ripartono dal confine di fase
senza ricreare candidati gia' checkpointati o duplicare supporti effettivi.

## Aggiunto

- orchestratore core con le fasi ordinate `parse -> derive -> review -> merge -> reconcile`;
- comando pubblico `batch consolidate <workspace>` con `--path`, `--strict-review`,
  `--reconcile`, `--stop-on-error` e `--resume RUN_ID`;
- `batch_checkpoint.json` scritto atomicamente dopo ogni transizione e
  `batch_report.json` aggregato nel formato `result_catalog_v1`;
- registrazione di `rule_set_version`, regola/versione, candidate batch e run figlie;
- review automatica soltanto per match esatto tra allowlist configurata e
  `automatic_review_policy` del catalogo, sempre tramite `CandidateReviewService`;
- merge multi-batch atomico che rilegge foglia e testa corrente sotto
  `BEGIN IMMEDIATE`, con contatori distinti per pending, rejected, superseded,
  no-positive-head e non-leaf;
- modalita' predefinita mixed (`0` se almeno un candidato e' unito), no-eligible
  (`4`, nessuna mutazione di merge) e strict (`4`, rollback dell'intero tentativo merge);
- set ordinati di candidati uniti/saltati, ragioni e decision ID osservati nel report;
- hash semantici delle viste effettive privi di path, timestamp e run ID operativi;
- test di input supportati/non supportati, zero candidates, policy, stati review misti,
  strict/no-eligible, reconcile, crash/retry, ordine inverso, entry point e no-network.

Non sono state aggiunte dipendenze, migrazioni, fixture o golden. Non e' stata spostata
logica di review o merge nei worker.

## Preflight e controllo anti-drift

Prima del codice sono stati letti integralmente `AGENTS.md`, design v02, design v01,
template report, analisi tecnica, contratti manifest, manuale utente e tutti i report
Slice 01-21 nell'ordine richiesto. Sono stati poi ispezionati `src/dsl_mngr`, test,
fixture/golden, schema/migrazioni effettivi e help CLI.

Il worktree iniziale conteneva gia' modifiche utente e l'implementazione non ancora
tracciata delle Slice 20-21. Le modifiche preesistenti sono state preservate; in
particolare non sono stati riscritti il prompt aggregato, migrazioni v1-v7, fixture,
golden, renderer, export, UI o test storici.

Classificazione del gate dipendenze:

| Precondizione | Evidenza osservata prima del codice | Esito |
|---|---|---|
| orchestratore Slice 16 | `process_dir`, run figlie, report e retry legacy coperti da `test_slice_16_batch_orchestration.py` | pronta |
| importer e modello candidati Slice 20 | importer comune, batch, lineage e migrazione v7 presenti | pronta |
| API review Slice 20 | `CandidateReviewService`, head concorrente, idempotenza e policy automatiche presenti | pronta |
| eligibility/merge Slice 20 | filtro foglia + testa `confirmed`, mixed/strict/no-eligible e reconcile presenti | pronta |
| derivazione Slice 21 | catalogo completo DDL/XML/DB code/log e report deterministici presenti | pronta |
| copertura dipendenze | baseline mirata Slice 16/20/21: 22 test passati | pronta |
| batch consolidato | non presente, come previsto dal perimetro Slice 22 | gap non bloccante, proprietario Slice 22 |
| schema | v7 sufficiente; il design assegna zero migrazioni alla Slice 22 | pronta |

Non sono emerse dipendenze bloccanti o contraddizioni normative. L'estensione minima a
una capacita' precedente e' il parametro core opzionale `parent_run_id` di `process_dir`,
necessario a collegare il batch parser alla run consolidata; il default preserva il
contratto e il comportamento Slice 16. Il modulo merge, gia' modificato dalla Slice 20,
e' stato esteso con un'API multi-batch atomica riusando integralmente la sua eligibility e
le primitive di materializzazione.

## Stato, checkpoint e retry per fase

| Fase | Transizioni normali persistite | Esiti terminali visibili | Ripresa |
|---|---|---|---|
| `parse` | `pending -> running -> completed` | `failed` con contatori/item legacy completi | riesegue parse se non completed |
| `derive` | `pending -> running -> completed` | `failed`; batch vuoti conteggiati | riusa il risultato completed; altrimenti riesegue derive |
| `review` | `pending -> running -> completed` | skip policy restano non-errori e candidati pending | riusa completed dopo crash; riapre dopo merge blocked/failed per rileggere policy/head |
| `merge` | `pending -> running -> completed` | `blocked` no-eligible o `failed` strict/operativo | riparte direttamente dal merge dopo crash post-review; non ripete merge completed |
| `reconcile` | `pending -> running -> completed` | `pending`, `failed` o `skipped` (`not_configured`/merge non completato) | riparte dal reconcile dopo crash post-merge |

Quando una fase terminale viene riaperta, il checkpoint aggiunge la transizione verso
`pending` con reason `retry`. Ogni entry conserva `attempts`, risultato e cronologia
transizioni. Un retry di una run terminale crea una nuova run parent collegata tramite
`parent_run_id`/`retry_of`; la ripresa di una run ancora `running` usa lo stesso artifact.

Artifact persistiti, tutti con path relativo al workspace:

```text
artifacts/runs/<RUN_ID>/batch_checkpoint.json
artifacts/runs/<RUN_ID>/batch_report.json
artifacts/runs/<CHILD_RUN_ID>/derive_report.json
artifacts/runs/<CHILD_RUN_ID>/review_report.json
artifacts/runs/<CHILD_RUN_ID>/merge_report.json
artifacts/runs/<CHILD_RUN_ID>/reconcile_report.json
```

Le fasi non producono contenuto sorgente lungo nei report. Il checkpoint registra gli ID
e i contatori necessari al resume, non ricostruisce implicitamente decisioni o supporti.

## Catalogo risultati ed exit code

| Condition/fase | Status | Reason | Mutazioni autoritative | Retry | Exit |
|---|---|---|---|---|---:|
| batch completato senza skip | `completed` | `success` | dichiarate dal report | no | 0 |
| merge misto con almeno un eleggibile | `completed` | `merge_completed_with_skips` | si' | no | 0 |
| nessun eleggibile, incluso zero candidates | `blocked` | `no_merge_eligible_candidates` | nessuna mutazione merge | si', dopo review/evidenza | 4 |
| strict incontra almeno uno skip | `failed` | `merge_review_precondition_failed` | rollback della transazione merge | si' | 4 |
| reconcile con sostituzione non materializzata | `pending` | `replacement_merge_pending` | eventuale compensazione dichiarata | si' | 4 |
| errore parser/fase operativo | `failed` | reason specifica o `batch_phase_failed` | partial esplicito nei risultati fase | si' | 2 |

La CLI stampa il report JSON su stdout per tutti gli esiti catalogati restituiti. Gli
errori di setup/configurazione vanno su stderr senza traceback. Gli skip review della
modalita' predefinita non diventano errori quando esiste almeno un merge; strict valuta
tutti i candidati prima della prima materializzazione.

## Convergenza e hash effettivi

Il test parametrico separa crash post-derive, post-review e post-merge. Per ciascun punto
confronta clean run, resume e secondo replay:

| Scenario | `effective_registry_hash` finale | Hash report semantico finale | Supporti fact/relation | Esito |
|---|---|---|---:|---|
| clean DDL | `8ee75a9706481211505f366b1b3dc069db65115d7f1125e4c1ec992aca0cc1af` | `8609e35c6d1bead70c8657aaad510d5b55611acd76c06d4ea98a66a79bf7a6ea` | 15 / 2 | riferimento |
| crash dopo derive -> resume -> replay | stesso hash | stesso hash | 15 / 2 | contatori identici; zero supporti duplicati |
| crash dopo review -> resume -> replay | stesso hash | stesso hash | 15 / 2 | contatori identici; zero supporti duplicati |
| crash dopo merge -> resume -> replay | stesso hash | stesso hash | 15 / 2 | merge non ripetuto; zero supporti duplicati |
| DDL+XML, creazione file forward | `5336cfc980739a5c8766e6c9289f616bc54ff0236362de3618ee279ef25aecbb` | `c6c40a01becbfc8c131a38549118fca756bc9182396b8615f4bebb104c9baaa0` | 20 / 3 | completed |
| DDL+XML, creazione file reverse | stesso hash | stesso hash | 20 / 3 | contatori identici |

Gli hash effettivi comprendono identita' semantiche, payload candidato, hash contenuto
sorgente, hash evidenza e policy/versione; escludono ID/path/timestamp operativi. Il test
controlla inoltre che `candidate_records` non aumenti durante il resume e che non esistano
duplicati `(owner, candidate_record_id)` nelle tabelle supporto.

## File della Slice

Runtime aggiunto/modificato:

```text
src/dsl_mngr/core/batch_consolidation.py
src/dsl_mngr/core/batch.py
src/dsl_mngr/core/merge.py
src/dsl_mngr/cli/commands/batch.py
src/dsl_mngr/cli/app.py
```

Test e documentazione:

```text
tests/test_slice_22_batch_consolidation.py
.kb/projects/slicing/slice_22/dsl_manager_slice_22_report.md
```

Schema/migrazioni: nessuna modifica. API pubbliche nuove:
`consolidate_batch`, `effective_registry_hashes`, `merge_candidate_batches` e comando
`batch consolidate`. Le API e opzioni legacy restano disponibili e invariate.

## Tracciabilita' Slice 22

Tutte le righe della sezione 17 assegnate alla Slice 22 sono coperte:

| Requisito sezione 17 | Implementazione finale | Test/esito finale |
|---|---|---|
| batch consolidato | `batch_consolidation.py`; fasi, checkpoint, aggregazione e resume; CLI in `batch.py`/`app.py` | `test_slice_22_retry_convergence` (3 crash point) - passed |

Coperture operative aggiuntive del prompt:

| Requisito | Test finale | Esito |
|---|---|---|
| input supportati/non supportati, policy presente, reconcile e no-network | `test_slice_22_mixed_inputs_policy_reconcile_and_no_network` | passed |
| policy assente/versione errata/presente; zero candidates; no eligible exit 4 | `test_slice_22_policy_absent_version_mismatch_and_zero_candidates` | passed |
| pending/rejected/superseded/confirmed insieme; default mixed; report ordinato | `test_slice_22_mixed_review_default_and_strict_rollback` | passed |
| strict rollback ed exit 4 | `test_slice_22_mixed_review_default_and_strict_rollback` | passed |
| crash dopo derive/review/merge, due retry, stessi contatori/hash e nessun doppio supporto | `test_slice_22_retry_convergence[after_*]` | passed |
| ordine inverso | `test_slice_22_inverse_input_order_converges` | passed |
| console script e modulo, stdout/stderr, exit 4 senza traceback | `test_slice_22_public_entrypoints_exit_four_without_traceback` | passed |

## Diff/status

Il diff stat globale include intenzionalmente le modifiche preesistenti delle Slice 20-21
e dell'utente, perche' il worktree non era pulito al preflight:

```text
28 tracked files changed, 1638 insertions(+), 58 deletions(-)
src/dsl_mngr/core/batch_consolidation.py    1035 righe (nuovo, non incluso nel diff stat)
tests/test_slice_22_batch_consolidation.py   355 righe (nuovo, non incluso nel diff stat)
```

File pertinenti alla Slice 22 nello stato finale:

```text
 M src/dsl_mngr/cli/app.py
 M src/dsl_mngr/cli/commands/batch.py
 M src/dsl_mngr/core/batch.py
 M src/dsl_mngr/core/merge.py
?? src/dsl_mngr/core/batch_consolidation.py
?? tests/test_slice_22_batch_consolidation.py
?? .kb/projects/slicing/slice_22/dsl_manager_slice_22_report.md
```

I primi due e `merge.py` contenevano gia' modifiche Slice 20-21; il diff pertinente e'
stato revisionato senza rimuoverle. `git diff --check` ha restituito exit 0; i soli
messaggi sono warning informativi LF/CRLF del worktree Windows.

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
.venv/Scripts/python.exe -m pytest tests/test_slice_16_batch_orchestration.py tests/test_slice_20_candidate_review.py tests/test_slice_20_migration_and_derivation.py tests/test_slice_21_deterministic_derivation.py -q
```

```text
22 passed in 24.91s
```

Test mirati Slice 22 dopo l'ultima modifica runtime:

```powershell
.venv/Scripts/python.exe -m pytest tests/test_slice_22_batch_consolidation.py -q
```

```text
9 passed in 80.97s (0:01:20)
```

Regressioni mirate intermedie eseguite:

```text
29 passed in 49.91s  # Slice 16/20/21/22
19 passed in 35.22s  # review/merge Slice 20 + batch Slice 22
```

Suite completa finale, rieseguita dopo l'ultima modifica al codice:

```powershell
.venv/Scripts/python.exe -m pytest
```

```text
100 passed in 598.79s (0:09:58)
```

Nessun test e' stato modificato per nascondere deviazioni; non sono stati creati o
aggiornati golden/fixture. I run elencati non hanno prodotto test falliti, skipped, xfail
o interrotti.

## Verifiche aggiuntive

- `py_compile` sui moduli Slice 22: exit 0;
- `.venv/Scripts/dsl-manager.exe batch consolidate --help`: exit 0;
- `.venv/Scripts/python.exe -m dsl_mngr batch consolidate --help`: exit 0, help equivalente;
- i due entry point su no-eligible: exit 4, JSON su stdout, stderr vuoto e nessun traceback,
  verificato dai test parametrizzati;
- ricerca statica: nessun client rete/AI o feature Excel/temporale nel runtime Slice 22;
- ricerca statica: nessun import da `src`, nessuna scrittura fact/relation fuori dal
  servizio merge;
- report/checkpoint riletti dai test e confrontati con il payload restituito;
- `git diff --check`: exit 0; `git diff --stat` e `git status --short` revisionati.

## Fuori scope / note

- nessun ingest Excel/OOXML, temporalita', DSL v2 o GEXF dinamico;
- nessuna nuova policy e nessuna auto-conferma di regole non allowlisted;
- nessuna rete o chiamata AI reale;
- nessuna migrazione, ORM, servizio esterno o dipendenza runtime aggiunta;
- nessun aggiornamento retroattivo di snapshot/artifact storici;
- nessun cambio implicito a stato, exit code o retry dei comandi batch Slice 16;
- documentazione utente/tecnica consolidata resta assegnata alla Slice 29;
- i cambi preesistenti non correlati sono rimasti preservati.

Autoverifica finale: perimetro, non-obiettivi, invarianti, failure mode, compatibilita'
legacy, determinismo, tracciabilita' e Definition of Done risultano soddisfatti.
