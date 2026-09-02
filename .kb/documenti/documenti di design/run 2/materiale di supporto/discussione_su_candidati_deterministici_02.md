altra domanda: il dsl-manager può funzionare anche senza package ai? ossia, il sistema di relazioni del dsl può essere costruito determisticamente, a prescindere dai candidati ai? in questo caso, come faccio a vedere il risultato, prima dell'aggiunta dei candidati?

----

## Risposta netta

**Sì, `dsl-manager` può funzionare senza creare un package AI e senza usare un’AI esterna.**

Ma bisogna distinguere:

1. **senza package AI:** sì;
2. **senza AI:** sì;
3. **senza alcun candidato:** il registry tecnico viene costruito, ma il DSL di dominio rimane sostanzialmente vuoto;
4. **con relazioni generate deterministicamente:** possibile, purché un processo deterministico produca record `candidate_fact` e `candidate_relation` conformi allo schema.

Il punto fondamentale è che, nell’implementazione descritta dal manuale, **“candidato” non significa necessariamente “prodotto da un’AI”**. È una proposta di fatto o relazione ancora da validare, qualunque sia il suo produttore.

---

# I due livelli del registry

Dopo scan e processamento, il registry contiene già materiale deterministico:

```text
source
source_revision
chunk
fragment
run
log
```

I parser possono estrarre, per esempio:

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

Questi elementi sono evidenze strutturate e verificabili.

Tuttavia, il manuale dice esplicitamente che un parser concluso correttamente **non ha ancora creato fatti di dominio**. Ha creato evidenze che potranno essere citate dai candidati. 

La separazione è quindi:

```text
LIVELLO DETERMINISTICO

fonti
  ↓
revisioni
  ↓
normalizzazione
  ↓
chunk e frammenti
```

e poi:

```text
LIVELLO SEMANTICO

chunk e frammenti
  ↓
candidate_fact / candidate_relation
  ↓
validazione
  ↓
merge
  ↓
fatti e relazioni
  ↓
snapshot DSL
```

---

# Senza package AI

Il package `AIPKG_*` è soprattutto un formato di esportazione per consegnare a un elaboratore esterno:

* le evidenze;
* gli identificativi;
* le istruzioni;
* lo schema dei candidati;
* un template JSONL.

Non è un prerequisito assoluto per creare candidati.

Il manuale presenta infatti questo comando più generale:

```cmd
"%PY%" -m dsl_mngr candidates validate "%WS%" --input "ai/inbox/un_altro_file.jsonl"
```

Questo valida direttamente un file JSONL presente nel workspace. A differenza di `ai import`, non collega il file a un package e non applica il controllo di obsolescenza del package. 

Il flusso senza package diventa:

```text
scan
  ↓
process-dir
  ↓
produzione autonoma di candidates.jsonl
  ↓
candidates validate
  ↓
facts merge
  ↓
dsl render
```

Per esempio:

```cmd
"%PY%" -m dsl_mngr candidates validate "%WS%" --input "candidates\deterministic_candidates.jsonl"
```

Il comando dovrebbe restituire un identificativo come:

```text
CBATCH_000001
```

Poi:

```cmd
"%PY%" -m dsl_mngr facts merge "%WS%" --batch CBATCH_000001
"%PY%" -m dsl_mngr dsl render "%WS%"
```

Quindi il package AI è una strada privilegiata per l’andata e ritorno con un modello esterno, ma **non è l’unica porta di ingresso dei candidati**.

---

# Senza AI, ma con candidati deterministici

È possibile avere un programma che legga i frammenti e produca deterministicamente:

```json
{
  "record_type": "candidate_relation",
  "candidate_id": "DET_REL_000001",
  "source_revision_id": "REV_000001",
  "fragment_id": "FRG_000142",
  "chunk_id": null,
  "source_entity": "PraticaPrestito",
  "relation_type": "belongs_to",
  "target_entity": "Cliente",
  "assertion_type": "explicit",
  "confidence": "high",
  "evidence_text": "CLIENTE_ID NUMBER NOT NULL",
  "notes": "Derivato deterministicamente da un vincolo FK"
}
```

L’esempio è indicativo: i campi esatti devono rispettare il `candidate_schema.json` dell’applicazione.

Un produttore deterministico potrebbe trasformare:

```text
DDL foreign key
```

in:

```text
candidate_relation
```

oppure:

```text
tabella PRATICA_PRESTITO
```

in:

```text
candidate_fact:
  business_entity = PraticaPrestito
```

In questo caso la pipeline sarebbe:

