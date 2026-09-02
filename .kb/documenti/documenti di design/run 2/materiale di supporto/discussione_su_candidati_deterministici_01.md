altra domanda: il dsl-manager può funzionare anche senza package ai? ossia, il sistema di relazioni del dsl può essere costruito determisticamente, a prescindere dai candidati ai? in questo caso, come faccio a vedere il risultato, prima dell'aggiunta dei candidati?

----

Sì, ma bisogna distinguere con precisione **tre cose diverse**:

1. usare un’AI;
2. creare un package AI;
3. produrre candidati.

La risposta sintetica è:

> **`dsl-manager` può funzionare senza AI e senza package AI, ma nella versione descritta dal manuale non può produrre un DSL di dominio popolato senza candidati.**

I candidati potrebbero essere scritti:

* da un’AI;
* manualmente;
* da uno script deterministico;
* da un altro analizzatore statico.

Il package `AIPKG_*` è soltanto il formato di consegna preparato per un’AI esterna. Non è il fondamento del registry.

---

# Che cosa viene costruito deterministicamente

Fino al batch, la pipeline è interamente deterministica:

```text
fonti
  ↓
source e source_revision
  ↓
normalizzazione
  ↓
chunk e frammenti
```

I parser producono elementi come:

```text
ddl_table
ddl_column
ddl_constraint
xml_form
xml_field
xml_button
sql_trigger
sql_procedure
sql_statement
log_event
```

Questi sono già dati strutturati e verificabili. Il manuale precisa però che un parser completato con successo **non ha ancora creato fatti di dominio**: ha creato evidenze che potranno essere citate dai candidati. 

Quindi, dopo il processamento, il registry può già sapere deterministicamente cose del tipo:

```text
Esiste la tabella PRATICHE_PRESTITO.
La tabella contiene la colonna CLIENTE_ID.
Esiste un vincolo FK_X.
Esiste la procedura APPROVA_PRATICA.
La procedura contiene una certa istruzione SQL.
Esiste la form PRATICA_PRESTITO.
La form contiene il campo IMPORTO.
```

Ma non ha necessariamente trasformato queste evidenze in affermazioni di dominio come:

```text
Cliente possiede PratichePrestito.
PraticaPrestito appartiene a Cliente.
PraticaPrestito può essere approvata.
Pagamento estingue una Rata.
```

La prima categoria è **struttura tecnica osservata**.
La seconda è **interpretazione semantica del dominio**.

---

# Le relazioni tecniche possono essere determinate automaticamente?

In linea di principio sì, almeno per molte relazioni.

Per esempio, dal DDL si possono ricavare deterministicamente:

```text
tabella contiene colonna
tabella ha vincolo
foreign key collega tabella A a tabella B
```

Dal codice SQL si possono ricavare:

```text
procedura legge tabella
procedura aggiorna tabella
trigger è associato a tabella
procedura chiama procedura
```

Dalle form XML:

```text
form contiene campo
pulsante invoca azione
campo è associato a item o sorgente dati
```

Quindi è perfettamente possibile costruire un **grafo tecnico deterministico**:

```text
FORM_PRATICA
    └─ usa → PRATICHE_PRESTITO
                  ├─ FK → CLIENTI
                  └─ modificata da → APPROVA_PRATICA
```

Il problema è che il manuale non indica che `dsl-manager v1` trasformi automaticamente questi frammenti in record `fact` e `relation`.

Dice invece esplicitamente:

* i parser producono evidenze;
* il merge inserisce `candidate_fact` e `candidate_relation`;
* se i parser hanno prodotto frammenti ma mancano import, validazione e merge, il DSL rimane vuoto. 

Perciò:

> **La materia prima per un grafo deterministico esiste già, ma l’attuale pipeline documentata non la promuove automaticamente nel DSL.**

---

# Package AI e candidati non sono la stessa cosa

Il manuale offre due percorsi di importazione.

## Percorso legato al package

```cmd
"%PY%" -m dsl_mngr ai import "%WS%" --package AIPKG_000001
```

