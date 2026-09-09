# Report Slice 27

Implementata la Slice 27 end-to-end, esclusivamente nel perimetro richiesto. Stato reale: **completata**.

Il percorso verticale verificato e' `fonti eterogenee -> raw_temporal_evidence -> gruppi di indipendenza/correlazione -> candidati temporal_interval pending -> review comune -> intervalli effettivi multipli -> DSL v2 -> GEXF 1.3 spells`, con integrazione batch `derive/review/merge/reconcile`, retry convergente e diff cross-schema soltanto su richiesta esplicita.

Nessun segnale ambiguo, contraddittorio, correlato o a timezone ignota viene promosso automaticamente. La confidence derivata dalla concordanza non sostituisce mai una decisione di review. Due ordini di input e un crash/retry producono gli stessi hash di evidenza, gruppi e candidati temporali.

## Aggiunto

- migrazione append-only v10 con `temporal_evidence_groups`, `temporal_evidence_group_members` e `temporal_conflicts`, relativi vincoli, indici e risoluzione tracciata dalla decisione;
- estrazione di PDF Info/XMP, HTML `time`/meta/JSON-LD, dichiarazioni esplicite in testo/Markdown/SQL/XML/log, token temporali nel nome file e soltanto `sources.first_seen_at` fra i timestamp operativi;
- conservazione separata di source key/format, raw value, metodo/versione, precisione, timezone, reliability, warning, revisione e target;
- consolidamento deterministico per target, con copie e stesso generatore non conteggiati come conferme indipendenti, concordanza indipendente valorizzata senza auto-review, contraddizioni persistite come conflitti;
- intervalli `year`/`month` come coverage envelope di calendario con precisione originale, `day` senza requisito timezone e `dateTime` materializzabile soltanto con `Z`, offset o timezone risolta;
- supporto a intervalli multipli/disgiunti per soggetto, ordinamento canonico e budget configurabile `temporal.max_intervals_per_subject`;
- policy esclusivamente esplicite `explicit_copy`, `intersection`, `aggregation` e `conflict`; nessuna ereditarieta' temporale implicita;
- relazioni `supersedes`, `precedes` e `version_of` prodotte come payload candidato soltanto in presenza del corrispondente riferimento letterale;
- handoff AI tramite protocollo adapter iniettato, evidenza raw a reliability bassa e candidate importer comune; nessuna scrittura diretta di intervalli e nessuna rete nel test;
- integrazione temporale nelle fasi batch esistenti: estrazione/consolidamento in derive, review comune, merge dei candidati temporali gia' materializzati e reconcile delle decisioni ritirate/corrette;
- DSL v2 con liste di intervalli multiple, mantenendo il default e il formato DSL v1 invariati;
- diff cross-schema solo con `--cross-schema`, con categorie separate `structural`, `governance` e `temporal` e cause tracciabili;
- GEXF 1.3 con bounds inclusivi, `spells` ordinati per intervalli multipli, validazione edge/node e policy `--temporal-output-mode {omit,separate,strict}`; `separate` pubblica un GEXF dedicato per l'altro profilo;
- golden condiviso DSL/spells e 21 test Slice 27.

Non sono state aggiunte dipendenze runtime o di sviluppo.

## Controllo anti-drift e dipendenze

Prima del codice sono stati letti integralmente `AGENTS.md`, design v02, design v01 come baseline, template report, analisi tecnica, contratti manifest, manuale utente, chat metadata, proposta temporale, chat formati/temporalita' e tutti i report Slice 01-26 in ordine. Sono stati inoltre ispezionati codice, schema/migrazioni, test, fixture, expected/golden e gli help pubblici pertinenti.

Classificazione iniziale:

- `pronta`: migrazioni v1-v9, raw evidence e candidati temporali Slice 26, review append-only comune, effective views, reconciliation gate, batch a checkpoint, DSL v2, GEXF 1.3 e validatore offline erano presenti e operativi;
- `pronta`: baseline dipendenze Slice 20, 22-26, `64 passed in 218.18s`, exit code 0;
- `gap non bloccante`: schema fermo a v9, sola estrazione OOXML, massimo un intervallo, assenza di gruppi/conflitti, fonti eterogenee, spells multipli, policy esplicite, batch temporale e cross-schema diff; tutti gap assegnati alla Slice 27;
- `bloccata da dipendenza`: nessuna;
- conflitti normativi non risolvibili: nessuno.

