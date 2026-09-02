# DSL Manager - estensione temporalità semantica v1.1

**Data:** 2026-06-13  
**Formato:** design document aggiuntivo al documento `.kb/documenti/documenti di design/run 1/design_document_v_01.md`  
**Repository di riferimento:** `dsl_manager-v1`  
**Package Python:** `dsl_mngr`  
**Scope:** temporalità semantica nel registry, nel DSL e negli export GEXF

---

## 1. Sintesi

Questo documento propone un'estensione del design v1 di DSL Manager con una
capacità nuova: rappresentare nel DSL e nei grafi esportati l'intervallo di
validità semantica delle informazioni ricostruite.

Per "validità semantica" si intende il periodo in cui una fonte o un contenuto
di dominio deve essere considerato applicabile al sistema legacy. Non coincide
con:

```text
- data di creazione del file nel filesystem;
- data di scansione del corpus;
- data di import nel registry;
- data di una run;
- data di rendering dello snapshot DSL.
```

La regola centrale è:

```text
Le date operative descrivono quando il workbench ha visto qualcosa.
Le date semantiche descrivono quando quel qualcosa è valido nel dominio.
```

La temporalità semantica entra nel sistema come evidenza candidata, non come
verità. Può essere estratta dal nome file, dai metadati del documento o dal
contenuto tramite AI, e questi metodi possono coesistere. Nessun intervallo
temporale deve influenzare il DSL o il grafo dinamico finché non è stato
confermato da un utente tramite una decisione di review.

---

## 2. Relazione con il design v1

Il design v1 contiene già i principi necessari:

```text
- Registry First;
- Append-Only by Default;
- Evidence-or-Reject;
- AI as Candidate Generator;
- review umana esplicita come evoluzione prevista;
- snapshot DSL generati dal registry;
- export GEXF come vista derivata.
```

Questa estensione non cambia il principio:

```text
Il DSL resta una vista generata.
Il registry resta la memoria primaria.
L'AI propone candidati.
L'utente conferma o rifiuta ciò che non è deterministico.
```

Il cambiamento principale è l'aggiunta di un livello temporale esplicito:

```text
source_revisions
  -> source_temporal_claims
  -> review_decisions
  -> source_revision_validity_intervals
  -> fact/relation temporal derivation
  -> temporal DSL
  -> dynamic GEXF
```

---

## 3. Stato Attuale Rilevato

### 3.1 Conferma sul meccanismo di review

Nel documento v1 il meccanismo di review è previsto a livello concettuale:

```text
review_decisions
human_review
pending_review
confirmed_by_human
```

Nell'implementazione corrente, però, non risulta ancora presente un flusso
completo di conferma utente:

```text
- non c'è una tabella `review_decisions` nelle migrazioni correnti;
- non c'è un comando CLI dedicato alla review;
- esiste `pending_review` come status possibile dei facts ambigui;
- esistono `candidate_question` e `conflicts`, ma non una decisione utente
  persistita e riusabile dal renderer.
```

Quindi questa feature deve:

```text
- riusare `review_decisions` se nel frattempo viene implementata;
- altrimenti introdurre una review minima sufficiente per confermare,
  correggere o rifiutare intervalli temporali candidati.
```

Non bisogna assumere che il meccanismo esista già nel codice attuale.

### 3.2 Export GEXF corrente

L'export GEXF corrente produce un grafo statico:

```text
<graph defaultedgetype="directed" mode="static">
```

Usa namespace GEXF 1.2draft e non assegna `start`, `end`, `timestamp` o
`spells` a nodi e archi.

Per supportare animazione temporale in Gephi e strumenti compatibili, l'export
deve diventare dinamico quando l'opzione temporale è attiva.

---

## 4. Obiettivi

### 4.1 Obiettivi funzionali

La feature deve permettere di:

```text
1. estrarre intervalli candidati di validità documento da nome file;
2. estrarre intervalli candidati da metadati documentali;
3. estrarre intervalli candidati dal contenuto tramite AI esterna;
4. conservare tutti i candidati con evidenza e provenienza;
5. marcare ogni candidato come non affidabile finché non è confermato;
6. far confermare, correggere o rifiutare i candidati da un utente;
7. derivare la validità temporale di facts e relations dalle fonti confermate;
8. renderizzare la temporalità nel DSL;
9. esportare GEXF dinamico filtrabile e animabile per intervallo temporale;
10. mantenere audit trail completo e diff tracciabile.
```

### 4.2 Obiettivi di integrazione

La feature deve integrarsi con:

```text
- source registry;
- normalizzazione documentale;
- chunk/fragments;
- AI handoff;
- candidate validation;
- facts merge;
- DSL renderer;
- DSL diff;
- graph export;
- batch orchestration.
```

### 4.3 Obiettivi di sicurezza epistemica

Il sistema deve rendere visibile la differenza tra:

```text
- data estratta deterministicamente;
- data suggerita da AI;
- data confermata da umano;
- data corretta manualmente;
- data sconosciuta.
```

Una data non confermata non deve mai apparire come `start`/`end` dinamico nel
grafo esportato di default.

---

## 5. Non Obiettivi

La prima implementazione non deve:

```text
1. dedurre automaticamente la validità temporale di un intero sistema;
2. fondere intervalli AI senza conferma umana;
3. usare date filesystem come validità semantica affidabile;
4. richiedere un provider AI integrato nel core;
5. imporre che ogni documento abbia una validità temporale;
6. supportare calendari non gregoriani;
7. modellare bitemporalità completa evento/transaction time;
8. implementare una UI ricca prima del comando CLI di review;
9. modificare retroattivamente snapshot DSL già persistiti;
10. esportare grafi dinamici basati su claim non confermati.
```

La bitemporalità completa può essere una evoluzione futura. Questa feature
distingue solo:

```text
- tempo operativo del registry;
- tempo semantico confermato delle fonti e delle informazioni derivate.
```

---

## 6. Concetti

### 6.1 Document Validity Interval

Intervallo in cui una specifica `source_revision` è ritenuta valida come fonte
semantica.

