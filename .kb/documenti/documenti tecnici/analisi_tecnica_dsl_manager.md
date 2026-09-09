# Analisi tecnica di DSL Manager

> Release applicativa di riferimento: **1.1.0**.

## 1. Scopo e stato osservato

Questo documento descrive il comportamento realmente consegnato fino alla Slice 28.
Il riferimento normativo della run 2 è il
[design v02](../documenti%20di%20design/run%202/design_document_v_02.md); il
[design v01](../documenti%20di%20design/run%201/design_document_v_01.md) resta una
baseline storica per le parti non sostituite. I dettagli dei formati sono nei
[contratti manifest](contratti_manifest_dsl_manager.md) e l'uso operativo nel
[manuale utente](../manuali/manuale_utente_dsl_manager.md).

Lo stato corrente implementa il percorso:

```text
byte sorgente immutabili
  -> source/source_revision
  -> normalizzazione o parser strutturale
  -> evidenze localizzabili
  -> candidati pending
  -> decisione persistita
  -> candidato merge-eligible
  -> merge autoritativo
  -> viste effettive
  -> DSL v1/v2, diff e GEXF statico/dinamico
```

La pipeline non attribuisce autorità semantica ai parser, a Docling, ai metadata
o a un generatore AI. Il registry SQLite è la base persistente; gli snapshot DSL
e i grafi sono viste derivate e immutabili.

## 2. Architettura

Il package usa il layout `src/` e import assoluti da `dsl_mngr`.

| Area | Responsabilità osservata |
|---|---|
| `dsl_mngr.cli` | parser dei comandi, validazione d'uso, messaggi ed exit code |
| `dsl_mngr.core` | workspace, registry, migrazioni, run, review, derivazione, merge, reconcile, DSL, diff, temporalità, OOXML e GEXF |
| `dsl_mngr.workers` | processi isolati per Docling, parser e costruzione degli artefatti |
| `dsl_mngr.resources.gexf` | XSD GEXF 1.3 vendorizzati, manifest e licenza |
| `tests` | unit, migrazione, integrazione, golden, no-network ed end-to-end Aurora |

Le mutazioni persistenti passano dal core e da transazioni SQLite. I worker
producono artefatti temporanei, che il processo padre valida prima di pubblicare
e registrare. Il codice non usa ORM né servizi esterni obbligatori.

## 3. Workspace, fonti ed evidenze

`dsl-manager init` crea la struttura del workspace; `dsl-manager db init`
applica le migrazioni. `corpus scan` calcola SHA-256, dimensione e percorso
relativo e mantiene distinti:

- `source`: identità logica nel tempo;
- `source_revision`: una precisa sequenza di byte;
- `chunk`: evidenza testuale normalizzata;
- `source_fragment`: evidenza strutturale prodotta dai parser.

Una modifica dei byte crea una nuova revisione. Chunk e frammenti sono ancorati
alla revisione e hanno locator verificabili. Gli hash semantici escludono path
assoluti, run ID, timestamp operativi e note di audit.

Il batch di base instrada documenti verso Docling e fonti DDL/XML/codice DB/log
verso parser dedicati. Normalizzazione e parsing sono osservazione, non review.

## 4. State machine di review

### 4.1 Invariante di merge

Un candidato appena importato o derivato è `pending`: l'assenza di una testa di
review non è un'approvazione. È merge-eligible soltanto se:

1. è la foglia corrente della propria lineage;
2. la testa corrente esiste;
3. l'outcome della testa è `confirmed`.

`rejected`, `superseded`, candidati non foglia e candidati senza testa sono
saltati, oppure causano rollback con `--strict-review`. Il merge rilegge testa e
foglia nella propria transazione, quindi una decisione obsoleta non può essere
usata come autorizzazione implicita.

### 4.2 Decisioni, idempotenza e concorrenza

Gli outcome persistiti sono `confirmed`, `rejected` e `superseded`. Le decisioni
sono append-only e la testa è separata in `review_subject_heads`.

- L'attore umano deve avere un `actor_id` stabile; non viene inferito dallo user
  name del sistema operativo.
- Una policy automatica deve essere presente nell'allowlist configurata e deve
  portare `policy_id` e `policy_version`.
- Il replay per `(actor_type, actor_id, idempotency_key)` viene verificato prima
  del controllo della testa.
- La stessa chiave con payload diverso produce
  `idempotency_payload_conflict`.
- `--expected-head-decision-id` implementa optimistic concurrency dentro
  `BEGIN IMMEDIATE`; una testa stantia produce `review_head_conflict`.