Il worktree iniziale era gia' dirty con modifiche tracked e untracked delle Slice 20-26. Sono state preservate integralmente; non sono stati eseguiti reset, checkout o cleanup distruttivi.

Due test Slice 26 codificavano contratti intenzionalmente sostituiti dalla Slice 27: ultima migrazione uguale a v9 e divieto del secondo intervallo. Sono stati aggiornati a v10/multi-intervallo senza ridurre le altre asserzioni. Durante l'integrazione e' stato aggiunto `merge.py` all'inventario iniziale: la modifica minima rende la fase merge consapevole di un candidato temporale gia' materializzato dalla review, senza creare una seconda via di materializzazione.

## Schema e invarianti

### Migrazione v10

La migrazione v10 e' aggiunta in coda a `MIGRATIONS`; nessuna migrazione applicata e' stata riscritta.

| tabella | responsabilita' |
|---|---|
| `temporal_evidence_groups` | target, policy/versione, hash deterministico e assessment |
| `temporal_evidence_group_members` | membership ordinata e classe `independent/correlated/duplicate/low_quality` |
| `temporal_conflicts` | conflitto aperto/risolto e decisione che lo risolve |

Il test v9 -> v10 copre rollback atomico, applicazione singola e secondo pass idempotente. Evidenze e intervalli v9 restano append-only; il conflitto v10 modifica soltanto il proprio stato di risoluzione governato.

### Evidenza, correlazione e review

La priorita' conservata e' contenuto dichiarativo > nome file > `sources.first_seen_at`. I timestamp filesystem, `last_seen_at` e `detected_at` non sono estratti come validita' semantica.

La chiave di correlazione comprende hash contenuto e famiglia del generatore. Due copie byte-identiche dello stesso segnale sono `duplicate`; due codifiche dello stesso generatore sono `correlated`; soltanto famiglie/contenuti indipendenti possono aumentare la forza. Il risultato resta comunque un candidato `ambiguous` pending. Piu' proposte incompatibili aprono `temporal_conflicts`; la conferma umana di una proposta collega la decisione e risolve il conflitto.

Il budget evidenze e' verificato sul totale canonico gia' persistito piu' i nuovi hash, quindi un replay al limite e' ammesso e un nuovo elemento oltre il limite fallisce. Raw invalidi o dateTime senza timezone restano evidenza/candidato e non diventano intervalli.

### Precisione, intervalli e policy

- `year`: envelope da 1 gennaio a 31 dicembre dei bounds dichiarati, `original_precision=year`;
- `month`: envelope dal primo all'ultimo giorno reale del mese, incluso il 29 febbraio, `original_precision=month`;
- `day`: date ISO complete, senza completamento o timezone obbligatoria;
- `dateTime`: nessun troncamento; materializzazione soltanto con offset esplicito/Z oppure timezone IANA risolta;
- PDF date parziali: anno/mese diventano envelope; componenti orarie incomplete non vengono riempite con zeri e restano raw non normalizzato;
- intervalli multipli: deduplicati per hash semantico, ordinati per start/end/hash e limitati dal budget configurato.

Le policy sono funzioni chiamate soltanto esplicitamente. `intersection` produce l'intersezione non vuota; un'intersezione vuota produce conflitto. `aggregation` conserva intervalli disgiunti senza colmare gap. `explicit_copy` copia soltanto le sorgenti nominate. `conflict` non produce un intervallo. La provenienza delle sorgenti e della policy resta nei raw evidence e nel payload candidato.

## DSL, diff, GEXF e hash

DSL v1 non e' stato modificato. DSL v2 conserva `intervals` come lista e ora include tutti gli intervalli effettivi compatibili o disgiunti in ordine canonico. Nei casi misti date/dateTime lo snapshot conserva entrambe le classi, mentre il profilo GEXF selezionato e le omissioni sono dichiarati nei metadata.

Il diff same-schema mantiene il contratto preesistente. Il diff v1 <-> v2 e' rifiutato senza `--cross-schema`; con il flag produce metadata `schema_version=cross` e categorie separate:

