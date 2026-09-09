# Report Slice 26

Implementata la Slice 26 end-to-end, solo nello scope richiesto. Stato reale: **completata**.

Il percorso verticale verificato e' `OOXML bytes -> raw_temporal_evidence -> candidate_record temporal_interval pending -> CandidateReviewService -> temporal_intervals -> DSL schema 2 persistito/riletto -> GEXF 1.3 dinamico validato XSD e semanticamente offline`. Solo una foglia `confirmed` con timezone `explicit` o `resolved` diventa intervallo effettivo; evidenza raw, candidati pending/rejected, timezone unknown/incompatible e intervalli di source revision non propagati non raggiungono DSL o grafo.

## Aggiunto

- migrazione append-only v9 con `raw_temporal_evidence`, `temporal_candidate_details`, `temporal_candidate_evidence` e `temporal_intervals`, indici, foreign key, check e protezione append-only di evidenze/intervalli;
- estrazione OOXML in memoria di core properties temporali, app properties scalari e timestamp ZIP per singola entry, conservando valore raw, chiave/formato, metodo/versione, precisione, timezone, reliability, warning, locator e hash;
- tipo candidato comune `temporal_interval`, validazione dei cinque target ammessi e materializzazione nello stesso servizio/transazione di review usato dagli altri candidati;
- massimo un intervallo effettivo per target nel nucleo, bounds aperti a un solo estremo, `coverage_envelope`, date complete e dateTime senza troncamento, con timezone esplicita o risolta;
- DSL schema 2 selezionabile con `dsl render --schema-version 2`, default schema 1 invariato, `intervals` sempre presente, viste effettive, roundtrip DB/file, hash semantico e diff solo same-schema;
- tracciabilita' temporale dall'intervallo all'evidenza raw e alla review; l'evidenza raw resta visibile ma e' esclusa direttamente dall'hash DSL, mentre intervallo normalizzato e governance effettiva contribuiscono agli hash;
- export `graph export --snapshot-id ID --dynamic` esclusivo per DSL v2, GEXF 1.3 dinamico con un solo `timeformat`, bounds inclusivi e hash indipendente dallo snapshot ID;
- validazione offline a due livelli: `lxml==6.1.2`/XSD no-network con resolver locale allowlist, poi vincoli semantici su namespace/versione/mode/timeformat, ID, ordine, riferimenti, tipi, bounds e contenimento edge/node;
- risorse GEXF 1.3 vendute con manifest di commit, URL, licenza e SHA-256 e caricate tramite `importlib.resources`;
- golden DSL v2 e 25 test Slice 26 su migrazione, raw evidence, review, target, precisione/timezone, hash/diff/roundtrip, compatibilita' v1, CLI, package XSD, no-network e validazione GEXF.

## Controllo anti-drift e dipendenze

Il preflight e' stato eseguito prima del codice leggendo integralmente `AGENTS.md`, design v02, design v01, template report, documenti tecnici e manuale, documento chat sull'affidabilita' metadata, proposta temporale, documento chat sui formati/temporalita', report Slice 01-25, codice, migrazioni, test, fixture/golden e help correnti. Sono state verificate anche tutte le fonti ufficiali richiamate dalla sezione 20 del design v02, incluse ECMA/OPC, Python/SQLite, Docling, GEXF e lxml.

Classificazione iniziale:

- `pronta`: migrazioni v1-v8, candidate importer, lineage/review append-only, effective views, reconciliation gate, consolidamento batch, lettura singola/preflight OOXML, manifest Excel, renderer/diff v1 e GEXF statico erano presenti;
- `pronta`: test critici Slice 20-22 prima del codice, `27 passed in 42.49s`;
- `gap non bloccante`: mancavano esclusivamente modello v9/temporalita', DSL2 e GEXF dinamico previsti dalla Slice 26;
- `bloccata da dipendenza`: nessuna;
- conflitti normativi non risolvibili: nessuno.

Durante la regressione completa sono emersi due adattamenti minimi indispensabili:

- proprieta' Slice 15: l'estensione globale del validator al tipo temporale si rifletteva automaticamente nello schema del pacchetto AI, ma l'handoff temporale AI appartiene alla Slice 27. `ai_package.py` filtra quindi `temporal_interval` e preserva byte/contratto dei cinque record type storici;
- proprieta' Slice 24: il test append-only v8 invocava tutte le migrazioni correnti e applicava legittimamente anche v9. Il test ora passa esplicitamente `MIGRATIONS[:8]`, cosi' continua a verificare soltanto la migrazione di cui e' proprietario.

