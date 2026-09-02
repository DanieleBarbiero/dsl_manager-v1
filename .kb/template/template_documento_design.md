# {{Nome sistema o componente}} - {{Titolo del design}} v{{Versione}}

**Data:** {{YYYY-MM-DD}}  
**Formato:** {{design document | estensione | ADR | specifica tecnica}}  
**Documento di riferimento:** `{{documento_base.md}}`  
**Repository di riferimento:** `{{repository}}`  
**Package / modulo:** `{{package_o_modulo}}`  
**Scope:** {{ambito sintetico del documento}}

<!--
Istruzioni d'uso:
- sostituire i segnaposto {{...}};
- eliminare le sezioni non applicabili;
- mantenere esempi, criteri di accettazione e test verificabili;
- separare sempre stato attuale, proposta e lavoro futuro.
-->

---

## 1. Sintesi

Descrivere in poche righe:

```text
- il problema;
- la capacità introdotta o modificata;
- il valore atteso;
- il principale vincolo architetturale o operativo.
```

Regola o tesi centrale:

```text
{{principio sintetico che guida il design}}
```

---

## 2. Relazione con il design esistente

### 2.1 Principi ereditati

```text
- {{principio esistente 1}};
- {{principio esistente 2}};
- {{principio esistente 3}}.
```

### 2.2 Cambiamenti introdotti

```text
{{stato o componente iniziale}}
  -> {{nuovo livello / processo}}
  -> {{persistenza o decisione}}
  -> {{output derivato}}
```

### 2.3 Compatibilità

Specificare:

```text
- cosa resta invariato;
- cosa cambia;
- quali versioni precedenti continuano a essere supportate;
- quali migrazioni sono necessarie.
```

---

## 3. Stato attuale rilevato

### 3.1 Funzionalità già presenti

```text
- {{funzionalità}};
- {{struttura dati}};
- {{comando o API}};
- {{test o garanzia esistente}}.
```

### 3.2 Lacune o limiti

```text
- {{funzionalità mancante}};
- {{comportamento incompleto}};
- {{rischio}};
- {{assunzione da non fare}}.
```

### 3.3 Evidenze

Indicare file, moduli, migrazioni, comandi, test o documentazione che giustificano lo stato rilevato.

---

## 4. Obiettivi

### 4.1 Obiettivi funzionali

```text
1. {{obiettivo verificabile}};
2. {{obiettivo verificabile}};
3. {{obiettivo verificabile}}.
```

### 4.2 Obiettivi di integrazione

```text
- {{sottosistema}};
- {{pipeline}};
- {{formato}};
- {{strumento esterno}}.
```

### 4.3 Obiettivi di sicurezza, affidabilità o correttezza

Esplicitare le distinzioni che il sistema deve rendere visibili:

```text
- {{dato certo}};
- {{dato candidato}};
- {{dato confermato}};
- {{dato sconosciuto}};
- {{errore o conflitto}}.
```

---

## 5. Non obiettivi

La prima implementazione non deve:

```text
1. {{funzione esclusa}};
2. {{automazione rinviata}};
3. {{integrazione non necessaria}};
4. {{caso limite non supportato}};
5. {{ottimizzazione prematura}}.
```

Indicare separatamente le possibili evoluzioni future.

---

## 6. Concetti e terminologia

### 6.1 {{Concetto principale}}

Definizione:

```text
{{definizione operativa e non ambigua}}
```

Esempio:

```text
{{esempio minimo}}
```

### 6.2 {{Secondo concetto}}

Definizione, stato, provenienza e regole.

### 6.3 Stati ammessi

```text
{{pending}}
{{confirmed}}
{{rejected}}
{{superseded}}
{{conflicted}}
```

### 6.4 Regole di derivazione

Default:

```text
{{output derivato}} = {{regola deterministica}}
```

Policy alternative:

```text
{{policy_1}}
{{policy_2}}
{{policy_3}}
```

---

## 7. Flusso funzionale

### 7.1 Input

```text
- {{input 1}};
- {{input 2}};
- {{input 3}}.
```

### 7.2 Elaborazione

```text
1. {{acquisizione}};
2. {{normalizzazione}};
3. {{validazione}};
4. {{persistenza}};
5. {{review o decisione}};
6. {{rendering o export}}.
```

### 7.3 Output

