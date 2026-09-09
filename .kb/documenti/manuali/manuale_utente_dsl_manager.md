# Manuale utente di DSL Manager

> Release applicativa di riferimento: **1.1.0**.

## 1. Che cosa fa

DSL Manager trasforma un corpus locale in evidenze tracciabili, candidati
revisionabili, fatti/relazioni consolidati, snapshot DSL e grafi. Il passaggio
fondamentale è:

```text
evidenza -> candidato pending -> decisione persistita -> merge -> output
```

Un candidato valido non è ancora approvato. Soltanto la foglia corrente con
testa di review `confirmed` è mergeabile. Metadata, nomi file, formule e output
Docling sono osservazioni: non diventano verità senza policy/review.

Per i dettagli tecnici vedere l'[analisi tecnica](../documenti%20tecnici/analisi_tecnica_dsl_manager.md)
e i [contratti manifest](../documenti%20tecnici/contratti_manifest_dsl_manager.md).

## 2. Requisiti e installazione

Il progetto richiede Python `>=3.12,<3.13`. In Windows/VS Code usare soltanto
`PROJECT_PYTHON` dichiarato in `.codex/config.toml`; nella configurazione
corrente è `.venv\Scripts\python.exe`.

Da PowerShell nella root del repository:

```powershell
& '.\.venv\Scripts\python.exe' -m pip install -e '.[dev]'
& '.\.venv\Scripts\python.exe' -m dsl_mngr --help
```

L'entry point equivalente, dopo l'installazione editable, è:

```powershell
dsl-manager --help
```

Gli esempi usano `dsl-manager` per brevità. Ogni comando può essere eseguito come
`<PROJECT_PYTHON> -m dsl_mngr ...` con gli stessi argomenti.

## 3. Quick start governato

### 3.1 Creare workspace e database

```powershell
dsl-manager init .workspaces/demo
dsl-manager db init .workspaces/demo
```

`db init` applica le migrazioni fino alla v10 ed è idempotente quando schema e
checksum coincidono.

### 3.2 Inserire e scansionare il corpus

Collocare i file in `.workspaces/demo/corpus/active/`, quindi:

```powershell
dsl-manager corpus scan .workspaces/demo
```

Il secondo scan sugli stessi byte deve risultare invariato. Una modifica crea
una nuova `source_revision`; non sovrascrive quella precedente.

### 3.3 Eseguire il batch consolidato

```powershell
dsl-manager batch consolidate .workspaces/demo --path corpus/active
```

Le fasi sono `parse`, `derive`, `review`, `merge`, `reconcile`. Senza policy
automatiche autorizzate, i candidati restano pending e il merge li salta. Per
richiedere rollback se ne incontra uno:

```powershell
dsl-manager batch consolidate .workspaces/demo --strict-review
```

Per eseguire anche reconcile dopo un merge completato:

```powershell
dsl-manager batch consolidate .workspaces/demo --reconcile
```

Per riprendere una run checkpointed:

```powershell
dsl-manager batch consolidate .workspaces/demo --resume RUN_000001
```

Usare gli ID realmente stampati; gli ID negli esempi sono segnaposto formattati.

### 3.4 Revisionare i candidati

```powershell
dsl-manager candidates review list .workspaces/demo --outcome pending
dsl-manager candidates review show .workspaces/demo CREC_000001
dsl-manager candidates review confirm .workspaces/demo CREC_000001 --actor-id reviewer-01 --reason 'evidenza verificata'
```

Un attore umano deve essere esplicito. `--reason` è facoltativa per `confirm`, ma
obbligatoria per `reject` e `correct`.

```powershell
dsl-manager candidates review reject .workspaces/demo CREC_000002 --actor-id reviewer-01 --reason 'locator insufficiente'
dsl-manager candidates review correct .workspaces/demo CREC_000003 --actor-id reviewer-01 --reason 'valore corretto' --payload corrections/CREC_000003.json
```

Per richieste concorrenti o retry controllati:

```powershell
dsl-manager candidates review confirm .workspaces/demo CREC_000004 --actor-id reviewer-01 --expected-head-decision-id RDEC_000010 --idempotency-key ticket-481
```