- `structural`: differenze di entita', fatti, relazioni e conflitti dopo aver escluso i campi temporali;
- `governance`: transizione esplicita del contratto schema;
- `temporal`: differenze nelle liste di intervalli.

Ogni categoria materializzata contiene cause evidence-backed. Gli hash non includono path assoluti, timestamp operativi, run ID o snapshot ID.

GEXF usa un solo `timeformat` per file. Un singolo intervallo usa bounds diretti; piu' intervalli usano `spells`, sempre inclusivi e ordinati. Le modalita' sono:

| modalita' | comportamento |
|---|---|
| `strict` | fallisce su un intervallo fuori dal profilo selezionato |
| `omit` | omette gli intervalli incompatibili e registra conteggio/warning |
| `separate` | produce il profilo principale e un file GEXF dedicato per l'altro timeformat |

Ogni file e' validato XSD e semanticamente prima della pubblicazione. Il validatore controlla che ogni intervallo edge sia contenuto nei bounds di entrambi i nodi endpoint; i nodi senza bounds restano intenzionalmente unbounded.

## Batch, retry, merge e reconcile

Le fasi pubbliche restano `parse`, `derive`, `review`, `merge`, `reconcile`, preservando il contratto Slice 22.

- `derive` estrae evidenza temporale per le revisioni completate e crea gruppi/candidati quando esistono fonti candidate-worthy;
- `review` usa esclusivamente `CandidateReviewService`; i candidati temporali non sono mai auto-reviewable;
- `merge` riconosce come gestito un candidato temporale confirmed soltanto se l'intervallo e' gia' stato materializzato atomicamente dalla review;
- `reconcile` rimuove immediatamente l'intervallo dalla vista effettiva tramite la testa review, chiude la coda e conserva la riga append-only storica;
- il checkpoint evita nuove evidenze/candidati al replay; hash e conteggi convergono fra esecuzione pulita, ordine inverso e crash dopo derive.

## Tracciabilita' iniziale e finale

| requisito design v02 / Slice 27 | implementazione finale | test finale | esito |
|---|---|---|---|
| precisione e timezone | validator/materializer, envelope year/month, offset/Z/IANA, no fill/truncate | `test_slice_27_precision_timezone` | passato |
| fonti multiple | estrattori eterogenei, grouping v10, correlation identity | `test_slice_27_evidence_concordance` | passato |
| piu' intervalli/spells | liste DSL v2, multi materialization, GEXF spells | `test_slice_27_spells_bounds` | passato |
| cross-schema diff | gate `--cross-schema`, categorie separate | `test_slice_27_cross_schema_diff` | passato |
| AI confinata all'handoff | `TemporalAiAdapter`, raw evidence + common candidate importer | `test_slice_27_ai_candidate_handoff` | passato |
| migrazione v10 | tre tabelle previste, FK/check/index, rollback/idempotenza | `test_slice_27_migration_v10_is_append_only_idempotent_and_atomic` | passato |
| matrice PDF/HTML/testo/MD/SQL/XML/log/nome/first_seen | `extract_temporal_evidence` e parser conservativi | `test_slice_27_all_source_extractors_and_exact_first_seen` | passato |
| correlazione/indipendenza/conflitto | classi membro e assessment deterministico | `test_slice_27_independent_concordance_correlation_and_conflict` | passato |
| timezone Z/offset/unknown | parsing esplicito e blocco unknown dateTime | test parametrico precision/timezone + unknown pending | passato |
| target a ogni granularita' | target v9 invariati e multi-intervallo v10 | `test_slice_26_all_temporal_targets_and_coverage_envelope` nella suite completa | passato |
| propagation/intersection/aggregation/conflict | API di policy esplicita e candidate-first | `test_slice_27_explicit_propagation_intersection_aggregation_and_conflict` | passato |
| intervalli disgiunti | aggregation senza coalescenza/gap fill | `test_slice_27_interval_operations_preserve_disjoint_ranges` | passato |
| edge fuori bounds | semantic validator GEXF | `test_slice_27_edge_outside_node_bounds_is_rejected` | passato |
| omit/separate/strict | opzione core/CLI e companion GEXF | `test_slice_27_temporal_output_modes_omit_separate_strict` | passato |
| temporal derive/review/merge/reconcile batch | sottoflusso nelle cinque fasi esistenti | `test_slice_27_batch_temporal_review_merge_and_reconcile` | passato |
| crash/retry/ordine | checkpoint + chiavi/hash canonici | `test_slice_27_batch_crash_retry_and_inverse_order_converge` | passato |
| `sources.first_seen_at` esatto | raw value copiato letteralmente dalla sola colonna ammessa | test matrice fonti | passato |
| budget at/over | verifica cumulativa evidence/intervals | `test_slice_27_budget_at_and_over_evidence_and_intervals` | passato |
| golden/hash condiviso | expected intervalli riusato per DSL e spells; doppio render byte-identico | `test_slice_27_spells_bounds_and_shared_golden_hash` | passato |
| fake AI/no-network | adapter finto con socket vietato | test AI handoff | passato |
| precedenza/versione solo esplicita | matcher ancorato e payload `candidate_relation` | `test_slice_27_version_precedence_requires_an_explicit_reference` | passato |
| reconcile temporale storico | effective head + coda chiusa, riga interval preservata | `test_slice_27_temporal_reconcile_closes_without_deleting_history` | passato |
| compatibilita' DSL v1 | ramo v1 invariato, suite Slice 07-09/26 | suite completa | passato |