- Se la semantica richiesta coincide con la testa corrente, l'azione è
  `semantic_noop` e non nasce una nuova decisione.

### 4.3 Correzione e reconcile

La correzione non modifica il candidato originario. In un'unica transazione:

1. marca la testa dell'originale `superseded`;
2. crea un batch `human_correction` e un candidato sostitutivo;
3. collega root, parent e gruppo di correzione;
4. conferma la sostituzione;
5. apre `reconciliation_required` se l'originale era già materializzato.

La lineage è append-only, aciclica e a foglia singola. La riconciliazione chiude
o sostituisce supporti materializzati senza cancellare la storia. Finché esiste
una riconciliazione aperta, render, diff ed export falliscono per default con
`reconciliation_required`.

### 4.4 Viste effettive

Le viste `effective_fact_evidence`, `effective_relation_evidence`,
`effective_facts` ed `effective_relations` selezionano solo supporti di foglie con
testa `confirmed`. Un fatto o una relazione resta effettivo se conserva almeno
un altro supporto positivo corrente. DSL v2 e GEXF dinamico leggono queste viste.

## 5. Derivazione candidate-first

`candidates derive` applica un solo contratto versionato alla volta e produce un
batch deterministico di candidati pending. Nessuna regola scrive direttamente
nel registro semantico.

| Regola | Evidenza | Output | Review automatica |
|---|---|---|---|
| `ddl_table_fact/1` | tabella DDL esplicita | fact tecnico | consentita con policy esatta |
| `ddl_column_fact/1` | colonna DDL | fact tecnico | consentita con policy esatta |
| `ddl_fk_relation/1` | FK risolta | relazione tecnica | consentita; FK irrisolta è rifiutata |
| `xml_form_structure/1` | form/campo/pulsante | fact tecnico | consentita con policy esatta |
| `xml_table_usage/1` | operazione XML esplicita | relazione tecnica | consentita con policy esatta |
| `db_code_unit/1` | funzione/procedura/trigger | fact tecnico | consentita con policy esatta |
| `db_code_dependency/1` | read/write/call | relazione osservata | consentita con locator completo |
| `log_event_observation/1` | evento di log | fact osservazionale | pending salvo policy nominata |
| `excel_workbook_fact/1` | manifest/regioni | fact workbook | consentita con policy esatta |
| `excel_sheet_fact/1` | foglio | fact foglio | consentita con policy esatta |
| `excel_region_fact/1` | regione | fact regione | consentita con policy esatta |
| `excel_named_range_fact/1` | named range | fact tecnico | consentita con policy esatta |
| `excel_table_fact/1` | tabella OOXML | fact tecnico | consentita con policy esatta |
| `excel_explicit_reference/1` | riferimento esplicito | relazione tecnica | mai automatica |

Il validator comune rifiuta riferimenti a revisione/evidenza incoerenti e
placeholder irrisolti nei campi semantici. Un nome tecnico non viene promosso a
concetto di dominio. `candidate_mapping`, `candidate_conflict` e
`candidate_question` sono validati e conservati, ma il merge corrente non crea
oggetti semantici dedicati per questi tre tipi.

## 6. Batch consolidato

`batch consolidate` orchestra cinque fasi checkpointed:

```text
parse -> derive -> review -> merge -> reconcile
```

Le fasi completate sono riusate da `--resume`; una ripresa di una run conclusa
crea una run figlia con `retry_of`. L'ordine degli input è normalizzato, i
contatori sono aggregati e gli artefatti di checkpoint/report sono pubblicati in
forma canonica. `--strict-review` rende atomico il fallimento per candidati non
eleggibili; `--reconcile` esegue la compensazione solo dopo merge completato.
L'assenza di policy automatiche lascia i candidati pending, come previsto.

## 7. Excel diretto e manifest

### 7.1 Un'unica sequenza di byte

`.xlsx` e `.xlsm` sono letti direttamente dalla medesima sequenza di byte già
registrata. `.xlsm` non viene convertito in `.xlsx`; le macro non sono eseguite,
le formule non sono ricalcolate e i collegamenti esterni non sono dereferenziati.
Prima e dopo l'elaborazione viene verificato l'hash della revisione.

Il preflight OOXML precede Docling e rifiuta package non ZIP, estensione/content
type incoerenti, path interni pericolosi, DTD/entity e relazioni esterne non
conformi. Docling 2.97.0 produce la vista leggibile `normalized.json` e
`normalized.md`. Il parser OOXML produce la vista strutturale
`workbook_manifest.json` e frammenti `excel_region`.