Entrambe le correzioni sono state rieseguite nella suite completa; non sono stati modificati golden o fixture storici per nascondere deviazioni.

File dichiarati prima dell'implementazione: `pyproject.toml`, migrazioni/config, candidate validator/importer/review, nuovo core temporale, renderer/diff DSL, graph export/validator, CLI DSL/graph, risorse GEXF, test/golden Slice 26 e questo report. L'inventario finale coincide con tale perimetro, oltre ai due adattamenti legacy appena documentati.

## Schema, API, comandi e artifact

### Migrazione e modello

- v9 e' aggiunta in coda a `MIGRATIONS`; nessuna migrazione applicata e' stata riscritta;
- `raw_temporal_evidence` e `temporal_intervals` sono append-only; evidenze identiche sono idempotenti per `evidence_hash`;
- `temporal_candidate_details` e la junction ordinata `temporal_candidate_evidence` estendono il normale `candidate_record_id` senza API di review parallela;
- target supportati e provati: `source_revision`, `source_fragment`, `candidate_record`, `fact`, `relation`;
- la review automatica e' sempre vietata ai candidati temporali, anche con confidence alta; la review umana materializza solo timezone risolta/esplicita e massimo un intervallo effettivo;
- `temporal_timezone_unknown` e' il reason code catalogato per un candidato che non puo' essere materializzato.

### DSL, diff e hashing

- `dsl render <workspace>` continua a produrre schema 1; `--schema-version 2` attiva temporal metadata e `intervals` su ogni fatto/relazione;
- v2 usa `effective_facts`, `effective_relations`, supporti effettivi e la testa review corrente degli intervalli foglia;
- `metadata.temporal` contiene `representation=interval`, base `day|timestamp`, mapping `date|dateTime` e timezone esplicita oppure `unknown`;
- snapshot v2 e' scritto e confrontato con DB/file dentro la transazione, quindi la riga DB e' riletta nuovamente dopo commit; DB JSON e bytes del file coincidono;
- registry hash include intervallo normalizzato e governance; DSL hash include la proiezione effettiva ma rimuove `traceability.temporal` dal preimage, perche' il raw deve essere tracciato senza alterare direttamente l'hash;
- diff v1-v1 e v2-v2 restano ammessi; v1-v2 e v2-v1 sono rifiutati. Un cambio intervallo appare come modifica del fatto/relazione e include cause `*_temporal` con `temporal_evidence_id`;
- nessun update retroattivo di snapshot: la prova v1 confronta bytes, DSL hash e riga DB prima/dopo l'aggiunta di un intervallo.

### GEXF e risorse

Le risorse vendute sono quelle esatte richieste dal design:

| file | URL sorgente | SHA-256 |
|---|---|---|
| `gexf.xsd` | `https://raw.githubusercontent.com/gephi/gexf/66efb132569f61e5e8a313d78144484238ac7315/specs/1.3/gexf.xsd` | `a8e1d0a6a5237fc4ce0825692fa3db49fb04d70cf3a84334f7a87c15422c1257` |
| `dynamics.xsd` | `https://raw.githubusercontent.com/gephi/gexf/66efb132569f61e5e8a313d78144484238ac7315/specs/1.3/dynamics.xsd` | `d5ee084a858baf6efebe210d4799050723bfce71fb44c9ddbf20a53f45be8298` |
| `viz.xsd` | `https://raw.githubusercontent.com/gephi/gexf/66efb132569f61e5e8a313d78144484238ac7315/specs/1.3/viz.xsd` | `e20e40bcfd4531026d4d1c74da5cbadc413ff5b81cf4418ca14f42ea994e2dc4` |

Commit: `66efb132569f61e5e8a313d78144484238ac7315`. Licenza: `CC BY 4.0`, registrata in `manifest.json` e `LICENSE.txt`.

L'export dinamico usa namespace `http://gexf.net/1.3`, `version=1.3`, `mode=dynamic`, `timerepresentation=interval`, bounds `start/end` inclusivi e un solo `timeformat`. Il file e' validato completamente prima di creare directory/file o registrare `graph_exports`; errori XSD e semantici producono reason/exit stabili e nessun artifact o record.

### Matrice schema version x render x diff x export x allow-incomplete