Esempi:

```text
manuale_ordini_2024.md
  -> documento valido nel 2024, se confermato

specifica_clienti_valid_from_2023-01-01_to_2023-12-31.pdf
  -> documento valido dal 2023-01-01 al 2023-12-31, se confermato

release_notes_v5_2022Q4.docx
  -> possibile validità 2022-10-01 / 2022-12-31, se confermato
```

### 6.2 Temporal Claim

Un claim temporale è una proposta di intervallo.

Può provenire da:

```text
filename
metadata
ai_content
manual_entry
previous_review_carryover
```

Un claim temporale è sempre auditabile e ha uno status:

```text
pending_review
confirmed
rejected
superseded
conflicted
```

### 6.3 Confirmed Validity Interval

Un intervallo confermato è il risultato di una decisione utente. Solo questi
intervalli possono influenzare:

```text
- DSL temporal fields;
- DSL hash;
- DSL diff;
- GEXF `start`, `end` e `spells`;
- animazione temporale in Gephi.
```

### 6.4 Temporal Derivation

Facts e relations non ricevono manualmente una data in prima battuta. La loro
validità si deriva dalle fonti che li supportano.

Default:

```text
validità fact/relation = unione degli intervalli confermati delle evidenze
                         che supportano quel fact o quella relation
```

Motivo:

```text
Se lo stesso fatto è supportato da due documenti validi in periodi diversi,
il fatto resta supportato nei due periodi.
```

Policy alternative, configurabili in futuro:

```text
intersection
  usa solo l'intersezione degli intervalli delle evidenze;

authority_weighted
  preferisce fonti con authority_level più alto;

latest_confirmed_only
  usa solo l'intervallo confermato della fonte corrente più recente.
```

---

## 7. Estrazione Dati Temporali dai Documenti

### 7.1 Estrazione da nome file

Il nome file è una fonte utile ma non affidabile.

Il worker deve riconoscere pattern comuni senza interpretarli come verità:

```text
YYYY
YYYY-MM
YYYY-MM-DD
YYYYMMDD
YYYY_Q1, YYYYQ1, YYYY-Q1
valid_from_YYYY-MM-DD
valid_to_YYYY-MM-DD
from_YYYY-MM-DD_to_YYYY-MM-DD
dal_YYYY-MM-DD_al_YYYY-MM-DD
release_YYYY
release_YYYY_Qn
vYYYY
```

Esempio:

```text
corpus/active/manuale_ordini_2024Q2.md
```

produce:

```json
{
  "extraction_method": "filename",
  "raw_value": "2024Q2",
  "valid_from": "2024-04-01",
  "valid_to": "2024-06-30",
  "precision": "quarter",
  "status": "pending_review"
}
```

Regole:

```text
- non usare automaticamente la data di modifica del file;
- non inferire da numeri ambigui se non c'è contesto;
- conservare sempre `raw_value`;
- salvare il pattern che ha prodotto il match;
- se ci sono più match incompatibili, creare più claim o un claim conflicted.
```

### 7.2 Estrazione da metadati

I metadati possono essere:

```text
- proprietà PDF;
- proprietà Office;
- front matter Markdown;
- header HTML;
- metadati prodotti da Docling;
- metadati custom aziendali;
- manifest esterni associati al file.
```

La data filesystem (`created`, `modified`) deve essere trattata come
operativa, non semantica. Può diventare un claim solo se una policy esplicita
lo abilita, e comunque resta `pending_review`.

Esempi di chiavi rilevanti:

```text
valid_from
valid_to
effective_from
effective_to
release_date
version_date
applicable_from
applicable_to
period
competence_year
```

Ogni claim da metadati deve salvare:

```text
- metadata key;
- raw metadata value;
- hash del payload metadati normalizzato;
- source_revision_id;
- extraction_method = metadata;
- confidence iniziale;
- status = pending_review.
```

### 7.3 Estrazione da contenuto via AI

L'AI può leggere chunk o frammenti e proporre un intervallo di validità del
documento.

Esempi di frasi:

```text
"Questo manuale si applica dal 01/01/2024."
"Valido per la release 5.3."
"Le regole descritte sono obsolete dal 2023."
"Documento aggiornato per l'anno fiscale 2022."
```

Il package AI deve includere istruzioni esplicite:

```text
- produrre solo candidati temporali se il testo contiene evidenza;
- non usare conoscenza esterna;
- copiare `evidence_text` letteralmente dal chunk/frammento;
- distinguere data esplicita, data inferita e data ambigua;
- non convertire versioni applicative in date se non c'è una tabella
  evidenziale nel package.
```

Nuovo record candidate proposto:

```jsonl
{"record_type":"candidate_source_validity","candidate_id":"CAND_TEMP_001","source_revision_id":"REV_000001","chunk_id":"CHK_000001","fragment_id":null,"assertion_type":"explicit","confidence":"medium","valid_from":"2024-01-01","valid_to":"2024-12-31","precision":"day","evidence_text":"Documento valido per l'anno 2024.","notes":""}
```

Questo record non deve creare direttamente un fact. Deve creare un temporal
claim `pending_review`.

### 7.4 Coesistenza dei metodi

I metodi possono produrre claim compatibili o incompatibili.

Esempio compatibile:

```text
filename: manuale_ordini_2024.md
AI: "Documento valido per l'anno 2024"

risultato:
  due claim pending_review compatibili;
  l'utente può confermare uno o entrambi;
  il sistema può suggerire una decisione aggregata.
```

Esempio incompatibile:

```text
filename: manuale_ordini_2024.md
metadata: valid_to = 2023-12-31

risultato:
  due claim pending_review;
  stato aggregato source_revision = temporal_conflict_pending_review;
  nessun intervallo confermato finché l'utente non decide.
```

---

## 8. Review e Conferma Utente

### 8.1 Requisito

Gli intervalli temporali non sono affidabili finché non sono confermati.

Il sistema deve quindi introdurre una review minima:

```text
dsl-manager temporal claims list <workspace>
dsl-manager temporal claims show <workspace> --claim TCLM_000001
dsl-manager temporal claims confirm <workspace> --claim TCLM_000001
dsl-manager temporal claims reject <workspace> --claim TCLM_000001 --reason "..."
dsl-manager temporal claims override <workspace> --claim TCLM_000001 --from 2024-01-01 --to 2024-12-31 --reason "..."
```

La UI locale futura potrà usare le stesse API/primitive.

### 8.2 Decisioni di review

Ogni decisione deve essere append-only.

Schema logico:

```text
review_decisions
  review_decision_id
  subject_type
  subject_id
  decision_type
  decision_payload_json
  reviewer_id
  reason
  created_at
  run_id
```

Valori:

```text
subject_type:
  source_temporal_claim
  source_revision_validity_interval
  fact_temporal_interval
  relation_temporal_interval

decision_type:
  confirm
  reject
  override
  supersede
```

Per installazioni locali single-user, `reviewer_id` può essere:

```text
local_user
unknown
valore configurato in project.yaml
```

### 8.3 Override

Un override permette di correggere una proposta mantenendo audit.

Esempio:

```text
claim AI:
  valid_from = 2024-01-01
  valid_to = 2024-12-31

decisione utente:
  override valid_to = 2024-06-30

risultato:
  claim originale resta invariato;
  review_decision contiene la correzione;
  source_revision_validity_intervals contiene l'intervallo corretto.
```

### 8.4 Propagazione dopo modifica fonte

Quando una `source_revision` viene superseded:

```text
- i claim della vecchia revision restano storici;
- gli intervalli confermati della vecchia revision non si trasferiscono
  automaticamente alla nuova;
- il sistema può generare un claim `previous_review_carryover`, ma resta
  pending_review;
- il DSL corrente usa solo revisioni active e intervalli confermati per quelle
  revisioni.
```

Questo evita che una conferma umana su una vecchia versione renda valida una
nuova versione non verificata.

---

## 9. Modello Dati

### 9.1 `source_temporal_claims`

Tabella append-only dei claim temporali associati a una source revision.

```text
source_temporal_claim_id
source_revision_id
claim_kind
valid_from
valid_to
precision
timezone
extraction_method
extraction_detail_json
assertion_type
confidence
evidence_kind
chunk_id
fragment_id
evidence_text
evidence_text_hash
raw_value
status
review_decision_id
created_at
updated_at
```

Valori:

```text
claim_kind:
  document_validity

precision:
  day
  month
  quarter
  year
  date_time
  unknown

extraction_method:
  filename
  metadata
  ai_content
  manual_entry
  previous_review_carryover

evidence_kind:
  filename
  metadata_field
  chunk
  fragment
  manual_note

status:
  pending_review
  confirmed
  rejected
  superseded
  conflicted
```

Regole:

```text
- `source_revision_id` è obbligatorio;
- `valid_from` e `valid_to` sono ISO normalizzati o null;
- almeno uno tra `valid_from` e `valid_to` deve essere valorizzato;
- `valid_from <= valid_to` se entrambi presenti;
- `raw_value` conserva il testo originale;
- `evidence_text` è richiesto per `ai_content`;
- `chunk_id` o `fragment_id` è richiesto per evidence_kind chunk/fragment;
- `review_decision_id` è valorizzato solo dopo decisione utente.
```

### 9.2 `source_revision_validity_intervals`

Tabella degli intervalli confermati e attivi per source revision.

```text
source_revision_validity_interval_id
source_revision_id
valid_from
valid_to
precision
timezone
source_temporal_claim_id
review_decision_id
status
created_at
updated_at
```

Valori status:

```text
active
superseded
invalid
```

Questa tabella è derivata da review, non da AI.

### 9.3 Estensione `candidate_records`

Il validatore candidati deve accettare un nuovo `record_type`:

```text
candidate_source_validity
```

Campi richiesti:

```text
candidate_id
record_type
source_revision_id
assertion_type
confidence
evidence_text
valid_from oppure valid_to
precision
```

Campi condizionali:

```text
chunk_id oppure fragment_id
```

Il record viene accettato solo se:

```text
- evidence_text è contenuto nel chunk/frammento indicato;
- la source_revision esiste;
- il chunk/frammento appartiene alla source_revision;
- le date sono parseabili;
- l'intervallo è coerente.
```

La persistenza crea un record in `source_temporal_claims`, non in `facts`.

### 9.4 Temporal intervals per facts e relations

Per la prima implementazione, gli intervalli di facts e relations possono essere
calcolati a render time a partire da:

```text
fact_evidence.source_revision_id
relation_evidence.source_revision_id
source_revision_validity_intervals
```

Se servono performance o query SQL più semplici, si possono materializzare:

```text
fact_temporal_intervals
  fact_temporal_interval_id
  fact_id
  valid_from
  valid_to
  derivation_policy
  source_revision_ids_json
  status
  created_at

relation_temporal_intervals
  relation_temporal_interval_id
  relation_id
  valid_from
  valid_to
  derivation_policy
  source_revision_ids_json
  status
  created_at
```

La scelta consigliata per MVP temporale:

```text
calcolo a render time;
materializzazione solo se il rendering diventa costoso.
```

---

## 10. Normalizzazione Date

### 10.1 Formato interno

Usare ISO 8601.

Per date senza ora:

```text
YYYY-MM-DD
```

Per date con ora:

```text
YYYY-MM-DDTHH:MM:SS+01:00
```

Default consigliato:

```text
timeformat = date
timezone = timezone di progetto, default Europe/Rome
```

### 10.2 Precisione

Se una fonte indica solo anno, trimestre o mese, il sistema deve espandere
l'intervallo ma conservare la precisione.

Esempi:

```text
2024
  valid_from = 2024-01-01
  valid_to = 2024-12-31
  precision = year

2024-05
  valid_from = 2024-05-01
  valid_to = 2024-05-31
  precision = month

2024Q2
  valid_from = 2024-04-01
  valid_to = 2024-06-30
  precision = quarter
```