Questo associa la risposta a un package e controlla anche che il package non sia diventato obsoleto.

## Percorso generico

```cmd
"%PY%" -m dsl_mngr candidates validate "%WS%" --input "percorso\candidati.jsonl"
```

Questo accetta un file di candidati presente nel workspace senza richiedere un `AIPKG_*`. Il manuale precisa che questo percorso non esegue il controllo di obsolescenza del package, proprio perché può funzionare indipendentemente da esso. 

Quindi uno script deterministico potrebbe fare:

```text
fragments.jsonl
    ↓
regole deterministiche
    ↓
deterministic_candidates.jsonl
    ↓
candidates validate
    ↓
facts merge
    ↓
dsl render
```

Per esempio:

```text
ddl_constraint FK_PRATICA_CLIENTE
    ↓ regola
candidate_relation:
    source = PraticaPrestito
    relation = belongs_to
    target = Cliente
```

Formalmente il risultato entra ancora come **candidato**, ma non è stato proposto da un’AI. “Candidato” significa soltanto:

> affermazione non ancora fusa nel modello, sottoposta a validazione.

Non significa necessariamente “output probabilistico”.

---

# Come vedere il risultato prima dei candidati

Prima dei candidati puoi vedere il **risultato dell’ingestione deterministica**, non ancora il DSL semantico.

Dopo:

```cmd
"%PY%" -m dsl_mngr corpus scan "%WS%"
"%PY%" -m dsl_mngr batch process-dir "%WS%"
```

hai quattro livelli osservabili.

## 1. Il report della run

```cmd
type "%WS%\artifacts\runs\RUN_000001\batch_report.json"
```

Mostra quali sorgenti sono state processate, saltate o hanno prodotto errori.

## 2. I documenti normalizzati

```cmd
dir /s /b "%WS%\normalized"
```

Puoi poi aprire uno specifico file:

```cmd
type "%WS%\normalized\...\normalized.md"
```

Qui vedi la versione testuale uniforme ottenuta dai documenti.

## 3. I chunk

```cmd
dir /s /b "%WS%\chunks\chunks.jsonl"
```

Poi:

```cmd
type "%WS%\chunks\...\chunks.jsonl"
```

Ogni riga contiene normalmente:

```text
chunk_id
source_revision_id
testo
offset
hash
```

## 4. I frammenti strutturati

```cmd
dir /s /b "%WS%\fragments\fragments.jsonl"
```

Poi:

```cmd
type "%WS%\fragments\...\fragments.jsonl"
```

Questa è la vista più vicina a ciò che stai cercando: contiene il risultato dei parser DDL, XML, PL/SQL e log.

Per esempio, idealmente vedrai record analoghi a:

```json
{
  "fragment_type": "ddl_table",
  "name": "PRATICHE_PRESTITO",
  "source_revision_id": "REV_..."
}
```

oppure:

```json
{
  "fragment_type": "ddl_constraint",
  "constraint_type": "foreign_key",
  "table": "PRATICHE_PRESTITO",
  "referenced_table": "CLIENTI"
}
```

I campi esatti dipendono dallo schema implementato.

---

# La UI cosa mostra in questa fase?

Puoi avviarla con:

```cmd
"%PY%" -m dsl_mngr ui serve "%WS%"
```

e aprire:

```text
http://127.0.0.1:8765/
```

Prima dei candidati dovrebbe permetterti di vedere almeno run e log.

Il manuale elenca esplicitamente queste viste:

* run;
* log;
* candidati rifiutati;
* conflitti;
* snapshot;
* diff.

Non dichiara però una vista dedicata a chunk e frammenti. Quindi **non darei per scontato che la UI sia già un browser del modello tecnico estratto**. Per i frammenti, il metodo documentato è leggere i file `fragments.jsonl`. 

---

# Posso eseguire `dsl render` prima dei candidati?

Sì, presumibilmente puoi eseguirlo:

```cmd
"%PY%" -m dsl_mngr dsl render "%WS%"
```