| profilo | render | diff | export | `--allow-incomplete` |
|---|---|---|---|---|
| schema 1, default | ammesso e invariato | solo v1 -> v1 | GEXF statico 1.2; `--dynamic` rifiutato | rifiutato |
| schema 2, esplicito | `--schema-version 2` | solo v2 -> v2, incluse variazioni intervallo | solo `--dynamic`, GEXF 1.3 | ammesso con omissioni/warning/conteggi espliciti |
| cross-schema | non applicabile | rifiutato nella Slice 26 | snapshot v1 dinamico e snapshot v2 statico rifiutati | nessun bypass |

La prova `test_slice_26_historical_snapshot_immutable` renderizza uno snapshot v1 prima dell'intervallo, aggiunge e conferma l'intervallo, renderizza nuovamente con il default e verifica identita' di bytes, `dsl_hash` e contenuto persistito.

## Checklist 1 - migrazione e review

| requisito | implementazione | test | esito |
|---|---|---|---|
| migrazione v9 append-only/atomica | quattro tabelle, FK/check/index/trigger; rollback transazionale | `test_slice_26_migration_v9_and_rollback` | passato |
| candidato temporale e' un candidate record | validator/importer comune + detail/junction | `test_slice_26_common_review` | passato |
| una sola review API | solo `CandidateReviewService`; auto-review vietata | `test_slice_26_common_review` | passato |
| foglia confirmed soltanto | query intervalli su current head + assenza child lineage | test review, rejection/reconciliation, DSL effective | passato |
| massimo un intervallo effettivo | controllo nella stessa transazione della decisione | `test_slice_26_one_interval_max_and_timezone_resolution` | passato |
| tutti i target v02 | risoluzione FK logica sui cinque registry | `test_slice_26_all_temporal_targets_and_coverage_envelope` | passato |

## Checklist 2 - evidenza temporale e intervallo

| requisito | implementazione | test | esito |
|---|---|---|---|
| evidenza grezza completa | record separati core/app/ZIP con tutti i campi sezione 8.3 | `test_slice_26_raw_evidence_fields` | passato |
| proprieta' concordanti/contraddittorie | confronto sintattico core e warning deterministici | raw evidence + `test_slice_26_contradictory_properties_stay_pending` | passato |
| nessun timestamp filesystem | estrazione soltanto dalle parti OOXML e dalla directory ZIP acquisita una volta | test campi/source key e code review | passato |
| pending prima della review | candidato ambiguous/low, nessuna testa/intervallo automatico | test contradiction/common review | passato |
| date/day e dateTime timezone-resolved | normalizzazione senza fill/truncate; ZoneInfo per policy risolta | test timezone core + `test_slice_26_datetime_timezone_resolved_without_truncation` | passato |
| precisione year/month condivisa con Slice 27 | nucleo conserva `original_precision` e accetta envelope esplicito, non completa il raw | test all targets/coverage envelope | passato nello scope 26 |
| zero/un intervallo | liste DSL sempre presenti; limite uno nel servizio | test one interval + `intervals=[]` | passato |
| nessuna ereditarieta' dalla source | solo target diretto fact/relation e nessuna propagation rule implicita | `test_slice_26_source_interval_is_not_inherited` | passato |

## Checklist 3 - DSL v2, hash e diff

| requisito | implementazione | test | esito |
|---|---|---|---|
| DSL v2 metadata/intervals | renderer schema 2 con profilo temporale esatto | `test_slice_26_dsl_v2_roundtrip` + golden | passato |
| persist/re-read/roundtrip | confronto DB/file/content/hash prima e dopo commit | `test_slice_26_dsl_v2_roundtrip` | passato |
| hash semantico stabile | canonical JSON; niente run/timestamp/path assoluti; raw escluso direttamente | roundtrip doppio + inserimento raw-only invariato | passato |
| viste effettive/governance | effective facts/relations/support, current review e leaf | golden/registry hash/reconciliation tests | passato |
| diff only same-schema | guard schema; intervalli nel confronto v2 | `test_slice_26_diff_same_schema_only` | passato |
| causa temporale del diff | trace raw associata al subject e causa `fact_temporal/relation_temporal` | `test_slice_26_diff_detects_interval_and_reports_temporal_evidence` | passato |
| default/v1 immutabile | ramo v1 e shape/hash preesistenti invariati | `test_slice_26_historical_snapshot_immutable`, suite Slice 07-09 | passato |
| reconciliation e incomplete | strict block; allow soltanto v2 con warning/conteggi | `test_slice_26_reconciliation_block_and_allow_incomplete_v2_only` | passato |