Il replay identico riusa la decisione. Una chiave riusata con payload diverso o
una testa stantia produce conflitto senza una mutazione parziale. La correzione
crea un candidato sostitutivo e non modifica l'originale.

### 3.5 Fare merge e reconcile

```powershell
dsl-manager facts merge .workspaces/demo --batch CBATCH_000001
dsl-manager facts merge-batch .workspaces/demo --batch CBATCH_000001 --batch CBATCH_000002
```

Solo candidati foglia con testa `confirmed` entrano nel merge. Per fallire invece
di saltare pending/rejected/superseded/non-leaf:

```powershell
dsl-manager facts merge .workspaces/demo --batch CBATCH_000001 --strict-review
```

Se una decisione positiva già materializzata viene sostituita:

```powershell
dsl-manager facts reconcile .workspaces/demo
dsl-manager facts reconcile .workspaces/demo --reconciliation-id RECON_000001 --strict
```

Finché una riconciliazione è aperta, render, diff ed export sono bloccati per
default.

### 3.6 Renderizzare DSL e grafi

Profilo legacy:

```powershell
dsl-manager dsl render .workspaces/demo --schema-version 1
dsl-manager graph export .workspaces/demo --snapshot-id DSL_000001
```

Profilo governato temporale:

```powershell
dsl-manager dsl render .workspaces/demo --schema-version 2
dsl-manager graph export .workspaces/demo --snapshot-id DSL_000002 --dynamic --timeformat date
```

Schema 1 e GEXF statico leggono lo stato fisico legacy. Schema 2 e GEXF dinamico
leggono le viste effettive. Gli snapshot esistenti non vengono aggiornati quando
cambia il registry.

## 4. Catalogo dei comandi pubblici

La tabella elenca i leaf command osservati con `--help` per l'entry point e per
`python -m dsl_mngr`.

| Comando | Uso sintetico |
|---|---|
| `init` | crea la struttura del workspace |
| `db init` | crea/aggiorna SQLite con migrazioni verificate |
| `corpus scan` | registra aggiunte, modifiche, rimozioni e invariati |
| `corpus normalize` | normalizza una revisione; instrada anche Excel diretto |
| `corpus chunk` | genera chunk da una revisione normalizzata |
| `corpus parse-ddl` | estrae frammenti DDL |
| `corpus parse-xml-form` | estrae frammenti Oracle Forms XML |
| `corpus parse-db-code` | estrae unità/dipendenze da codice DB |
| `corpus parse-log` | estrae eventi osservati da log |
| `batch process-dir` | scan e lavorazione per directory |
| `batch chunk-dir` | chunk di più revisioni |
| `batch consolidate` | parse/derive/review/merge/reconcile checkpointed |
| `candidates validate` | valida/importa un file JSONL candidato |
| `candidates validate-batch` | valida più JSONL dalla directory |
| `candidates derive` | applica una regola deterministica versionata |
| `candidates review list` | elenca pending o teste per outcome |
| `candidates review show` | mostra payload, evidence, lineage e decisioni |
| `candidates review confirm` | crea una testa positiva |
| `candidates review reject` | crea una testa negativa |
| `candidates review correct` | crea sostituzione, lineage e decisioni |
| `ai package` | crea un package locale per handoff AI |
| `ai package-batch` | crea package per più revisioni |
| `ai inbox scan` | elenca output candidati e staleness |
| `ai import` | importa candidati legati a un package |
| `facts merge` | fonde un batch di candidati confermati |
| `facts merge-batch` | fonde più batch |
| `facts reconcile` | risolve richieste di riconciliazione |
| `dsl render` | crea snapshot JSON/YAML/Markdown schema 1 o 2 |
| `dsl diff` | confronta snapshot |
| `graph export` | crea GEXF statico o dinamico |
| `run start` | apre una run applicativa |
| `run status` | mostra stato e artefatti di una run |
| `log table` | visualizza JSONL come tabella/HTML/CSV legacy |
| `log csv` | produce CSV deterministico |
| `ui serve` | avvia UI locale read-only |

