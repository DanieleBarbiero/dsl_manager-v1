# DSL Manager — documento di design v02

Stato: proposta implementativa vincolante  
Data di redazione: 2026-09-02  
Runtime di riferimento: Python `>=3.12,<3.13`  
Baseline: repository e worktree osservati durante la redazione, senza ricostruzioni da `HEAD`

## 1. Sintesi

Questa revisione completa il percorso già implementato dalle slice 01–19 senza riscriverlo. Il sistema dispone di workspace, registro SQLite, scansione, worker, normalizzazione Docling, parser strutturali, import di candidati, merge, DSL v1, diff, golden, batch, GEXF statico, log viewer e UI di sola lettura. Mancano però tre passaggi indispensabili per rendere il registro affidabile come base di modernizzazione:

1. i risultati deterministici dei parser non diventano candidati senza un passaggio esterno;
2. un candidato strutturalmente valido è oggi consumabile dal merge anche senza una decisione persistita;
3. Excel e la temporalità semantica non hanno ancora un contratto end-to-end verificabile.

La soluzione introduce un unico ciclo di governo:

`evidenza → pending → decisione persistita → merge-eligible → merge autoritativo`

La validità strutturale non equivale mai a eleggibilità al merge. Una decisione positiva è valida solo se è la testa corrente della catena del soggetto; il merge materializza fatti o relazioni, mentre le viste effettive determinano ciò che è ancora sostenuto da decisioni correnti. Se una decisione già materializzata viene superata, il supporto cessa immediatamente nelle viste effettive e si apre una riconciliazione esplicita. Snapshot storici già emessi restano immutabili.

Il lavoro è suddiviso esattamente nelle slice 20–29. Le prime tre chiudono candidati, review, derivazione deterministica e batch; le successive tre introducono Excel trasparente e il nucleo temporale; le ultime tre consolidano temporalità, corpus Aurora e documentazione. Non sono previste slice ulteriori in questo documento.

## 2. Relazione con l'architettura esistente

La v01 resta la baseline concettuale per registro append-only, evidenza obbligatoria, artefatti deterministici e separazione tra estrazione e interpretazione. La v02 sostituisce la v01 quando tratta review, merge eligibility, viste effettive, Excel, temporalità, DSL v2 e GEXF dinamico.

Le decisioni qui descritte rispettano lo stato corrente:

- il database è SQLite e possiede migrazioni v1–v6;
- `candidate_batches.input_path` è attualmente `NOT NULL`;
- `candidate_records.candidate_id` è un identificatore dichiarato dalla sorgente e non è univoco globalmente;
- il merge corrente legge candidati accettati e materializza fatti/relazioni senza review persistita;
- il renderer DSL v1 e il diff leggono stati fisici;
- l'export esistente usa GEXF `1.2draft`, modalità statica e DSL v1;
- Docling è fissato a `2.97.0`, ma il routing corrente non include `.xlsx` o `.xlsm`;
- i parser DDL, XML, codice database e log producono metadati strutturati, non candidati;
- test e report delle slice 01–19 costituiscono storia utile, non prova che il worktree attuale sia verde.

I contratti pubblici esistenti restano compatibili per impostazione predefinita: DSL v1 e GEXF statico continuano a funzionare sulla semantica fisica legacy finché il chiamante non richiede schema v2 o export dinamico. Le nuove funzioni non cambiano il contenuto degli snapshot già creati.

## 3. Obiettivi e non-obiettivi

### 3.1 Obiettivi

- Rendere persistenti, concorrenti, idempotenti e auditabili le decisioni umane e automatiche sui candidati.
- Impedire a candidati `pending`, `rejected` o `superseded` di diventare autoritativi.
- Derivare candidati tecnici deterministici dagli output già prodotti dai parser, senza inventare semantica di dominio.
- Integrare derivazione, review automatica consentita e merge nel batch con report stabili.
- Accettare `.xlsx` e `.xlsm` direttamente, senza conversione, ricalcolo o esecuzione di contenuto attivo.
- Conservare due viste dello stesso workbook: normalizzazione Docling leggibile e manifest OOXML strutturale/provenienziale.
- Modellare l'evidenza temporale grezza separatamente dall'intervallo validato.
- Emissione deterministica di DSL v2 temporale e GEXF 1.3 dinamico validato offline.
- Rendere Aurora un fixture end-to-end realistico e riproducibile.
- Fornire per ogni slice un prompt d'implementazione completo.

### 3.2 Non-obiettivi

- Supportare `.xls`, `.xlsb`, `.ods` o formati spreadsheet diversi da `.xlsx`/`.xlsm`.
- Avviare Excel, LibreOffice, macro, query, collegamenti esterni o ricalcolo di formule.
- Considerare il testo Markdown di Docling fonte strutturale primaria per Excel.
- Trasformare metadati incorporati, nomi file o timestamp del filesystem in verità temporale.
- Introdurre un secondo motore di review specifico per la temporalità.
- Modificare snapshot storici, riscrivere decisioni o cancellare evidenza.
- Aggiungere chiamate AI reali ai test o consentire a un generatore di scrivere direttamente nel registro autoritativo.

## 4. Navigazione e matrice delle slice

### 4.1 Indice

