# Analisi della capacità di generare candidati deterministici

## Esito

**Risposta operativa: no. L’attuale `dsl-manager` non dispone di una funzione che derivi autonomamente, con regole deterministiche, candidati significativi per il merge a partire da chunk o frammenti.**

L’applicazione:

- estrae deterministicamente chunk e frammenti tecnici;
- accetta e valida candidati JSONL prodotti all’esterno, anche senza AI e senza package `AIPKG_*`;
- fonde deterministicamente i `candidate_fact` e i `candidate_relation` validi;
- renderizza deterministicamente il registry semantico risultante.

Manca però il passaggio applicativo:

```text
chunk / source_fragment
  -> regola di derivazione deterministica
  -> candidate_fact / candidate_relation significativo
  -> candidate_records
```

Esiste un’eccezione letterale importante: `ai package` genera deterministicamente un `output_template.jsonl` contenente record formalmente di tipo `candidate_fact`, `candidate_relation` e `candidate_question`. Quei record usano però valori placeholder come `REPLACE_ENTITY` e `REPLACE_RELATION`: sono modelli da compilare, non conclusioni ricavate dalle evidenze. Poiché il validatore attuale li considera validi, potrebbero anche essere importati e, per fact e relation, fusi senza modifiche. Questa è una lacuna di validazione, non una reale capacità di generazione deterministica della conoscenza.

La formulazione più precisa è quindi:

> `dsl-manager` possiede una pipeline deterministica **a valle** dei candidati e produce deterministicamente le evidenze **a monte** dei candidati, ma non implementa la derivazione deterministica che collega i due livelli.

## Perimetro e metodo

L’analisi è stata svolta sui documenti richiesti, sui report delle slice 1-19, sui 55 file Python correnti sotto `src/dsl_mngr`, sui 23 file Python di test e sulle fixture pertinenti. Non sono stati eseguiti test: la verifica è statica e documentale, in conformità alla limitazione della richiesta.

Sono stati confrontati separatamente:

1. ciò che il design prevedeva;
2. ciò che i manuali dichiarano;
3. ciò che il codice di produzione può effettivamente eseguire;
4. ciò che i test dimostrano;
5. il caso limite del template generato dal package AI.

In caso di contrasto, il verdetto sulla capacità corrente è basato sul codice e sui test, non sul design prospettico.

## Distinzioni necessarie

Nel progetto, quattro concetti non sono equivalenti:

| Livello | Oggetti | Produttore corrente | Funzione |
| --- | --- | --- | --- |
| Evidenza documentale | `chunks` | chunker | Blocchi di testo citabili |
| Evidenza strutturale | `source_fragments` | parser DDL, XML, DB code e log | Oggetti e collegamenti tecnici osservati |
| Proposta da validare | `candidate_records` | file JSONL esterno, importato dall’applicazione | Staging prima del merge |
| Conoscenza consolidata | `facts`, `relations` | `facts merge` | Input del renderer DSL |

Un parser deterministico può quindi conoscere già una foreign key o una relazione `form edits table` senza che quella conoscenza sia stata materializzata come `candidate_relation` o come record nella tabella `relations`.

Anche “merge deterministico” e “generazione deterministica dei candidati” sono capacità diverse:

- il primo trasforma in modo ripetibile candidati già disponibili;
- la seconda dovrebbe creare quei candidati a partire dalle evidenze.

Il primo esiste; la seconda no.

## Evidenze nel codice

### 1. I parser producono frammenti, non candidati

I parser correnti costruiscono record con `fragment_type`, testo, hash, metadati e riferimenti alla revisione:

- `ddl_parser.py` genera `ddl_table`, `ddl_column` e `ddl_constraint` (`src/dsl_mngr/core/ddl_parser.py`, da riga 203);
- `xml_form_parser.py` genera `xml_form`, `xml_field` e `xml_button` (`src/dsl_mngr/core/xml_form_parser.py`, da riga 258);
- `db_code_parser.py` genera `sql_trigger`, `sql_procedure` e `sql_statement` (`src/dsl_mngr/core/db_code_parser.py`, da riga 291);
- `log_parser.py` genera `log_event` (`src/dsl_mngr/core/log_parser.py`, da riga 178).

I metadati contengono già informazioni adatte a regole deterministiche:

- DDL: `table_name`, `column_name`, `constraint_kind`, `references_table`;
- XML: `form_name`, `table_name`, `column_name`, `edit_relations`;
- DB code: `target_table`, `reads`, `writes`, `calls`;
- log: `component`, `event_kind`, `observed_identifiers`.

Questa è la materia prima necessaria per generare candidati tecnici, ma nessuno dei quattro parser costruisce record `candidate_*`, chiama l’import candidati o scrive nelle tabelle semantiche.

I report di implementazione lo dichiarano senza ambiguità:

- Slice 12: “Nessun inserimento diretto in `facts` e nessun candidate record sintetico”;
- Slice 13: nessun inserimento in `facts`, `relations` o `candidate_records` da parte del parser;
- Slice 14: i worker parser non inseriscono `candidate_records`, `facts` o `relations`.

### 2. Non esiste un comando o un modulo di derivazione

La CLI espone scan, normalizzazione, chunking, parser, package/import AI, validazione candidati, merge, render, diff ed export. In `src/dsl_mngr/cli/app.py` non esiste un comando equivalente a:

```text
candidates derive
infer deterministic
fragments promote
```

Nell’intero codice di produzione non è presente un modulo che trasformi i metadati dei frammenti in `candidate_fact` o `candidate_relation` significativi.

Anche `batch process-dir` si ferma a normalizzazione, chunking o parser. Le azioni eseguite sono elencate in `src/dsl_mngr/core/batch.py`, righe 467-578; la pianificazione per tipo di sorgente è alle righe 665-739. Non viene pianificata alcuna generazione di candidati.

Esistono batch separati per:

- trovare file JSONL già disponibili;
- validarli e importarli;
- fondere i relativi candidate batch.

Sono consumer e orchestratori di candidati esistenti, non generatori.

### 3. L’import generico accetta candidati di qualunque origine

`import_candidate_file` legge un file UTF-8 riga per riga, valida ogni payload e inserisce i record accettati in `candidate_records` (`src/dsl_mngr/core/candidate_import.py`, righe 119-200).

Il comando:

```text
dsl-manager candidates validate <workspace> --input <file.jsonl>
```

non richiede un package AI. Il manuale lo documenta come validazione manuale senza package AI (`manuale_utente_dsl_manager.md`, righe 865-869).

Di conseguenza, uno script esterno deterministico può già produrre un JSONL conforme e usare la pipeline corrente:

```text
regole esterne
  -> deterministic_candidates.jsonl
  -> candidates validate
  -> facts merge
  -> dsl render
```

Questo dimostra che l’applicazione non dipende tecnicamente dall’AI. Non dimostra però che sia l’applicazione a creare i candidati.

Il registry non conserva inoltre un campo strutturato equivalente a `producer_type`, `rule_id` o `rule_version`. Un candidato generato da uno script deterministico risulta quindi distinguibile da uno AI o manuale solo tramite convenzioni nei campi liberi, non tramite una provenienza applicativa forte.

### 4. Il validatore verifica forma ed evidenza, non deriva semantica

`validate_candidate_payload` (`src/dsl_mngr/core/candidate_validation.py`, righe 61-167) controlla:

- tipo record e campi obbligatori;
- `assertion_type` e `confidence`;
- esistenza di revisione, chunk o frammento;
- appartenenza dell’evidenza alla revisione;
- presenza letterale di `evidence_text` nel chunk o frammento.

Non controlla che:

- `source_entity` e `target_entity` siano ricavati dai metadati citati;
- una `relation_type` sia compatibile con il tipo di frammento;
- un `candidate_fact` descriva davvero l’evidenza;
- i marker `REPLACE_*` siano stati sostituiti;
- la regola che avrebbe prodotto il candidato esista e sia versionata.

Il validatore è quindi un gate “evidence-or-reject”, non un motore di inferenza.

### 5. Il merge consuma esclusivamente candidate record

`merge_candidate_batch` carica i record da `candidate_records` e:

- invia `candidate_fact` a `_merge_fact`;
- invia `candidate_relation` a `_merge_relation`;
- salta gli altri tipi correnti.

Il dispatch è in `src/dsl_mngr/core/merge.py`, righe 160-188. Gli inserimenti in `facts` e `relations` avvengono rispettivamente a partire dalle righe 267 e 352.

Il merge non legge `source_fragments` per scoprire nuovi fatti o relazioni. Usa chunk e frammenti solo indirettamente come riferimenti di evidence già presenti nel candidate record.

### 6. Il renderer non promuove le evidenze

Il renderer carica `facts`, `relations`, `conflicts` e le relative evidence table (`src/dsl_mngr/core/dsl_renderer.py`, righe 331-411). Non legge chunk o frammenti come contenuto semantico autonomo.

Pertanto:

```text
parser riuscito
  + source_fragments popolati
  + nessun candidate_record fuso
  =
snapshot senza quei fatti e quelle relazioni
```

Il renderer non colma il passaggio mancante.

## Evidenze nei test

I test dei parser confermano la separazione:

- `test_slice_12_parse_ddl.py` esegue il parser, poi costruisce esplicitamente in test un dizionario `candidate_relation`, lo scrive in un file e invoca `candidates validate`;
- `test_slice_13_parse_xml_form.py` fa lo stesso per la relazione `FRM_CLIENTE -[edits]-> ANCLI`;
- `test_slice_14_parse_db_code_log.py` costruisce esplicitamente candidate fact e relation per comportamento SQL ed eventi log;
- `test_slice_09_golden_pipeline.py` usa una fixture statica di candidati AI prima del merge;
- `test_slice_16_batch_orchestration.py` prepara ancora candidati come input del batch di validazione.

Questi test dimostrano che i frammenti sono evidence lookup validi per candidati, non che i parser generino i candidati.

Nessun test di produzione copre un flusso:

```text
parse
  -> candidate_records creati automaticamente
  -> merge
```

I test coprono invece:

```text
parse
  -> candidato scritto dalla fixture o dal test
  -> validate/import
  -> merge
```

## Il controesempio di `output_template.jsonl`

`build_output_template_jsonl` (`src/dsl_mngr/core/ai_package.py`, righe 692-770) crea deterministicamente record JSONL con:

- ID reali di chunk o frammenti;
- `evidence_text` realmente presente;
- campi obbligatori non vuoti;
- valori semantici placeholder come `REPLACE_ENTITY`, `REPLACE_FACT_TYPE`, `REPLACE_RELATION`.

`test_slice_15_ai_package.py`, righe 95-103, verifica esplicitamente che i record template siano accettati da `validate_candidate_payload`.

Ne deriva un risultato sottile:

1. l’applicazione produce byte che hanno formalmente la forma di candidati;
2. tali record sono deterministici e validabili;
3. il file è presentato come template destinato a un elaboratore esterno;
4. il contenuto non rappresenta fatti o relazioni derivati dall’evidenza;
5. il merge non rifiuta i placeholder.

Se l’utente passasse direttamente quel template a `candidates validate` e poi a `facts merge`, il `candidate_fact` e il `candidate_relation` placeholder potrebbero essere materializzati. Il `candidate_question` sarebbe invece conservato ma saltato dal merge corrente.

Per questo motivo sono necessarie due risposte:

| Interpretazione della domanda | Risposta |
| --- | --- |
| L’applicazione genera autonomamente candidati utili, semanticamente derivati e ripetibili? | **No** |
| L’applicazione genera deterministicamente record che hanno la forma sintattica di candidati? | **Sì, soltanto come template placeholder** |
| Quei template costituiscono una feature di derivazione deterministica? | **No** |
| I placeholder possono attraversare per errore validazione e merge? | **Sì** |

Il manuale descrive correttamente `output_template.jsonl` come “esempi compilati con identificativi reali” (`manuale_utente_dsl_manager.md`, righe 829-835), ma non evidenzia con sufficiente forza che tali esempi sono validabili e potenzialmente mergeable senza sostituzione.

## Confronto tra design, manuali e implementazione

### Design v1

Il design v1 prevedeva più di quanto sia stato implementato:

- DDL: `parse_ddl -> structural facts diretti` e “estrazione deterministica minima” (`.kb/documenti/documenti di design/run 1/design_document_v_01.md`, righe 1176-1197);
- XML: `parse_xml_form -> facts strutturali diretti` (righe 1199-1208);
- procedure e trigger: relazioni read/write/call dirette (righe 1210-1219);
- log: eventi osservati prima dell’eventuale AI (righe 1221-1230);
- deliverable delle slice 12-14: structural facts, procedure/trigger facts, log event facts e `observed_in` relations (righe 3148-3219).

Contemporaneamente, la pipeline standard del medesimo design prevede la pausa `WAITING_FOR_AI_CANDIDATES` prima di import, validate e merge (righe 1144-1160). Il design contiene quindi due filoni non completamente riconciliati: promozione strutturale diretta e pipeline candidate-first.

### Implementazione e report slice

L’implementazione ha scelto il secondo filone:

```text
parser
  -> source_fragments
  -> candidato esterno
  -> candidate_records
  -> facts / relations
```

I report delle slice 12-14 precisano esplicitamente che l’inserimento automatico di candidati, fact e relation è fuori scope. Il report della Slice 15 aggiunge che non è stata introdotta alcuna “euristica di generazione candidati”. Il report della Slice 16 ribadisce che non è stata aggiunta generazione euristica.

Questa è una deviazione funzionale rispetto alle parti del design che richiedevano structural facts diretti.

### Manuali correnti

I manuali correnti sono sostanzialmente coerenti con il codice:

- i candidati sono prodotti da un’AI o da un operatore (`manuale_utente_dsl_manager.md`, righe 181-183);
- i parser producono frammenti;
- il package prepara evidenze, schema e template;
- `candidates validate` o `ai import` crea i candidate record;
- `facts merge` consuma i candidate record;
- il DSL deriva da facts e relations.

`analisi_tecnica_dsl_manager.md` mostra esplicitamente le pipeline tecniche:

```text
DDL/XML/SQL/log
  -> source_fragments
  -> AI package
  -> candidati
  -> registry
```

alle righe 729-782.

Le due discussioni sui candidati deterministici arrivano dunque alla conclusione operativa corretta: manca la promozione automatica `frammenti -> candidati deterministici`. Alcune loro frasi presentano però come citazione esplicita del manuale ciò che è soprattutto una deduzione dalla pipeline documentata. La conclusione resta valida, ma la prova decisiva viene dai report slice e dal codice.

## Cosa può fare oggi il sistema senza AI

Senza usare un modello AI, l’applicazione può:

- scansionare e revisionare le fonti;
- normalizzare e chunkare documenti;
- estrarre tabelle, colonne, vincoli, form, field, button, procedure, trigger, statement ed eventi;
- creare un package leggibile di evidenze, senza inviarlo a un’AI;
- importare candidati scritti manualmente o da uno script deterministico esterno;
- validarli, fonderli, renderizzare il DSL ed esportare il grafo.

Non può, con una feature interna supportata:

- convertire automaticamente una foreign key in `candidate_relation`;
- convertire automaticamente una tabella o colonna in `candidate_fact`;
- convertire `reads`, `writes` o `calls` in relazioni candidate;
- convertire un mapping XML form/column in candidato;
- convertire un `log_event` in candidate fact o relation;
- registrare la regola deterministica e la sua versione come provenienza del candidato.

Il package AI non è obbligatorio. Il concetto di candidato, nella pipeline corrente, lo è invece per popolare facts e relations attraverso l’API pubblica prevista.

## Lacuna funzionale identificata

La capacità mancante potrebbe essere espressa come un comando:

```text
dsl-manager candidates derive <workspace> --rules <profilo>
```

con il seguente contratto minimo:

1. leggere solo evidenze attive;
2. applicare regole versionate e idempotenti;
3. produrre `candidate_fact` e `candidate_relation` con evidence letterale;
4. registrare `producer_type=deterministic_rule`, `rule_id` e `rule_version`;
5. rifiutare marker placeholder;
6. creare un normale `CBATCH_*`;
7. lasciare invariati validazione, merge e render.

Regole iniziali a bassa ambiguità potrebbero coprire `references`, `has_column`, `primary_key`, `edits`, `binds_to`, `triggered_on`, `reads`, `writes`, `calls` e `observed_in`. Il mapping da oggetti tecnici a concetti di dominio dovrebbe rimanere separato quando richiede interpretazione.

## Verdetto finale

Alla domanda:

> L’applicazione dispone della capacità di creare candidati per il merge deterministici?

la risposta verificata è:

> **No, non dispone di una capacità funzionale di generazione deterministica di candidati significativi.** Dispone dei dati strutturati necessari per implementarli, accetta candidati deterministici prodotti esternamente e tratta deterministicamente validazione, merge e rendering. Genera inoltre template candidate-shaped deterministici, ma sono placeholder e non costituiscono derivazione di conoscenza.

Pertanto l’affermazione centrale dei manuali e delle discussioni è corretta sul piano operativo, purché sia qualificata con l’eccezione di `output_template.jsonl` e con la distinzione tra:

```text
determinismo dell’estrazione
determinismo della generazione dei candidati
determinismo del merge
```

Solo il secondo manca.

## Autoverifica

- **La conclusione risponde direttamente alla domanda?** Sì: il verdetto operativo è “no”.
- **È stato distinto “senza AI” da “senza candidati”?** Sì: l’AI non è obbligatoria; un candidato importabile lo è nel percorso pubblico verso facts e relations.
- **È stato verificato che i parser non scrivano candidate record o oggetti semantici?** Sì, tramite parser, registry, report Slice 12-14 e test relativi.
- **È stato verificato che il merge non generi candidati?** Sì: consuma esclusivamente `candidate_records`.
- **È stato verificato che il renderer non promuova frammenti?** Sì: legge facts, relations, conflicts ed evidence associate.
- **È stato considerato un controesempio alla risposta “no”?** Sì: `output_template.jsonl` crea record candidate-shaped deterministici e validabili.
- **Il controesempio cambia il verdetto funzionale?** No, perché contiene semantica placeholder e non deriva conclusioni dalle evidenze.
- **Sono state considerate discrepanze documentali?** Sì: il design v1 prevedeva structural facts diretti, mentre implementazione e report slice li hanno esclusi.
- **Sono stati eseguiti test o modificato codice?** No. È stata svolta analisi statica, come richiesto.
- **È stato necessario consultare il web?** No: il repository fornisce evidenze primarie sufficienti e più autorevoli per la domanda sull’implementazione locale.

## Infrazioni alla regola sui file non-input

Nessuna. Non è stato letto il contenuto di file non inclusi nel perimetro indicato. L’unico file creato è il presente output, espressamente richiesto.