e leggere:

```cmd
type "%WS%\exports\dsl\DSL_000001.md"
```

Ma il risultato sarà vuoto, o quasi vuoto, perché il renderer legge fatti e relazioni fusi, non direttamente chunk e frammenti.

Il manuale lo dice esplicitamente:

> Se il DSL è vuoto ma i parser hanno prodotto frammenti, manca almeno uno fra import, validazione e merge. 

Quello snapshot vuoto può essere utile come baseline tecnica, ma **non è una visualizzazione delle relazioni estratte dai parser**.

Analogamente, il grafo GEXF viene esportato da uno snapshot DSL:

```cmd
"%PY%" -m dsl_mngr graph export "%WS%" --snapshot DSL_000001
```

Se lo snapshot non contiene relazioni, anche il grafo non rappresenterà la struttura tecnica contenuta nei frammenti.

---

# Lo schema effettivo della versione corrente

La pipeline documentata è questa:

```text
                FASE DETERMINISTICA

fonti
  ↓
scan
  ↓
normalizzazione e parser
  ↓
chunk e frammenti
  ↓
evidenze nel registry


                FASE SEMANTICA

evidenze
  ↓
candidati prodotti da AI, persona o script
  ↓
validazione
  ↓
merge
  ↓
fatti e relazioni
  ↓
DSL
  ↓
grafo
```

Pertanto, la risposta precisa alle tue domande è:

| Domanda                                                      | Risposta                                                      |
| ------------------------------------------------------------ | ------------------------------------------------------------- |
| Può fare ingestione senza AI?                                | Sì                                                            |
| Può creare il registry delle fonti senza AI?                 | Sì                                                            |
| Può produrre chunk e frammenti senza AI?                     | Sì                                                            |
| Può individuare strutture tecniche senza AI?                 | Sì                                                            |
| Il package AI è obbligatorio?                                | No                                                            |
| I candidati devono necessariamente provenire da AI?          | No                                                            |
| Il DSL v1 viene popolato direttamente dai parser?            | No, secondo il manuale                                        |
| Posso vedere i risultati deterministici prima dei candidati? | Sì, nei report, chunk e soprattutto `fragments.jsonl`         |
| Posso vedere già un grafo tecnico nella UI/GEXF?             | Non risulta dalla documentazione                              |
| Posso costruirlo con regole deterministiche?                 | Sì, producendo `candidate_fact` e `candidate_relation` validi |

# La lacuna architetturale che hai individuato

La tua domanda mette in evidenza una mancanza reale: fra i frammenti e il DSL dovrebbe probabilmente esistere uno strato di **candidate generation deterministica**.

Per esempio:

```text
ddl_table
    → business_entity_candidate o technical_entity_candidate

ddl_column
    → property_candidate

foreign_key
    → relation_candidate

trigger_on_table
    → technical_dependency_candidate

procedure_reads_table
    → read_dependency_candidate
```

Poi l’AI dovrebbe occuparsi soltanto delle trasformazioni che richiedono interpretazione:

```text
PRAT_CLIENTE_FK
    → «PraticaPrestito appartiene a Cliente»

STATO = A
    → «A significa Approvata»

procedura X + manuale Y
    → «l’approvazione sopra una soglia è manuale»

due fonti discordanti
    → conflitto o domanda aperta
```

Questa divisione sarebbe più robusta:

```text
relazioni certe e sintattiche
    → estrazione deterministica

relazioni semantiche ma ambigue
    → AI o revisione umana
```

Il punto importante è che **non serve scegliere fra “tutto deterministico” e “tutto AI”**. Il disegno più sensato è:

> estrarre deterministicamente tutto ciò che è direttamente dimostrabile dalla struttura; usare candidati AI soltanto per attribuire significato, riconciliare fonti e formulare relazioni di dominio non esplicite.

Nella versione descritta dal manuale, però, il primo pezzo si ferma ai frammenti: manca ancora il passaggio automatico `frammenti → candidati deterministici → DSL`.