Il DSL e il GEXF devono includere `precision` come attributo informativo.

### 10.3 Intervalli aperti

Sono ammessi:

```text
valid_from valorizzato, valid_to null
valid_from null, valid_to valorizzato
```

Semantica:

```text
valid_from only:
  valido da quella data in avanti

valid_to only:
  valido fino a quella data
```

Nel GEXF questo si traduce omettendo `start` o `end`.

### 10.4 Inclusività

Gli intervalli interni sono trattati come inclusivi:

```text
[valid_from, valid_to]
```

Motivo:

```text
GEXF 1.3 usa `start` e `end` inclusivi per gli intervalli.
```

Se in futuro si vuole supportare semantica half-open, va aggiunto un campo
esplicito. Non va simulata nascostamente nel primo export.

---

## 11. Propagazione Temporale al DSL

### 11.1 Versione schema DSL

La temporalità modifica la semantica dello snapshot. Si consiglia:

```text
metadata.schema_version = "2"
```

oppure, se si vuole mantenere compatibilità stretta:

```text
metadata.schema_version = "1"
metadata.features = ["semantic_temporality"]
```

Raccomandazione:

```text
usare schema_version "2" quando il renderer include campi temporali.
```

Il graph exporter dovrà accettare schema 1 e schema 2:

```text
schema 1 -> grafo statico o dinamico senza intervalli;
schema 2 -> grafo dinamico quando richiesto.
```

### 11.2 Metadati DSL

Nuova sezione:

```yaml
metadata:
  schema_version: "2"
  dsl_hash: "..."
  registry_hash: "..."
  temporal:
    model_version: "1"
    enabled: true
    derivation_policy: "source_revision_union"
    trusted_interval_policy: "confirmed_only"
    timeformat: "date"
    timezone: "Europe/Rome"
    counts:
      source_revision_intervals: 3
      facts_with_confirmed_temporality: 6
      relations_with_confirmed_temporality: 2
      temporal_unknown: 1
      pending_claims: 4
```

### 11.3 Facts

Ogni fact può avere una sezione `temporal`.

Esempio:

```yaml
facts:
  -
    fact_id: "FACT_000001"
    fact_type: "business_entity"
    property_name: "description"
    property_value: "Cliente del dominio commerciale."
    assertion_type: "explicit"
    confidence: "high"
    status: "active"
    temporal:
      status: "confirmed"
      derivation_policy: "source_revision_union"
      intervals:
        -
          start: "2024-01-01"
          end: "2024-12-31"
          precision: "year"
          source_revision_ids:
            - "REV_000001"
          source_temporal_claim_ids:
            - "TCLM_000001"
          review_decision_ids:
            - "RDEC_000001"
```

Se non ci sono intervalli confermati:

```yaml
temporal:
  status: "unknown"
  intervals: []
  pending_claim_count: 2
```

### 11.4 Relations

Ogni relation può avere la stessa struttura:

```yaml
relations:
  -
    relation_id: "REL_000001"
    source_entity: "Cliente"
    relation_type: "places"
    target_entity: "Ordine"
    status: "active"
    temporal:
      status: "confirmed"
      derivation_policy: "source_revision_union"
      intervals:
        -
          start: "2024-01-01"
          end: "2024-12-31"
          precision: "year"
```

### 11.5 Entities

Le entities sono aggregati. La loro validità temporale è derivata da:

```text
- facts appartenenti all'entità;
- relations incidenti;
- eventuali mapping futuri.
```

Default:

```text
entity temporal intervals = unione degli intervalli dei facts dell'entità
                            e delle relations incidenti
```

Questo garantisce che un nodo entity sia visibile in Gephi quando esiste almeno
un fatto o una relazione temporalmente valida che lo riguarda.

### 11.6 Conflicts

I conflitti devono diventare temporalmente consapevoli.

Regola:

```text
Un conflict temporale è rilevante solo negli intervalli in cui i fatti
confliggenti sono entrambi validi.
```

Esempio:

```text
FACT_A status = "BOZZA" valido nel 2022
FACT_B status = "CONFERMATO" valido nel 2024
```

Non c'è conflitto temporale se gli intervalli non si sovrappongono.

Il registry può conservare il conflict logico, ma il DSL temporale deve
distinguere:

```text
status: open
temporal.status: non_overlapping
```

oppure:

```text
temporal.status: confirmed
intervals: [overlap intervals]
```

### 11.7 Traceability

La traceability deve esporre anche le decisioni temporali.

Esempio:

```yaml
traceability:
  facts:
    FACT_000001:
      -
        candidate_record_id: "CREC_000001"
        source_revision_id: "REV_000001"
        source_id: "SRC_000001"
        file_path: "corpus/active/manuale_clienti_2024.md"
        chunk_id: "CHK_000001"
        fragment_id: null
        evidence_text_hash: "..."
        temporal:
          source_temporal_claim_ids:
            - "TCLM_000001"
          review_decision_ids:
            - "RDEC_000001"
          intervals:
            -
              start: "2024-01-01"
              end: "2024-12-31"
```

---

## 12. Hash, Diff e Snapshot

### 12.1 DSL hash

Gli intervalli confermati fanno parte del contenuto DSL e devono influenzare
`dsl_hash`.

Non devono influenzare `dsl_hash`:

```text
- claim pending_review;
- claim rejected;
- data operative created_at/updated_at;
- ordine fisico non canonico dei claim.
```

### 12.2 Registry hash

Il `registry_hash` usato dal renderer deve includere:

```text
- source_revision_validity_intervals active;
- review_decisions che supportano tali intervalli;
- relazioni tra intervalli e source revisions;
- fact/relation evidence da cui derivare temporalità.
```

Non deve includere claim pending se il renderer è configurato `confirmed_only`.

### 12.3 DSL diff

Il diff deve riconoscere cambiamenti temporali:

```text
temporal_interval_added
temporal_interval_removed
temporal_interval_modified
temporal_status_changed
temporal_precision_changed
temporal_derivation_changed
```