## Checklist 4 - GEXF XSD e semantica

| requisito | implementazione | test | esito |
|---|---|---|---|
| namespace/version/mode/timeformat | serializer GEXF 1.3 dinamico interval | `test_slice_26_gexf_offline` | passato |
| XSD offline transitivi | XMLSchema lxml, parser no-network, resolver locale dei tre nomi | offline/package test | passato |
| bounds inclusivi e ordinati | solo start/end, parsing date/dateTime e sort stabile | semantic parameterized tests | passato |
| riferimenti e unicita' | node/edge ID unici, source/target esistenti | semantic refs/order tests | passato |
| tipi attributi | dichiarazione per class/id e validazione scalare/list/range | semantic type test | passato |
| edge entro endpoint | controllo applicativo oltre XSD; nodo senza intervallo e' unbounded | semantic bounds test + export reale | passato |
| dateTime con offset risolto | nessun troncamento; offset nel bound GEXF | `test_slice_26_datetime_export_is_timezone_resolved_and_hash_stable` | passato |
| nessuna pubblicazione su errore | validazione prima di mkdir/write/insert | test parametrico XSD + semantic failure | passato |

## Checklist 5 - packaging, risorse e offline

| requisito | implementazione | test | esito |
|---|---|---|---|
| pin lxml esatto | dependency runtime `lxml==6.1.2` | editable install + `pip show lxml` | passato |
| tre SHA esatti | costanti + manifest + confronto bytes | `test_slice_26_xsd_sha_package_and_no_network` | passato |
| importlib.resources | package `dsl_mngr.resources.gexf`, directory `1.3` | stesso test | passato |
| commit/URL/licenza | `manifest.json` e `LICENSE.txt` | assert manifest | passato |
| nessuna rete runtime/test | `no_network=True`, DTD/entities off, socket vietato nel test | package/no-network test | passato |
| resolver allowlist locale | accetta solo nome locale o `resource:///nome`, nega URI esterni | compilazione/validazione completa XSD | passato |

## Tracciabilita' sezione 17

| riga assegnata alla Slice 26 | file/test | esito |
|---|---|---|
| evidenza temporale grezza | `temporal.py`, v9, `test_slice_26_raw_evidence_fields` | passato |
| review temporale comune | `candidate_review.py`, `test_slice_26_common_review` | passato |
| DSL v2 | `dsl_renderer.py`, golden, `test_slice_26_dsl_v2_roundtrip` | passato |
| GEXF 1.3 offline | resources, `gexf_validation.py`, `test_slice_26_gexf_offline` | passato |
| precisione e timezone, responsabilita' 26-27 | core date/dateTime/envelope/unknown; test timezone/envelope/dateTime | passato per il nucleo 26; consolidamento resta alla 27 |
| immutabilita' snapshot storici, responsabilita' 20/26 | renderer v1 invariato, `test_slice_26_historical_snapshot_immutable` | passato |

Tutte le righe pertinenti della sezione 17 assegnate alla Slice 26 sono state verificate.

## Diff/status

File modificati o aggiunti dalla Slice 26:

```text
M  pyproject.toml
M  src/dsl_mngr/cli/app.py
M  src/dsl_mngr/cli/commands/dsl.py
M  src/dsl_mngr/cli/commands/graph.py
M  src/dsl_mngr/core/ai_package.py
M  src/dsl_mngr/core/candidate_import.py
M  src/dsl_mngr/core/candidate_validation.py
M  src/dsl_mngr/core/config.py
M  src/dsl_mngr/core/dsl_diff.py
M  src/dsl_mngr/core/dsl_renderer.py
M  src/dsl_mngr/core/graph_export.py
M  src/dsl_mngr/core/migrations.py
?? src/dsl_mngr/core/candidate_review.py (preesistente dalla Slice 20, integrato)
?? src/dsl_mngr/core/gexf_validation.py
?? src/dsl_mngr/core/temporal.py
?? src/dsl_mngr/resources/__init__.py
?? src/dsl_mngr/resources/gexf/__init__.py
?? src/dsl_mngr/resources/gexf/1.3/dynamics.xsd
?? src/dsl_mngr/resources/gexf/1.3/gexf.xsd
?? src/dsl_mngr/resources/gexf/1.3/viz.xsd
?? src/dsl_mngr/resources/gexf/1.3/manifest.json
?? src/dsl_mngr/resources/gexf/1.3/LICENSE.txt
?? tests/slice_26_test_support.py
?? tests/test_slice_26_cli_contract.py
?? tests/test_slice_26_dsl_v2.py
?? tests/test_slice_26_gexf_offline.py
?? tests/test_slice_26_temporal_core.py
?? tests/expected/expected_slice_26_dsl_v2.json
?? tests/test_slice_24_workbook_manifest.py (preesistente dalla Slice 24, test limitato a v8)
?? .kb/projects/slicing/slice_26/dsl_manager_slice_26_report.md
```