```text
- {{record persistito}};
- {{artefatto}};
- {{report}};
- {{warning o errore}}.
```

### 7.4 Coesistenza di metodi o fonti

Descrivere come vengono gestiti risultati:

```text
compatibili
incompatibili
duplicati
parziali
ambigui
```

---

## 8. Review e decisioni utente

<!-- Eliminare questa sezione se la feature è interamente deterministica. -->

### 8.1 Requisito

Specificare quali dati richiedono conferma e quali non possono produrre effetti prima della review.

### 8.2 Operazioni

```text
list
show
confirm
reject
override
supersede
```

### 8.3 Audit

Ogni decisione deve indicare:

```text
decision_id
subject_type
subject_id
decision_type
payload
reviewer_id
reason
created_at
run_id
```

### 8.4 Propagazione delle modifiche

Definire cosa accade quando l'oggetto sorgente cambia versione o viene sostituito.

---

## 9. Modello dati

### 9.1 {{Tabella o entità principale}}

```text
{{id}}
{{foreign_key}}
{{campo_1}}
{{campo_2}}
{{status}}
{{created_at}}
{{updated_at}}
```

Valori ammessi:

```text
{{enum o dominio}}
```

Vincoli:

```text
- {{campo obbligatorio}};
- {{coerenza fra campi}};
- {{unicità}};
- {{append-only o mutabilità}};
- {{vincolo referenziale}}.
```

### 9.2 {{Tabella derivata o risolta}}

Descrivere origine, materializzazione, invalidazione e audit.

### 9.3 Estensioni a record esistenti

Specificare:

```text
- nuovi record_type;
- campi obbligatori;
- campi condizionali;
- regole di validazione;
- destinazione della persistenza.
```

### 9.4 Calcolo a runtime o materializzazione

Decisione consigliata:

```text
{{calcolo a runtime | materializzazione}}
```

Motivazione e soglia per rivalutare la scelta.

---

## 10. Normalizzazione e formato canonico

### 10.1 Formato interno

```text
{{formato canonico}}
```

### 10.2 Precisione o granularità

```text
{{livello 1}}
{{livello 2}}
{{livello 3}}
```

### 10.3 Valori aperti, null o sconosciuti

Definire la semantica di:

```text
null
unknown
unbounded
not_applicable
```

### 10.4 Regole di confronto

Specificare inclusività, ordinamento, equivalenza, timezone, locale e normalizzazione Unicode.

---

## 11. Propagazione agli artefatti derivati

### 11.1 Versione dello schema

```text
schema_version = "{{versione}}"
```

Oppure:

```text
features = ["{{feature_flag}}"]
```

### 11.2 Metadati

```yaml
metadata:
  schema_version: "{{versione}}"
  {{feature}}:
    enabled: true
    model_version: "{{versione_modello}}"
    policy: "{{policy}}"
    counts:
      {{contatore}}: 0
```

### 11.3 Oggetti principali

Esempio:

```yaml
{{collection}}:
  -
    id: "{{ID_000001}}"
    status: "{{status}}"
    {{feature}}:
      status: "{{status_feature}}"
      policy: "{{policy}}"
      values: []
```

### 11.4 Aggregati

Definire come gli oggetti aggregati ereditano o combinano i dati dei componenti.

### 11.5 Conflitti

Definire:

```text
- quando esiste un conflitto;
- quando due valori sono compatibili;
- come viene rappresentata la sovrapposizione;
- come viene preservato il conflitto storico.
```

### 11.6 Traceability

Ogni valore derivato deve essere riconducibile a:

```text
- sorgente;
- revisione;
- evidenza;
- candidato;
- decisione;
- run.
```

---

## 12. Hash, diff e snapshot

### 12.1 Hash dell'artefatto

Deve includere:

```text
- {{contenuto semanticamente rilevante}};
- {{decisioni attive}};
- {{relazioni necessarie alla derivazione}}.
```

Non deve includere:

```text
- timestamp operativi irrilevanti;
- record rifiutati;
- ordine fisico non canonico;
- dati candidati non attivi.
```

### 12.2 Hash della sorgente o del registry

Definire esattamente il perimetro del calcolo.

### 12.3 Tipi di cambiamento nel diff

```text
{{feature}}_added
{{feature}}_removed
{{feature}}_modified
{{status}}_changed
{{policy}}_changed
```