Esempio output:

```json
{
  "change_type": "temporal_interval_modified",
  "owner_type": "relation",
  "owner_id": "REL_000001",
  "path": "relations[REL_000001].temporal.intervals[0]",
  "before": {"start": "2024-01-01", "end": "2024-12-31"},
  "after": {"start": "2024-01-01", "end": "2024-06-30"},
  "cause": {
    "review_decision_id": "RDEC_000002",
    "source_temporal_claim_id": "TCLM_000001"
  }
}
```

---

## 13. Export GEXF Dinamico

### 13.1 Requisito Gephi

Per animazione temporale in Gephi, il GEXF deve rappresentare una rete
dinamica.

Configurazione consigliata:

```xml
<graph mode="dynamic"
       timerepresentation="interval"
       timeformat="date"
       defaultedgetype="directed">
```

Nodi e archi possono usare:

```xml
<node id="entity:ordine" label="Ordine" start="2024-01-01" end="2024-12-31" />
<edge id="relation:REL_000001" source="entity:cliente" target="entity:ordine" start="2024-01-01" end="2024-12-31" />
```

Per intervalli multipli disgiunti:

```xml
<node id="entity:ordine" label="Ordine">
  <spells>
    <spell start="2022-01-01" end="2022-12-31" />
    <spell start="2024-01-01" end="2024-12-31" />
  </spells>
</node>
```

### 13.2 Versione GEXF

Raccomandazione:

```text
nuovi export temporali -> GEXF 1.3
export statici legacy -> possono restare 1.2draft finché serve compatibilità
```

Motivo:

```text
GEXF 1.3 definisce esplicitamente timerepresentation, date/dateTime,
timestamp mode e intervalli inclusivi.
```

Il writer interno può supportare entrambe le versioni:

```text
format = gexf
gexf_version = 1.2draft | 1.3
dynamic = true | false
```

### 13.3 Policy per elementi senza temporalità confermata

Default sicuro:

```text
unknown_temporality_policy = omit_from_dynamic_topology
```

Alternative configurabili:

```text
include_as_unbounded
  include il nodo/arco senza start/end; in GEXF questo significa intervallo
  infinito. Va usato solo se l'utente accetta il rischio semantico.

include_as_static_context
  include nodi di contesto, ma non archi semantici non temporali.

fail
  fallisce l'export se esistono facts/relations senza temporalità confermata.
```

Il default deve evitare che una data sconosciuta venga visualizzata come
"sempre valida".

### 13.4 Regole per nodi

Nodi source:

```text
spells = unione degli intervalli confermati delle source_revision incluse
```

Nodi entity:

```text
spells = unione degli intervalli dei facts dell'entità e delle relations
         incidenti
```

Nodi fact:

```text
spells = intervalli temporali del fact
```

Nodi conflict:

```text
spells = sovrapposizione temporale dei facts confliggenti
```

Nodi orphan:

```text
se strict_orphans = true -> failure
se strict_orphans = false -> includere solo se si può derivare almeno un
                              intervallo dall'arco che li richiede
```

### 13.5 Regole per archi

Archi relation:

```text
spells = intervalli temporali della relation
```

Archi mentions entity -> fact:

```text
spells = intervalli temporali del fact
```

Archi derives_from source -> fact/relation:

```text
spells = intersezione tra intervallo della fonte e intervallo dell'owner
```

Archi conflict:

```text
spells = intervalli di sovrapposizione del conflitto
```

Regola GEXF importante:

```text
un arco deve esistere dentro i bounds temporali dei nodi sorgente e target.
```

Il builder deve quindi calcolare prima gli intervalli dei nodi e poi validare o
clippare gli intervalli degli archi.

### 13.6 Attributi GEXF statici aggiuntivi

Oltre a `start`/`end` o `spells`, aggiungere attributi statici:

```text
temporal_status
temporal_precision
temporal_derivation_policy
validity_source_revision_ids
source_temporal_claim_ids
review_decision_ids
temporal_unknown_reason
```

Questi attributi aiutano l'analisi in Gephi Data Laboratory senza sostituire
la timeline dinamica.

### 13.7 Report export

Il report GEXF deve includere:

```text
dynamic: true
gexf_version: "1.3"
timeformat: "date"
timerepresentation: "interval"
temporal_policy: "confirmed_only"
unknown_temporality_policy: "omit_from_dynamic_topology"
dynamic_node_count
dynamic_edge_count
omitted_temporal_unknown_count
unbounded_node_count
unbounded_edge_count
temporal_warning_count
warnings
```

Warning utili:

```text
temporal_unknown_omitted
edge_interval_clipped_to_node_bounds
relation_without_confirmed_temporality
source_revision_without_confirmed_validity
conflict_without_temporal_overlap
```

---

## 14. Configurazione

### 14.1 `configs/project.yaml`

Nuova sezione:

```yaml
temporal:
  enabled: true
  timezone: Europe/Rome
  default_timeformat: date
  trusted_interval_policy: confirmed_only
  derivation_policy: source_revision_union
  filename_extraction:
    enabled: true
    ambiguous_numeric_policy: ignore
  metadata_extraction:
    enabled: true
    filesystem_timestamps_enabled: false
  ai_extraction:
    enabled: true
    record_type: candidate_source_validity
  review:
    required_for_export: true
    reviewer_id: local_user
```

### 14.2 `configs/workers/temporal.filename.yaml`

```yaml
worker:
  name: detect_temporal_from_filename
  version: 1.0
temporal_filename:
  output_claims_jsonl: true
  supported_patterns:
    - year
    - year_month
    - date
    - quarter
    - from_to
  strict_options_fail_on_unsupported_option: true
```

### 14.3 `configs/workers/temporal.metadata.yaml`

```yaml
worker:
  name: detect_temporal_from_metadata
  version: 1.0
temporal_metadata:
  output_claims_jsonl: true
  filesystem_timestamps_enabled: false
  accepted_keys:
    - valid_from
    - valid_to
    - effective_from
    - effective_to
    - release_date
    - period
  strict_options_fail_on_unsupported_option: true
```