```text
DDL
  ↓
parse-ddl
  ↓
ddl_table / ddl_column / ddl_constraint
  ↓
regole deterministiche
  ↓
candidate_fact / candidate_relation
  ↓
validazione
  ↓
merge
  ↓
DSL
```

Il merge non distingue necessariamente, almeno per quanto documentato, fra un candidato scritto da:

* un’AI;
* una persona;
* uno script Python;
* un parser specializzato;
* una regola deterministica.

Valida la struttura e la corrispondenza dell’evidenza, quindi fonde `candidate_fact` e `candidate_relation`. 

## Il vantaggio architetturale

Questo permette un modello ibrido:

```text
deterministico
  ├─ tabelle
  ├─ colonne
  ├─ foreign key
  ├─ chiamate esplicite
  └─ elementi XML strutturati

AI o revisione umana
  ├─ concetti di dominio
  ├─ sinonimi
  ├─ significato delle procedure
  ├─ regole distribuite
  ├─ conflitti documentali
  └─ relazioni implicite
```

È probabilmente l’approccio migliore: **non chiedere all’AI ciò che può essere estratto con certezza da una grammatica o da una struttura formale**.

---

# Senza candidati del tutto

Qui la risposta è invece **no, non ottieni un DSL di dominio significativo**.

Il manuale è molto esplicito:

> I parser producono evidenza, non conoscenza di dominio definitiva. Servono candidati validi, import, merge e render. 

Inoltre indica che la versione corrente fonde nel registry solamente:

```text
candidate_fact
candidate_relation
```

Sono quindi questi record a creare i fatti e le relazioni che successivamente entrano nello snapshot DSL. 

Lo schema effettivo è:

```text
frammento ddl_constraint
        ≠
relazione DSL
```

Il frammento può contenere l’informazione necessaria per dedurre una relazione, ma non viene automaticamente promosso a relazione di dominio.

## Distinzione importante

Una foreign key come:

```sql
PRATICA.CLIENTE_ID → CLIENTE.ID
```

è certamente una relazione tecnica.

Ma non dimostra automaticamente quale relazione di dominio sia corretta:

```text
PraticaPrestito appartiene a Cliente
Cliente richiede PraticaPrestito
Cliente possiede PraticaPrestito
PraticaPrestito è intestata a Cliente
```

Il parser può estrarre deterministicamente il collegamento fisico. La sua interpretazione semantica può richiedere una regola, una configurazione o un candidato.

---

# Come vedere il risultato prima dei candidati

Hai tre visualizzazioni diverse.

## 1. Vedere il livello deterministico grezzo

Dopo:

```cmd
"%PY%" -m dsl_mngr corpus scan "%WS%"
"%PY%" -m dsl_mngr batch process-dir "%WS%"
```

puoi elencare i frammenti:

```cmd
dir /s /b "%WS%\fragments\fragments.jsonl"
```

Poi aprire un file specifico:

```cmd
type "%WS%\fragments\REV_000001\fragments.jsonl"
```

Il percorso preciso dipende dalla struttura generata.

Per i chunk:

```cmd
dir /s /b "%WS%\chunks\chunks.jsonl"
```

e:

```cmd
type "%WS%\chunks\REV_000001\chunks.jsonl"
```

Per i documenti normalizzati:

```cmd
dir /s /b "%WS%\normalized\*"
```

Questa è la rappresentazione più fedele di ciò che il sistema ha estratto **prima di qualsiasi interpretazione semantica**.

## 2. Leggere il report del batch

```cmd
type "%WS%\artifacts\runs\RUN_000001\batch_report.json"
```

Mostra:

* fonti processate;
* parser applicati;
* operazioni completate;
* elementi saltati;
* eventuali errori.

Non è un DSL, ma è il modo migliore per verificare lo stato dell’ingestione.

## 3. Renderizzare comunque un DSL di baseline

Puoi eseguire il render anche prima dei candidati:

```cmd
"%PY%" -m dsl_mngr dsl render "%WS%"
```

Poi:

```cmd
type "%WS%\exports\dsl\DSL_000001.md"
```

Il risultato dovrebbe essere vuoto o quasi vuoto, perché non sono ancora presenti fatti e relazioni fusi.

Il manuale lo considera esplicitamente un caso diagnostico:

```text
parser riusciti + frammenti presenti + DSL vuoto
=
mancano candidati validi, validazione/import e merge
```



Questo snapshot vuoto può comunque essere utile come **baseline semantica zero**:

```text
DSL_000001 — solo ingestione, nessun fatto promosso
DSL_000002 — relazioni deterministiche
DSL_000003 — candidati AI revisionati
```

Il diff permette poi di distinguere chiaramente ciò che è stato aggiunto da ciascuno strato.