Il worktree iniziale era gia' dirty con 33 file tracked modificati e file/report/fixture/test untracked delle Slice 20-25. Tutto e' stato preservato. In particolare `candidate_review.py` e `tests/test_slice_24_workbook_manifest.py` erano untracked preesistenti e sono stati integrati in modo puntuale; nessun reset, checkout o cleanup distruttivo e' stato eseguito.

Il `git diff --stat` globale prima del report include lavoro preesistente e non include gli untracked:

```text
35 files changed, 4368 insertions(+), 181 deletions(-)
```

Per questa ragione lo stat globale non viene presentato come dimensione esclusiva della Slice 26. Il diff pertinente e l'elenco untracked sono stati revisionati integralmente; non risultano fonti PDF/HTML/nome/contenuto, multi-intervallo/spells, cross-schema diff o altre funzioni della Slice 27.

## Test

Interprete usato esclusivamente: `.\.venv\Scripts\python.exe` / Python `3.12.10`, letto da `PROJECT_PYTHON` in `.codex/config.toml`.

Install editable finale:

```powershell
.\.venv\Scripts\python.exe -m pip install -e ".[dev]"
```

Risultato: exit code `0`; `dsl_mngr-0.1.0` reinstallato editable, `docling==2.97.0`, `lxml==6.1.2` e `pytest` soddisfatti. `pip show lxml` ha confermato `Version: 6.1.2`; `pip check` ha restituito `No broken requirements found`, exit code `0`.

Baseline dipendenze pre-codice:

```powershell
.\.venv\Scripts\python.exe -m pytest tests/test_slice_20_candidate_review.py tests/test_slice_20_migration_and_derivation.py tests/test_slice_21_deterministic_derivation.py tests/test_slice_22_batch_consolidation.py -q
```

Risultato: `27 passed in 42.49s`.

Test mirato finale:

```powershell
.\.venv\Scripts\python.exe -m pytest tests/test_slice_26_temporal_core.py tests/test_slice_26_dsl_v2.py tests/test_slice_26_gexf_offline.py tests/test_slice_26_cli_contract.py -q
```

Risultato finale post-allineamento catalogo: `25 passed in 18.64s`, exit code `0`.

Retest delle due regressioni d'integrazione e della Slice 26:

```powershell
.\.venv\Scripts\python.exe -m pytest tests/test_slice_15_ai_package.py::test_build_ai_package tests/test_slice_24_workbook_manifest.py::test_slice_24_v8_is_append_only_from_v7 tests/test_slice_26_temporal_core.py tests/test_slice_26_dsl_v2.py tests/test_slice_26_gexf_offline.py tests/test_slice_26_cli_contract.py -q
```

Risultato: `27 passed in 20.00s`, exit code `0`.

Suite completa finale, eseguita dopo l'ultima modifica runtime:

```powershell
.\.venv\Scripts\python.exe -m pytest
```

Risultato:

```text
145 passed in 289.72s (0:04:49)
exit code 0
```

Nessun test fallito, saltato, xfail o interrotto nella suite finale.

### Esecuzioni intermedie e non verdi