### 14.4 `configs/workers/gexf.dynamic.yaml`

```yaml
worker:
  name: export_gexf
  version: 2.0
graph:
  format: gexf
  gexf_version: "1.3"
  dynamic: true
  timeformat: date
  timerepresentation: interval
  temporal_policy: confirmed_only
  unknown_temporality_policy: omit_from_dynamic_topology
  include_sources: true
  include_fact_nodes: true
  include_conflicts: true
  strict_orphans: false
```

---

## 15. CLI Proposta

### 15.1 Detection

```cmd
dsl-manager temporal detect-filename <workspace> --revision REV_000001
dsl-manager temporal detect-metadata <workspace> --revision REV_000001
dsl-manager temporal detect-batch <workspace> --method filename --method metadata
```

Output:

```text
Run: RUN_000123
Revision: REV_000001
Claims created: 2
Pending review: 2
Report: artifacts/runs/RUN_000123/process_report.json
```

### 15.2 Review

```cmd
dsl-manager temporal claims list <workspace>
dsl-manager temporal claims show <workspace> --claim TCLM_000001
dsl-manager temporal claims confirm <workspace> --claim TCLM_000001
dsl-manager temporal claims reject <workspace> --claim TCLM_000001 --reason "Nome file ambiguo"
dsl-manager temporal claims override <workspace> --claim TCLM_000001 --from 2024-01-01 --to 2024-06-30 --reason "Validità corretta dal frontespizio"
```

### 15.3 Rendering DSL

```cmd
dsl-manager dsl render <workspace> --temporal
```

Oppure da configurazione:

```yaml
dsl:
  include_temporal: true
```

### 15.4 Export grafo

```cmd
dsl-manager graph export <workspace> --snapshot DSL_000001 --dynamic-temporal
```

Opzioni:

```cmd
--gexf-version 1.3
--timeformat date
--unknown-temporality-policy omit_from_dynamic_topology
--unknown-temporality-policy include_as_unbounded
--unknown-temporality-policy fail
```

---

## 16. AI Handoff

### 16.1 Package content

Il package AI deve includere una sezione dedicata:

```markdown
## Temporal validity extraction

Produce candidate_source_validity records only when evidence is present in the
provided chunks/fragments. Do not infer validity from external knowledge.
```

### 16.2 Candidate schema

Il `candidate_schema.json` deve aggiungere:

```text
candidate_source_validity
```

Campi:

```text
record_type
candidate_id
source_revision_id
chunk_id
fragment_id
valid_from
valid_to
precision
assertion_type
confidence
evidence_text
notes
```

### 16.3 Validazione

Stesse regole Evidence-or-Reject:

```text
- evidence_text deve essere presente nell'evidenza referenziata;
- date normalizzabili;
- intervallo coerente;
- precision ammessa;
- confidence ammessa;
- assertion_type ammesso.
```

### 16.4 Import

Il comando esistente `ai import` può importare anche questi record, ma il merge
non deve creare facts o relations. Deve invece creare claim temporali.

---

## 17. Failure Mode

### 17.1 Data non parseabile

```text
claim rejected o rejected_candidate;
reason = invalid_temporal_value;
nessun intervallo confermato.
```

### 17.2 Intervallo invertito

```text
valid_from > valid_to
reason = invalid_temporal_interval;
```

### 17.3 Evidence AI non trovata

```text
reason = evidence_text_not_found;
```

### 17.4 Claim multipli incompatibili

```text
source revision temporal aggregate = pending_review_conflict;
nessun export dinamico basato su quei claim;
utente deve confermare o correggere.
```

### 17.5 Export dinamico senza intervalli confermati

Default:

```text
export completa ma omette elementi unknown, con warning.
```

Se configurato `unknown_temporality_policy = fail`:

```text
run status = failed;
report indica owner senza temporalità confermata.
```

### 17.6 Arco fuori dai bounds dei nodi

Il builder deve:

```text
1. calcolare intervalli nodi;
2. calcolare intervalli archi;
3. validare edge interval subset node intervals;
4. clippare o fallire in base a config.
```

Default:

```text
clip_to_node_bounds + warning.
```

---

## 18. Strategia di Test

### 18.1 Fixture temporali

Aggiungere:

```text
tests/fixtures/corpus_temporal/
  manuale_clienti_2024.md
  manuale_ordini_valid_2023-01-01_2023-12-31.md
  manuale_ordini_metadata.md
  manuale_ambiguous_01_02.md
```

### 18.2 Candidate fixture

```text
tests/fixtures/ai_candidates/AIPKG_TEMPORAL_001_candidates.jsonl
```

Contiene:

```text
- candidate_source_validity valido;
- candidate_source_validity con evidence mancante;
- candidate_source_validity con intervallo invertito;
- candidate_fact supportato da fonte con temporalità confermata;
- candidate_relation supportata da fonte con temporalità confermata.
```

### 18.3 Expected output

```text
tests/expected/expected_dsl.temporal.json
tests/expected/expected_dsl.temporal.yaml
tests/expected/expected_graph_temporal_edges.json
tests/expected/expected_gexf_temporal_spells.json
```

### 18.4 Test principali

```text
test_temporal_filename_detection_creates_pending_claim
test_temporal_metadata_detection_creates_pending_claim
test_candidate_source_validity_validation
test_reject_temporal_candidate_without_evidence
test_confirm_temporal_claim_creates_validity_interval
test_override_temporal_claim_preserves_audit
test_temporal_claims_do_not_affect_dsl_before_confirmation
test_temporal_dsl_contains_confirmed_intervals
test_temporal_dsl_hash_changes_after_confirmed_interval
test_temporal_diff_reports_interval_change
test_dynamic_gexf_has_mode_dynamic_and_timeformat_date
test_dynamic_gexf_uses_spells_for_multiple_intervals
test_dynamic_gexf_omits_unknown_temporal_elements_by_default
test_conflict_temporal_overlap
```

---