Consultare sempre il leaf help prima di automatizzare:

```powershell
dsl-manager candidates review correct --help
dsl-manager graph export --help
```

## 5. Elaborazione per tipo di file

### 5.1 Documenti leggibili

```powershell
dsl-manager corpus normalize .workspaces/demo --revision REV_000001 --profile docling.no_images
dsl-manager corpus chunk .workspaces/demo --revision REV_000001 --profile docling.chunking
```

Gli artefatti principali sono `normalized.json`, `normalized.md` e
`chunks.jsonl`. Docling crea una vista leggibile, non una decisione semantica.

### 5.2 DDL, XML, codice DB e log

```powershell
dsl-manager corpus parse-ddl .workspaces/demo --revision REV_000002 --profile ddl.default
dsl-manager corpus parse-xml-form .workspaces/demo --revision REV_000003 --profile xml_form.default
dsl-manager corpus parse-db-code .workspaces/demo --revision REV_000004 --profile db_code.default
dsl-manager corpus parse-log .workspaces/demo --revision REV_000005 --profile log.default
```

I parser producono frammenti tecnici. Le regole di derive li trasformano in
candidati; non creano direttamente fatti.

### 5.3 `.xlsx` e `.xlsm`

```powershell
dsl-manager corpus normalize .workspaces/demo --revision REV_000006 --profile docling.no_images
```

Il route Excel usa direttamente i byte registrati. `.xlsm` non viene convertito
in `.xlsx`. Le macro non vengono eseguite, le formule non sono ricalcolate e i
link esterni non sono seguiti.

Il risultato ha due viste:

- `normalized.json`/`normalized.md` da Docling, per lettura;
- `workbook_manifest.json` più frammenti `excel_region`, per struttura.

Nel manifest formula e cached value sono distinti. Il valore mostrato da Docling
non è autoritativo per la formula; nessuno dei due è automaticamente una verità
di dominio. Il preflight verifica sicurezza, content type, hash e budget prima
della normalizzazione.

## 6. Derivazione deterministica

Esempio:

```powershell
dsl-manager candidates derive .workspaces/demo --source-revision-id REV_000002 --rule ddl_table_fact/1
```

Regole disponibili:

```text
ddl_table_fact/1
ddl_column_fact/1
ddl_fk_relation/1
xml_form_structure/1
xml_table_usage/1
db_code_unit/1
db_code_dependency/1
log_event_observation/1
excel_workbook_fact/1
excel_sheet_fact/1
excel_region_fact/1
excel_named_range_fact/1
excel_table_fact/1
excel_explicit_reference/1
```

Ogni output resta pending. Le prime cinque regole Excel su fatti possono essere
auto-revisionate soltanto con la policy esatta in allowlist; la relazione Excel
esplicita non è mai auto-confermata. Le regole non deducono entità di dominio da
nomi tecnici e rifiutano placeholder non risolti.

## 7. Candidate JSONL e AI handoff

### 7.1 Validazione manuale

```powershell
dsl-manager candidates validate .workspaces/demo --input ai/inbox/candidates.jsonl
dsl-manager candidates validate-batch .workspaces/demo --input-dir ai/inbox --pattern '*.jsonl'
```

Tipi ammessi: `candidate_fact`, `candidate_relation`, `candidate_mapping`,
`candidate_conflict`, `candidate_question`, `temporal_interval`. Solo fact,
relation e temporal interval hanno materializzazione corrente; gli altri restano
nel candidate registry.

### 7.2 Package e inbox

```powershell
dsl-manager ai package .workspaces/demo --revision REV_000001 --profile ai_package.default
dsl-manager ai package-batch .workspaces/demo --revision REV_000001 --revision REV_000002 --profile ai_package.default
dsl-manager ai inbox scan .workspaces/demo
dsl-manager ai import .workspaces/demo --package AIPKG_000001
```

Il package contiene manifest, inventario delle evidenze, istruzioni, schema e
template. DSL Manager non chiama autonomamente un servizio AI. L'output esterno
deve tornare come JSONL e passa dal validator; rimane pending.

Se le revisioni del package sono cambiate, l'import è bloccato. L'opzione:

```powershell
dsl-manager ai import .workspaces/demo --package AIPKG_000001 --allow-stale
```

registra un'eccezione esplicita, ma non rende le evidenze obsolete affidabili.

## 8. Temporalità

L'estrazione temporale è integrata nei servizi e in `batch consolidate`; non
esiste un leaf command temporale autonomo.

Le fonti includono proprietà OOXML, timestamp ZIP interni, metadata PDF/HTML,
dichiarazioni esplicite in testo/Markdown/SQL/XML/log, token del nome file e
`sources.first_seen_at`. Sono evidenze grezze con affidabilità e warning. I
timestamp filesystem `mtime`/`ctime` non sono usati come evidenza.

Il sistema raggruppa segnali indipendenti/correlati/duplicati, apre conflitti per
valori discordanti e crea candidati `temporal_interval` pending. Solo review
`confirmed` materializza l'intervallo.

Precisione:

- un anno copre l'intero anno;
- un mese copre l'intero mese;
- un giorno resta giorno;
- un `dateTime` conserva offset/timezone;
- timezone unknown o incompatible non viene troncata a data;
- più intervalli disgiunti restano più spells.

La temporalità non si propaga automaticamente da una sorgente a un fatto.

## 9. DSL v1/v2 e allow-incomplete

### 9.1 Compatibilità

Schema 1 è legacy e fisico; GEXF statico consuma soltanto schema 1. Schema 2 usa
effective views e include sempre `intervals`, anche quando vuoti; GEXF dinamico
consuma soltanto schema 2.

### 9.2 Riconciliazione aperta

Default sicuro:

```powershell
dsl-manager dsl render .workspaces/demo --schema-version 2
```

fallisce se la riconciliazione è aperta. Solo quando si accetta un output
esplicitamente incompleto:

```powershell
dsl-manager dsl render .workspaces/demo --schema-version 2 --allow-incomplete
```

Il render omette oggetti non effettivi e riporta warning/conteggi. Non cambia
decisioni e non rende mergeabili i pending. Lo schema 1 rifiuta
`--allow-incomplete`.

Per il grafo l'opzione è ammessa solo in modalità dinamica:

```powershell
dsl-manager graph export .workspaces/demo --snapshot-id DSL_000002 --dynamic --allow-incomplete
```

## 10. Diff

Stesso schema:

```powershell
dsl-manager dsl diff .workspaces/demo --from DSL_000002 --to DSL_000003
```

Fra schema 1 e 2 occorre consenso esplicito:

```powershell
dsl-manager dsl diff .workspaces/demo --from DSL_000001 --to DSL_000002 --cross-schema
```

Il report cross-schema separa differenze strutturali, di governance e temporali.
Non confronta implicitamente stato fisico ed effettivo come se fossero uguali.

## 11. GEXF 1.3 dinamico

Esempio strict:

```powershell
dsl-manager graph export .workspaces/demo --snapshot-id DSL_000002 --dynamic --timeformat date --temporal-output-mode strict
```

Un GEXF usa un solo `timeformat`. Per intervalli incompatibili:

```powershell
dsl-manager graph export .workspaces/demo --snapshot-id DSL_000002 --dynamic --timeformat date --temporal-output-mode omit
dsl-manager graph export .workspaces/demo --snapshot-id DSL_000002 --dynamic --temporal-output-mode separate
```

- `strict` fallisce;
- `omit` omette con warning;
- `separate` produce file distinti per profilo.

L'export dinamico è validato offline sia contro gli XSD GEXF 1.3 vendorizzati,
sia con controlli semantici: IDs e riferimenti, tipi, ordine, bounds inclusivi,
timeformat unico e contenimento degli edge nei nodi. La sola XSD non basta.

Limite noto: il budget designato per il totale nodi+archi GEXF non è ancora
applicato dal runtime.

## 12. Budget e sicurezza Excel