- [5. Linguaggio e invarianti](#5-linguaggio-e-invarianti)
- [6. Flusso end-to-end](#6-flusso-end-to-end)
- [7. Review, correzione e riconciliazione](#7-review-correzione-e-riconciliazione)
- [8. Modello dati e migrazioni](#8-modello-dati-e-migrazioni)
- [9. Canonicalizzazione, hash e idempotenza](#9-canonicalizzazione-hash-e-idempotenza)
- [10. Derivazione deterministica](#10-derivazione-deterministica)
- [11. Excel trasparente e sicuro](#11-excel-trasparente-e-sicuro)
- [12. Temporalità semantica](#12-temporalità-semantica)
- [13. DSL v2, diff e GEXF 1.3](#13-dsl-v2-diff-e-gexf-13)
- [14. CLI, configurazione e catalogo esiti](#14-cli-configurazione-e-catalogo-esiti)
- [15. Sicurezza, budget e offline](#15-sicurezza-budget-e-offline)
- [16. Test e fixture](#16-test-e-fixture)
- [17. Tracciabilità](#17-tracciabilità)
- [18. Piano per slice](#18-piano-per-slice)
- [19. Roadmap e criteri globali](#19-roadmap-e-criteri-globali)
- [20. Fonti esterne verificate](#20-fonti-esterne-verificate)
- [21. Auto-verifica del design](#21-auto-verifica-del-design)
- [22. Prompt di implementazione](#22-prompt-di-implementazione)

### 4.2 Matrice compatta

| Slice | Obiettivo | Dipendenze | Capacità consegnata | Migrazione | Fixture guida | Artefatti |
|---|---|---|---|---|---|---|
| 20 | Fondazione candidati/review | 01–19 | decisioni, correzione, viste effettive, primo `DDL table → fact` | v7 | DB v6 realistico, DDL minimo | report review/derive, batch correzione |
| 21 | Regole deterministiche complete | 20 | DDL FK, XML, codice DB, log | — | parser fixture 12–14 | batch candidati e report regole |
| 22 | Consolidamento batch | 20–21 | derive/review/merge orchestrati e retry convergente | — | corpus misto | report batch unificato |
| 23 | Ingest Excel trasparente | 22 | `.xlsx`/`.xlsm`, byte immutabili, preflight sicuro, Docling 2.97.0 | — | workbook reale minimo | `normalized.json`, `normalized.md`, preflight report |
| 24 | Struttura workbook | 23 | manifest OOXML, regioni e frammenti | v8 | workbook strutturale | `workbook_manifest.json`, fragments |
| 25 | Candidati Excel | 20, 24 | regole tecniche da workbook | — | regioni nominate e tabelle | candidate batch/report |
| 26 | Nucleo temporale completo | 20, 22 | evidenza→review→intervallo, DSL v2, hash, GEXF 1.3 offline | v9 | date core/props esplicite | DSL v2, diff, GEXF dinamico |
| 27 | Consolidamento temporale | 26 | fonti multiple, precisione, conflitti, batch/reconcile/golden | v10 | corpus temporale | report concordanza/conflitto |
| 28 | Aurora aggiornato | 23–27 | fixture E2E Excel/temporale e guide coerenti | — | corpus Aurora v2 | manifest atteso, golden, checklist |
| 29 | Consolidamento documentale | 20–28 | manuale, contratti, analisi e guida operativa allineati | — | esempi documentali | documentazione verificata |

## 5. Linguaggio e invarianti

### 5.1 Termini

- **Evidenza**: dato osservabile con origine e localizzatore; non è una decisione.
- **Candidato strutturalmente valido**: record conforme allo schema e collegato a evidenza esistente. Nasce `pending`.
- **Decisione**: evento append-only umano o automatico sulla testa nota di un soggetto.
- **Testa**: unica decisione corrente di un soggetto.
- **Merge-eligible**: candidato che è foglia corrente della propria linea di correzione e la cui testa corrente è `confirmed`.
- **Merge autoritativo**: transazione che materializza o collega il candidato a fatti/relazioni.
- **Effettivo**: oggetto sostenuto da almeno una evidenza il cui candidato/lineage ha testa corrente positiva.
- **Riconciliazione**: lavoro persistente necessario quando lo stato fisico materializzato diverge dalle viste effettive.
- **Rifiuto strutturale**: record in `rejected_candidates`; è distinto da una decisione di review `rejected`.
- **Correzione**: nuovo candidato completo in un nuovo batch, collegato una sola volta alla foglia precedente; non è una mutazione del candidato originale.

### 5.2 Invarianti

1. Ogni candidato valido ha un `candidate_record_id` persistente; `candidate_id` resta dichiarativo e può ripetersi tra batch.
2. Esiste al massimo una testa di decisione per `(subject_type, subject_id)`.
3. `supersedes_decision_id` deve riferirsi allo stesso soggetto e le catene devono essere acicliche.
4. Una scrittura di decisione confronta `expected_head_decision_id` nella stessa transazione che inserisce la nuova decisione e aggiorna la testa.
5. Un replay con la stessa chiave e lo stesso `request_payload_hash` restituisce la decisione esistente prima del controllo della testa; stessa chiave con hash diverso è conflitto.
6. Un no-op semantico non crea una decisione; può creare solo una nota audit separata, priva di hash semantico.
7. Solo una testa `confirmed` è positiva. `rejected` e `superseded` non lo sono.
8. Una correzione ha al massimo un figlio; si applica alla foglia attesa e non crea rami.
9. Solo la foglia confermata di una linea di correzione è merge-eligible; un antenato non torna eleggibile se la foglia viene poi rifiutata.
10. Il merge rilegge testa e foglia nella propria transazione.
11. Le viste effettive escludono immediatamente un supporto la cui decisione positiva è stata superata.
12. Un fatto o una relazione resta effettivo finché ha almeno un altro supporto positivo corrente.
13. Con riconciliazioni aperte, render, diff ed export falliscono per default con `reconciliation_required`.
14. Solo DSL v2 ammette `--allow-incomplete`; omette gli oggetti non più effettivi e riporta warning e conteggi. DSL v1 resta bloccato.
15. Snapshot e graph export già registrati non cambiano.
16. Percorsi assoluti, timestamp operativi, identificatori di run e note audit non entrano negli hash semantici.

## 6. Flusso end-to-end

```text
byte sorgente immutabili
  ├─ parser/preflight → evidenza strutturale
  ├─ normalizzazione → artefatti leggibili
  └─ estrattore temporale → evidenza temporale grezza
             ↓
regole versionate → candidate batch → validazione strutturale
             ↓                         └─ rejected_candidates
          pending
             ↓
review comune (human | policy automatica)
             ↓
decisione persistita: confirmed | rejected | superseded
             ↓
foglia confirmed → merge-eligible → merge autoritativo
             ↓
effective_* → DSL v2 / diff / GEXF dinamico
```

I parser producono osservazioni. Le regole deterministiche creano candidati tecnici. Le policy automatiche possono confermare soltanto regole nominate e versionate; un livello di confidenza, da solo, non è autorizzazione. Candidati interpretativi, inferiti, ambigui o in conflitto restano in coda umana.

## 7. Review, correzione e riconciliazione

### 7.1 API comune

Il servizio `CandidateReviewService` è l'unico punto di scrittura per attori umani e automatici. Accetta soggetto, operazione, outcome, reason normalizzata, eventuale payload corretto, riferimenti all'evidenza, identità attore/policy, testa attesa e chiave idempotente. Restituisce sempre `decision_id`, testa precedente e corrente, chiave effettiva, hash della richiesta, indicazione `created|replayed|semantic_noop` e stato di riconciliazione.

Per un attore automatico `policy_id` e `policy_version` sono obbligatori. Per un attore umano sono `null`. L'identità umana proviene da `--actor-id` o `review.default_actor_id`; in assenza l'operazione fallisce con `review_actor_required`. Non si usa mai username, hostname o account di sistema. `reject` e `correct` richiedono una motivazione non vuota; `confirm` usa la motivazione esplicita oppure `human_confirmed`.

### 7.2 Concorrenza e idempotenza

La transazione usa `BEGIN IMMEDIATE`, cerca prima `(actor_type, actor_id, idempotency_key)`, verifica l'hash di richiesta, poi legge e confronta la testa. Il confronto avviene anche quando la testa attesa è `null`. Una testa stantia produce `review_head_conflict`, nessuna mutazione e nessuna seconda testa.

La chiave automatica è una funzione deterministica di soggetto, hash del candidato, policy id/versione, operazione, payload semantico e testa attesa; la testa è solo un guard di concorrenza e non entra nel `semantic_payload_hash`. Per l'attore umano `--idempotency-key` è accettato. Se manca, il client deriva e stampa una chiave da attore, soggetto, operazione e `request_payload_hash`; un retry dopo crash la riusa. Una ripetizione intenzionale dopo una decisione intermedia richiede una nuova chiave esplicita.

### 7.3 Correzione

`correct` esegue in un'unica transazione:

1. verifica che il soggetto sia la foglia attesa;
2. registra sul candidato originale una nuova decisione di testa `superseded`;
3. crea `candidate_correction` con `correction_group_id`, delta, riferimenti alle evidenze e reason;
4. crea un nuovo batch già `completed`, `origin_type=human_correction`, `origin_ref=review://CORR_000001` nel formato sequenziale effettivo, `input_path=null`, conteggi coerenti (`1` ricevuto, `1` valido, `0` rifiutati);
5. crea un nuovo candidato con payload completo, nuovo `candidate_record_id` e `supersedes_candidate_record_id` uguale all'originale;
6. registra la testa `confirmed` del candidato sostitutivo;
7. apre la riconciliazione se il supporto originale era materializzato;
8. restituisce anche il nuovo `batch_id`.

Il payload originale non viene modificato e un batch d'import completato non viene riaperto. I riferimenti della correzione devono puntare a evidenza esistente oppure a una nuova attestazione umana; sono facoltativi solo per correzioni puramente canoniche che non cambiano il significato. Delta, originale, attestazione e reason restano audit separato dal payload semantico. Il vincolo unico sul genitore impedisce branching; un trigger/controllo ricorsivo impedisce cicli.

### 7.4 Merge misto

Il merge predefinito tratta un batch misto senza far diventare gli skip errori di batch:

- unisce solo candidati merge-eligible;
- conta separatamente `skipped_pending`, `skipped_rejected`, `skipped_superseded`, `skipped_no_positive_head` e `skipped_non_leaf`;
- termina `0` se almeno un candidato è unito e non ci sono errori;
- se non esiste alcun eleggibile termina `4`, `no_merge_eligible_candidates`, senza mutazioni;
- la modalità stretta esplicita `--strict-review` fallisce con `4` e rollback dell'intero tentativo se incontra uno skip.

Il report include set ordinato degli ID uniti e saltati, ragioni, decisioni osservate e contatori. Un replay converge sugli stessi supporti grazie ai vincoli già esistenti e alle nuove chiavi.

### 7.5 Viste effettive e riconciliazione

Le viste SQL `effective_fact_evidence` e `effective_relation_evidence` includono solo evidenze materializzate la cui origine candidata è la foglia e ha testa corrente `confirmed`. `effective_facts` e `effective_relations` includono un oggetto se esiste almeno una riga di evidenza effettiva positiva. Queste viste alimentano DSL v2, diff v2 e ogni export dinamico.

`reconciliation_required` è una coda persistente, non un flag calcolato in memoria. Il merge del batch di correzione, nella stessa transazione, materializza la sostituzione, disattiva/compensa il supporto originale e chiude la voce. Un retry standalone può rimuovere un supporto superato; se la sostituzione non è ancora materializzata la voce resta aperta con `replacement_merge_pending`. Un semplice rifiuto senza sostituzione può chiudersi dopo la compensazione. Qualunque ordine tra review, crash, retry e merge converge allo stesso insieme effettivo.

## 8. Modello dati e migrazioni

### 8.1 Migrazione v7 — review, lineage e derivazione

La slice 20 aggiunge:

```text
review_decisions(
  decision_id PK, subject_type, subject_id, actor_type, actor_id,
  outcome, reason, run_id, created_at, supersedes_decision_id,
  expected_head_decision_id, idempotency_key,
  request_payload_hash, semantic_payload_hash,
  policy_id NULL, policy_version NULL,
  request_payload_json, semantic_payload_json
)
review_subject_heads(subject_type, subject_id, decision_id, updated_at,
                     PK(subject_type, subject_id), UNIQUE(decision_id))
review_decision_evidence(decision_id, evidence_ref, ordinal,
                         PK(decision_id, ordinal))
review_audit_notes(note_id PK, subject_type, subject_id, actor_type, actor_id,
                   reason, request_payload_hash, idempotency_key, run_id, created_at)
candidate_lineage(candidate_record_id PK, root_candidate_record_id,
                  parent_candidate_record_id NULL UNIQUE, correction_group_id NULL)
candidate_corrections(correction_id PK, correction_group_id UNIQUE,
                      original_candidate_record_id, replacement_candidate_record_id UNIQUE,
                      delta_json, correction_evidence_refs_json, reason, created_at)
reconciliation_required(reconciliation_id PK, subject_type, subject_id,
                        replacement_subject_id NULL, reason, opened_by_decision_id,
                        status, opened_at, closed_at NULL, closed_by_run_id NULL)
candidate_derivation_runs(derivation_id PK, run_id, rule_set_version,
                          source_revision_id NULL, batch_id NULL, status,
                          counters_json, report_path, created_at, completed_at NULL)
```

`candidate_batches.input_path` diventa nullable con ricostruzione tabella SQLite. Un `CHECK` richiede il percorso per origini file e lo vieta per `human_correction`; origini interne deterministiche possono usare `null` con `origin_ref` obbligatorio. Indici unici coprono `(actor_type, actor_id, idempotency_key)`, ID di correzione e testa. Trigger e validazione di servizio impongono stesso soggetto e aciclicità. Gli esiti ammessi iniziali sono `confirmed`, `rejected`, `superseded`.

La migrazione popola `candidate_lineage` per ogni candidato esistente. Per candidati che sostengono fatti/relazioni `active` derivati da assertion `explicit` o `observed`, crea decisioni sintetiche `confirmed` con attore `system/migration`, policy `legacy_backfill/1` e ID/chiavi deterministiche dal `candidate_record_id`. Candidati `inferred`, `pending_review`, `ambiguous` o `conflicted` non sono confermati e rimangono in coda. Non si modificano snapshot preesistenti. I renderer schema 1 e gli export statici legacy continuano a leggere gli stati fisici; schema 2 e nuovi export leggono le viste effettive.

### 8.2 Migrazione v8 — workbook

La slice 24 aggiunge cataloghi normalizzati per rintracciare gli artefatti, senza duplicare l'intero XML:

```text
workbook_manifests(manifest_id PK, source_revision_id UNIQUE, schema_version,
                   content_hash, manifest_hash, artifact_path, status, warnings_json)
workbook_sheets(sheet_id PK, manifest_id, sheet_index, name, visibility,
                relationship_id, part_name, max_row, max_column,
                UNIQUE(manifest_id, sheet_index), UNIQUE(manifest_id, name))
workbook_regions(region_id PK, sheet_id, ordinal, start_cell, end_cell,
                 region_kind, region_hash, fragment_id NULL,
                 UNIQUE(sheet_id, ordinal))
```

Formule, cached values, celle, merge, named ranges, relazioni, external link e macro rimangono nel manifest canonico; il DB conserva chiavi e hash utili a query e idempotenza.

### 8.3 Migrazione v9 — nucleo temporale

La slice 26 aggiunge:

```text
raw_temporal_evidence(
  temporal_evidence_id PK, target_subject_type, target_subject_id,
  source_revision_id, source_fragment_id NULL, source_key, source_format,
  raw_value, extraction_method, extraction_version, precision,
  timezone_status, timezone_value NULL, initial_reliability,
  warnings_json, evidence_hash UNIQUE, created_at
)
temporal_candidate_details(
  candidate_record_id PK, target_subject_type, target_subject_id,
  normalized_start NULL, normalized_end NULL, original_precision,
  timezone_status, timezone_value NULL, bounds_semantics,
  derivation_policy_id, derivation_policy_version
)
temporal_candidate_evidence(candidate_record_id, temporal_evidence_id, ordinal,
                            PK(candidate_record_id, ordinal))
temporal_intervals(
  interval_id PK, subject_type, subject_id, start_value NULL, end_value NULL,
  timeformat, timezone_value NULL, original_precision, bounds_semantics,
  decision_id, source_candidate_record_id, interval_hash,
  created_at, UNIQUE(subject_type, subject_id, interval_hash)
)
```

Un candidato temporale è comunque un `candidate_record`: il tipo viene esteso a `temporal_interval`; la review usa il medesimo servizio e il medesimo `candidate_record_id`. Il target dell'intervallo è uno fra `source_revision`, `source_fragment`, `candidate_record`, `fact`, `relation`.

### 8.4 Migrazione v10 — consolidamento temporale

La slice 27 aggiunge, solo dove non bastano le tabelle v9:

```text
temporal_evidence_groups(group_id PK, target_subject_type, target_subject_id,
                         policy_id, policy_version, group_hash UNIQUE,
                         assessment, created_at)
temporal_evidence_group_members(group_id, temporal_evidence_id,
                                independence_class, ordinal,
                                PK(group_id, temporal_evidence_id))
temporal_conflicts(conflict_id PK, target_subject_type, target_subject_id,
                   group_id, reason, status, created_at, resolved_by_decision_id NULL)
```

Più righe in `temporal_intervals` per soggetto abilitano intervalli disgiunti. Nessuna colonna `first_seen` viene introdotta: il solo nome corrente è `sources.first_seen_at`.

## 9. Canonicalizzazione, hash e idempotenza

### 9.1 Profilo JSON canonico condiviso

Tutti i componenti usano una sola funzione versionata `canonical_json_v1`:

- encoding UTF-8, Unicode normalizzato NFC;
- oggetti con chiavi ordinate per sequenza di code point Unicode dopo NFC;
- nessuno spazio, indentazione, BOM o slash superfluo;
- escape JSON solo per virgolette, backslash e caratteri di controllo, con non-ASCII emesso direttamente;
- `null` è conservato e resta distinto da un campo assente;
- booleani minuscoli JSON;
- interi in base dieci senza `+` e senza zeri iniziali; `-0` diventa `0`;
- numeri non interi vengono convertiti nel modello tipizzato in stringhe decimali canoniche prima dell'hash; `NaN`, infinito e float binari non sono ammessi;
- le liste mantengono l'ordine semantico; gli insiemi sono ordinati dal produttore con una chiave documentata prima della serializzazione;
- i byte canonici usati dagli hash non hanno newline finale; gli artefatti `.json` aggiungono esattamente un LF e il loro file hash copre anche quel LF.

Golden condivisi coprono accenti composti/decomposti, emoji, controlli, chiavi non ASCII, null/mancante, interi grandi, zero negativo rifiutato/normalizzato, decimali tipizzati, liste ordinate e set preordinati.

### 9.2 Hash delle decisioni

`request_payload_hash = sha256(canonical_json_v1(request_payload))`, dove la richiesta include almeno soggetto, operazione, outcome, reason normalizzata, payload/delta di correzione, riferimenti evidenza ordinati, attore, policy e testa attesa.

`semantic_payload_hash` include soggetto, outcome, payload corretto completo, riferimenti evidenza semantici e policy applicata. Esclude reason, attore, decision ID, chiave idempotente, testa attesa, timestamp e run. Se l'hash semantico equivale alla testa corrente, il servizio restituisce `semantic_noop` senza nuova decisione.

### 9.3 Hash autoritativi

Il registry/DSL/diff include, per ogni supporto effettivo, hash semantico e outcome della testa corrente, policy id/versione ed eventuale contenuto corretto. Non include note audit, retry, timestamp operativi, run ID o percorsi assoluti. Gli intervalli contribuiscono solo dopo risoluzione e review, mediante valori normalizzati, `timeformat`, timezone, precisione originale e `bounds_semantics`; l'evidenza temporale grezza resta tracciata ma non altera direttamente l'hash DSL.

## 10. Derivazione deterministica

### 10.1 Contratto delle regole

Una regola dichiara `rule_id`, `rule_version`, parser e schema di input, tipo candidato, assertion prodotta, algoritmo di localizzazione dell'evidenza e policy automatica eventualmente autorizzata. L'output passa sempre dal normale importer di candidati; non scrive direttamente fatti o relazioni. Un `candidate_id` è deterministico nel contesto del batch, ma l'identità persistente resta `candidate_record_id`.

Le regole tecniche iniziali sono:

| Regola | Input osservato | Candidato | Assertion | Review predefinita |
|---|---|---|---|---|
| `ddl_table_fact/1` | tabella parsata con locator | fact tecnico `database_table` | `explicit` | auto consentita con policy nominata |
| `ddl_column_fact/1` | colonna e tipo dichiarati | fact tecnico `database_column` | `explicit` | auto consentita |
| `ddl_fk_relation/1` | FK esplicita e target risolto | relation `references` | `explicit` | auto consentita |
| `xml_form_structure/1` | form, block, item dichiarati | fact tecnico | `explicit` | auto consentita |
| `xml_table_usage/1` | table reference esplicita | relation `reads_from`/`writes_to` solo se parser distingue l'operazione | `explicit` | auto solo sul segnale esplicito |
| `db_code_unit/1` | procedura/funzione/trigger dichiarato | fact tecnico | `explicit` | auto consentita |
| `db_code_dependency/1` | read/write/call estratto | relation tecnica corrispondente | `observed` | auto consentita se locator completo |
| `log_event_observation/1` | evento parsato | fact osservazionale | `observed` | resta pending salvo policy esplicita |

La slice 20 consegna fondazione, catalogo, report e sola regola `ddl_table_fact/1`. La slice 21 completa le altre regole in sottopassi interni DDL/FK, XML, codice DB e log; tali sottopassi non sono nuove slice.

Il validator rifiuta template irrisolti (`${...}`, `{{...}}` o token equivalenti) nei campi destinati a diventare semantica. Una regola non può inferire significato di dominio da un nome tecnico. Dati incompleti generano candidato pending o report `derivation_insufficient_evidence`, mai un fatto diretto.

### 10.2 CLI e report

`candidates derive <workspace> [--source-revision-id ID] [--rule RULE] [--run-id ID]` elabora in ordine stabile `source_revision_id`, parser kind, localizzatore e rule ID. Crea un batch per invocazione, anche vuoto, con origine `deterministic_derivation` e `origin_ref=derive://<derivation_id>`. Il report elenca versione rule set, input, prodotti, deduplicati, rifiutati, pending, auto-confermati e motivi. Nessuna chiamata AI è ammessa.

## 11. Excel trasparente e sicuro

### 11.1 Una sola sequenza di byte

Per una revisione già registrata, il normalizzatore legge il file una sola volta in un buffer limitato, calcola SHA-256 e confronta il valore con `source_revisions.content_hash`. Una differenza produce `source_revision_changed` prima di qualsiasi parsing. Preflight e Docling ricevono cursori indipendenti sulla stessa sequenza immutabile; il percorso non viene riaperto. Il `DocumentStream` ha il nome originale, quindi conserva `.xlsx` o `.xlsm`.

`.xlsx` è instradato a `InputFormat.XLSX`. `.xlsm` viene instradato esplicitamente allo stesso formato solo dopo aver verificato estensione e content type OOXML macro-enabled. Questa è una decisione applicativa da provare con un file `.xlsm` reale: Docling 2.97.0 documenta XLSX, non XLSM come formato autonomo. Un fallimento della prova è bloccante per la slice 23 e non autorizza conversione o downgrade.

Docling produce `normalized.json` e la proiezione leggibile `normalized.md`. `normalized.json` e il manifest OOXML costituiscono congiuntamente la vista derivata autoritativa per struttura e provenance, mai per significato di dominio: il primo conserva il modello/provenance Docling, il secondo è prevalente per struttura OOXML lossless, formule e cached values. Il codice v2.97.0 usa il backend Excel con `data_only=True`, quindi la sola vista Docling può esporre cached values ma non è il deposito autoritativo delle formule. `normalized.md` serve a lettura e chunk/AI e non è fonte primaria.

### 11.2 Preflight OOXML minimo

Il parser tratta il package come input non fidato, non estrae file sul filesystem e usa lettura streaming limitata. Prima di Docling verifica:

- firma ZIP e directory centrale coerente;
- nomi entry validi, nessun assoluto, drive/UNC, backslash ambiguo, segmento `..`, percent-decoding evasivo o collisione esatta/case-fold;
- presenza e unicità di `[Content_Types].xml`, relazione package `_rels/.rels`, workbook part e relazioni workbook minime; rifiuto di dichiarazioni duplicate `Default/Extension` o `Override/PartName` nei content type;
- content type coerente con `.xlsx` o `.xlsm`;
- XML well-formed senza DTD, entity declaration o entity expansion;
- relationship XML ben formato con attributi obbligatori e `Id` unici all'interno di ciascuna part;
- target interni normalizzati entro il package;
- target esterni URI assoluti sintatticamente validi, senza caratteri di controllo, userinfo o schemi attivi; non vengono mai dereferenziati;
- conteggi, dimensioni compresse/decompresse, rapporto di compressione e output entro budget.

Il preflight minimo nasce nella slice 23; la slice 24 estende lo stesso parser per manifest e regioni, senza introdurne uno parallelo. I contatori streaming ricavano i bytes decompressi effettivamente letti e non si fidano dei soli valori dichiarati nella directory centrale ZIP.

### 11.3 Manifest canonico

`workbook_manifest.json`, `schema_version="1"`, ha ordine stabile e almeno:

```text
source_revision {id, content_hash, extension, package_content_type}
workbook {part_name, date_system, calculation_properties, macro_presence}
sheets[] {index, name, visibility, part_name, relationship_id, dimensions,
          cells[], merged_ranges[], regions[]}
cells[] {coordinate, row, column, type, value, formula, cached_value, style_id}
named_ranges[] {scope: workbook|sheet, sheet_name|null, name, refers_to}
relationships[] {source_part, relationship_id, type, target, target_mode}
external_links[] {source_part, relationship_id, target, disposition}
macros {present, part_name|null, content_hash|null, executed:false}
warnings[] {reason, locator, severity}
```

Fogli sono ordinati per indice workbook; celle per riga/colonna; merge per coordinata; named range per scope/nome; relazioni per part/rId; warning per reason/locator. Visibilità distingue `visible`, `hidden`, `very_hidden`. Tipi cella distinguono stringa, numero decimale canonico, booleano, data, errore e blank. Il manifest non contiene timestamp di esecuzione o percorsi assoluti.

Le regioni sono componenti connesse di celle non vuote, unite anche da merge e intervalli nominati, poi segmentate da righe/colonne vuote secondo una regola versionata. Ogni frammento porta sheet, rettangolo di coordinate, celle ordinate, riferimenti a formula/cached e locator OOXML. `normalized.md` serve a lettura e chunk/AI; manifest e frammenti sono la fonte primaria per derivazioni strutturali.

## 12. Temporalità semantica

### 12.1 Evidenza grezza e matrice delle fonti

Ogni estrattore persiste valore grezzo, chiave sorgente, formato, metodo/versione, precisione dichiarata o stimata, stato timezone, affidabilità iniziale, warning e localizzatore. I timestamp del filesystem sono esclusi.

| Formato/segnale | Chiavi | Ruolo iniziale | Note |
|---|---|---|---|
| OOXML core properties | `dcterms:created`, `dcterms:modified`, eventuali campi custom espliciti | primaria come evidenza incorporata, non come verità | confrontare identità/produttore e altre fonti |
| OOXML app properties e timestamp ZIP | application/versione e tempi entry | secondaria | spesso correlati allo strumento di generazione |
| PDF | Info dictionary e XMP | primaria/secondaria secondo coerenza | conservare entrambi e segnalare divergenze |
| HTML | `time`, meta dichiarativi, JSON-LD esplicito | primaria solo se semantica dichiarata | date nel testo sono candidati interpretativi |
| testo/Markdown/SQL/XML/log | dichiarazioni nel contenuto, nome file, `sources.first_seen_at` | dichiarazione contenuto > nome file > first_seen_at | nessun metadato nativo implicito |

I campi “created/modified” descrivono normalmente il documento o il package, non automaticamente il periodo di validità del fatto. Il corpus Aurora già mostra perché: un file che nel nome/contenuto richiama il 2025 può avere proprietà OOXML del 2026; un manuale 2024 può contenere proprietà del 2013. Tali segnali devono diventare evidenze in conflitto, non intervalli validati automaticamente.

### 12.2 Dalla prova all'intervallo

La pipeline è:

1. estrazione append-only di evidenza grezza;
2. normalizzazione sintattica senza colmare parti mancanti;
3. raggruppamento per indipendenza e correlazione;
4. creazione di candidato `temporal_interval` con target esplicito;
5. review comune;
6. materializzazione in `temporal_intervals` solo dalla foglia `confirmed`;
7. proiezione su DSL v2 e GEXF.

Fonti indipendenti e concordanti possono aumentare affidabilità; copie, campi prodotti dallo stesso tool o segnali derivati l'uno dall'altro non contano come conferme indipendenti. Contraddizioni, bassa qualità o ambiguità mantengono il candidato pending e producono conflitto. Alta confidenza non equivale a validazione. Segnali interpretativi o inferiti richiedono review umana.

### 12.3 Granularità e propagazione

Un intervallo appartiene direttamente a `source_revision`, `source_fragment`, `candidate_record`, `fact` o `relation`. L'intervallo della sorgente non si eredita automaticamente. Ogni propagazione è una regola versionata e genera un nuovo candidato con evidenze:

- `explicit_copy`: solo una dichiarazione afferma esplicitamente la stessa validità per il target;
- `intersection`: intersezione non vuota di vincoli indipendenti compatibili;
- `aggregation`: insieme di intervalli disgiunti, senza colmare gap;
- `conflict`: nessuna proiezione quando i limiti si contraddicono.

Il nucleo della slice 26 supporta zero o un intervallo validato per oggetto. La slice 27 abilita multipli intervalli, correlazione avanzata, intersezione e aggregazione.

### 12.4 Precisione e timezone

Valori `date` completi usano precisione giorno. Anno o mese non vengono completati silenziosamente: solo `bounds_semantics=coverage_envelope` può rappresentare `2025` come `[2025-01-01, 2025-12-31]` o `2025-03` come `[2025-03-01, 2025-03-31]`, conservando `original_precision=year|month`. Valori `dateTime` sono accettati solo con offset/Z esplicito o timezone risolta da una policy dichiarata; un timezone sconosciuto resta evidenza/candidato e non entra nel grafo.

Ogni file GEXF usa un solo `timeformat`, `date` oppure `dateTime`, e solo rappresentazione a intervalli. Segnali sconosciuti o incompatibili vengono omessi con conteggio in modalità incompleta, separati in un export dedicato se richiesto, oppure causano fallimento in modalità stretta. Non si tronca un `dateTime` a `date` e non si inventa un orario.

## 13. DSL v2, diff e GEXF 1.3

### 13.1 DSL schema 2

Il comando è `dsl render <workspace> --schema-version 2`; il default resta `1`. Un documento v2 contiene esattamente `metadata.schema_version="2"`. In `metadata.temporal` dichiara `representation="interval"`, `base="day"|"timestamp"`, `gexf_timeformat="date"|"dateTime"` e `timezone` esplicita oppure `"unknown"`; `day` mappa solo a `date`, `timestamp` solo a `dateTime`. Ogni fatto e relazione ha una collezione `intervals`, presente anche se vuota. Nel nucleo può contenere al massimo una voce; dopo la slice 27 può contenerne più di una, in ordine canonico.

Il renderer persiste e rilegge lo snapshot v2 prima di confermarne il successo. Hash e diff usano solo viste effettive e temporalità risolta. Un diff tra v1 e v2 è rifiutato nel nucleo; la slice 27 introduce un confronto cross-schema esplicito che separa variazioni strutturali, di governance e temporali.

### 13.2 GEXF dinamico

L'export dinamico accetta solo snapshot DSL v2. Produce namespace `http://gexf.net/1.3`, `version="1.3"`, `graph mode="dynamic"`, `timerepresentation="interval"` e un solo `timeformat`. Per intervalli multipli usa `<spells><spell .../></spells>` su nodi e archi. In GEXF 1.3 `start` e `end` sono inclusivi; il validator applicativo verifica inoltre che ogni intervallo dell'arco sia contenuto in quelli dei due nodi, cosa che l'XSD non garantisce.

La validazione ha due livelli:

1. `lxml==6.1.2` con `XMLSchema`, parser `no_network=True`, DTD/entity disabilitati e resolver allowlist esclusivamente locale;
2. controlli semantici per namespace, mode, timeformat, bounds inclusivi, ordine e validità degli spell, ordinamento stabile di nodi e archi, riferimenti source/target, unicità ID, contenimento temporale edge/node e tipi degli attributi.

Sono venduti in `src/dsl_mngr/resources/gexf/1.3/` tutti i file transitivi della versione 1.3, fissati al commit upstream `66efb132569f61e5e8a313d78144484238ac7315`, licenza CC BY 4.0:

| File | URL sorgente esatta | SHA-256 atteso |
|---|---|---|
| `gexf.xsd` | `https://raw.githubusercontent.com/gephi/gexf/66efb132569f61e5e8a313d78144484238ac7315/specs/1.3/gexf.xsd` | `a8e1d0a6a5237fc4ce0825692fa3db49fb04d70cf3a84334f7a87c15422c1257` |
| `dynamics.xsd` | `https://raw.githubusercontent.com/gephi/gexf/66efb132569f61e5e8a313d78144484238ac7315/specs/1.3/dynamics.xsd` | `d5ee084a858baf6efebe210d4799050723bfce71fb44c9ddbf20a53f45be8298` |
| `viz.xsd` | `https://raw.githubusercontent.com/gephi/gexf/66efb132569f61e5e8a313d78144484238ac7315/specs/1.3/viz.xsd` | `e20e40bcfd4531026d4d1c74da5cbadc413ff5b81cf4418ca14f42ea994e2dc4` |

Un manifest risorse registra URL, versione, commit, licenza e SHA. Test di packaging aprono le risorse tramite `importlib.resources`; test hash impediscono drift. Non si scarica nulla a runtime. `lxml` è scelto perché offre validazione XSD e resolver locali, ha supporto Python 3.12 dichiarato e wheel multipiattaforma; il pin evita differenze di libxml2 non controllate.

## 14. CLI, configurazione e catalogo esiti

### 14.1 Comandi

La review umana espone esattamente questi sottocomandi:

```text
candidates review list <workspace> [--outcome pending|confirmed|rejected|superseded]
candidates review show <workspace> <candidate_record_id>
candidates review confirm <workspace> <candidate_record_id> [--reason TEXT]
                          [--actor-id ID] [--expected-head-decision-id ID]
                          [--idempotency-key KEY]
candidates review reject <workspace> <candidate_record_id> --reason TEXT
                         [--actor-id ID] [--expected-head-decision-id ID]
                         [--idempotency-key KEY]
candidates review correct <workspace> <candidate_record_id> --payload PATH_OR_JSON
                          --reason TEXT [--evidence-ref REF ...]
                          [--actor-id ID] [--expected-head-decision-id ID]
                          [--idempotency-key KEY]
facts reconcile <workspace> [--reconciliation-id ID] [--strict]
```

`list` mostra per default i pending, ordinati per `candidate_record_id`; `show` espone payload, evidenze, lineage, catena decisionale e stato materializzato/effettivo. Le risposte machine-readable hanno `schema_version`, `status`, `outcome`, `reason`, `exit_code`, `mutations`, `retryable`, ID e contatori. I valori di catalogo sono sempre lowercase `snake_case`.

Comandi aggiunti dalle slice successive:

```text
candidates derive <workspace> [--source-revision-id ID] [--rule RULE]
dsl render <workspace> [--schema-version 1|2] [--allow-incomplete]
dsl diff <left> <right> [--cross-schema]
graph export <workspace> --snapshot-id ID [--dynamic]
             [--timeformat date|dateTime] [--allow-incomplete]
```

`--allow-incomplete` è rifiutato per schema 1. `--dynamic` è rifiutato per snapshot v1. La CLI non espone opzioni per eseguire macro, aggiornare link o ricalcolare formule.

### 14.2 Configurazione

Nuove chiavi, tutte validate e con default esplicito:

```toml
[review]
default_actor_id = ""                 # vuoto significa non configurato
automatic_policies = []

[derive]
rule_set_version = "1"

[excel]
max_file_bytes = 67108864
max_zip_entries = 20000
max_uncompressed_bytes = 536870912
max_compression_ratio = 100
max_xml_part_bytes = 33554432
max_sheets = 256
max_cells = 2000000
max_regions = 10000
max_relationships = 50000
max_output_bytes = 268435456
worker_timeout_seconds = 120
worker_memory_bytes = 1073741824

[temporal]
max_evidence_per_source = 100000
max_intervals_per_subject = 1000
default_timeformat = "date"
unknown_timezone_policy = "pending"

[gexf]
schema_version = "1.3"
validator_dependency = "lxml==6.1.2"
```

Gli override sono riportati nei report, non possono superare gli hard maximum della sezione 15 e non possono disabilitare no-network, blocco macro/DTD/entity o controllo hash.

### 14.3 Catalogo versionato di outcome, status, reason ed exit

Il catalogo `result_catalog_v1` è condiviso da review, derive, merge, OOXML, temporalità e GEXF. Ogni report contiene almeno `catalog_version`, `condition`, `status`, `outcome|null`, `reason`, `severity`, `mutations`, `retryable`, `exit_code`, `run_id|null`, `subject_ids`, `artifact_paths` relativi e `counters`.

| Condition | Status/outcome | Reason | Severità | Mutazioni | Retry | Exit |
|---|---|---|---|---|---|---:|
| operazione completata | `completed` | `success` | info | sì/no dichiarato | no | 0 |
| replay identico | `completed` | outcome esistente | `idempotent_replay` | no | no | 0 |
| no-op semantico | `completed` | outcome corrente | `semantic_noop` | solo audit opzionale | no | 0 |
| attore umano assente | `failed` | null | `review_actor_required` | no | sì dopo config | 2 |
| reason obbligatoria assente | `failed` | null | `review_reason_required` | no | sì | 2 |
| testa stantia | `conflict` | null | `review_head_conflict` | no | sì dopo refresh | 4 |
| chiave riusata con payload diverso | `conflict` | null | `idempotency_payload_conflict` | no | no con stessa chiave | 4 |
| correzione non sulla foglia | `conflict` | null | `correction_leaf_conflict` | no | sì dopo refresh | 4 |
| candidato non valido | `rejected` | null | `candidate_schema_invalid` | rifiuto strutturale | no | 3 |
| evidenza insufficiente | `completed` | `pending` | `derivation_insufficient_evidence` | candidato/report | sì con nuova evidenza | 0 |
| batch misto con almeno un merge | `completed` | null | `merge_completed_with_skips` | sì | no | 0 |
| nessun eleggibile | `blocked` | null | `no_merge_eligible_candidates` | no | sì dopo review | 4 |
| strict incontra skip | `failed` | null | `merge_review_precondition_failed` | rollback | sì | 4 |
| riconciliazione aperta | `blocked` | null | `reconciliation_required` | no | sì dopo reconcile | 4 |
| sostituzione non materializzata | `pending` | null | `replacement_merge_pending` | compensazione possibile | sì | 4 |
| revisione bytes diversa | `failed` | null | `source_revision_changed` | no | sì dopo nuova scan | 4 |
| package non sicuro | `rejected` | null | `ooxml_security_violation` | report solo | no | 3 |
| limite superato | `rejected` | null | `ooxml_budget_exceeded` | report solo | sì con override valido | 3 |
| relazione esterna non conforme | `rejected` | null | `ooxml_external_target_invalid` | report solo | no | 3 |
| Docling timeout/errore | `failed` | null | `normalization_operational_failure` | parziale eliminato | sì | 5 |
| conversione parziale accettabile | `partial` | null | `normalization_partial` | artefatti marcati | sì | 6 |
| conflitto temporale | `pending` | null | `temporal_conflict` | evidenza/candidato | sì dopo review | 0 |
| timezone irrisolto | `pending` | null | `temporal_timezone_unknown` | evidenza/candidato | sì | 0 |
| profilo tempo incompatibile | `failed` | null | `temporal_profile_incompatible` | no | sì con export separato | 3 |
| XSD non valido | `failed` | null | `gexf_xsd_invalid` | artefatto non registrato | no | 3 |
| vincolo grafo non valido | `failed` | null | `gexf_semantic_invalid` | artefatto non registrato | no | 3 |
| output incompleto consentito | `completed` | null | `incomplete_output_allowed` | sì con omissioni | no | 0 |

Exit `6` indica successo parziale esplicito e non è collassato in errore operativo. Un batch aggrega l'esito più grave, tranne gli skip di review previsti: se vi è almeno un merge e nessun errore, resta `0`.

## 15. Sicurezza, budget e offline

### 15.1 Limiti riproducibili

| Risorsa | Default | Hard maximum |
|---|---:|---:|
| file sorgente | 64 MiB | 256 MiB |
| entry ZIP | 20.000 | 100.000 |
| bytes decompressi totali | 512 MiB | 2 GiB |
| rapporto compressione per entry/totale | 100:1 | 1.000:1 |
| singola part XML | 32 MiB | 128 MiB |
| fogli | 256 | 1.024 |
| celle indirizzate | 2.000.000 | 10.000.000 |
| regioni | 10.000 | 50.000 |
| relazioni | 50.000 | 250.000 |
| output derivati totali per sorgente | 256 MiB | 1 GiB |
| timeout worker Excel | 120 s | 600 s |
| memoria worker Excel | 1 GiB | 4 GiB |
| evidenze temporali per sorgente | 100.000 | 1.000.000 |
| intervalli per soggetto | 1.000 | 10.000 |
| nodi+archi GEXF | 1.000.000 | 5.000.000 |

I test “al limite” e “oltre limite” usano contatori e stream sintetici piccoli, non allocazioni proporzionali ai massimi; sono quindi indipendenti dalla macchina. I report distinguono violazione di sicurezza, superamento operativo e risultato parziale. Le slice 23–28 riportano budget osservati e massimi effettivi.

### 15.2 Isolamento

Preflight e normalizzazione Excel girano in un worker isolato. Il parent impone timeout e limite dell'output. Su piattaforme con hard memory limit usa primitive del sistema; dove non sono disponibili monitora il processo, lo termina al superamento e dichiara nel report `memory_limit_mode=monitored`, senza fingere una garanzia hard. File parziali vengono pubblicati solo tramite rename atomico dopo validazione e hash.

Tutti i test di Docling, OOXML, temporalità e GEXF installano una guardia no-network che fallisce su socket, HTTP o resolver non locale. Gli XSD sono risorse del package. Link e query di workbook sono inventariati ma mai dereferenziati; macro non vengono caricate come codice né eseguite.

## 16. Test e fixture

### 16.1 Piramide

- Unit: canonical JSON, state machine, catene/lineage, policy, parser OPC, normalizzazione temporale, mapping GEXF.
- DB/migrazione: v6 realistico→v7, v7→v8, v8→v9, v9→v10, rollback atomico e riapertura.
- Integrazione: CLI review/derive/reconcile, merge misto/strict, batch, Docling reale per `.xlsx` e `.xlsm`, persistenza/rilettura DSL v2, validazione XSD offline.
- Golden: request/semantic hash, manifest workbook, DSL v2, diff, GEXF 1.3 e report.
- End-to-end: Aurora, inclusi crash/retry e ordine alternativo review→merge→correzione→reconcile.

Non si effettuano chiamate AI reali. Eventuale generazione temporale usa l'handoff candidati esistente, fixture locali e adapter finto; non scrive intervalli o fatti direttamente.

### 16.2 Fixture Excel obbligatorie

`tests/fixtures/excel/` contiene binari immutabili:

- `.xlsx` multi-sheet e multi-region;
- formule con cached value verificabile e formula senza cached value;
- merged cells;
- named range workbook e sheet scoped;
- fogli `visible`, `hidden`, `very_hidden`;
- celle string, numero, booleano, data, errore e blank;
- external link non dereferenziato;
- `.xlsm` reale con macro part inerte;
- package malformati e conversione parziale controllata.

Ogni binario ha SHA-256 letterale in `checksums.json`; il test fallisce se cambia. Il file formula/cached usato in Aurora è copia byte-for-byte o ha lo stesso SHA registrato. I fixture malevoli vengono costruiti in memoria quando possibile.

### 16.3 Fixture temporali obbligatorie

`tests/fixtures/corpus_temporal/` copre: proprietà OOXML core/app/ZIP concordanti e discordanti; PDF Info/XMP; HTML dichiarativo; testo/SQL/XML/log con data nel nome, nel contenuto e `sources.first_seen_at`; anno/mese/giorno/dateTime con Z/offset/timezone ignoto; fonti indipendenti e correlate; intervalli sovrapposti, disgiunti, aperti e conflittuali; arco fuori dai bounds dei nodi.

### 16.4 Matrice Aurora aggiornata

Il corpus della slice 28 deve verificare:

- ingest originale immutabile di tutte le sorgenti attive;
- `.xlsx` multi-sheet/multi-region con formula+cached, merge, named range, hidden e veryHidden, tutti i tipi cella ed external link;
- `.xlsm` macro-enabled reale, macro rilevata ma mai eseguita;
- package malformed e caso partial distinti;
- `normalized.json`, `normalized.md`, `workbook_manifest.json`, fragments e report per ogni workbook valido;
- candidati deterministici DDL/XML/codice/log/Excel, review e merge;
- evidenze temporali contraddittorie presenti nel corpus senza promozione automatica;
- DSL v1 legacy, DSL v2 effettivo, diff e GEXF dinamico XSD+semanticamente valido;
- budget, no-network, retry e hash su due run.

I riferimenti interni correnti a `corpus_mock_aurora_prestiti.zip` e `guida_dsl-manager.md` nella root non corrispondono a file presenti: la slice 28 aggiorna guide e checklist verso la directory reale e i due file guida effettivi, senza creare alias fittizi.

## 17. Tracciabilità

| Requisito | Fonte primaria | Decisione | Slice | Migrazione/schema | Test | Criterio di accettazione |
|---|---|---|---:|---|---|---|
| validità ≠ merge eligibility | prompt v02 + codice merge corrente | testa confirmed e foglia | 20 | v7 | `test_slice_20_pending_not_mergeable` | pending mai materializzato |
| review append-only | prompt v02 | decisioni immutabili + head pointer | 20 | v7 | `test_slice_20_decision_chain` | una testa, catena aciclica |
| concorrenza ottimistica | prompt v02 | expected head in stessa txn | 20 | v7 | `test_slice_20_stale_head_atomic` | stale non muta e non crea doppia testa |
| idempotenza | prompt v02 | replay prima del head check | 20 | v7 | `test_slice_20_review_idempotency` | replay stesso ID; hash diverso conflitto |
| correzione | prompt v02 | nuovo batch/candidato, no mutation | 20 | v7 | `test_slice_20_correction_atomic` | originale intatto, foglia confermata |
| attore umano stabile | prompt v02 | flag/config, mai OS username | 20 | config | `test_slice_20_actor_required` | errore stabile senza identità |
| viste effettive | prompt v02 | quattro viste governate dalla testa | 20 | v7 | `test_slice_20_effective_support` | altro supporto mantiene oggetto effettivo |
| legacy migration | contratti + prompt | backfill solo explicit/observed active | 20 | v6→v7 | `test_slice_20_migrate_real_v6` | pending/conflicted non confermati |
| primo candidato DDL | supporto candidati + parser corrente | table fact rule | 20 | schema candidati | `test_slice_20_ddl_table_candidate` | evidence→pending→confirmed→merge |
| regole DDL/XML/code/log | parser correnti | catalogo tecnico versionato | 21 | — | `test_slice_21_rule_matrix` | output deterministico senza dominio inventato |
| placeholder proibiti | supporto candidati | validator comune | 21 | candidate schema | `test_slice_21_unresolved_template_rejected` | nessun token irrisolto importato |
| batch consolidato | batch corrente + prompt | fasi e contatori unificati | 22 | report v2 | `test_slice_22_retry_convergence` | due retry stesso stato/hash |
| byte singoli | prompt + Docling 2.97.0 | buffer immutabile/DocumentStream | 23 | — | `test_slice_23_single_byte_sequence` | preflight e Docling stesso hash |
| `.xlsm` diretto | prompt; Docling non lo documenta autonomamente | route XLSX dopo content type | 23 | — | `test_slice_23_real_xlsm_docling` | successo diretto o slice bloccata, mai conversione |
| preflight sicuro | ECMA-376 Part 2 + policy app | OPC streaming, no extraction | 23 | report | `test_slice_23_ooxml_attacks` | ogni attacco ha reason stabile |
| due viste Excel | Docling backend + prompt | Docling leggibile, manifest strutturale | 23–24 | manifest v1/v8 | `test_slice_24_formula_cached` | formula e cached distinti |
| struttura workbook | prompt | fogli/celle/regioni/named/rel | 24 | v8 | `test_slice_24_manifest_golden` | JSON/hash identici su due run |
| candidati Excel | prompt | solo struttura esplicita | 25 | candidate schema | `test_slice_25_excel_candidates` | evidence locator completo, pending/auto policy |
| evidenza temporale grezza | chat metadata + prompt | tabella append-only completa | 26 | v9 | `test_slice_26_raw_evidence_fields` | nessun campo obbligatorio perso |
| review temporale comune | prompt | temporal candidate è candidate_record | 26 | v9/v7 | `test_slice_26_common_review` | nessuna API parallela |
| DSL v2 | prompt | metadata esatta + intervals sempre | 26 | schema 2 | `test_slice_26_dsl_v2_roundtrip` | persiste/rilegge, hash stabile |
| GEXF 1.3 offline | GEXF/Gephi ufficiali | XSD venduti + semantic validator | 26 | resources | `test_slice_26_gexf_offline` | no rete, XSD e bounds validi |
| precisione e timezone | prompt | coverage envelope, niente fill/truncate | 26–27 | v9/v10 | `test_slice_27_precision_timezone` | year/month conservati, unknown non esportato |
| fonti multiple | chat metadata + supporto temporale | indipendenza/correlazione/conflitto | 27 | v10 | `test_slice_27_evidence_concordance` | correlate non aumentano forza |
| più intervalli/spells | GEXF 1.3 | intervalli disgiunti ordinati | 27 | v10/DSL2 | `test_slice_27_spells_bounds` | spell inclusivi e contenuti |
| cross-schema diff | prompt | modalità esplicita e categorie separate | 27 | diff report | `test_slice_27_cross_schema_diff` | nessun confronto implicito |
| Aurora completo | corpus locale + prompt | sostituzione fixture e guide | 28 | fixture | `test_slice_28_aurora_e2e` | checklist completa su due run |
| docs consolidate | prompt + template | aggiornare contratti/manuale/analisi | 29 | doc schema | test link/comandi o verifica testuale automatica | nessun riferimento obsoleto; non serve test runtime ulteriore |
| immutabilità snapshot storici | contratti manifest | nessun update retroattivo | 20, 26 | v7/v9 | `test_slice_26_historical_snapshot_immutable` | byte/hash preesistenti invariati |
| AI confinata all'handoff | design v01 + prompt | fake adapter, candidate-only | 27 | — | `test_slice_27_ai_candidate_handoff` | nessuna chiamata rete o scrittura diretta |

La voce documentale della slice 29 usa una verifica automatica di link, nomi comando e riferimenti; non richiede test di runtime aggiuntivo perché non modifica codice.

## 18. Piano per slice

### 18.1 Slice 20 — fondazione candidati, review e viste effettive

Dipende dalle slice 01–19. Implementa migrazione v7, canonical JSON/hash, servizio e CLI review, catene/head/idempotenza, correzione atomica, lineage, coda di riconciliazione, viste effettive, filtro merge e backfill legacy. Aggiunge il catalogo delle regole e la prima regola `ddl_table_fact/1`, così il percorso completo parser→evidenza→pending→decisione→merge è dimostrato subito.

Artefatti: report JSON review/derive, batch di correzione, audit note opzionale. Test obbligatori: migrazione da un DB v6 realistico, race su testa, crash/replay, no-op, correzione/branch/ciclo, merge misto/strict, supporti multipli, blocco render per riconciliazione. Accettazione: nessun candidato privo di testa positiva corrente entra nel nuovo merge. [Prompt eseguibile](#prompt-slice-20).

### 18.2 Slice 21 — derivazione deterministica completa

Dipende dalla 20. Completa in sottopassi interni DDL colonne/FK, XML form/block/item/table reference, unità e dipendenze DB, osservazioni log. Usa solo metadati e locator già prodotti, regole pure/versionate e importer comune. Non modifica il batch orchestrator.

Test: golden per regola, ordinamento, deduplica, evidenza mancante, placeholder, nomi ambigui e assenza di semantica di dominio inventata. Accettazione: a parità di parser output, due esecuzioni producono lo stesso report semantico e gli stessi payload/hash candidati. [Prompt eseguibile](#prompt-slice-21).

### 18.3 Slice 22 — consolidamento batch e orchestrazione

Dipende da 20–21. Inserisce derive come fase dopo parser strutturali; applica solo policy automatiche abilitate; merge usa eligibility corrente; reconcile può essere fase finale. Definisce stato aggregato, report catalogato, retry dopo crash e zero-candidate.

Test: batch con sorgenti supportate/non supportate, candidati pending/rejected/confirmed, nessun eleggibile, strict, crash tra fasi, ripresa e due run convergenti. Accettazione: lo stesso workspace raggiunge medesimi effective hash indipendentemente dai retry. [Prompt eseguibile](#prompt-slice-22).

### 18.4 Slice 23 — ingest `.xlsx`/`.xlsm` trasparente

Dipende dalla 22. Estende routing e normalizer, implementa lettura singola, confronto `content_hash`, preflight sicuro minimo e worker isolato. Mantiene `docling==2.97.0`. Produce `normalized.json`, `normalized.md` e preflight report; non interpreta ancora regioni.

Test reali Docling per `.xlsx` e `.xlsm`, mismatch revision, ZIP traversal/bomb/duplicate, XML DTD/entity, relazioni invalide, limiti at/over, timeout, no-network e assenza ricalcolo/macro. Accettazione `.xlsm`: conversione diretta comprovata; se il backend non la supporta, la slice fallisce esplicitamente senza fallback. [Prompt eseguibile](#prompt-slice-23).

### 18.5 Slice 24 — manifest, struttura e frammenti workbook

Dipende dalla 23. Estende il medesimo parser e aggiunge migrazione v8, manifest canonico, region detector, frammenti e persistenza dei riferimenti. Conserva formula/cached, merge, named range scoped, visibility, relazioni, external link e presenza/hash macro.

Test golden e DB per tutti i tipi cella, regioni multiple, nomi/ordine Unicode, worksheet hidden/veryHidden, relazione esterna, budget regioni/celle/output e roundtrip. Accettazione: manifest e frammenti identici su due macchine/run e nessun dato strutturale richiesto affidato solo a `normalized.md`. [Prompt eseguibile](#prompt-slice-24).

### 18.6 Slice 25 — candidati Excel deterministici

Dipende da 20 e 24. Introduce regole conservative: workbook/sheet/region/named table come fatti tecnici; riferimenti espliciti tra regioni come relazioni solo se osservabili; header e label restano attributi/evidenze, non dominio. Tutto passa da candidate batch e review comune.

Test su regioni duplicate, named range scope, formule, fogli nascosti e candidate ID ripetuti tra batch. Accettazione: nessun valore di cella diventa automaticamente una regola di business. [Prompt eseguibile](#prompt-slice-25).

### 18.7 Slice 26 — nucleo temporale, DSL v2 e GEXF 1.3

Dipende da 20 e 22. Implementa migrazione v9, estrattori minimi OOXML core/app/ZIP, evidenza grezza, candidati temporali, review comune, un intervallo massimo, DSL schema 2/hashing/diff same-schema, export GEXF 1.3 dinamico, risorse XSD vendute e validazione offline doppia.

Test: raw evidence fields, contraddizione, day/dateTime timezone, review/merge temporale, snapshot v2 roundtrip, `intervals=[]`, hash, XSD SHA/package/no-network, edge bounds e immutabilità v1. Accettazione: solo intervalli resolved+confirmed raggiungono DSL/grafo. [Prompt eseguibile](#prompt-slice-26).

### 18.8 Slice 27 — consolidamento temporale

Dipende dalla 26. Aggiunge migrazione v10, fonti PDF/HTML/testo/SQL/XML/log/nome file/`sources.first_seen_at`, indipendenza/correlazione/conflitto, multipli intervalli, precisione year/month, relazioni di versione/precedenza solo quando esplicite, propagazione esplicita, batch/reconcile, diff cross-schema e golden completi. Integra facoltativamente il generatore AI solo tramite handoff candidato finto.

Test: matrice fonti, conflitti e correlazione, timezone unknown, coverage envelope, spells ordinati/inclusivi, relazione fuori bounds, modalità omit/separate/strict, retry e budget. Accettazione: nessun riempimento o troncamento silenzioso. [Prompt eseguibile](#prompt-slice-27).

### 18.9 Slice 28 — corpus Aurora aggiornato

Dipende da 23–27. Sostituisce/amplia i fixture Aurora con workbook completi e immutabili, xlsm macro, malformed/partial, segnali temporali discordanti e attesi v2. Aggiorna inventario, checklist e guide rimuovendo i riferimenti mancanti a ZIP/guida di root.

Test end-to-end e hash su due run, no-network e limiti. Accettazione: tutti gli elementi della checklist 16.4 hanno un atteso verificato e il binario formula/cached coincide con la fixture test per SHA. [Prompt eseguibile](#prompt-slice-28).

### 18.10 Slice 29 — consolidamento documentale

Dipende da 20–28. Aggiorna analisi tecnica, contratti manifest, manuale utente e documenti architetturali per stato realmente implementato, comandi, migrazioni, codici esito, formati, sicurezza e compatibilità. Non cambia runtime.

Verifica automatica link/comandi/nomi e confronto con `--help`. Accettazione: nessun documento presenta pending come mergeabile, `.xlsm` come conversione, metadata come verità o GEXF dinamico come validato dalla sola XSD. [Prompt eseguibile](#prompt-slice-29).

## 19. Roadmap e criteri globali

L'ordine è rigoroso: 20→21→22→23→24→25; la 26 può iniziare dopo 22 ma deve integrare le viste della 20; 27 segue 26; 28 segue 23–27; 29 chiude tutto. Ogni slice è una verticalità minima, migra da database reali della versione precedente, conserva compatibilità dichiarata e aggiorna il proprio report.

Definition of done globale:

- tutte le migrazioni sono atomiche, idempotenti all'apertura e testate in upgrade reale;
- ogni output semantico è deterministico su due run e privo di path/timestamp instabili;
- catalogo esiti e contatori sono coerenti tra CLI, report e batch;
- nessuna rete nei test o a runtime per gli input locali;
- nessun contenuto attivo Office viene eseguito;
- ogni decisione, candidatura, intervallo e materializzazione torna all'evidenza;
- schema v1/statico legacy e snapshot storici restano leggibili;
- schema v2/dinamico usa esclusivamente viste effettive;
- suite completa eseguita col Python di progetto dopo ogni modifica di codice.

## 20. Fonti esterne verificate

Verifica effettuata il 2026-09-02; sono state usate soltanto fonti ufficiali/primarie.

| Fonte | Versione/data | Evidenza usata | Decisione supportata |
|---|---|---|---|
| [Docling supported formats al tag v2.97.0](https://github.com/docling-project/docling/blob/v2.97.0/docs/usage/supported_formats.md) | v2.97.0, release 2026-06-03 | XLSX è formato OOXML supportato; XLSM non è elencato separatamente | mantenere pin; trattare `.xlsm` come contratto da provare |
| [Docling DocumentConverter v2.97.0](https://github.com/docling-project/docling/blob/v2.97.0/docling/document_converter.py) | tag v2.97.0 | mapping XLSX→Excel backend; input `DocumentStream`; limite file | routing esplicito e singola sequenza byte |
| [Docling Excel backend v2.97.0](https://github.com/docling-project/docling/blob/v2.97.0/docling/backend/msexcel_backend.py) | tag v2.97.0 | backend accetta stream, dichiara XLSX e carica con `data_only=True` | manifest parallelo per formula/cached |
| [ECMA-376](https://ecma-international.org/publications-and-standards/standards/ecma-376/) | Part 2 OPC, 5a ed., dicembre 2021 | packaging, parti, content type e relazioni OOXML | preflight OPC; i limiti di sicurezza sono policy applicativa |
| [GEXF schema ufficiale](https://gexf.net/schema.html) | 1.3 raccomandata | tutti gli XSD necessari; limiti noti della sola XSD | vendoring completo + validator semantico |
| [GEXF dynamics](https://gexf.net/dynamics.html) | 1.3 | graph dynamic, timeformat, start/end e spells | profilo dinamico a intervalli |
| [Repository ufficiale GEXF](https://github.com/gephi/gexf/tree/66efb132569f61e5e8a313d78144484238ac7315/specs/1.3) | commit fissato, CC BY 4.0 | tre XSD 1.3 e changelog inclusività/timezone | URL/SHA/licenza riproducibili |
| [Gephi: import dynamic data](https://docs.gephi.org/desktop/User_Manual/Import_Dynamic_Data/) | consultata 2026-09-02 | una rappresentazione/formato per grafo; date/dateTime; bounds inclusivi e contenimento edge | profilo singolo e semantic checks |
| [lxml XMLSchema](https://lxml.de/validation.html) e [resolver](https://lxml.de/resolvers.html) | `lxml==6.1.2`, pubblicato 2026-08-19 su [PyPI](https://pypi.org/project/lxml/) | API XSD, resolver locali e `no_network`; Python 3.12 dichiarato | validatore offline pinned |

Nessuna fonte ufficiale consultata garantisce autonomamente che ogni `.xlsm` sia convertibile dal backend XLSX di Docling 2.97.0; per questo il test reale è un gate e non una formalità. Analogamente, la fonte GEXF dichiara che l'XSD non verifica riferimenti degli archi, tipi e contenimento dinamico: tali controlli sono applicativi.

## 21. Auto-verifica del design

- [x] Sono definite esattamente dieci nuove slice, numerate 20–29.
- [x] Ogni slice ha perimetro, dipendenze, migrazione/schema, fixture, artefatti, test, accettazione e prompt collegato.
- [x] La state machine è `evidence → pending → persisted decision → merge-eligible → authoritative merge`.
- [x] Review, idempotenza, concorrenza, correzione, lineage, effective views e riconciliazione sono specificate.
- [x] Migrazione legacy e compatibilità schema1/static sono esplicite.
- [x] Derivazione DDL/XML/codice/log è candidate-first e non genera dominio.
- [x] Excel usa Docling 2.97.0, singoli byte, preflight, due viste e nessuna conversione/esecuzione.
- [x] Manifest, formule/cached, visibility, named range, link e macro sono coperti.
- [x] Temporalità conserva raw evidence, precisione, timezone, affidabilità, conflitto e review comune.
- [x] DSL v2 ha `metadata.schema_version="2"` e `intervals` sempre presente.
- [x] GEXF 1.3 è dinamico, offline, XSD+semantico, con risorse versionate/licenziate/hashate.
- [x] Budget at/over, no-network, fixture Excel/temporal/Aurora e golden sono obbligatori.
- [x] La matrice di tracciabilità assegna test o motivazione esplicita.
- [x] Tutti i prompt sono senza placeholder di template e pronti all'uso.

Conclusione: il design è implementabile per incrementi, preserva il registro storico e rende ogni promozione semantica esplicita, persistita, verificabile e revocabile nelle viste correnti senza riscrivere il passato.

## 22. Prompt di implementazione

I prompt seguenti sono completi, pronti all'uso e costituiscono parte normativa del perimetro di ciascuna slice.

### Prompt Slice 20

Implementa solo la Slice 20 — fondazione candidati, review, lineage, riconciliazione, viste effettive e prima regola DDL table→fact — nel repository DSL Manager. Produci `.kb/projects/slicing/slice_20/dsl_manager_slice_20_report.md`.

Prima di modificare codice, leggi integralmente `AGENTS.md`, questo documento v02, l'analisi tecnica, i contratti manifest, il manuale utente, il design v01, i report 01–19 e il materiale di supporto sui candidati. Ispeziona il worktree corrente e preserva modifiche non correlate. Usa Python 3.12 e l'interprete indicato da `.codex/config.toml`; installa editable con extra dev prima del codice e usa quello stesso interprete per i test.

Obiettivo verticale minimo: dimostrare `evidenza DDL → candidato pending → decisione persistita → merge-eligible → fatto effettivo`, mantenendo compatibilità legacy.

Perimetro obbligatorio:

- migrazione v7 esattamente secondo la sezione 8.1, inclusa nullabilità controllata di `candidate_batches.input_path` e upgrade da DB v6 realistico;
- `CandidateReviewService`, canonical JSON/hash condiviso, chain/head aciclici, optimistic concurrency, idempotenza e no-op della sezione 7/9;
- CLI esatta `candidates review list/show/confirm/reject/correct` e `facts reconcile <workspace>`;
- identità umana da flag/config, reason obbligatoria, policy id/versione per automatici;
- correzione atomica in nuovo batch `human_correction`, lineage senza branch e output del batch ID;
- quattro viste `effective_fact_evidence`, `effective_relation_evidence`, `effective_facts`, `effective_relations` e coda `reconciliation_required`;
- merge che rilegge decisione nella propria transazione, modalità mixed/strict e report catalogato;
- backfill legacy solo per supporti active explicit/observed, senza cambiare snapshot;
- framework di derivazione e sola regola `ddl_table_fact/1`, con import candidato normale;
- blocco render/diff/export in presenza di riconciliazione; soltanto schema 2 futuro potrà usare allow-incomplete.

Non implementare le altre regole, Excel o temporalità. Non mutare decisioni/candidati esistenti, non usare username macchina, non rendere `candidate_id` univoco globale, non confermare inferred/pending/conflicted.

Test minimi obbligatori: migrazione v6→v7; chain/head/same-subject/ciclo; due writer con testa stantia; replay prima del head check; collisione chiave; semantic no-op; actor/reason; correct atomica/crash/retry/no-branch; mixed merge, strict e no eligible; supporti multipli; reconcile semplice/sostituzione pending; hash Unicode/numeri/null/list/key order; primo DDL end-to-end. Aggiorna golden e test esistenti solo dove il contratto lo richiede.

La slice è finita quando la suite completa passa, gli output di due run sono deterministici, nessun pending è materializzato dal percorso nuovo e il report di slice elenca file, migrazione, comandi, test ed eventuali scostamenti. Prima di codificare dichiara brevemente i file previsti; poi implementa, esegui test mirati e completi e riassumi risultato e diff.

### Prompt Slice 21

Implementa solo la Slice 21 — derivazione deterministica completa da DDL, XML, codice database e log. Produci `.kb/projects/slicing/slice_21/dsl_manager_slice_21_report.md`.

Leggi integralmente `AGENTS.md`, design v02, analisi tecnica, contratti, manuale, report delle slice 12–14 e 20 e materiale di supporto candidati. Ispeziona parser, fixture e worktree; usa esclusivamente il Python 3.12 configurato, installa editable dev e preserva modifiche non correlate.

Obiettivo verticale minimo: trasformare gli output strutturati già persistiti dai parser in candidate batch deterministici e reviewable, senza accesso AI e senza scrittura diretta di fatti/relazioni.

Implementa, come sottopassi interni alla stessa slice, `ddl_column_fact/1`, `ddl_fk_relation/1`, `xml_form_structure/1`, `xml_table_usage/1`, `db_code_unit/1`, `db_code_dependency/1`, `log_event_observation/1`. Ogni regola deve dichiarare versione, schema input, assertion, locator e policy consentita; usare l'importer della slice 20; ordinare e deduplicare stabilmente; produrre report `result_catalog_v1`. Usa solo segnali espliciti/observed descritti nella sezione 10. Se un read/write/call o target FK non è esplicito, mantieni pending o segnala evidenza insufficiente. Aggiungi al validator il rifiuto di placeholder semantici irrisolti.

Non modificare l'orchestratore batch, non introdurre nuove migrazioni salvo una necessità dimostrata e compatibile, non inventare concetti di dominio da nomi, non auto-confermare log per default e non creare sottoslice ulteriori.

Test obbligatori: golden per ogni regola e parser; FK risolta/non risolta; XML read/write esplicito/ambiguo; unità e dipendenze DB; log pending; locator mancante; placeholder; candidate ID uguali in batch diversi; ordine input invertito; due run con payload/hash identici; nessuna chiamata rete/AI. Esegui test mirati e suite completa.

Done: tutte le regole consegnano candidati validi o ragioni stabili, non facts diretti; il report di slice documenta conteggi per rule/version e il diff resta nel perimetro. Prima del codice elenca i file previsti; dopo i test riporta esito e modifiche.

### Prompt Slice 22

Implementa solo la Slice 22 — consolidamento batch e orchestrazione di parse, derive, review automatica autorizzata, merge e reconcile. Produci `.kb/projects/slicing/slice_22/dsl_manager_slice_22_report.md`.

Leggi integralmente `AGENTS.md`, design v02, contratti batch/worker/candidate/merge, manuale e report 16, 20 e 21. Ispeziona il worktree e il modello di stato corrente. Usa il Python 3.12 configurato, installazione editable dev e preserva cambi estranei.

Obiettivo verticale minimo: una singola esecuzione batch su input misti produce candidati deterministici, applica solo policy abilitate, unisce solo eleggibili e può riprendere dopo crash convergendo allo stesso stato.

Inserisci derive dopo i parser strutturali, registra versione regole e batch; integra review automatica via `CandidateReviewService`; rilegge eligibility nel merge; esegui reconcile finale se configurato. Definisci checkpoint, retry per fase, aggregazione `result_catalog_v1`, contatori mixed/strict/no-eligible, zero candidates e report ordinati. La modalità predefinita tratta skip review come non-errori quando esiste almeno un merge; no eligible esce 4; strict rollback/esce 4. Non duplicare logica review o merge nel worker.

Non aggiungere Excel o temporalità, non auto-confermare regole non allowlisted, non cambiare snapshot storici e non nascondere partial/failure.

Test obbligatori: input supportati/non supportati; pending/rejected/superseded/confirmed insieme; policy assente/presente/versione diversa; zero candidates; no eligible; strict rollback; crash dopo derive/review/merge e resume; ordine inverso; due run/retry con stessi effective hash, contatori e nessun doppio supporto; no-network. Esegui test mirati e suite completa.

Done: report e exit code sono conformi al catalogo, il batch non promuove nulla implicitamente e retry/ordine convergono. Dichiara file previsti prima del codice; chiudi con test e diff.

### Prompt Slice 23

Implementa solo la Slice 23 — ingest trasparente e sicuro `.xlsx`/`.xlsm` con Docling 2.97.0. Produci `.kb/projects/slicing/slice_23/dsl_manager_slice_23_report.md`.

Leggi integralmente `AGENTS.md`, design v02, analisi/contratti/manuale, report 10–11 e 22, fonti ufficiali Docling v2.97.0 ed ECMA-376 Part 2 indicate nella sezione 20. Ispeziona dipendenze e worktree. Usa il Python 3.12 configurato; mantieni `docling==2.97.0`; installa editable dev senza upgrade non richiesti.

Obiettivo verticale minimo: una source revision Excel valida viene letta una volta, preflightata e passata a Docling come stream con lo stesso hash, producendo `normalized.json`, `normalized.md` e report; input malevoli falliscono prima della conversione.

Estendi routing a `.xlsx` e `.xlsm`. Carica una sequenza byte limitata, confronta SHA-256 con `source_revisions.content_hash`, crea due cursori e non riaprire il path. Implementa il preflight minimo della sezione 11.2 senza estrazione su disco, DTD/entity o rete. `.xlsm` deve superare content type macro-enabled ed essere inoltrato esplicitamente come `InputFormat.XLSX` con nome `.xlsm`; prova un file reale. Isola il worker con timeout/output/memory hard dove supportato o monitored+kill dichiarato. Pubblica artefatti atomici e usa reason/status del catalogo. Nessun ricalcolo, macro, link/query o conversione.

Non implementare manifest completo, regioni o candidati Excel. Se il test Docling `.xlsm` fallisce, marca la slice bloccata con evidenza: non introdurre LibreOffice, openpyxl come normalizzatore sostitutivo, rinomina o downgrade.

Test obbligatori: `.xlsx` reale; `.xlsm` reale; byte identity/mismatch; estensione-content type; traversal/absolute/duplicate/case-fold; zip bomb/entry e streaming limits; DTD/entity; relationship duplicate/target invalido; parti minime mancanti; external link mai dereferenziato; at/over ogni limite rilevante; timeout/output/memory mode; partial distinto; no-network; due run stessi output. Esegui suite completa.

Done: i due formati seguono il percorso trasparente autorizzato, gli attacchi hanno esiti stabili e nessun path viene riaperto. Dichiara file prima del codice e riporta test/diff.

### Prompt Slice 24

Implementa solo la Slice 24 — manifest OOXML canonico, struttura workbook, regioni e frammenti. Produci `.kb/projects/slicing/slice_24/dsl_manager_slice_24_report.md`.

Leggi integralmente `AGENTS.md`, design v02, contratti manifest/evidence, report 11–14 e 23, ECMA-376 Part 2. Ispeziona il parser preflight della slice 23 e riusalo: non crearne uno parallelo. Usa Python 3.12 configurato, installazione editable dev e preserva worktree estraneo.

Obiettivo verticale minimo: dallo stesso buffer validato ottenere un `workbook_manifest.json` autoritativo, riferimenti DB v8 e frammenti localizzati, deterministici e sufficienti a distinguere formula e cached value.

Implementa migrazione v8, schema/ordine della sezione 11.3, parsing streaming esteso, region detector versionato, fragments, hash e persistenza. Conserva sheet order/name/visibility, coordinate e tipi cella, formule/cached, merge, named ranges con scope, relazioni part+rId, external link e macro presence/part/hash/`executed:false`. Stabilizza i prodotti Docling in ordine e formato; `normalized.md` resta secondario. Escludi timestamp operativi e path assoluti. Applica limiti celle/regioni/relazioni/output e report catalogato.

Non interpretare dominio, non produrre candidati, non eseguire/recalcolare/aggiornare alcun contenuto e non copiare XML non limitato in memoria.

Test obbligatori con binari immutabili: multi-sheet/multi-region; formula con/senza cached; merged; named range workbook/sheet; visible/hidden/veryHidden; string/number/bool/date/error/blank; external link; xlsm macro; Unicode/ordine; at/over limits; DB roundtrip; manifest golden e hash uguali su due run/macchine logiche; no-network. Registra SHA dei binari e testa il checksum. Esegui suite completa.

Done: manifest/fragments coprono ogni campo obbligatorio e sono fonte primaria strutturale. Prima elenca file; dopo riporta test e diff.

### Prompt Slice 25

Implementa solo la Slice 25 — candidati deterministici da Excel. Produci `.kb/projects/slicing/slice_25/dsl_manager_slice_25_report.md`.

Leggi integralmente `AGENTS.md`, design v02, report 20–24, materiale candidati e contratti candidate/evidence. Ispeziona manifest e fragments correnti. Usa Python 3.12 configurato, editable dev e conserva modifiche non correlate.

Obiettivo verticale minimo: workbook→manifest/fragments→candidate batch→review comune, senza attribuire significato di business ai valori delle celle.

Definisci regole versionate conservative per fatti tecnici workbook, sheet, region e named range/table e relazioni soltanto quando un riferimento è esplicito. Ogni candidato usa locator sheet+coordinate/part, evidence ref esistente, payload completo e importer comune. Header, label, formule e valori restano evidenza/attributi; policy automatica è allowlisted solo per struttura certa. Supporta fogli nascosti senza considerarli inattivi. Produci report per rule/version e ordine stabile.

Non creare fatti di dominio, non leggere `normalized.md` come fonte primaria, non modificare review/merge e non aggiungere formati spreadsheet.

Test obbligatori: regioni multiple/duplicate, named range scoped, table reference, formule/cached, hidden/veryHidden, external link non semantico, candidate ID ripetuto tra batch, evidenza mancante, ordine invertito, pending vs auto policy, golden e due run, no-network. Esegui test mirati e completi.

Done: tutti gli output passano da candidati e decisioni e nessuna cella diventa direttamente autoritativa. Elenca file prima; riporta test/diff dopo.

### Prompt Slice 26

Implementa solo la Slice 26 — nucleo temporale completo, DSL schema 2, hashing e GEXF 1.3 dinamico validato offline. Produci `.kb/projects/slicing/slice_26/dsl_manager_slice_26_report.md`.

Leggi integralmente `AGENTS.md`, design v02, documento metadata chat, proposta temporale, design v01, contratti snapshot/diff/GEXF, report 17 e 20–25 e tutte le fonti ufficiali della sezione 20. Il prompt/design v02 prevale sulla proposta di supporto in caso di conflitto. Usa Python 3.12 configurato; aggiungi il pin `lxml==6.1.2`; installa editable dev; preserva il worktree.

Obiettivo verticale minimo: evidenza OOXML grezza→candidato temporale pending→review comune→intervallo validato→DSL v2 persistito/riletto→GEXF 1.3 dinamico valido XSD e semanticamente, tutto offline.

Implementa migrazione v9 e modello della sezione 8.3. Estrai almeno core properties, app properties e timestamp ZIP separati, con tutti i campi raw/metodo/versione/precisione/timezone/reliability/warning. Estendi `candidate_records` al tipo temporale e usa esclusivamente `CandidateReviewService`. Supporta target source_revision/source_fragment/candidate_record/fact/relation e zero/un intervallo. Non ereditare automaticamente l'intervallo sorgente.

Implementa `dsl render --schema-version 2`, default v1, `metadata.schema_version="2"`, `metadata.temporal.base="day"|"timestamp"`, timezone esplicita/`unknown` e `intervals` sempre presenti; usa effective views, hash semantico e roundtrip snapshot. Diff solo same-schema. Export dinamico solo v2, namespace/version/mode/timeformat/intervalli inclusivi.

Vendi `gexf.xsd`, `dynamics.xsd`, `viz.xsd` nel path e con commit/URL/licenza/SHA esatti della sezione 13.2. Usa lxml no-network con resolver allowlist locale; aggiungi validazione semantica di riferimenti, tipi, ordine e bounds. Testa packaging via `importlib.resources` e SHA. Un unico timeformat per file; day e dateTime timezone-resolved; unknown/incompatible non esportato silenziosamente.

Non aggiungere ancora fonti PDF/HTML/nome/contenuto, multi-intervallo o cross-schema diff. Non usare filesystem timestamp, alta confidenza come conferma, rete o XSD scaricati a runtime.

Test obbligatori: migrazioni/rollback; raw fields; proprietà concordanti/contraddittorie; timezone; common review; un interval max; `intervals=[]`; v2 hash/golden/persist-re-read; v1 immutabile/default; reconciliation block e allow-incomplete solo v2; tre SHA XSD, package, no-network; namespace/mode/timeformat; edge bounds/ref/type; output non registrato su errore. Esegui suite completa.

Done: solo interval resolved+confirmed appare nel DSL/grafo, XSD e semantic validation passano offline e v1 resta compatibile. Elenca file prima; riporta test/diff dopo.

### Prompt Slice 27

Implementa solo la Slice 27 — consolidamento temporale, fonti multiple, conflitti, precisione, timezone, diff/batch/reconcile e golden. Produci `.kb/projects/slicing/slice_27/dsl_manager_slice_27_report.md`.

Leggi integralmente `AGENTS.md`, design v02, metadata chat, proposta temporale, contratti e report 16–17 e 26. In conflitto prevale design v02. Usa Python 3.12 configurato, editable dev e preserva modifiche estranee.

Obiettivo verticale minimo: più segnali eterogenei vengono raggruppati per indipendenza, producono candidati reviewable e, se risolti, più intervalli corretti in DSL v2/GEXF spells con batch e retry convergenti.

Implementa migrazione v10. Aggiungi estrattori PDF Info/XMP, HTML dichiarativo e testo/Markdown/SQL/XML/log per dichiarazioni contenuto, nome file e solo `sources.first_seen_at`; conserva source format/key/method/version/raw/precision/timezone/reliability/warnings. Classifica correlazione: segnali dello stesso generatore/copia non aumentano forza; indipendenti concordanti sì; contraddittori/low quality restano pending. Deriva relazioni di versione/precedenza soltanto da riferimenti espliciti e tramite candidati. Implementa propagation policies esplicite, intersection, aggregation e conflict senza inheritance implicita.

Supporta intervalli multipli/disgiunti, year/month come coverage envelope con original precision, dateTime solo timezone-resolved, output omit/separate/strict, spells inclusivi/ordinati e bounds edge/node. Integra temporal derive/review/merge/reconcile nel batch; aggiungi diff cross-schema esplicito e categorie separate; golden condivisi. Se integri generazione AI, usa adapter finto e handoff candidato esistente, mai scrittura diretta o rete.

Non colmare date, troncare dateTime, contare fonti correlate come conferme né cambiare DSL v1.

Test obbligatori: matrice di tutte le fonti; correlazione/indipendenza/conflitto; precision year/month/day/dateTime; timezone Z/offset/unknown; target a ogni granularità; propagation/intersection/aggregation; multi intervals/spells; edge fuori bounds; omit/separate/strict; cross-schema diff; batch crash/retry/order; first_seen_at esatto; budget at/over; golden/hash; fake AI/no-network. Esegui suite completa.

Done: nessun segnale ambiguo entra automaticamente nell'output e due ordini/retry convergono. Elenca file prima; riporta test/diff dopo.

### Prompt Slice 28

Implementa solo la Slice 28 — aggiornamento completo del corpus mock Aurora e dei relativi test end-to-end. Produci `.kb/projects/slicing/slice_28/dsl_manager_slice_28_report.md`.

Leggi integralmente `AGENTS.md`, design v02, tutto il corpus Aurora corrente, inventario, checklist, guide e report 23–27. Ispeziona i nuovi fixture test e checksum. Usa Python 3.12 configurato, editable dev e preserva modifiche non correlate.

Obiettivo verticale minimo: un corpus Aurora autoconsistente esercita Excel, candidati/review, temporalità, DSL v2 e GEXF dinamico con attesi riproducibili, conservando gli scenari legacy utili.

Aggiorna il workbook Aurora a multi-sheet/multi-region con formula+cached, merged, named range, visible/hidden/veryHidden, celle string/number/bool/date/error/blank ed external link; usa esattamente il binario formula/cached dei fixture o lo stesso SHA. Aggiungi `.xlsm` reale macro-enabled inerte, malformed e partial controllati. Registra checksum immutabili. Inserisci segnali temporali concordanti/discordanti significativi, senza adattare le attese a una falsa verità.

Aggiorna `inventario_fonti.csv`, `checklist_risultati_attesi.md`, `LEGGIMI_PRIMA.md` e le due guide reali. Rimuovi/correggi riferimenti a `corpus_mock_aurora_prestiti.zip` e `guida_dsl-manager.md` di root che non esistono; non creare alias fittizi. Le attese devono includere normalized JSON/MD, workbook manifest/fragments/report, candidate batches/decisioni, DSL v1/v2/diff e GEXF XSD+semantic valido.

Non cambiare codice runtime salvo un difetto necessario e documentato emerso dal corpus; se emerge, fermati e assegna la correzione alla slice proprietaria invece di espandere di nascosto il perimetro. Non eseguire macro/rete.

Test obbligatori: checklist della sezione 16.4; checksum; due run stessi hash; ordine/retry; budget/no-network; xlsm; malformed vs partial; contraddizioni temporali pending; export validato. Esegui test mirati e suite completa.

Done: corpus, inventario, guide, checksum e attesi sono coerenti e nessun riferimento interno punta a file mancante. Elenca file prima; riporta test/diff dopo.

### Prompt Slice 29

Implementa solo la Slice 29 — consolidamento documentale finale delle capacità realmente consegnate dalle slice 20–28. Produci `.kb/projects/slicing/slice_29/dsl_manager_slice_29_report.md`.

Leggi integralmente `AGENTS.md`, design v02, codice/test/report finali 20–28, analisi tecnica, contratti manifest, manuale utente, design v01 e documentazione Aurora. Ispeziona il worktree; usa Python 3.12 configurato per eventuali verifiche CLI/test e preserva modifiche estranee.

Obiettivo verticale minimo: documentazione tecnica e utente coerente con schema, comandi, compatibilità, limiti e rischi effettivamente implementati.

Aggiorna analisi tecnica, contratti manifest, manuale, riferimenti architetturali e guide necessarie. Documenta state machine, decision schema/idempotenza/correzione/reconcile, effective views, derivazione, batch, `.xlsx`/`.xlsm` e limitazioni, manifest, budget/sicurezza, temporal evidence/policy/precision/timezone, DSL v2/diff, GEXF 1.3/XSD+semantic offline, migrazioni v7–v10, result catalog ed esempi CLI. Marca chiaramente compatibilità schema1/static e comportamento allow-incomplete. Correggi link e nomi ordinati.

Non aggiungere feature runtime, non retrodatare lo stato e non descrivere: pending come mergeabile; `.xlsm` come conversione; metadata come verità; formula Docling come autoritativa; sola XSD come validazione completa; filesystem timestamps come evidenza.

Verifiche obbligatorie: lint/link check locale o test equivalente; confronto esempi con `--help`; ricerca riferimenti obsoleti e nomi non zero-padded; suite completa perché eventuali doctest/snapshot CLI restino coerenti. Se una capacità prevista non è implementata, documenta il gap e non dichiararla completa.

Done: documenti e CLI si contraddicono in zero punti noti, i riferimenti sono risolvibili e il report di slice elenca file, verifiche e gap. Prima dichiara file previsti; dopo mostra test e diff.