## 19. Slice Verticali

Le etichette T0-T10 di questa sezione sono soltanto un'ipotesi di scomposizione
del documento di supporto e non costituiscono la numerazione finale. Nel design
v2 le nuove slice devono proseguire dalla Slice 20, rimappando queste ipotesi
insieme agli altri aggiornamenti previsti. Il core DSL e l'export GEXF statico,
introdotti nelle Slice 1-19, costituiscono la baseline.

### 19.1 Slice T0 - Review Foundation Minima

Obiettivo:

```text
introdurre una decisione utente append-only riusabile dalla temporalità.
```

Deliverable:

```text
- migration `review_decisions`;
- API core per creare decisioni;
- CLI minima per list/show decisioni;
- test append-only e audit.
```

Criteri:

```text
- nessuna decisione sovrascrive record storici;
- ogni decisione ha subject_type, subject_id, decision_type e created_at;
- se una review generale è già stata implementata, questa slice si limita ad
  adattarla ai subject temporali.
```

### 19.2 Slice T1 - Temporal Claims Schema

Obiettivo:

```text
persistire claim temporali non affidabili associati a source revisions.
```

Deliverable:

```text
- migration `source_temporal_claims`;
- migration `source_revision_validity_intervals`;
- validatori date/intervalli/precision;
- API core per inserire claim pending_review;
- report claims.
```

Test:

```text
test_insert_temporal_claim_pending
test_reject_invalid_interval
test_confirmed_interval_requires_review_decision
```

### 19.3 Slice T2 - Filename Temporal Detector

Obiettivo:

```text
estrarre claim temporali dal nome file senza fidarsi del risultato.
```

Deliverable:

```text
- worker `detect_temporal_from_filename`;
- profilo `temporal.filename.yaml`;
- comando `temporal detect-filename`;
- claim con extraction_method filename.
```

Test:

```text
test_detect_year_from_filename
test_detect_quarter_from_filename
test_ambiguous_filename_ignored_or_pending
```

### 19.4 Slice T3 - Metadata Temporal Detector

Obiettivo:

```text
estrarre claim temporali da metadati documentali.
```

Deliverable:

```text
- worker `detect_temporal_from_metadata`;
- supporto front matter Markdown;
- supporto metadata JSON da normalizzazione quando disponibile;
- filesystem timestamps disabilitati di default.
```

Test:

```text
test_detect_valid_from_to_from_markdown_front_matter
test_filesystem_modified_not_used_by_default
test_metadata_claim_contains_raw_value_hash
```

### 19.5 Slice T4 - AI Candidate Source Validity

Obiettivo:

```text
permettere all'AI esterna di proporre validità documento come candidato.
```

Deliverable:

```text
- estensione `candidate_validation`;
- record_type `candidate_source_validity`;
- output_template AI aggiornato;
- import che crea `source_temporal_claims` pending_review;
- rejected_candidates per errori.
```

Test:

```text
test_candidate_source_validity_accepted_with_evidence
test_candidate_source_validity_rejected_without_evidence
test_ai_import_creates_pending_temporal_claim
```

### 19.6 Slice T5 - Temporal Review CLI

Obiettivo:

```text
far confermare, correggere o rifiutare claim temporali da utente.
```

Deliverable:

```text
- `temporal claims list/show`;
- `temporal claims confirm`;
- `temporal claims reject`;
- `temporal claims override`;
- creazione intervalli confermati;
- supersede intervalli precedenti quando serve.
```

Test:

```text
test_confirm_claim_creates_active_interval
test_reject_claim_does_not_create_interval
test_override_claim_preserves_original_claim
test_new_source_revision_requires_new_review
```

### 19.7 Slice T6 - Temporal DSL Renderer

Obiettivo:

```text
propagare intervalli confermati a facts, relations, entities e conflicts.
```

Deliverable:

```text
- schema DSL v2 o feature flag temporal;
- derivation policy `source_revision_union`;
- sezione metadata.temporal;
- temporal fields su facts/relations/entities/conflicts;
- traceability temporale;
- hash canonico aggiornato.
```

Test:

```text
test_unconfirmed_claim_does_not_affect_dsl
test_confirmed_source_interval_appears_on_fact
test_relation_interval_derived_from_relation_evidence
test_entity_interval_union
test_conflict_overlap_interval
```

### 19.8 Slice T7 - Temporal DSL Diff

Obiettivo:

```text
rendere visibili modifiche temporali tra snapshot.
```

Deliverable:

```text
- change types temporali;
- cause review_decision/source_temporal_claim;
- Markdown diff leggibile;
- JSON diff stabile.
```

Test:

```text
test_diff_temporal_interval_added
test_diff_temporal_interval_modified
test_diff_temporal_status_changed
```

### 19.9 Slice T8 - Dynamic GEXF Export

Obiettivo:

```text
esportare grafi GEXF dinamici compatibili con timeline Gephi.
```

Deliverable:

```text
- supporto GEXF 1.3;
- `mode="dynamic"`;
- `timerepresentation="interval"`;
- `timeformat="date"`;
- start/end per intervallo singolo;
- spells per intervalli multipli;
- attributi statici temporali;
- report warning temporali;
- policy unknown_temporality_policy.
```

Test:

```text
test_gexf_dynamic_graph_attributes
test_gexf_node_spells
test_gexf_edge_spells
test_gexf_unknown_temporality_omitted
test_gexf_edge_bounds_within_node_bounds
```

### 19.10 Slice T9 - Batch e Golden Temporale

Obiettivo:

```text
stabilizzare pipeline end-to-end temporale senza AI reale.
```

Deliverable:

```text
- fixture corpus_temporal;
- candidate fixture temporal;
- expected DSL temporal;
- expected GEXF temporal;
- batch detect/review/render/export nei test.
```

Test:

```text
test_temporal_golden_pipeline
test_temporal_batch_report
```

### 19.11 Slice T10 - UI Locale Review Opzionale

Obiettivo:

```text
rendere ergonomica la conferma utente senza spostare logica nella UI.
```