| Risorsa | Default | Hard maximum |
|---|---:|---:|
| file | 64 MiB | 256 MiB |
| entry ZIP | 20.000 | 100.000 |
| decompressione totale | 512 MiB | 2 GiB |
| rapporto compressione | 100:1 | 1.000:1 |
| part XML | 32 MiB | 128 MiB |
| fogli | 256 | 1.024 |
| celle | 2.000.000 | 10.000.000 |
| regioni | 10.000 | 50.000 |
| relazioni | 50.000 | 250.000 |
| output | 256 MiB | 1 GiB |
| timeout | 120 s | 600 s |
| memoria | 1 GiB | 4 GiB |
| evidenze temporali/sorgente | 100.000 | 1.000.000 |
| intervalli/soggetto | 1.000 | 10.000 |

Gli override non possono superare gli hard maximum o disabilitare hash check,
no-network, blocco DTD/entity, macro e link esterni. Su piattaforme senza hard
memory limit il report dichiara `memory_limit_mode=monitored`.

## 13. Esiti ed errori

Exit code principali:

| Exit | Significato operativo |
|---:|---|
| 0 | completato, anche con skip dichiarati |
| 2 | uso/configurazione/errore applicativo ordinario |
| 3 | input o profilo semantico rifiutato |
| 4 | conflitto, precondizione o riconciliazione |
| 5 | errore operativo/timeout worker |
| 6 | normalizzazione partial accettabile e dichiarata |

Gli errori attesi della CLI non devono mostrare traceback. Le reason più utili
sono `review_actor_required`, `review_head_conflict`,
`idempotency_payload_conflict`, `no_merge_eligible_candidates`,
`merge_review_precondition_failed`, `reconciliation_required`,
`ooxml_security_violation`, `ooxml_budget_exceeded`,
`temporal_profile_incompatible`, `gexf_xsd_invalid` e
`gexf_semantic_invalid`.

Review, derive, merge, reconcile e batch consolidato usano
`result_catalog_v1`. Limite noto: preflight OOXML/worker usa ancora
`catalog_version: 1` e i report temporali/GEXF non espongono l'envelope completo;
non assumere uniformità del catalogo in automazioni generiche.

## 14. Log, run e UI

```powershell
dsl-manager run status .workspaces/demo RUN_000001
dsl-manager log table .workspaces/demo
dsl-manager log table .workspaces/demo --format html --output run_log.html
dsl-manager log csv .workspaces/demo --output run_log.csv
dsl-manager ui serve .workspaces/demo --host 127.0.0.1 --port 8765
```

La UI è locale e read-only. Run ID e timestamp servono all'audit, ma non entrano
negli hash semantici.

## 15. Checklist prima di pubblicare

- Nessun candidato pending è stato trattato come mergeabile.
- Le correzioni hanno prodotto una nuova foglia, non un update dell'originale.
- Le riconciliazioni aperte sono state chiuse oppure l'incomplete è esplicito.
- `.xlsm` è stato letto direttamente; macro/link/formule non sono stati eseguiti.
- Il manifest è usato per la struttura e Docling solo come vista leggibile.
- Metadata e date del nome file sono stati revisionati come evidenze, non assunti
  come verità.
- Schema 1/statico e schema 2/dinamico non sono stati confusi.
- Il diff cross-schema è esplicito.
- GEXF dinamico ha superato XSD e validazione semantica offline.
- Gli artifact path sono relativi e gli hash escludono dati operativi.

## 16. Esempio Aurora

Il corpus completo e le guide per shell sono disponibili in:

- [LEGGIMI Aurora](../../projects/corpus%20aurora/corpus_mock_aurora_prestiti/LEGGIMI_PRIMA.md)
- [Guida PowerShell](../../projects/corpus%20aurora/corpus_mock_aurora_prestiti/materiale_di_supporto/guida_dsl-manager-powershell.md)
- [Guida CMD](../../projects/corpus%20aurora/corpus_mock_aurora_prestiti/materiale_di_supporto/guida_dsl-manager_cmd.md)
- [Checklist risultati](../../projects/corpus%20aurora/corpus_mock_aurora_prestiti/materiale_di_supporto/checklist_risultati_attesi.md)

L'[outline input-output](outline%20dsl%20manager%20flow%20from%20input%20to%20output.md)
offre una mappa più breve dell'intero viaggio.