Esempio:

```json
{
  "change_type": "{{change_type}}",
  "owner_type": "{{owner_type}}",
  "owner_id": "{{OWNER_000001}}",
  "path": "{{path}}",
  "before": {},
  "after": {},
  "cause": {}
}
```

---

## 13. Export e interfacce esterne

### 13.1 Requisiti del formato

```text
- {{versione formato}};
- {{modalità}};
- {{attributi obbligatori}};
- {{vincoli di compatibilità}}.
```

### 13.2 Policy per dati mancanti

Default sicuro:

```text
{{policy_default}}
```

Alternative:

```text
{{include}}
{{omit}}
{{fail}}
```

### 13.3 Regole per oggetti e relazioni

Definire ordine di calcolo, clipping, validazione dei bounds e gestione degli orphan.

### 13.4 Report di export

```text
format
version
policy
object_count
relation_count
omitted_count
warning_count
warnings
```

---

## 14. Configurazione

### 14.1 Configurazione di progetto

```yaml
{{feature}}:
  enabled: true
  policy: "{{policy}}"
  strict: true
```

### 14.2 Configurazione worker

```yaml
worker:
  name: "{{worker_name}}"
  version: "{{versione}}"
{{feature}}:
  output_report: true
  strict_options_fail_on_unsupported_option: true
```

### 14.3 Default e override

Documentare precedenza, valori impliciti e comportamento in caso di opzione sconosciuta.

---

## 15. CLI e API

### 15.1 Comandi principali

```text
{{cli}} {{feature}} detect <workspace>
{{cli}} {{feature}} list <workspace>
{{cli}} {{feature}} show <workspace> --id {{ID}}
{{cli}} {{feature}} confirm <workspace> --id {{ID}}
{{cli}} {{feature}} reject <workspace> --id {{ID}} --reason "..."
{{cli}} {{feature}} export <workspace>
```

### 15.2 Output atteso

```text
Run: {{RUN_ID}}
Objects created: {{N}}
Pending review: {{N}}
Warnings: {{N}}
Report: {{path}}
```

### 15.3 Contratti API

Per ogni endpoint o funzione indicare input, output, errori, idempotenza e autorizzazioni.

---

## 16. AI handoff

<!-- Eliminare questa sezione se non viene usata AI. -->

### 16.1 Contenuto del package

```markdown
## {{Task AI}}

Produce candidati solo quando l'evidenza è presente nel materiale fornito.
Non usare conoscenza esterna.
```

### 16.2 Schema candidato

```text
record_type
candidate_id
source_revision_id
evidence_id
assertion_type
confidence
evidence_text
notes
```

### 16.3 Validazione

```text
- evidenza presente;
- riferimenti coerenti;
- valori normalizzabili;
- enum ammessi;
- nessuna persistenza diretta nello stato confermato.
```

### 16.4 Import

Specificare in quale tabella o coda vengono persistiti i candidati.

---

## 17. Failure mode

### 17.1 {{Errore di parsing}}

```text
reason = {{reason_code}}
effect = {{nessun effetto | warning | failure}}
```

### 17.2 {{Dati incoerenti}}

```text
reason = {{reason_code}}
```

### 17.3 {{Evidenza mancante}}

```text
reason = evidence_not_found
```

### 17.4 {{Conflitto}}

Definire stato aggregato, blocchi e azione richiesta.

### 17.5 {{Export incompleto}}

Default, modalità strict e contenuto del report.

### 17.6 {{Vincolo fra oggetti}}

Definire ordine di calcolo e strategia:

```text
clip
omit
warn
fail
```

---

## 18. Strategia di test

### 18.1 Fixture

```text
tests/fixtures/{{feature}}/
  {{fixture_1}}
  {{fixture_2}}
  {{fixture_ambigua}}
```

### 18.2 Input candidati

```text
tests/fixtures/{{feature}}_candidates/{{package}}.jsonl
```

### 18.3 Expected output

```text
tests/expected/{{expected_1}}
tests/expected/{{expected_2}}
```

### 18.4 Test principali

```text
test_{{feature}}_happy_path
test_{{feature}}_invalid_input
test_{{feature}}_requires_review
test_{{feature}}_does_not_affect_output_before_confirmation
test_{{feature}}_changes_hash_after_confirmation
test_{{feature}}_diff
test_{{feature}}_export
test_{{feature}}_golden_pipeline
```