Tutte le righe pertinenti della sezione 17 assegnate alla Slice 27 e tutti i test obbligatori del prompt sono verificati.

## Comandi pubblici verificati

Nuove opzioni:

```text
dsl-manager dsl diff ... --cross-schema
dsl-manager graph export ... --temporal-output-mode {omit,separate,strict}
```

Sono stati verificati entrambi gli entry point `dsl-manager` e `python -m dsl_mngr`, relativi `--help`, parsing opzioni, exit code, stdout/stderr e assenza di traceback negli errori attesi. La suite mantiene anche i test CLI Slice 20 e 26.

## Diff/status

File modificati o aggiunti dalla Slice 27:

```text
M  src/dsl_mngr/cli/app.py
M  src/dsl_mngr/cli/commands/dsl.py
M  src/dsl_mngr/cli/commands/graph.py
M  src/dsl_mngr/core/candidate_validation.py
M  src/dsl_mngr/core/dsl_diff.py
M  src/dsl_mngr/core/dsl_renderer.py
M  src/dsl_mngr/core/graph_export.py
M  src/dsl_mngr/core/merge.py
M  src/dsl_mngr/core/migrations.py
?? src/dsl_mngr/core/batch_consolidation.py (preesistente Slice 22, integrato)
?? src/dsl_mngr/core/candidate_review.py (preesistente Slice 20, integrato)
?? src/dsl_mngr/core/reconciliation.py (preesistente Slice 20/22, integrato)
?? src/dsl_mngr/core/temporal.py (preesistente Slice 26, esteso)
?? src/dsl_mngr/core/temporal_consolidation.py
?? tests/slice_27_test_support.py
?? tests/test_slice_27_ai_candidate_handoff.py
?? tests/test_slice_27_batch_policies.py
?? tests/test_slice_27_cross_schema_diff.py
?? tests/test_slice_27_evidence_concordance.py
?? tests/test_slice_27_precision_timezone.py
?? tests/test_slice_27_spells_bounds.py
?? tests/expected/expected_slice_27_temporal_spells.json
?? tests/test_slice_26_temporal_core.py (preesistente Slice 26, aspettative v10/multi aggiornate)
?? .kb/projects/slicing/slice_27/dsl_manager_slice_27_report.md
```

Il `git diff --stat` globale comprende anche il lavoro dirty preesistente delle Slice 20-26 e Git non include gli untracked nello stat. Non viene quindi presentato come dimensione esclusiva della Slice 27. Il diff pertinente, i nuovi file e lo status completo sono stati revisionati; non risultano feature di Slice successive.

## Test

Interprete usato esclusivamente: `.venv/Scripts/python.exe`, Python `3.12.10`, letto da `PROJECT_PYTHON` in `.codex/config.toml` come richiesto da `AGENTS.md` per Windows/VS Code.

Install editable pre-codice:

```powershell
.\.venv\Scripts\python.exe -m pip install -e ".[dev]"
```

Risultato: exit code 0; package editable reinstallato e dipendenze dev soddisfatte.