### 7.2 Autorità delle due viste

Per struttura, formule, tipi cella, fogli, regioni, named range, tabelle,
relazioni e macro hash, il manifest è la fonte tecnica. Il Markdown Docling è
solo una vista di lettura. Formula e cached value restano campi distinti; nessuno
dei due diventa automaticamente verità di dominio.

Il manifest registra, senza esecuzione:

- ordine/nome/visibilità dei fogli e relative parti OOXML;
- celle tipizzate, coordinate, valori, formule e cached value disponibili;
- celle unite, named range, tabelle, hyperlink e relazioni;
- link esterni inventariati come non dereferenziati;
- presenza e SHA-256 del progetto VBA per `.xlsm`;
- regioni deterministiche e locator dei frammenti.

## 8. Sicurezza e budget

I default/hard maximum applicati dal codice sono:

| Risorsa | Default | Hard maximum |
|---|---:|---:|
| file OOXML | 64 MiB | 256 MiB |
| entry ZIP | 20.000 | 100.000 |
| byte decompressi | 512 MiB | 2 GiB |
| rapporto di compressione | 100:1 | 1.000:1 |
| singola part XML | 32 MiB | 128 MiB |
| fogli | 256 | 1.024 |
| celle indirizzate | 2.000.000 | 10.000.000 |
| regioni | 10.000 | 50.000 |
| relazioni | 50.000 | 250.000 |
| output per sorgente | 256 MiB | 1 GiB |
| timeout worker Excel | 120 s | 600 s |
| memoria worker Excel | 1 GiB | 4 GiB |
| evidenze temporali per sorgente | 100.000 | 1.000.000 |
| intervalli per soggetto | 1.000 | 10.000 |

Su Windows il limite di memoria può essere `monitored`: il processo viene
osservato e terminato oltre soglia, ma il report non lo presenta come hard limit.
Timeout, memoria e output limit sono imposti dal parent. Gli artefatti parziali
non validi vengono scartati; lo stato `partial`/exit `6` è distinto da un errore
operativo.

Gap osservato: il design prevede anche un budget per `nodi+archi GEXF`
(1.000.000 default, 5.000.000 hard maximum), ma il codice corrente non espone né
applica tale limite.

## 9. Evidenza temporale e policy

Le migrazioni v9 e v10 separano quattro livelli:

```text
raw_temporal_evidence
  -> gruppo/concordanza/conflitto
  -> candidato temporal_interval pending
  -> decisione comune di review
  -> temporal_intervals effettivi
```

Le fonti implementate includono proprietà OOXML, timestamp interni ZIP, metadata
PDF/HTML/JSON-LD, dichiarazioni esplicite in testo/Markdown/SQL/XML/log, token nel
nome file e `sources.first_seen_at`. Sono segnali con affidabilità e warning, non
verità. In particolare, i timestamp del filesystem (`mtime`, `ctime`) non sono
raccolti come evidenza; `sources.first_seen_at` è una registrazione operativa a
bassa affidabilità e non dimostra validità semantica.

Segnali duplicati o correlati non aumentano la forza. Segnali indipendenti
concordi sono raggruppati; segnali incompatibili aprono un conflitto. Ogni
proposta resta pending e usa la stessa review dei candidati ordinari.

Precisione e timezone non vengono inventate:

- `year` e `month` diventano coverage envelope inclusivi;
- `day` resta una data precisa;
- `dateTime` conserva offset esplicito o richiede timezone risolta;
- timezone `unknown`/`incompatible` non viene troncata a data e non è esportata
  in strict mode;
- più intervalli disgiunti sullo stesso soggetto restano più intervalli/spells.

La propagazione temporale è solo esplicita e versionata; non esiste ereditarietà
automatica da sorgente a fatto o relazione.

## 10. DSL, diff e GEXF

### 10.1 DSL v1 e v2

Lo schema 1 rimane il profilo legacy/statico e legge lo stato fisico. Lo schema
2 legge le viste effettive, include sempre `intervals` e metadata temporali e
supporta più intervalli. Snapshot già registrati non sono riscritti.

Con riconciliazioni aperte entrambi gli schemi sono bloccati per default. Solo
`dsl render --schema-version 2 --allow-incomplete` può produrre una vista
incompleta: omette oggetti non effettivi e registra warning e conteggi. Lo schema
1 rifiuta `--allow-incomplete`.

`dsl diff` confronta per default snapshot dello stesso schema. Il confronto
v1/v2 richiede `--cross-schema` e separa categorie strutturali, di governance e
temporali; non finge equivalenza tra rappresentazioni fisiche ed effettive.