### 18.5 Vincoli dei test

```text
- nessuna dipendenza esterna non controllata;
- nessuna chiamata AI reale nei test automatici;
- fixture riproducibili;
- output canonico;
- test di regressione per gli snapshot precedenti.
```

---

## 19. Slice verticali

### 19.1 Slice {{S0}} - {{Fondazione}}

Obiettivo:

```text
{{valore end-to-end minimo}}
```

Deliverable:

```text
- {{migrazione}};
- {{API core}};
- {{CLI}};
- {{test}}.
```

Criteri:

```text
- {{criterio verificabile}};
- {{criterio verificabile}}.
```

### 19.2 Slice {{S1}} - {{Persistenza}}

Obiettivo, deliverable e test.

### 19.3 Slice {{S2}} - {{Acquisizione o detection}}

Obiettivo, deliverable e test.

### 19.4 Slice {{S3}} - {{Review o validazione}}

Obiettivo, deliverable e test.

### 19.5 Slice {{S4}} - {{Rendering o propagazione}}

Obiettivo, deliverable e test.

### 19.6 Slice {{S5}} - {{Export}}

Obiettivo, deliverable e test.

### 19.7 Slice {{S6}} - {{Golden end-to-end}}

Obiettivo, fixture, expected output e test.

### 19.8 Slice {{S7}} - {{UI opzionale}}

La UI deve richiamare primitive core già testate e non duplicare la logica di dominio.

---

## 20. Roadmap consigliata

Sequenza minima:

```text
{{S0}}
{{S1}}
{{S2}}
{{S3}}
{{S4}}
{{S5}}
{{S6}}
```

Fase successiva:

```text
{{integrazione avanzata}}
{{ottimizzazione}}
{{UI}}
```

Motivazione:

```text
{{perché questa sequenza riduce dipendenze e dimostra presto il valore}}
```

---

## 21. Acceptance criteria

La feature è accettabile quando:

```text
1. {{criterio osservabile}};
2. {{criterio osservabile}};
3. {{dato candidato non produce effetti prematuri}};
4. {{decisione produce stato attivo}};
5. {{output derivato è tracciabile}};
6. {{hash e diff reagiscono correttamente}};
7. {{export rispetta il formato}};
8. {{dati mancanti seguono la policy}};
9. {{errori sono riportati con reason code}};
10. {{test automatici sono deterministici}};
11. {{snapshot precedenti restano immutati}}.
```

---

## 22. Esempio end-to-end

Input:

```text
{{input}}
```

Acquisizione:

```text
{{SOURCE_ID}}
{{REVISION_ID}}
```

Candidato:

```text
{{CANDIDATE_ID}}
status = pending_review
```

Decisione:

```text
{{DECISION_ID}} confirms {{CANDIDATE_ID}}
```

Stato risolto:

```text
{{RESOLVED_ID}}
status = active
```

Artefatto derivato:

```yaml
id: "{{OBJECT_ID}}"
{{feature}}:
  status: "confirmed"
  values:
    - {{value}}
```

Export:

```text
{{rappresentazione finale minima}}
```

---

## 23. Riferimenti tecnici

```text
{{specifica ufficiale}}
{{documentazione del framework}}
{{repository di riferimento}}
{{ADR o design precedente}}
```

Per ogni riferimento, annotare i punti che influenzano concretamente il design.

---

## 24. Autoverifica del design

```text
[ ] Il problema è definito.
[ ] Stato attuale e proposta sono separati.
[ ] Obiettivi e non obiettivi sono espliciti.
[ ] Le assunzioni sono dichiarate.
[ ] I dati candidati non vengono trattati come certi.
[ ] Persistenza e audit sono definiti.
[ ] Hash, diff e snapshot sono considerati.
[ ] Failure mode e policy di default sono conservativi.
[ ] Le slice producono valore end-to-end.
[ ] I test non dipendono da servizi non controllati.
[ ] Gli esempi sono coerenti con gli schemi.
[ ] Gli acceptance criteria sono verificabili.
[ ] Compatibilità e migrazioni sono documentate.
```

---

## 25. Nota finale

Riassumere il criterio prudenziale o architetturale che deve guidare l'implementazione:

```text
{{principio conclusivo breve e memorabile}}
```