---

# Il package può essere usato senza AI

C’è anche una via intermedia: generare il package, ma non inviarlo a nessuna AI.

```cmd
"%PY%" -m dsl_mngr ai package "%WS%"
```

Poi leggere:

```cmd
type "%WS%\ai\outbox\AIPKG_000001\content.md"
```

`content.md` è una vista consolidata delle evidenze attive con gli ID reali. È spesso più comodo da leggere rispetto a decine di file `chunks.jsonl` e `fragments.jsonl`.

Quindi:

```text
creare un AI package
≠
usare un’AI
```

Il package è soltanto un artefatto di esportazione. Può essere usato per:

* revisione umana;
* debugging;
* controllo delle evidenze;
* sviluppo delle regole deterministiche;
* test della pipeline.

---

# Conclusione

La situazione attuale sembra essere questa:

| Funzione                       | Senza package | Senza AI | Senza candidati |
| ------------------------------ | ------------: | -------: | --------------: |
| Scan delle fonti               |            Sì |       Sì |              Sì |
| Normalizzazione                |            Sì |       Sì |              Sì |
| Chunk                          |            Sì |       Sì |              Sì |
| Frammenti strutturati          |            Sì |       Sì |              Sì |
| Registry tecnico               |            Sì |       Sì |              Sì |
| Fatti DSL                      |            Sì |       Sì |              No |
| Relazioni DSL                  |            Sì |       Sì |              No |
| Snapshot DSL significativo     |            Sì |       Sì |              No |
| Grafo di dominio significativo |            Sì |       Sì |              No |

La formulazione più precisa è:

> `dsl-manager` non dipende dall’AI, ma nella versione descritta dipende dal concetto di candidato. I candidati possono essere prodotti da un’AI, da una persona oppure da regole deterministiche. I parser deterministici, da soli, popolano il livello delle evidenze; non promuovono automaticamente quelle evidenze a fatti e relazioni del DSL.

Per una pipeline robusta, adotterei proprio questa progressione:

```text
DSL_000001
baseline vuota dopo ingestione

DSL_000002
fatti e relazioni deterministici

DSL_000003
interpretazioni assistite dall’AI

DSL_000004
risultato revisionato e approvato
```

In questo modo è sempre possibile sapere **quale parte della conoscenza è stata estratta con certezza, quale dedotta da regole e quale proposta dall’AI**.

----

ma i candidati non prodotti da ai non vengono prodotti da dsl-manager stesso? mi sembrerebbe un processo automatizzabile: hai le entità → le metti in relazione → ??? → dsl! no?

----

**Sì: la tua intuizione è corretta.** E, alla luce del manuale, la risposta più precisa è:

> **`dsl-manager` potrebbe produrre automaticamente molti candidati deterministici, ma la versione descritta nella guida apparentemente non lo fa.**

La pipeline corrente sembra fermarsi un passaggio troppo presto:

```text
fonti
  ↓
parser deterministici
  ↓
frammenti strutturati
  ↓
[ manca una derivazione deterministica ]
  ↓
candidati
  ↓
merge
  ↓
DSL
```

Il manuale dichiara esplicitamente che i parser producono `ddl_table`, `ddl_column`, `ddl_constraint`, `sql_procedure`, `xml_field` e altri frammenti, ma che **non li trasformano automaticamente in fatti di dominio**. Aggiunge inoltre che, se i frammenti esistono ma il DSL è vuoto, mancano candidati, validazione e merge. 

Quindi, **nella versione documentata, no: `dsl-manager` non sembra creare da solo i candidati deterministici**. Li riceve da un file JSONL, li valida e li fonde.

Questo non significa che non dovrebbe farlo.

# Il tuo “hai le entità → le metti in relazione → DSL” è quasi giusto

La variante più precisa è:

```text
hai gli oggetti tecnici
  ↓
li normalizzi
  ↓
ricavi fatti e relazioni certe
  ↓
li registri come candidati deterministici
  ↓
validazione e merge
  ↓
DSL tecnico
```

Per esempio, da questo DDL:

```sql
CREATE TABLE PRATICA_PRESTITO (
    ID NUMBER PRIMARY KEY,
    CLIENTE_ID NUMBER NOT NULL,
    IMPORTO NUMBER(12,2),
    CONSTRAINT FK_PRATICA_CLIENTE
        FOREIGN KEY (CLIENTE_ID)
        REFERENCES CLIENTE(ID)
);
```

il sistema può ricavare deterministicamente:

```text
entità tecnica: PRATICA_PRESTITO
entità tecnica: CLIENTE
proprietà: PRATICA_PRESTITO.ID
proprietà: PRATICA_PRESTITO.CLIENTE_ID
proprietà: PRATICA_PRESTITO.IMPORTO
identificatore: PRATICA_PRESTITO.ID
relazione: PRATICA_PRESTITO references CLIENTE
vincolo: PRATICA_PRESTITO.CLIENTE_ID è obbligatorio
```

Non serve un’AI per scoprirlo.

Lo stesso vale per molte altre relazioni.

## Dal DDL

```text
table           → entity
column          → property
primary key     → identifier
foreign key     → references
unique          → uniqueness constraint
not null        → required property
check           → allowed values / constraint
```

## Dal PL/SQL

```text
SELECT FROM     → reads_from
INSERT INTO     → writes_to
UPDATE          → updates
DELETE FROM     → deletes_from
procedure call  → calls
trigger on      → triggered_by
```

## Dalle form XML

```text
form            → user_interface
block           → presents_entity
field           → binds_to_column
button          → invokes_action
validation      → enforces_constraint
```

## Dai log

```text
evento          → observed_behavior
componente      → emits_event
identificatore  → correlates_with
sequenza        → precedes / follows
```

Tutto questo è perfettamente automatizzabile.

# Perché chiamarli comunque “candidati”?

Anche quando il risultato è deterministico, ha senso passare attraverso il livello dei candidati:

```text
fragment
  ↓
candidate
  ↓
validation
  ↓
fact / relation
```

Il candidato funziona come **area di staging**. Permette di verificare:

* che la fonte esista;
* che il frammento citato esista;
* che l’evidenza sia corretta;
* che la relazione non sia duplicata;
* che source e target siano validi;
* quale regola abbia prodotto il risultato;
* se una revisione successiva renda il risultato obsoleto.

Un candidato deterministico potrebbe contenere informazioni come:

```json
{
  "record_type": "candidate_relation",
  "candidate_id": "DET_REL_000042",
  "source_revision_id": "REV_000012",
  "fragment_id": "FRG_000391",
  "source_entity": "PRATICA_PRESTITO",
  "relation_type": "references",
  "target_entity": "CLIENTE",
  "assertion_type": "explicit",
  "confidence": "high",
  "evidence_text": "FOREIGN KEY (CLIENTE_ID) REFERENCES CLIENTE(ID)",
  "notes": "Generated by rule ddl_foreign_key_v1"
}
```

Questa relazione non è proposta da un LLM. È generata da una regola ripetibile:

```text
ddl_constraint.type == foreign_key
    →
candidate_relation(type = references)
```

Il merge può poi trattarla esattamente come gli altri candidati.

# Dov’è allora il vero `???`

Il problema è che non tutte le relazioni sono allo stesso livello.

## Relazione tecnica

Dal database puoi affermare con certezza:

```text
PRATICA_PRESTITO.CLIENTE_ID references CLIENTE.ID
```

## Relazione di dominio

Non puoi sempre dedurre automaticamente quale sia la formulazione corretta:

```text
Cliente presenta PraticaPrestito
Cliente possiede PraticaPrestito
PraticaPrestito è intestata a Cliente
PraticaPrestito riguarda Cliente
```

La foreign key dimostra il collegamento strutturale, ma non necessariamente il suo significato di business.

Analogamente:

```text
table: ST_PRAT
```

non implica automaticamente:

```text
business entity: PraticaPrestito
```

Potrebbe essere:

* una tabella di staging;
* una tabella storica;
* una materializzazione;
* una tabella tecnica;
* una tabella associativa;
* un dettaglio interno di un’entità più ampia.

Quindi servono due livelli distinti.

# DSL tecnico e DSL di dominio

## Livello 1: deterministico

Può essere prodotto interamente da `dsl-manager`:

```text
TABLE PRATICA_PRESTITO
  HAS_COLUMN ID
  HAS_COLUMN CLIENTE_ID
  REFERENCES CLIENTE
  READ_BY PROC_CALCOLA_RATA
  UPDATED_BY TRG_PRATICA_AUDIT
  PRESENTED_BY FORM_PRATICA
```

È un modello del software esistente.

## Livello 2: semantico

Richiede regole configurate, revisione umana o AI:

```text
PraticaPrestito
  belongs_to Cliente
  consists_of Rata
  receives Pagamento
  follows ApprovalWorkflow
```

È un modello del dominio.

Il primo è quasi completamente meccanico. Il secondo richiede interpretazione.

# L’architettura che avrebbe più senso

La pipeline dovrebbe essere:

```text
                         ┌──────────────────────────┐
                         │ derivazione deterministica│
                         │ FK, call, read/write, bind │
                         └────────────┬─────────────┘
                                      ↓
fonti → parser → frammenti → candidati deterministici
                                      ↓
                               validate + merge
                                      ↓
                              DSL tecnico iniziale
                                      ↓
                         candidati AI / umani
                                      ↓
                               validate + merge
                                      ↓
                           DSL semantico arricchito
```

In termini di snapshot:

```text
DSL_000001
  struttura e relazioni tecniche deterministiche

DSL_000002
  mapping degli oggetti tecnici sul dominio

DSL_000003
  regole, stati e comportamenti ricavati dai documenti

DSL_000004
  conflitti risolti e modello revisionato
```

Questo sarebbe molto più convincente di una baseline vuota.

# Cosa manca, concretamente, nel programma descritto

Manca apparentemente un comando del genere:

```cmd
dsl-manager candidates derive workspace
```

oppure:

```cmd
dsl-manager infer deterministic workspace
```

che faccia:

1. legge i frammenti attivi;
2. applica un insieme versionato di regole;
3. genera `candidate_fact` e `candidate_relation`;
4. registra per ciascuno la regola di provenienza;
5. valida i candidati;
6. produce un `CBATCH_*`;
7. consente il merge normale.

Per esempio:

```cmd
dsl-manager candidates derive "%WS%" --rules ddl
dsl-manager candidates derive "%WS%" --rules db-code
dsl-manager candidates derive "%WS%" --rules xml-form
dsl-manager facts merge "%WS%" --batch CBATCH_000001
dsl-manager dsl render "%WS%"
```

Il risultato sarebbe disponibile prima di qualunque package AI.

# Quali regole implementerei per prime

Un primo modulo deterministico potrebbe limitarsi a risultati quasi incontestabili:

| Evidenza                       | Candidato prodotto       |
| ------------------------------ | ------------------------ |
| `ddl_table`                    | entità tecnica           |
| `ddl_column`                   | proprietà tecnica        |
| primary key                    | identificatore           |
| foreign key                    | relazione `references`   |
| unique                         | vincolo di unicità       |
| not null                       | proprietà obbligatoria   |
| trigger su tabella             | relazione `triggered_on` |
| procedura che legge tabella    | `reads_from`             |
| procedura che modifica tabella | `writes_to`              |
| form field associato a colonna | `binds_to`               |
| procedura che chiama procedura | `calls`                  |

In questa fase eviterei deliberatamente affermazioni come:

```text
ST_PRAT è PraticaPrestito
CLIENTE possiede PraticaPrestito
PROC_X implementa l’approvazione
```

finché non ci siano regole di mapping esplicite o evidenze semantiche.

# Quindi: stiamo usando l’AI per fare cose inutilmente semplici?

**Nella pipeline descritta, in parte sì.**

Se il package chiede all’AI di riconoscere che:

```sql
FOREIGN KEY (CLIENTE_ID) REFERENCES CLIENTE(ID)
```

rappresenta un collegamento fra le due tabelle, l’AI sta facendo un lavoro che un parser può svolgere:

* più velocemente;
* senza costi di inferenza;
* in modo ripetibile;
* senza allucinazioni;
* con copertura testabile.

L’AI dovrebbe essere riservata a cose come:

* associare `TB_PRAT` a `PraticaPrestito`;
* riconciliare nomi diversi dello stesso concetto;
* interpretare documentazione narrativa;
* ricostruire una regola distribuita fra più fonti;
* formulare ipotesi su relazioni di dominio;
* individuare contraddizioni non puramente sintattiche;
* proporre domande aperte.

# Verdetto corretto

**Il manuale descrive un sistema nel quale i parser costruiscono il materiale necessario, ma non completano automaticamente il passaggio verso fatti e relazioni.**

Quindi:

```text
parser deterministico
  → frammento
```

esiste;

```text
frammento
  → candidato deterministico
```

apparentemente manca;

```text
candidato
  → fatto o relazione
```

esiste.

Il pezzo mancante è implementabile e, secondo me, **non è un’aggiunta facoltativa: è una parte importante del design**. Senza di esso, `dsl-manager` usa l’AI anche come collante fra strutture che ha già riconosciuto deterministicamente. Con esso, l’AI interviene soltanto dove serve davvero interpretazione.

La formulazione più onesta è dunque:

> Il sistema attuale è un registry di evidenze con validazione e rendering del DSL, ma non è ancora un generatore deterministico completo del DSL. Per diventarlo deve aggiungere un livello di derivazione che trasformi automaticamente frammenti strutturati in candidati tecnici tracciabili.