Baseline dipendenze pre-codice:

```powershell
.\.venv\Scripts\python.exe -m pytest -q tests\test_slice_20_candidate_review.py tests\test_slice_22_batch_consolidation.py tests\test_slice_23_excel_ingest.py tests\test_slice_24_workbook_manifest.py tests\test_slice_25_excel_candidates.py tests\test_slice_26_temporal_core.py tests\test_slice_26_dsl_v2.py tests\test_slice_26_gexf_offline.py tests\test_slice_26_cli_contract.py
```

Risultato: `64 passed in 218.18s`, exit code 0.

Test mirato Slice 27 finale:

```powershell
.\.venv\Scripts\python.exe -m pytest -q tests\test_slice_27_evidence_concordance.py tests\test_slice_27_precision_timezone.py tests\test_slice_27_spells_bounds.py tests\test_slice_27_cross_schema_diff.py tests\test_slice_27_ai_candidate_handoff.py tests\test_slice_27_batch_policies.py
```

Risultato: `21 passed in 51.14s`, exit code 0.

Suite completa finale, eseguita dopo l'ultima modifica di codice e test:

```powershell
.\.venv\Scripts\python.exe -m pytest
```

Risultato:

```text
166 passed in 865.75s (0:14:25)
exit code 0
```

Nessun test fallito, saltato, xfail o interrotto nella suite finale.

Verifiche finali:

- `python -m compileall -q src tests`: exit code 0;
- `python -m dsl_mngr dsl diff --help`: exit code 0, flag `--cross-schema` presente;
- `python -m dsl_mngr graph export --help`: exit code 0, modalita' temporali presenti;
- `dsl-manager dsl diff --help`: exit code 0;
- `dsl-manager graph export --help`: exit code 0;
- `git diff --check`: exit code 0; soli warning informativi LF/CRLF del worktree preesistente.

### Esecuzioni intermedie non verdi o interrotte

- primo retest Slice 22/26 dopo la rimozione del limite: `2 failed, 30 passed`; i due test falliti erano le aspettative storiche `v9 ultima migrazione` e `massimo un intervallo`, sostituite normativamente dalla Slice 27 e aggiornate a v10/multi;
- primo gruppo Slice 27: due failure di test, una asserzione sul JSON formattato e il guard legacy `len(intervals)>1` rimasto nel graph exporter; entrambi corretti, retest `2 passed` e poi gruppo completo verde;
- primo test batch Slice 27 con file testo e' stato interrotto manualmente durante i worker Docling per evitare un'attesa non necessaria; il caso e' stato riformulato con input SQL equivalente e parser deterministico in-scope, quindi eseguito realmente fino a `passed`;
- primo retest batch SQL: due errori esclusivamente nelle nuove asserzioni (`payload_hash` non e' una colonna e il conteggio include correttamente anche i candidati low-quality `first_seen_at`); corrette le asserzioni, senza modificare il comportamento runtime;
- regressione estesa successiva: `3 failed, 61 passed` per un argomento CLI passato alla funzione di preflight anziche' al costruttore delle opzioni; corretto il wiring, retest specifico `3 passed in 28.32s` e suite completa finale verde.

Nessuna esecuzione intermedia non verde viene dichiarata come passata.

## Fuori scope

- nessuna modifica del formato o del default DSL v1;
- nessuna rete, chiamata AI reale, modello o provider esterno;
- nessuna inferenza di validita' da filesystem timestamp, ordine lessicale, numero di versione o copia file;
- nessuna ereditarieta' temporale automatica;
- nessun ORM, servizio esterno o nuova dipendenza;
- nessuna riscrittura di migrazioni, snapshot o artifact storici;
- nessuna feature appartenente a Slice successive.

## Definition of Done

La Slice 27 soddisfa nucleo normativo e protocollo operativo: nessun segnale ambiguo entra automaticamente in DSL/GEXF; fonti correlate non aumentano la forza; timezone ignota resta pending; intervalli confermati multipli e disgiunti raggiungono DSL v2 e GEXF spells; edge bounds, output modes, diff cross-schema, batch/retry/reconcile, budget, golden e fake AI sono verificati. Due ordini e retry convergono, DSL v1 resta compatibile e l'intera suite e' verde.