Deliverable:

```text
- pagina claim pending;
- confronto claim multipli per source revision;
- confirm/reject/override;
- preview effetto su DSL/GEXF;
- link a evidenza chunk/frammento.
```

Test:

```text
test_temporal_review_ui_routes_smoke
test_temporal_review_ui_actions_call_core_api
```

---

## 20. Roadmap Consigliata

Sequenza minima:

```text
T0 Review Foundation Minima
T1 Temporal Claims Schema
T2 Filename Temporal Detector
T5 Temporal Review CLI
T6 Temporal DSL Renderer
T8 Dynamic GEXF Export
T9 Golden Temporale
```

Poi:

```text
T3 Metadata Temporal Detector
T4 AI Candidate Source Validity
T7 Temporal DSL Diff
T10 UI Locale Review
```

Motivo:

```text
Il valore principale è dimostrare end-to-end che un intervallo confermato
entra nel DSL e anima il grafo. Filename detection + review CLI sono sufficienti
per il primo ciclo senza dipendere da AI o parsing metadati complesso.
```

---

## 21. Acceptance Criteria

La feature è accettabile quando:

```text
1. un documento con data nel nome produce un claim pending_review;
2. un claim pending_review non modifica DSL, DSL hash o GEXF dinamico;
3. un utente può confermare un claim;
4. la conferma crea un intervallo active per la source_revision;
5. facts e relations supportati dalla source_revision ricevono temporalità;
6. il DSL espone intervalli e traceability temporale;
7. il DSL diff segnala modifiche temporali;
8. l'export GEXF dinamico usa mode=dynamic e timeformat=date;
9. nodi e archi hanno start/end o spells quando temporalmente confermati;
10. elementi senza temporalità confermata non sono esportati come sempre validi
    salvo configurazione esplicita;
11. i conflitti vengono valutati anche rispetto alla sovrapposizione temporale;
12. ogni intervallo esportato è riconducibile a source_revision, claim e
    review_decision;
13. i test automatici non chiamano AI reale;
14. gli snapshot precedenti restano immutati.
```

---

## 22. Esempio End-to-End

Input:

```text
corpus/active/manuale_ordini_2024.md
```

Scan:

```text
SRC_000001
REV_000001
```

Detection filename:

```text
TCLM_000001
source_revision_id = REV_000001
valid_from = 2024-01-01
valid_to = 2024-12-31
precision = year
status = pending_review
```

Review:

```text
RDEC_000001 confirms TCLM_000001
```

Resolved interval:

```text
SRVI_000001
source_revision_id = REV_000001
valid_from = 2024-01-01
valid_to = 2024-12-31
status = active
```

Candidate fact:

```text
FACT_000001 Ordine.status_values = BOZZA, CONFERMATO, EVASO, ANNULLATO
evidence REV_000001 / CHK_000001
```

DSL:

```yaml
fact_id: "FACT_000001"
temporal:
  status: "confirmed"
  intervals:
    -
      start: "2024-01-01"
      end: "2024-12-31"
      precision: "year"
      source_revision_ids: ["REV_000001"]
      source_temporal_claim_ids: ["TCLM_000001"]
      review_decision_ids: ["RDEC_000001"]
```

GEXF:

```xml
<graph mode="dynamic" timerepresentation="interval" timeformat="date" defaultedgetype="directed">
  <nodes>
    <node id="entity:ordine" label="Ordine" start="2024-01-01" end="2024-12-31" />
    <node id="fact:FACT_000001" label="Ordine.status_values" start="2024-01-01" end="2024-12-31" />
  </nodes>
  <edges>
    <edge id="mentions:FACT_000001" source="entity:ordine" target="fact:FACT_000001" start="2024-01-01" end="2024-12-31" />
  </edges>
</graph>
```

---

## 23. Riferimenti Tecnici

Riferimenti usati per la parte GEXF dinamica:

```text
GEXF Dynamics:
https://gexf.net/dynamics.html

Gephi Desktop - Import Dynamic Data:
https://docs.gephi.org/desktop/User_Manual/Import_Dynamic_Data/

Gephi Desktop - GEXF File Format:
https://docs.gephi.org/desktop/User_Manual/Import/GEXF_File_Format/

GEXF specifications repository:
https://github.com/gephi/gexf
```

Punti rilevanti:

```text
- GEXF supporta lifetime di nodi, archi e dati;
- `mode="dynamic"` abilita reti dinamiche;
- `timerepresentation="interval"` usa intervalli;
- `timeformat="date"` usa date `yyyy-mm-dd`;
- `start` e `end` definiscono limiti temporali;
- `spells` rappresenta intervalli multipli disgiunti;
- in GEXF 1.3 gli intervalli sono inclusivi;
- l'omissione di start o end rappresenta bound infinito;
- timestamp e interval non vanno mescolati nello stesso file.
```

---

## 24. Autoverifica del Design

Checklist:

```text
[x] Il documento non richiede modifica codice immediata.
[x] La temporalità deriva dai documenti iniziali.
[x] Nome file, metadati e AI possono coesistere.
[x] I dati temporali non sono affidabili finché non confermati.
[x] Il documento conferma che la review non risulta completa nel codice attuale.
[x] La review viene modellata come prerequisito/slice dedicata.
[x] Il DSL espone temporalità e traceability.
[x] Il DSL hash cambia solo per intervalli confermati.
[x] Il GEXF dinamico usa start/end/spells compatibili con Gephi.
[x] Gli elementi senza temporalità confermata non appaiono come sempre validi
    nel default.
[x] Le slice verticali sono elencate con obiettivi e test.
[x] Non si assume AI deterministica.
[x] Non si usa data filesystem come validità semantica affidabile.
```

---

## 25. Nota Finale

La temporalità semantica è potente ma pericolosa: una data sbagliata può far
sparire o comparire nel grafo informazioni in modo molto convincente.

Per questo la feature deve restare conservativa:

```text
estrai molto;
fidati poco;
chiedi conferma;
esporta solo ciò che è tracciabile.
```