- un primo run aggregato Slice 20-25 non ha conservato il riepilogo nel canale tool dopo i primi progress marker; classificazione `limite di cattura output`, non contato come evidenza. E' stato sostituito dal baseline nominato e dalle suite complete;
- il primo test temporale mirato ha avuto exit code `1` perche' il test contraddizione non aveva creato un `run_id`; classificazione `introdotto dal test Slice 26`. Corretto il setup con `start_run`; il gruppo ha poi prodotto `5 passed in 2.80s` e, dopo l'estensione dei target, `6 passed in 3.67s`;
- due run DSL mirati hanno avuto exit code `1` durante l'introduzione della tracciabilita' e dell'esclusione raw dal preimage hash: in entrambi il solo delta era il nuovo golden/hash previsto. Classificazione `golden nuovo in costruzione`, non regressione storica; il golden v2 e' stato aggiornato solo dopo confronto bytes e i 7 test finali sono verdi;
- un run GEXF ha prodotto `1 failed, 8 passed in 3.54s`: il test assumeva un solo warning ma la fixture conteneva anche un warning orphan valido. Classificazione `asserzione test Slice 26 troppo restrittiva`; ora verifica esattamente un warning `reconciliation_required` senza vietare warning indipendenti;
- il comando `.\.venv\Scripts\python.exe -m pytest tests/test_slice_26_*.py -q` ha restituito exit code `1`, `no tests ran`, perche' PowerShell ha passato il wildcard letterale. Classificazione `errore d'invocazione`; sostituito dal comando esplicito, che ha prodotto `25 passed`;
- la prima suite completa ha prodotto `2 failed, 143 passed in 400.50s`: `test_build_ai_package` esponeva indebitamente il tipo temporale nello schema AI, e `test_slice_24_v8_is_append_only_from_v7` applicava anche v9. Classificazione `introdotto dall'integrazione Slice 26`; correzioni minime descritte nel preflight e retest `27 passed`;
- suite complete verdi intermedie: `145 passed in 280.56s`, poi `145 passed in 341.48s`; la suite e' stata rieseguita ancora dopo gli ultimi allineamenti CLI/catalogo, producendo il risultato finale sopra.

Nessun test finale e' stato omesso. Le esecuzioni non verdi non sono state nascoste e non incidono sulla Definition of Done perche' ogni causa e' stata corretta e l'intera suite post-correzione e' verde.

## Verifiche aggiuntive

- `.\.venv\Scripts\python.exe --version`: `Python 3.12.10`, exit code `0`;
- `.\.venv\Scripts\python.exe -m compileall -q src tests`: exit code `0`;
- `dsl-manager dsl render --help` e `.\.venv\Scripts\python.exe -m dsl_mngr dsl render --help`: exit code `0`, stdout equivalente, stderr vuoto, opzioni `--schema-version {1,2}` e `--allow-incomplete` presenti;
- `dsl-manager graph export --help` e `.\.venv\Scripts\python.exe -m dsl_mngr graph export --help`: exit code `0`, stdout equivalente, stderr vuoto, opzione canonica `--snapshot-id` con alias `--snapshot`, `--dynamic`, `--timeformat` e `--allow-incomplete` presenti;
- test CLI di successo reale su entrambi gli entry point e test degli errori attesi: exit code stabili, stderr senza traceback;
- `git diff --check`: exit code `0`; i soli messaggi sono warning Git sulla futura conversione LF/CRLF di file gia' nel worktree;
- tre XSD aperti via `importlib.resources`, SHA esatti e compilazione XMLSchema verificati senza socket/rete;
- revisione diff: import assoluti `dsl_mngr`, path artifact relativi, nessun timestamp/run ID/path assoluto negli hash semantici, nessun ORM o servizio esterno.

## Fuori scope / note

- nessuna fonte temporale PDF, HTML, nome file, contenuto testuale/SQL/XML/log o `sources.first_seen_at`;
- nessuna correlazione/indipendenza avanzata, tabella v10, conflitto temporale consolidato, intersezione/aggregazione o propagazione;
- nessun multi-intervallo o `<spells>` prodotto dal nucleo; il validator sa rifiutare ordine/bounds non validi, ma l'abilitazione multipla resta alla Slice 27;
- nessun cross-schema diff e nessun `--cross-schema`;
- nessun handoff temporale AI: il package AI resta deliberatamente compatibile con la Slice 15 fino alla Slice 27;
- nessun timestamp filesystem, download XSD runtime, macro/link/rete o conversione di formato;
- nessuna alta confidence equivale a conferma e nessuna sorgente trasferisce automaticamente il proprio intervallo a fact/relation.

Autoverifica finale: perimetro, non-obiettivi, invarianti, matrice di tracciabilita', failure mode, compatibilita' legacy, determinismo e Definition of Done risultano soddisfatti. La Slice 26 e' **completata**: solo un intervallo resolved/explicit e confirmed appare nel DSL/grafo, XSD e semantic validation passano offline e lo schema 1 resta compatibile.