### 10.2 GEXF

- snapshot DSL v1 -> export GEXF statico legacy;
- snapshot DSL v2 -> `graph export --dynamic` GEXF 1.3;
- `--allow-incomplete` è ammesso solo con `--dynamic`;
- un file usa un solo `timeformat`, `date` oppure `dateTime`;
- `--temporal-output-mode strict|omit|separate` governa profili incompatibili;
- bounds e spells sono inclusivi e ordinati;
- ogni intervallo di edge deve essere contenuto negli intervalli dei nodi
  estremi.

Il GEXF dinamico viene validato offline in due passaggi: XSD 1.3 vendorizzati e
validazione semantica. La sola validazione XSD non è sufficiente. Le risorse XSD
sono verificate per SHA-256 e un resolver locale nega risoluzioni esterne.

## 11. Migrazioni v7-v10

Le migrazioni sono append-only, checksumate e applicate atomicamente.

| Versione | Nome | Contratto principale |
|---:|---|---|
| 7 | `create_candidate_review_lineage_schema` | review, heads, evidence, lineage, correzioni, reconcile, derivation run, effective views; backfill legacy selettivo |
| 8 | `create_workbook_manifest_schema` | manifest, fogli e regioni workbook |
| 9 | `create_temporal_core_schema` | raw evidence, dettagli/evidence candidati e intervalli append-only |
| 10 | `create_temporal_consolidation_schema` | gruppi, indipendenza/correlazione e conflitti temporali |

Il backfill v7 conferma solo candidati legacy `explicit`/`observed` che già
sostengono oggetti `active`, con policy `legacy_backfill/1`. Pending, inferred,
ambiguous e conflicted non vengono promossi. Le migrazioni non cambiano i byte o
gli hash degli snapshot storici.

## 12. Result catalog osservato

Review, derive, merge, reconcile e batch consolidato espongono
`catalog_version: result_catalog_v1` e campi machine-readable per condition,
status/outcome, reason, severity, mutations, retryable, exit code, soggetti,
artefatti e contatori.

Gap osservato rispetto al design: preflight OOXML e fallback del worker usano
`catalog_version: 1`, mentre report temporali e `graph_report.json` non espongono
l'intero envelope comune. Gli exit code e le reason specialistiche esistono, ma
il catalogo non è ancora uniforme fra tutti i produttori previsti. La Slice 29
documenta il gap e non introduce la correzione runtime.

## 13. AI handoff e assenza di rete

`ai package` crea un package locale con manifest, source manifest, istruzioni,
schema candidato e template. `ai inbox scan` verifica package e staleness;
`ai import` importa JSONL soltanto attraverso il validator comune. L'opzione
`--allow-stale` è una scelta esplicita e viene riportata; non rende affidabile
l'evidenza obsoleta. I candidati importati restano pending.

Il repository non contiene una chiamata AI reale nel percorso end-to-end. Un
adapter può soltanto proporre evidenze o candidati; non può scrivere fatti,
decisioni o intervalli autoritativi. Test OOXML, temporali e GEXF verificano
l'assenza di rete nei percorsi previsti.

## 14. Compatibilità e limiti noti

- DSL schema 1 e GEXF statico preservano la semantica fisica legacy; DSL schema
  2 e GEXF dinamico sono le viste governate.
- `--allow-incomplete` non è una scorciatoia di merge: vale solo per DSL v2 o
  export dinamico e produce omissioni dichiarate.
- `.xlsm` è input diretto, non conversione; macro e link non vengono eseguiti.
- `candidate_mapping`, `candidate_conflict` e `candidate_question` non hanno
  materializzazione semantica dedicata.
- La semantica temporale non è esposta da un comando CLI autonomo: è integrata
  nei servizi e nel batch consolidato.
- Il catalogo esiti e il budget GEXF hanno i gap indicati nelle sezioni 8 e 12.
- La UI resta locale e di sola lettura.

## 15. Evidenze di implementazione

Le capacità sopra sono coperte dai test `test_slice_20_*` fino a
`test_slice_28_*`; i golden principali sono in `tests/expected`. Il corpus
end-to-end è descritto nel
[LEGGIMI Aurora](../../projects/corpus%20aurora/corpus_mock_aurora_prestiti/LEGGIMI_PRIMA.md).
La mappa sintetica del viaggio è nell'
[outline input-output](../manuali/outline_dsl_manager_flow_from_input_to_output_riassunto.md).
