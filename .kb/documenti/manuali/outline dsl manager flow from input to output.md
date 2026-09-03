Outline program flow from input to output

Sep 2 · pragma/dsl\_manager-v1 · main

Archive

Share

parti dal file <root>/.kb\documenti\documenti di design\run 2\design\_document\_v\_02.md, ma sentiti libero di spaziare a tutti i file collegati, se necessario.
stiamo per usare questo documento per generare dei prompt di slice, che andranno eseguiti per aggiornare il progetto.
temo (come essere umano) di non avere più una chiara idea del funzionamento interno del programma. quindi vorrei farti delle domande, e vorrei che tu rispondessi in forma completa ma concisi, nella maniera più semplice e illustrativa possibile.
l'idea generale dovrebbe essere: tu mi illustri il funzionamento del programma, come fosse un viaggio da dato grezzo a output finale di dsl manager, \*\*ma\*\* non me lo dici tutto insieme: lo spezzetti a step (1 step = 1 risposta) e così, nel caso, posso farti delle domande follow up.
quindi, prima domanda: da dove si comincia?

Copy

Worked for 7m 2s

## Step 1 — Preparare il contenitore e registrare il dato grezzo

Si comincia **prima dell’interpretazione dei documenti**.

Il primo tratto del viaggio è:

```
file reale
   ↓
workspace
   ↓
corpus/active
   ↓
scansione
   ↓
source + source_revision
```

### 1. Il workspace: la “scatola del progetto”

DSL Manager non lavora direttamente su una cartella arbitraria piena di file. Lavora dentro un **workspace**, cioè una directory organizzata che contiene:

- il corpus sorgente;
- il database SQLite;
- configurazioni;
- evidenze estratte;
- artefatti intermedi;
- log;
- esportazioni finali.

Il codice di inizializzazione crea infatti directory separate per corpus attivo, file ignorati o cancellati, frammenti, chunk, run ed export.

Operativamente, la preparazione iniziale è:

````
Bash


```
dsl-manager init <workspace>
dsl-manager db init <workspace>
```
````

Il primo comando crea la struttura; il secondo crea e migra `workspace.sqlite`. Il registry SQLite è il vero centro persistente dell’applicazione: il DSL finale sarà soltanto una sua vista derivata e riproducibile.

### 2. Il dato grezzo entra in `corpus/active`

I file che vogliamo analizzare vengono collocati in:

```
<workspace>/corpus/active/
```

Per esempio:

```
workspace/
└── corpus/
    └── active/
        ├── schema_clienti.sql
        ├── maschera_ordini.xml
        ├── manuale_operativo.pdf
        └── applicazione.log
```

In questa fase il file è ancora soltanto **materiale grezzo**. Non è ancora un fatto, una relazione o una voce del DSL.

### 3. La scansione registra la fonte

Si esegue:

````
Bash


```
dsl-manager corpus scan <workspace>
```
````

La scansione calcola per ogni file:

- percorso relativo;
- dimensione;
- hash SHA-256 del contenuto.

Questo è esattamente ciò che fa `_scan_files`: visita ordinatamente i file e costruisce per ciascuno un record con `relative_path`, `content_hash` e `file_size`.

Dopodiché confronta il risultato con quanto già presente nel registry e classifica ogni file come:

- **added**;
- **modified**;
- **deleted**;
- **unchanged**.

Il confronto avviene in una transazione, quindi la scansione viene applicata integralmente oppure annullata in caso di errore.

### 4. La distinzione fondamentale: fonte e revisione

DSL Manager assegna due identità diverse:

```
SRC_000001   → la fonte logica
REV_000001   → questa precisa versione del suo contenuto
```

La **source** rappresenta il documento nel tempo:

> “schema clienti”

La **source revision** rappresenta invece i byte osservati in uno specifico momento:

> “schema clienti con questo preciso hash”

Quando un nuovo file viene registrato, il programma crea sia un `source_id` sia un `source_revision_id`, collega la revisione alla fonte e la rende corrente.

Se domani modifichiamo il file e ripetiamo la scansione:

```
SRC_000001
├── REV_000001  superseded
└── REV_000002  active
```

La fonte rimane la stessa, ma nasce una nuova revisione. Se il file scompare dal corpus, viene registrato come cancellato senza eliminare la sua storia.

---

## Perché il viaggio deve iniziare qui?

Perché tutto ciò che verrà dopo deve poter rispondere alla domanda:

> **“Questa informazione da quali byte proviene?”**

Il design v02 definisce infatti l’evidenza come un dato osservabile dotato di **origine e localizzatore**, precisando che l’evidenza non è ancora una decisione. {line\_range\_start=105 line\_range\_end=118 path=.kb/documenti/documenti di design/run 2/design\_document\_v\_02.md git\_url="https://github.com/DanieleBarbiero/dsl\_manager-v1/blob/main/.kb/documenti/documenti di design/run 2/design\_document\_v\_02.md#L105-L118"}

Perciò il vero punto di partenza concettuale non è:

```
documento → DSL
```

ma:

```
byte identificati e versionati
        ↓
evidenze localizzabili
        ↓
candidati
        ↓
decisioni
        ↓
fatti e relazioni
        ↓
DSL
```

Il diagramma end-to-end della v02 parte coerentemente dai **“byte sorgente immutabili”**; solo dopo vengono parsing, normalizzazione ed estrazione temporale. {line\_range\_start=139 line\_range\_end=157 path=.kb/documenti/documenti di design/run 2/design\_document\_v\_02.md git\_url="https://github.com/DanieleBarbiero/dsl\_manager-v1/blob/main/.kb/documenti/documenti di design/run 2/design\_document\_v\_02.md#L139-L157"}

### L’idea da conservare

> **DSL Manager comincia costruendo una catena di custodia del dato.**

In questo primo step non cerca ancora di capire cosa significhi il documento. Stabilisce soltanto:

1. quale file è stato osservato;
2. dove si trovava;
3. quali byte conteneva;
4. se era nuovo, modificato, invariato o rimosso;
5. quale revisione rappresenta quei byte nel registry.

Il prossimo step naturale sarà quindi: **una volta registrata una revisione, come decide DSL Manager quale elaborazione applicarle e come la trasforma in evidenza?**

**Verifiche effettuate**

- ✅ `find .. -name AGENTS.md -print`
- ✅ `sed -n '1,240p' '.kb/documenti/documenti di design/run 2/design_document_v_02.md'`
- ✅ `rg -n "Flusso|workspace|scan|sorgent|source|ingest|revision|immut" '.kb/documenti/documenti di design/run 1/design_document_v_01.md'`
- ✅ `sed -n '1,240p' '.kb/documenti/manuali/manuale_utente_dsl_manager.md'`
- ✅ `nl -ba src/dsl_mngr/core/source_registry.py | sed -n '1,300p'`
- ✅ `nl -ba src/dsl_mngr/core/workspace.py | sed -n '1,180p'`
- ✅ `git status --short` — worktree pulito; non sono state apportate modifiche, quindi non è stato creato alcun commit o pull request.

(a scanso di equivoci: questo tour del programma è interamente virtuale, non occorre che venga eseguito veramente e non occorre creare / modificare / cancellare dati.)
(sempre a beneficio di questo tutorial: il programma non è stato ancora aggiornato, ma ai fini di questa discussione ti chiedo di considerarlo come giù aggiornato con le specifiche di document\_design\_v\_02.md - ma mi sembra tu lo stia già facendo.)
ottimo, finora è tutto chiaro. poi cosa succede?

Copy

Worked for 1m 45s

## Step 2 — Dalla revisione grezza alle evidenze

Dopo la scansione, DSL Manager conosce:

```
SRC_000001  = la fonte logica
REV_000001  = i byte precisi attualmente osservati
```

Ma **non sa ancora cosa contenga davvero il file**.

Il passo successivo serve a trasformare quei byte in qualcosa di consultabile e localizzabile:

```
source_revision
       ↓
riconoscimento del formato
       ↓
elaborazione specializzata
       ↓
evidenze
```

La parola importante di questo step è **evidenza**, non ancora “conoscenza”.

---

# 1. DSL Manager instrada ogni revisione

Il programma esamina ogni revisione attiva e decide quale elaborazione applicare in base al tipo di file e, quando necessario, al suo contenuto.

Virtualmente possiamo immaginare uno smistatore:

```
                         ┌─ documento ──────→ normalizzazione + chunk
REV_000001 ─→ router ───┼─ DDL SQL ────────→ parser DDL
                         ├─ XML form ────────→ parser XML
                         ├─ codice database ─→ parser DB
                         ├─ log ─────────────→ parser log
                         └─ Excel ───────────→ preflight + Docling + parser OOXML
```

Nella CLI attuale questa orchestrazione corrisponde concettualmente a:

````
Bash


```
dsl-manager batch process-dir <workspace>
```
````

Il batch esegue la scansione, carica le revisioni attive e costruisce un piano di lavorazione per ciascuna revisione. Questo comportamento è visibile anche nell’implementazione corrente: `process_dir` chiama prima `scan_corpus`, poi carica le revisioni attive e infine pianifica gli item da eseguire.

Nel programma idealmente aggiornato alla v02, il batch non è un “cervello semantico”: è principalmente un **orchestratore**. Decide quale strumento tecnico deve osservare ciascun file.

---

# 2. Ci sono due famiglie principali di elaborazione

## A. Documenti destinati alla lettura

Esempi:

- PDF;
- DOCX;
- PowerPoint;
- HTML;
- Markdown;
- testo;
- workbook Excel, con alcune cautele aggiuntive.

Questi documenti vengono **normalizzati**: il loro contenuto viene rappresentato in forme più uniformi e riproducibili, tipicamente:

```
normalized.json
normalized.md
```

Poi il contenuto leggibile può essere suddiviso in **chunk**, cioè porzioni testuali abbastanza piccole da essere citate, analizzate o fornite a un processo interpretativo.

Esempio:

```
manuale_clienti.pdf
        ↓
normalized.md
        ↓
CHK_000001: sezione “Creazione cliente”
CHK_000002: sezione “Blocco cancellazione”
CHK_000003: sezione “Gestione ordini”
```

Il manuale distingue infatti il worker di normalizzazione, che produce Markdown e JSON normalizzati, dal worker di chunking, che genera blocchi testuali stabili.

## B. Fonti strutturate o tecniche

Esempi:

- DDL SQL;
- form XML;
- stored procedure e trigger;
- log;
- struttura OOXML di Excel.

Qui non è sufficiente produrre testo leggibile. Un parser specializzato individua elementi strutturali precisi.

Per esempio, da:

````
SQL


```
CREATE TABLE cliente (
    id INTEGER PRIMARY KEY,
    nome VARCHAR(100)
);
```
````

il parser DDL potrebbe osservare:

```
frammento: dichiarazione di tabella
nome osservato: cliente
colonne osservate: id, nome
primary key osservata: id
localizzatore: file + posizione della dichiarazione
```

Analogamente:

```
XML       → form, campi, pulsanti, riferimenti a tabelle
DB code   → procedure, trigger, letture, scritture, chiamate
log       → eventi realmente osservati
Excel     → fogli, celle, formule, regioni, named range, relazioni
```

La pipeline originaria già separava queste elaborazioni: documenti verso normalizzazione e chunking, DDL verso `parse_ddl`, XML verso `parse_xml_form`, codice database verso `parse_db_code` e log verso `parse_log`. {line\_range\_start=1142 line\_range\_end=1159 path=.kb/documenti/documenti di design/run 1/design\_document\_v\_01.md git\_url="https://github.com/DanieleBarbiero/dsl\_manager-v1/blob/main/.kb/documenti/documenti di design/run 1/design\_document\_v\_01.md#L1142-L1159"}{line\_range\_start=1162 line\_range\_end=1174 path=.kb/documenti/documenti di design/run 1/design\_document\_v\_01.md git\_url="https://github.com/DanieleBarbiero/dsl\_manager-v1/blob/main/.kb/documenti/documenti di design/run 1/design\_document\_v\_01.md#L1162-L1174"}

---

# 3. Il risultato è un insieme di evidenze

Alla fine di questo step abbiamo principalmente due tipi di “pezzi citabili”:

```
chunks
```

per il testo normalizzato, e:

```
source_fragments
```

per gli elementi strutturali estratti dai parser.

Un’evidenza deve poter dire:

```
che cosa ho osservato?
in quale revisione?
in quale punto preciso?
con quale parser o procedimento?
```

Per esempio:

```
REV_000001
└── FRAG_000001
    ├── tipo: ddl_table
    ├── nome osservato: cliente
    ├── locator: dichiarazione CREATE TABLE
    └── testo/proprietà strutturali originali
```

Oppure:

```
REV_000002
└── CHK_000001
    ├── heading: Regole di cancellazione
    ├── testo: “Non è possibile cancellare...”
    └── posizione nel documento normalizzato
```

Questi oggetti sono **ancorati alla revisione**, non genericamente alla fonte. Ciò permette di sapere esattamente da quale versione del documento proviene ogni osservazione.

---

# 4. Osservare non significa ancora affermare

Questa è probabilmente la distinzione più importante dell’intero programma.

Supponiamo che il parser trovi:

```
CREATE TABLE CLIENTE
```

In questo step DSL Manager può affermare soltanto:

> Nel frammento `FRAG_000001` della revisione `REV_000001` è stata osservata una dichiarazione DDL di una tabella chiamata `CLIENTE`.

Non ha ancora stabilito necessariamente che:

> “Cliente è un’entità di dominio del sistema.”

La prima è un’**osservazione tecnica**; la seconda è un’**interpretazione semantica**.

Allo stesso modo, se un log contiene:

```
2026-01-15 DELETE cliente id=42
```

il parser può registrare che è stata osservata una certa riga o un certo evento. Non può dedurre automaticamente, senza una regola esplicita, che:

> “Il sistema consente sempre la cancellazione dei clienti.”

Un evento osservato non è una regola universale.

Il design v02 rende esplicita questa separazione:

> i parser producono osservazioni; le regole deterministiche creano successivamente candidati tecnici. {line\_range\_start=139 line\_range\_end=160 path=.kb/documenti/documenti di design/run 2/design\_document\_v\_02.md git\_url="https://github.com/DanieleBarbiero/dsl\_manager-v1/blob/main/.kb/documenti/documenti di design/run 2/design\_document\_v\_02.md#L139-L160"}

Quindi, a questo punto:

```
abbiamo prove
≠
abbiamo già deciso la verità del DSL
```

---

# 5. Il caso particolare di Excel

Nel programma aggiornato alla v02, Excel segue due strade parallele perché un workbook ha contemporaneamente:

1. una forma **leggibile**;
2. una struttura tecnica interna molto significativa.

```
workbook.xlsx
    ├── Docling
    │     ├── normalized.json
    │     └── normalized.md
    │
    └── parser OOXML
          ├── workbook_manifest.json
          └── source fragments delle regioni
```

## La vista leggibile

`normalized.md` permette a una persona o a un processo interpretativo di leggere il workbook in forma testuale.

## La vista strutturale

Il manifest OOXML conserva invece:

- ordine e nomi dei fogli;
- visibilità dei fogli;
- coordinate e tipi delle celle;
- valori;
- formule e valori memorizzati;
- celle unite;
- named range;
- relazioni ed eventuali collegamenti esterni;
- presenza e hash delle macro, senza eseguirle.

Il design precisa che `normalized.md` rimane una vista secondaria: per le derivazioni strutturali Excel, le fonti primarie sono manifest e frammenti. {line\_range\_start=393 line\_range\_end=412 path=.kb/documenti/documenti di design/run 2/design\_document\_v\_02.md git\_url="https://github.com/DanieleBarbiero/dsl\_manager-v1/blob/main/.kb/documenti/documenti di design/run 2/design\_document\_v\_02.md#L393-L412"}

## Il controllo preliminare

Prima dell’analisi, il workbook viene considerato input non fidato. Il preflight:

- verifica che il package ZIP/OOXML sia coerente;
- impedisce percorsi interni pericolosi;
- rifiuta XML con DTD o entity;
- controlla i content type;
- non segue collegamenti esterni;
- non esegue macro;
- applica limiti dimensionali.

Questi controlli avvengono prima di Docling. {line\_range\_start=377 line\_range\_end=391 path=.kb/documenti/documenti di design/run 2/design\_document\_v\_02.md git\_url="https://github.com/DanieleBarbiero/dsl\_manager-v1/blob/main/.kb/documenti/documenti di design/run 2/design\_document\_v\_02.md#L377-L391"}

Inoltre, l’hash dei byte letti viene confrontato con quello della `source_revision`. In questo modo non si rischia di registrare una revisione e analizzare silenziosamente una versione del file cambiata nel frattempo. {line\_range\_start=369 line\_range\_end=375 path=.kb/documenti/documenti di design/run 2/design\_document\_v\_02.md git\_url="https://github.com/DanieleBarbiero/dsl\_manager-v1/blob/main/.kb/documenti/documenti di design/run 2/design\_document\_v\_02.md#L369-L375"}

---

# 6. Anche la temporalità, per ora, resta evidenza grezza

La v02 aggiunge una terza uscita possibile:

```
source_revision
       ↓
estrattore temporale
       ↓
evidenza temporale grezza
```

Per esempio, un documento potrebbe contenere o incorporare:

```
“valido dal 1 gennaio 2024”
```

oppure un workbook potrebbe possedere:

- proprietà di creazione;
- proprietà di modifica;
- timestamp ZIP;
- una data esplicita in una cella.

In questo step il sistema registra separatamente ciò che ha trovato, con:

- valore originale;
- origine;
- metodo di estrazione;
- precisione;
- timezone, se disponibile;
- affidabilità;
- eventuali warning.

Ma non decide ancora automaticamente che quella data rappresenti il periodo di validità di un fatto. Un timestamp tecnico può essere semplicemente la data in cui un file è stato salvato.

---

# Il risultato dello step 2

Alla fine, la situazione assomiglia a questa:

```
REV_000001: schema_clienti.sql
├── FRAG_000001: tabella CLIENTE
├── FRAG_000002: colonna CLIENTE.ID
└── FRAG_000003: primary key CLIENTE.ID

REV_000002: manuale_clienti.pdf
├── CHK_000001: descrizione anagrafica
└── CHK_000002: regola di cancellazione

REV_000003: configurazione.xlsx
├── normalized.json
├── normalized.md
├── workbook_manifest.json
├── FRAG_000004: regione Foglio1!A1:D20
└── evidenze temporali grezze
```

Tutto è:

- registrato;
- collegato alla revisione corretta;
- localizzabile;
- riproducibile;
- ancora **non autoritativo dal punto di vista semantico**.

## Formula mentale dello step

```
STEP 1: “Quali byte abbiamo?”
STEP 2: “Che cosa è osservabile dentro quei byte?”
```

Il prossimo passaggio sarà:

```
evidenze
   ↓
regole deterministiche o interpretazione
   ↓
candidati pending
```

È lì che DSL Manager comincerà a formulare possibili affermazioni, mantenendole però separate dalla verità autoritativa.

**Verifiche documentali**

- ✅ `nl -ba '.kb/documenti/manuali/manuale_utente_dsl_manager.md' | sed -n '215,390p'`
- ✅ `nl -ba '.kb/documenti/documenti di design/run 1/design_document_v_01.md' | sed -n '1070,1245p'`
- ✅ `nl -ba '.kb/documenti/documenti di design/run 2/design_document_v_02.md' | sed -n '367,414p'`
- ✅ `nl -ba src/dsl_mngr/core/batch.py | sed -n '1,260p'`
- ✅ `git status --short` — nessuna modifica effettuata; il tour è rimasto interamente virtuale.

okay, passa pure al prossimo step.

Copy

Worked for 2m 14s

## Step 3 — Dalle evidenze ai candidati

Alla fine dello step precedente DSL Manager possiede osservazioni localizzabili:

```
source_revision
├── chunks testuali
├── frammenti strutturali
├── manifest tecnici
└── evidenze temporali grezze
```

Ora deve compiere un passaggio delicato:

> trasformare ciò che è stato osservato in **possibili affermazioni** sul sistema.

Queste possibili affermazioni si chiamano **candidati**.

```
evidenza
   ↓
regola o interpretazione
   ↓
candidato
```

Un candidato non è ancora una verità accettata. È una proposta accompagnata dalle prove che permettono di verificarla.

---

# 1. Perché introdurre i candidati?

Si potrebbe pensare:

> Se il parser ha trovato una tabella `CLIENTE`, perché non inserirla immediatamente nel DSL?

Perché questo mescolerebbe tre operazioni diverse:

1. **osservare** qualcosa nel file;
2. **interpretare** che cosa rappresenta;
3. **decidere** se accettarlo nel modello autoritativo.

DSL Manager le mantiene separate:

```
“Ho letto CREATE TABLE CLIENTE”
                ↓
“Propongo un fatto tecnico database_table=CLIENTE”
                ↓
“Accettiamo o rifiutiamo questa proposta?”
```

Questa separazione impedisce a un parser, a una regola imperfetta o a un’AI di scrivere direttamente nella conoscenza autoritativa.

Il design v02 impone infatti che anche le regole deterministiche passino attraverso il normale importer dei candidati e **non scrivano direttamente fatti o relazioni**. {line\_range\_start=340 line\_range\_end=345 path=.kb/documenti/documenti di design/run 2/design\_document\_v\_02.md git\_url="https://github.com/DanieleBarbiero/dsl\_manager-v1/blob/main/.kb/documenti/documenti di design/run 2/design\_document\_v\_02.md#L340-L345"}

---

# 2. Com’è fatto concettualmente un candidato?

Un candidato contiene almeno quattro gruppi di informazioni.

## A. Che cosa viene proposto

Per esempio:

```
tipo: candidate_fact
fact_type: database_table
entity_name: CLIENTE
```

Oppure:

```
tipo: candidate_relation
source_entity: ORDINE
relation_type: references
target_entity: CLIENTE
```

## B. Quale prova lo sostiene

Per esempio:

```
source_revision_id: REV_000001
fragment_id: FRAG_000007
evidence_text: FOREIGN KEY (cliente_id) REFERENCES cliente(id)
```

## C. Come è stata ottenuta l’affermazione

Per esempio:

```
assertion_type: explicit
rule_id: ddl_fk_relation
rule_version: 1
```

## D. Qual è la sua identità

Il design distingue:

```
candidate_id
```

che è un identificatore dichiarativo e può ripetersi in batch differenti, da:

```
candidate_record_id
```

che identifica univocamente il record persistito nel registry. {line\_range\_start=107 line\_range\_end=118 path=.kb/documenti/documenti di design/run 2/design\_document\_v\_02.md git\_url="https://github.com/DanieleBarbiero/dsl\_manager-v1/blob/main/.kb/documenti/documenti di design/run 2/design\_document\_v\_02.md#L107-L118"}

Questa distinzione è utile perché due elaborazioni separate potrebbero produrre entrambe un candidato chiamato, ad esempio, `CAND_000001`, senza che i due record vengano confusi nel database.

---

# 3. Prima strada: derivazione deterministica

Quando l’evidenza è tecnica e sufficientemente esplicita, DSL Manager applica una **regola deterministica versionata**.

“Deterministica” significa che:

> a parità di input e versione della regola, si ottiene lo stesso candidato.

Per esempio:

```
FRAG_000001
tipo osservato: ddl_table
nome: CLIENTE
locator: schema.sql, CREATE TABLE CLIENTE
```

attraversa la regola:

```
ddl_table_fact/1
```

e produce:

```
Candidato:
  tipo: fact
  fact_type: database_table
  nome: CLIENTE
  assertion: explicit
  evidenza: FRAG_000001
```

La regola non “pensa” liberamente. Ha un contratto preciso:

- `rule_id`;
- `rule_version`;
- parser e schema di input richiesti;
- tipo di candidato prodotto;
- tipo di assertion;
- metodo per localizzare l’evidenza;
- eventuale policy autorizzata alla review automatica.

Questi elementi fanno parte esplicitamente del contratto delle regole della v02. {line\_range\_start=340 line\_range\_end=345 path=.kb/documenti/documenti di design/run 2/design\_document\_v\_02.md git\_url="https://github.com/DanieleBarbiero/dsl\_manager-v1/blob/main/.kb/documenti/documenti di design/run 2/design\_document\_v\_02.md#L340-L345"}

---

# 4. Esempi di derivazione tecnica

## DDL

Da una tabella dichiarata:

````
SQL


```
CREATE TABLE CLIENTE (...)
```
````

si può derivare conservativamente:

```
fact tecnico:
  database_table = CLIENTE
```

Da una colonna:

````
SQL


```
DATA_NASCITA DATE
```
````

si può derivare:

```
fact tecnico:
  database_column = CLIENTE.DATA_NASCITA
  declared_type = DATE
```

Da una foreign key esplicita e risolta:

````
SQL


```
FOREIGN KEY (cliente_id) REFERENCES CLIENTE(id)
```
````

si può derivare:

```
relation tecnica:
  ORDINE references CLIENTE
```

Il catalogo iniziale della v02 contempla precisamente fatti per tabelle e colonne e relazioni `references` per foreign key esplicite. {line\_range\_start=346 line\_range\_end=357 path=.kb/documenti/documenti di design/run 2/design\_document\_v\_02.md git\_url="https://github.com/DanieleBarbiero/dsl\_manager-v1/blob/main/.kb/documenti/documenti di design/run 2/design\_document\_v\_02.md#L346-L357"}

## XML

Da un form XML si possono proporre fatti tecnici relativi a:

- form;
- blocchi;
- item;
- campi dichiarati.

Una relazione `reads_from` o `writes_to` può essere proposta soltanto se il parser ha trovato un segnale esplicito che distingue l’operazione. Un riferimento generico a una tabella non autorizza a inventare la direzione del flusso. {line\_range\_start=353 line\_range\_end=354 path=.kb/documenti/documenti di design/run 2/design\_document\_v\_02.md git\_url="https://github.com/DanieleBarbiero/dsl\_manager-v1/blob/main/.kb/documenti/documenti di design/run 2/design\_document\_v\_02.md#L353-L354"}

## Codice database

Da procedure, funzioni e trigger dichiarati si possono derivare fatti tecnici.

Da operazioni esplicitamente individuate si possono proporre relazioni come:

```
PROCEDURA_X reads_from CLIENTE
PROCEDURA_X writes_to ORDINE
TRIGGER_Y calls PROCEDURA_Z
```

La derivazione automatica è consentita solo quando il localizzatore dell’evidenza è completo. {line\_range\_start=355 line\_range\_end=356 path=.kb/documenti/documenti di design/run 2/design\_document\_v\_02.md git\_url="https://github.com/DanieleBarbiero/dsl\_manager-v1/blob/main/.kb/documenti/documenti di design/run 2/design\_document\_v\_02.md#L355-L356"}

## Log

Da un evento di log si può produrre un fatto **osservazionale**:

```
“questa operazione è stata osservata”
```

Non:

```
“questa operazione rappresenta sempre il comportamento del sistema”
```

Per questo i candidati derivati dai log restano normalmente `pending`, salvo l’esistenza di una policy esplicita. {line\_range\_start=357 line\_range\_end=357 path=.kb/documenti/documenti di design/run 2/design\_document\_v\_02.md git\_url="https://github.com/DanieleBarbiero/dsl\_manager-v1/blob/main/.kb/documenti/documenti di design/run 2/design\_document\_v\_02.md#L357-L357"}

---

# 5. Seconda strada: interpretazione

Non tutte le evidenze sono traducibili mediante semplici regole tecniche.

Consideriamo un manuale:

```
“Quando un cliente ha ordini aperti,
la cancellazione dell’anagrafica non è consentita.”
```

Da questo testo si potrebbe proporre:

```
candidate_fact:
  fact_type: business_rule
  entity: Cliente
  property: deletion_constraint
  value: vietata in presenza di ordini aperti
```

Questa operazione contiene più interpretazione rispetto al riconoscimento di una `CREATE TABLE`. Il candidato potrebbe provenire da:

- un operatore;
- un sistema esterno;
- un’elaborazione AI;
- in futuro, un’altra regola esplicitamente definita.

Ma il percorso di ingresso rimane lo stesso:

```
interpretazione
      ↓
candidate batch
      ↓
validazione
      ↓
pending
```

L’origine del candidato può cambiare; non cambia il fatto che il candidato debba essere ancorato a un’evidenza e non possa diventare direttamente autoritativo.

---

# 6. Il limite fondamentale: niente semantica inventata

Supponiamo che il database contenga:

````
SQL


```
CREATE TABLE CLI_MSTR (...)
```
````

Una regola tecnica può proporre:

```
database_table = CLI_MSTR
```

Non può concludere autonomamente:

```
business_entity = Cliente
```

Potrebbe sembrare evidente a un essere umano, ma quella è già un’interpretazione del nome tecnico.

Allo stesso modo, da una colonna:

```
STATO = "A"
```

non si può dedurre senza evidenza aggiuntiva:

```
"A" significa cliente attivo
```

Il design lo vieta espressamente: una regola non può inferire significato di dominio da un nome tecnico. Se i dati sono insufficienti, il risultato deve rimanere `pending` oppure essere segnalato come `derivation_insufficient_evidence`; non deve diventare direttamente un fatto. {line\_range\_start=359 line\_range\_end=361 path=.kb/documenti/documenti di design/run 2/design\_document\_v\_02.md git\_url="https://github.com/DanieleBarbiero/dsl\_manager-v1/blob/main/.kb/documenti/documenti di design/run 2/design\_document\_v\_02.md#L359-L361"}

Per Excel vale lo stesso principio:

```
intestazione “Cliente”
```

non significa automaticamente:

```
entità di dominio Cliente
```

Header, label e valori di cella rimangono attributi o evidenze. Nessun valore di cella diventa automaticamente una regola di business. {line\_range\_start=746 line\_range\_end=750 path=.kb/documenti/documenti di design/run 2/design\_document\_v\_02.md git\_url="https://github.com/DanieleBarbiero/dsl\_manager-v1/blob/main/.kb/documenti/documenti di design/run 2/design\_document\_v\_02.md#L746-L750"}

---

# 7. I candidati vengono raccolti in un batch

Le proposte non vengono inserite come record isolati senza contesto. Vengono raccolte in un **candidate batch**:

```
CBATCH_000001
├── Candidato A
├── Candidato B
├── Candidato C
└── report di derivazione/import
```

Il batch conserva il contesto dell’operazione:

- origine;
- versione delle regole;
- input elaborati;
- candidati prodotti;
- duplicati;
- record rifiutati;
- motivazioni;
- conteggi.

Per una derivazione deterministica, il comando concettuale della v02 è:

````
Bash


```
dsl-manager candidates derive <workspace>
```
````

Ogni invocazione crea un batch, anche quando non produce alcun candidato. Il report elenca input, output, deduplicazioni, rifiuti, candidati pending ed eventuali auto-conferme. La derivazione deterministica non effettua chiamate AI. {line\_range\_start=363 line\_range\_end=365 path=.kb/documenti/documenti di design/run 2/design\_document\_v\_02.md git\_url="https://github.com/DanieleBarbiero/dsl\_manager-v1/blob/main/.kb/documenti/documenti di design/run 2/design\_document\_v\_02.md#L363-L365"}

---

# 8. Prima di entrare nel registry semantico, il candidato viene validato

A questo punto DSL Manager non domanda ancora:

> “È vero?”

Domanda prima:

> “È costruito correttamente e la prova che cita esiste davvero?”

La validazione strutturale controlla, per esempio:

- tipo di candidato supportato;
- campi obbligatori;
- assertion type ammesso;
- presenza del riferimento all’evidenza;
- esistenza della `source_revision`;
- esistenza del chunk o frammento;
- appartenenza dell’evidenza alla revisione dichiarata;
- corrispondenza del testo citato con l’evidenza.

Il validatore corrente mostra concretamente questa distinzione: richiede almeno un `chunk_id` o un `fragment_id`, controlla che appartenga alla revisione indicata e verifica che `evidence_text` compaia nell’evidenza referenziata.

## Se la struttura non è valida

Il record finisce tra i rifiuti strutturali:

```
rejected_candidates
```

Esempi:

- revisione inesistente;
- frammento inesistente;
- frammento appartenente a un’altra revisione;
- campi obbligatori mancanti;
- placeholder irrisolti;
- citazione non trovata.

Questo significa:

> “Non posso nemmeno sottoporre correttamente questa proposta a giudizio.”

## Se la struttura è valida

Il candidato viene persistito e nasce:

```
pending
```

Questo significa:

> “La proposta è formalmente esaminabile e possiede una prova valida, ma non è ancora stata approvata.”

---

# 9. Validità strutturale e verità sono due cose diverse

Questo è il cuore dello step:

```
candidato valido
≠
candidato confermato
≠
fatto autoritativo
```

Un candidato può essere perfettamente ben formato, citare un frammento reale e tuttavia:

- interpretare male l’evidenza;
- essere ambiguo;
- essere troppo generale;
- essere contraddetto da un’altra fonte;
- richiedere giudizio umano;
- essere successivamente corretto.

Per questo il candidato valido nasce sempre `pending`. La v02 lo stabilisce nella propria definizione fondamentale. {line\_range\_start=107 line\_range\_end=118 path=.kb/documenti/documenti di design/run 2/design\_document\_v\_02.md git\_url="https://github.com/DanieleBarbiero/dsl\_manager-v1/blob/main/.kb/documenti/documenti di design/run 2/design\_document\_v\_02.md#L107-L118"}

---

# 10. Anche le date diventano candidati

Il percorso temporale segue lo stesso modello.

Supponiamo che un documento contenga:

```
“Questa regola è valida dal 1 gennaio 2025.”
```

L’estrattore registra prima l’evidenza grezza. Poi una regola può produrre:

```
candidate_temporal_interval:
  target: una specifica regola
  start: 2025-01-01
  end: null
  precision: day
  evidenza: frase del documento
```

Anche questo intervallo:

- non viene applicato direttamente;
- entra nel batch dei candidati;
- viene sottoposto alla review comune;
- viene materializzato soltanto se confermato.

La pipeline temporale della v02 passa esplicitamente da evidenza grezza, normalizzazione e raggruppamento alla creazione del candidato `temporal_interval`; solo dopo la review avviene la materializzazione. {line\_range\_start=430 line\_range\_end=442 path=.kb/documenti/documenti di design/run 2/design\_document\_v\_02.md git\_url="https://github.com/DanieleBarbiero/dsl\_manager-v1/blob/main/.kb/documenti/documenti di design/run 2/design\_document\_v\_02.md#L430-L442"}

Inoltre, la temporalità non si propaga automaticamente. Il fatto che una fonte sia datata 2025 non implica che ogni fatto contenuto nella fonte sia valido per tutto il 2025. Ogni propagazione richiede una regola versionata e genera un nuovo candidato con le proprie evidenze. {line\_range\_start=444 line\_range\_end=453 path=.kb/documenti/documenti di design/run 2/design\_document\_v\_02.md git\_url="https://github.com/DanieleBarbiero/dsl\_manager-v1/blob/main/.kb/documenti/documenti di design/run 2/design\_document\_v\_02.md#L444-L453"}

---

# Risultato dello step 3

Ora il registry può trovarsi in questa situazione:

```
CBATCH_000001
├── CAND_REC_000001
│   ├── proposta: database_table CLIENTE
│   ├── evidenza: FRAG_000001
│   ├── regola: ddl_table_fact/1
│   └── stato: pending
│
├── CAND_REC_000002
│   ├── proposta: ORDINE references CLIENTE
│   ├── evidenza: FRAG_000007
│   ├── regola: ddl_fk_relation/1
│   └── stato: pending
│
└── CAND_REC_000003
    ├── proposta: regola di cancellazione Cliente
    ├── evidenza: CHK_000004
    ├── origine: interpretativa
    └── stato: pending
```

Nessuno di questi candidati è ancora entrato nel modello autoritativo.

## Formula mentale aggiornata

```
STEP 1: Quali byte abbiamo?
STEP 2: Che cosa è osservabile dentro quei byte?
STEP 3: Quali affermazioni possiamo proporre sulla base di quelle osservazioni?
```

Il prossimo step sarà la **review**:

```
candidato pending
        ↓
decisione umana o policy automatica autorizzata
        ↓
confirmed / rejected / superseded
```

È il punto in cui DSL Manager distingue formalmente una proposta ben costruita da una proposta effettivamente approvata.

**Verifiche documentali**

- ✅ `nl -ba '.kb/documenti/documenti di design/run 2/design_document_v_02.md' | sed -n '311,367p'`
- ✅ `nl -ba '.kb/documenti/documenti di design/run 2/design_document_v_02.md' | sed -n '412,463p'`
- ✅ `nl -ba '.kb/documenti/documenti di design/run 2/design_document_v_02.md' | sed -n '714,758p'`
- ✅ `nl -ba src/dsl_mngr/core/candidate_validation.py | sed -n '1,260p'`
- ✅ `git status --short` — nessun file creato, modificato o cancellato.

okay. passa pure al prossimo step.

Copy

Worked for 2m 15s

## Step 4 — La review: decidere che cosa può diventare autoritativo

Alla fine dello step precedente abbiamo candidati strutturalmente validi, per esempio:

```
CAND_REC_000001
├── proposta: esiste la tabella CLIENTE
├── evidenza: FRAG_000001
├── origine: ddl_table_fact/1
└── stato: pending
```

Ora DSL Manager deve rispondere a una domanda diversa:

> **Questa proposta deve essere accettata, rifiutata oppure sostituita con una versione corretta?**

Il passaggio è:

```
candidato pending
        ↓
review
        ↓
decisione persistita
        ↓
confirmed | rejected | superseded
```

La review rappresenta il **confine di autorità** del programma.

Prima della review abbiamo osservazioni e proposte. Dopo una decisione positiva possiamo avere materiale autorizzato a entrare nel modello.

---

# 1. Chi può prendere una decisione?

La review può essere effettuata da due categorie di attori:

```
┌─ essere umano
│
review
│
└─ policy automatica esplicitamente autorizzata
```

Entrambe usano lo stesso componente centrale:

```
CandidateReviewService
```

Questo servizio è l’unico punto autorizzato a scrivere decisioni, indipendentemente dal fatto che l’attore sia umano o automatico. {line\_range\_start=162 line\_range\_end=168 path=.kb/documenti/documenti di design/run 2/design\_document\_v\_02.md git\_url="https://github.com/DanieleBarbiero/dsl\_manager-v1/blob/main/.kb/documenti/documenti di design/run 2/design\_document\_v\_02.md#L162-L168"}

Ciò evita due pericoli:

1. che la CLI umana e il batch automatico applichino regole diverse;
2. che una policy automatica aggiri i controlli imposti agli esseri umani.

---

# 2. Review umana

Una persona può consultare la coda dei candidati pending:

```
CAND_REC_000001  database_table CLIENTE
CAND_REC_000002  ORDINE references CLIENTE
CAND_REC_000003  business_rule Cliente/deletion_constraint
```

Concettualmente può poi aprire un candidato e vedere:

- payload completo;
- evidenze citate;
- revisione sorgente;
- origine del candidato;
- regola che lo ha prodotto;
- catena di decisioni;
- eventuali correzioni;
- stato materializzato;
- stato effettivo.

La CLI progettata dalla v02 prevede infatti:

````
Bash


```
dsl-manager candidates review list <workspace>
dsl-manager candidates review show <workspace> CAND_REC_000001
```
````

Per impostazione predefinita `list` mostra i candidati pending, mentre `show` espone payload, evidenze, lineage e storia decisionale. {line\_range\_start=490 line\_range\_end=510 path=.kb/documenti/documenti di design/run 2/design\_document\_v\_02.md git\_url="https://github.com/DanieleBarbiero/dsl\_manager-v1/blob/main/.kb/documenti/documenti di design/run 2/design\_document\_v\_02.md#L490-L510"}

La persona può quindi scegliere tra tre operazioni principali:

```
confirm
reject
correct
```

---

# 3. Prima possibilità: confermare

Una conferma significa:

> “Considerate le evidenze disponibili, approvo questa proposta.”

Esempio:

```
CAND_REC_000001
proposta: database_table CLIENTE
evidenza: CREATE TABLE CLIENTE
```

Decisione:

```
DEC_000001
├── soggetto: CAND_REC_000001
├── attore: human/reviewer_anna
├── outcome: confirmed
├── reason: human_confirmed
└── evidenza: FRAG_000001
```

Il comando concettuale è:

````
Bash


```
dsl-manager candidates review confirm \
  <workspace> CAND_REC_000001 \
  --actor-id reviewer_anna
```
````

Se non viene fornita una motivazione esplicita, una conferma umana può usare la motivazione normalizzata `human_confirmed`. {line\_range\_start=164 line\_range\_end=168 path=.kb/documenti/documenti di design/run 2/design\_document\_v\_02.md git\_url="https://github.com/DanieleBarbiero/dsl\_manager-v1/blob/main/.kb/documenti/documenti di design/run 2/design\_document\_v\_02.md#L164-L168"}

## Che cosa non significa ancora `confirmed`?

Non significa necessariamente che il fatto sia già stato scritto nelle tabelle autoritative.

Significa:

```
il candidato è approvato
        +
è potenzialmente eleggibile al merge
```

La materializzazione vera e propria avverrà nello step successivo.

---

# 4. Seconda possibilità: rifiutare

Un rifiuto significa:

> “La proposta è formalmente valida, ma non deve essere accettata.”

Esempio:

```
CAND_REC_000003
proposta:
  “Ogni cliente può sempre essere cancellato”

evidenza:
  log con una singola cancellazione riuscita
```

Il candidato era strutturalmente valido perché:

- il log esisteva;
- il frammento esisteva;
- la citazione era corretta.

Ma l’interpretazione era eccessiva: un singolo evento osservato non prova una regola universale.

Decisione:

```
DEC_000003
├── soggetto: CAND_REC_000003
├── outcome: rejected
└── reason: single_observation_does_not_establish_business_rule
```

Il comando concettuale è:

````
Bash


```
dsl-manager candidates review reject \
  <workspace> CAND_REC_000003 \
  --actor-id reviewer_anna \
  --reason "single observation does not establish a business rule"
```
````

Il rifiuto richiede sempre una motivazione non vuota. {line\_range\_start=164 line\_range\_end=168 path=.kb/documenti/documenti di design/run 2/design\_document\_v\_02.md git\_url="https://github.com/DanieleBarbiero/dsl\_manager-v1/blob/main/.kb/documenti/documenti di design/run 2/design\_document\_v\_02.md#L164-L168"}

Il candidato non viene cancellato. Rimangono conservati:

- proposta originale;
- evidenze;
- autore/origine;
- decisione;
- motivazione;
- data della decisione.

Quindi il sistema conserva non solo ciò che crede, ma anche **ciò che ha valutato e deciso di non credere**.

---

# 5. “Rejected” non significa “strutturalmente invalido”

Esistono due rifiuti diversi.

## Rifiuto strutturale

```
rejected_candidates
```

Vuol dire:

> “Il record non era nemmeno una proposta esaminabile.”

Per esempio:

- mancava l’evidenza;
- il frammento non esisteva;
- il payload non rispettava lo schema;
- erano presenti placeholder irrisolti.

## Decisione di review `rejected`

Vuol dire:

> “La proposta era esaminabile, ma è stata giudicata non accettabile.”

La v02 distingue espressamente queste due situazioni. {line\_range\_start=107 line\_range\_end=118 path=.kb/documenti/documenti di design/run 2/design\_document\_v\_02.md git\_url="https://github.com/DanieleBarbiero/dsl\_manager-v1/blob/main/.kb/documenti/documenti di design/run 2/design\_document\_v\_02.md#L107-L118"}

---

# 6. Terza possibilità: correggere

A volte una proposta non è completamente sbagliata: deve essere modificata.

Immaginiamo:

```
CAND_REC_000004
proposta originale:
  ORDINE writes_to CLIENTE
```

Dall’evidenza risulta invece:

```
ORDINE references CLIENTE
```

DSL Manager **non modifica il candidato originale**. La correzione produce una linea storica:

```
CAND_REC_000004
├── payload originale: ORDINE writes_to CLIENTE
├── decisione corrente: superseded
│
└── CAND_REC_000010
    ├── payload corretto: ORDINE references CLIENTE
    ├── parent: CAND_REC_000004
    └── decisione corrente: confirmed
```

Questa struttura si chiama **lineage**, cioè linea di discendenza della correzione.

Il candidato originale rimane intatto. Nasce un nuovo candidato completo, con:

- un nuovo `candidate_record_id`;
- un collegamento al candidato precedente;
- il payload corretto;
- evidenze esistenti o una nuova attestazione umana;
- la motivazione della correzione;
- una nuova decisione.

La correzione viene eseguita atomicamente: il vecchio candidato diventa `superseded`, nasce il batch di correzione, viene creato il nuovo candidato e il sostituto riceve la testa `confirmed`. {line\_range\_start=176 line\_range\_end=189 path=.kb/documenti/documenti di design/run 2/design\_document\_v\_02.md git\_url="https://github.com/DanieleBarbiero/dsl\_manager-v1/blob/main/.kb/documenti/documenti di design/run 2/design\_document\_v\_02.md#L176-L189"}

## Perché non modificare direttamente il record?

Per non perdere la risposta alle domande:

- che cosa era stato proposto originariamente?
- chi l’ha corretto?
- perché?
- quale evidenza sosteneva la correzione?
- quale versione è quella corrente?

La storia diventa:

```
proposta originale
        ↓
correzione
        ↓
eventuale seconda correzione
        ↓
foglia corrente
```

Solo la **foglia corrente** può essere presa in considerazione per il merge.

---

# 7. La decisione è un evento, non un campo sovrascritto

DSL Manager non gestisce la review come un semplice campo:

```
candidate.status = confirmed
```

Gestisce invece una successione append-only di decisioni:

```
DEC_000001: confirmed
      ↓ superseded_by
DEC_000007: rejected
      ↓ superseded_by
DEC_000012: confirmed
```

Ogni nuova decisione viene aggiunta; quella precedente non viene riscritta.

Una tabella conserva tutte le decisioni:

```
review_decisions
```

e una seconda struttura indica qual è la decisione corrente:

```
review_subject_heads
```

Il modello dati della v02 registra per ogni decisione il soggetto, l’attore, l’outcome, la motivazione, gli hash, la decisione precedente, la testa attesa e l’identità della policy; conserva separatamente anche la testa corrente del soggetto. {line\_range\_start=211 line\_range\_end=229 path=.kb/documenti/documenti di design/run 2/design\_document\_v\_02.md git\_url="https://github.com/DanieleBarbiero/dsl\_manager-v1/blob/main/.kb/documenti/documenti di design/run 2/design\_document\_v\_02.md#L211-L229"}

Possiamo visualizzarlo così:

```
storia completa                     puntatore corrente

DEC_000001 confirmed ─┐
DEC_000007 rejected  ─┼──────────→ HEAD = DEC_000012
DEC_000012 confirmed ─┘
```

Quello che conta per le operazioni future è la **testa corrente**, ma tutta la storia rimane auditabile.

---

# 8. Review automatica: consentita, ma sotto regole strette

Una regola deterministica può produrre un candidato molto affidabile, per esempio:

````
SQL


```
CREATE TABLE CLIENTE
```
````

La pipeline potrebbe essere autorizzata a confermarlo automaticamente.

Ma la condizione non è semplicemente:

```
confidence = high
```

Deve esistere una policy esplicitamente configurata e versionata:

```
policy_id: confirm_explicit_ddl_tables
policy_version: 1
```

La decisione automatica conserva:

- ID della policy;
- versione;
- candidato;
- evidenza;
- hash della richiesta;
- outcome;
- decisione eventualmente superata.

Per un attore automatico, `policy_id` e `policy_version` sono obbligatori. {line\_range\_start=164 line\_range\_end=168 path=.kb/documenti/documenti di design/run 2/design\_document\_v\_02.md git\_url="https://github.com/DanieleBarbiero/dsl\_manager-v1/blob/main/.kb/documenti/documenti di design/run 2/design\_document\_v\_02.md#L164-L168"}

Le policy automatiche abilitate sono inoltre elencate esplicitamente nella configurazione:

````
TOML


```
[review]
automatic_policies = []
```
````

Il valore predefinito vuoto significa che non bisogna presumere un’autorizzazione automatica generale. {line\_range\_start=524 line\_range\_end=535 path=.kb/documenti/documenti di design/run 2/design\_document\_v\_02.md git\_url="https://github.com/DanieleBarbiero/dsl\_manager-v1/blob/main/.kb/documenti/documenti di design/run 2/design\_document\_v\_02.md#L524-L535"}

La regola mentale è:

```
alta confidenza
≠
autorizzazione alla conferma automatica
```

---

# 9. Protezione contro due decisioni simultanee

Immaginiamo che Anna e Marco aprano contemporaneamente lo stesso candidato.

Entrambi vedono:

```
HEAD = nessuna decisione
```

Anna conferma per prima:

```
HEAD = DEC_000001 confirmed
```

Marco tenta subito dopo di rifiutare il candidato basandosi sulla vecchia situazione:

```
expected HEAD = nessuna
actual HEAD   = DEC_000001
```

DSL Manager rifiuta l’operazione di Marco con:

```
review_head_conflict
```

Non crea una seconda testa parallela.

Marco deve ricaricare il candidato, vedere la decisione di Anna e scegliere consapevolmente se superarla.

Il confronto tra testa attesa e testa corrente avviene nella stessa transazione che registra la decisione. Una testa non aggiornata non produce mutazioni. {line\_range\_start=170 line\_range\_end=174 path=.kb/documenti/documenti di design/run 2/design\_document\_v\_02.md git\_url="https://github.com/DanieleBarbiero/dsl\_manager-v1/blob/main/.kb/documenti/documenti di design/run 2/design\_document\_v\_02.md#L170-L174"}

Questo impedisce una storia ambigua come:

```
             ┌── confirmed
candidato ───┤
             └── rejected
```

Deve sempre esistere una sola sequenza:

```
candidato
   ↓
confirmed
   ↓
eventuale decisione successiva che la supera
```

---

# 10. Protezione contro i retry duplicati

Un altro problema pratico è:

1. l’utente invia `confirm`;
2. il database registra la decisione;
3. la connessione si interrompe prima che l’utente riceva la risposta;
4. l’utente ripete il comando.

Senza protezione potrebbero nascere due decisioni identiche.

DSL Manager usa una **chiave idempotente** e un hash della richiesta:

```
stessa chiave + stesso payload
        ↓
restituisci la decisione già esistente
```

Non viene creata una seconda decisione.

Se invece qualcuno riutilizza la stessa chiave con un contenuto differente:

```
stessa chiave + payload diverso
        ↓
idempotency_payload_conflict
```

Il catalogo distingue esplicitamente il replay identico, il no-op semantico, il conflitto di testa e il riutilizzo scorretto della chiave idempotente. {line\_range\_start=563 line\_range\_end=576 path=.kb/documenti/documenti di design/run 2/design\_document\_v\_02.md git\_url="https://github.com/DanieleBarbiero/dsl\_manager-v1/blob/main/.kb/documenti/documenti di design/run 2/design\_document\_v\_02.md#L563-L576"}

---

# 11. Quale candidato diventa merge-eligible?

Non basta trovare una decisione `confirmed` da qualche parte nella storia.

Un candidato è eleggibile soltanto se:

1. è la **foglia corrente** della propria linea di correzione;
2. la sua **testa decisionale corrente** è `confirmed`.

Esempio:

```
CAND_A
├── vecchia decisione: confirmed
├── testa corrente: superseded
│
└── CAND_B
    └── testa corrente: rejected
```

In questo caso:

- `CAND_A` non è eleggibile, perché non è più la foglia;
- `CAND_B` non è eleggibile, perché la testa è `rejected`;
- la linea non fornisce alcun candidato eleggibile.

Il vecchio candidato non “torna valido” soltanto perché la sua correzione è stata rifiutata. Questa è una delle invarianti esplicite del design. {line\_range\_start=120 line\_range\_end=131 path=.kb/documenti/documenti di design/run 2/design\_document\_v\_02.md git\_url="https://github.com/DanieleBarbiero/dsl\_manager-v1/blob/main/.kb/documenti/documenti di design/run 2/design\_document\_v\_02.md#L120-L131"}

---

# Risultato dello step 4

Dopo la review possiamo avere:

```
CBATCH_000001
├── CAND_REC_000001
│   ├── proposta: database_table CLIENTE
│   └── testa: confirmed
│
├── CAND_REC_000002
│   ├── proposta: ORDINE references CLIENTE
│   └── testa: confirmed
│
├── CAND_REC_000003
│   ├── proposta: regola universale ricavata da un log
│   └── testa: rejected
│
└── CAND_REC_000004
    ├── proposta originale errata
    ├── testa: superseded
    └── sostituito da CAND_REC_000010
        └── testa: confirmed
```

I candidati eleggibili sono:

```
CAND_REC_000001
CAND_REC_000002
CAND_REC_000010
```

Non sono eleggibili:

```
CAND_REC_000003  → rejected
CAND_REC_000004  → superseded e non più foglia
```

## Formula mentale aggiornata

```
STEP 1: Quali byte abbiamo?
STEP 2: Che cosa è osservabile dentro quei byte?
STEP 3: Quali affermazioni possiamo proporre?
STEP 4: Quali proposte approviamo?
```

Il prossimo step sarà il **merge autoritativo**:

```
candidati merge-eligible
          ↓
materializzazione
          ↓
facts + relations + supporti
```

Vedremo soprattutto una distinzione importante: un fatto non viene soltanto “copiato” dal candidato, ma viene collegato alle evidenze che lo sostengono, e più candidati possono sostenere lo stesso fatto.

**Verifiche documentali**

- ✅ `nl -ba '.kb/documenti/documenti di design/run 2/design_document_v_02.md' | sed -n '162,210p'`
- ✅ `nl -ba '.kb/documenti/documenti di design/run 2/design_document_v_02.md' | sed -n '488,599p'`
- ✅ `nl -ba '.kb/documenti/documenti di design/run 2/design_document_v_02.md' | sed -n '209,247p'`
- ✅ `git status --short` — nessun dato o file è stato creato, modificato o cancellato.

okay. una domanda extra percorso prima di procedere al prossimo step: il prossimo step parla del coinvolgimento ai? non occorre una risposta lunga. è giusto per sapere se arriviamo al momento in cui il processo (suppongo) si biforca e abbiamo candidati deterministici e candidati ai.

Copy

Worked for 5m 16s

## Risposta breve

La biforcazione è avvenuta **nello step 3**, prima della review:

```
evidenze
   ├── regole deterministiche ─→ candidati deterministici
   └── AI/operatore esterno ───→ candidati interpretativi
                                  ↓
                         importer e validazione comuni
                                  ↓
                               pending
```

L’AI non è quindi il prossimo step e non costituisce una pipeline autoritativa separata: è **uno dei possibili produttori di candidati**. Tutti i candidati, qualunque sia l’origine, devono essere collegati a evidenze e attraversare la review comune. Le regole deterministiche non usano l’AI. {line\_range\_start=340 line\_range\_end=365 path=.kb/documenti/documenti di design/run 2/design\_document\_v\_02.md git\_url="https://github.com/DanieleBarbiero/dsl\_manager-v1/blob/main/.kb/documenti/documenti di design/run 2/design\_document\_v\_02.md#L340-L365"}

Il prossimo step è invece il **merge autoritativo** dei soli candidati confermati ed eleggibili. Possiamo però, prima di affrontarlo, dedicare un breve step specifico al ramo AI per rendere evidente come nasce e poi si ricongiunge al flusso principale.

sì, grazie, esploriamo il ramo AI. per facilitare il processo di ricostruzione del percorso, trattalo come "step <numero che avrebbe dovuto avere nel percorso>" alternativo (o "step <numero> A, B, C..." alternativi, se ce ne vogliono più di uno). torneremo al flusso principale con lo step 5.

Copy

Worked for 1m 41s

## Step 3B — Il ramo AI: dalle evidenze ai candidati interpretativi

Lo **step 3A** visto in precedenza era il ramo deterministico:

```
evidenze strutturali
        ↓
regole deterministiche versionate
        ↓
candidati tecnici
```

Il ramo alternativo è:

```
evidenze testuali e strutturali
        ↓
package AI
        ↓
elaborazione AI esterna
        ↓
candidati interpretativi JSONL
        ↓
import e validazione
        ↓
candidati pending
```

I due rami si ricongiungono prima della review:

```
                     ┌─ 3A: regole deterministiche
evidenze ────────────┤
                     └─ 3B: AI esterna
                                ↓
                       candidati validi
                                ↓
                         STEP 4: review
```

---

# 3B.1 — DSL Manager prepara un dossier per l’AI

DSL Manager non consegna necessariamente all’AI i file originali senza contesto. Costruisce un **AI package** deterministico contenente le evidenze già preparate nello step 2:

- revisioni sorgente;
- chunk testuali;
- frammenti strutturali;
- istruzioni;
- schema dei candidati consentiti;
- modello dell’output atteso;
- manifest e hash del package.

Il comando virtuale è:

````
Bash


```
dsl-manager ai package <workspace>
```
````

Il package risultante ha una struttura simile a:

```
ai/outbox/AIPKG_000001/
├── instructions.md
├── content.md
├── source_manifest.json
├── candidate_schema.json
├── output_template.jsonl
└── package_manifest.json
```

Questa struttura è prevista dal flusso operativo documentato.

Il codice conferma che il package viene costruito caricando dal registry revisioni, chunk attivi e frammenti attivi; se non esiste alcuna evidenza attiva, il package non può essere prodotto.

---

# 3B.2 — Che cosa riceve realmente l’AI?

L’AI riceve un dossier che, concettualmente, dice:

```
Queste sono le evidenze disponibili.
Queste sono le loro identità e revisioni.
Questo è lo schema delle proposte ammesse.
Per ogni proposta devi indicare la prova che la sostiene.
Restituisci esclusivamente candidati, non fatti autoritativi.
```

Per esempio, nel package potrebbe trovare:

```
CHK_000004
Fonte: manuale_clienti.pdf
Revisione: REV_000002

“Quando un cliente ha ordini aperti,
la cancellazione dell’anagrafica non è consentita.”
```

L’AI potrebbe restituire:

````
JSON


```
{
  "record_type": "candidate_fact",
  "candidate_id": "CAND_000001",
  "source_revision_id": "REV_000002",
  "chunk_id": "CHK_000004",
  "fact_type": "business_rule",
  "entity_name": "Cliente",
  "property_name": "deletion_constraint",
  "property_value": "La cancellazione è vietata in presenza di ordini aperti",
  "assertion_type": "explicit",
  "evidence_text": "Quando un cliente ha ordini aperti, la cancellazione dell’anagrafica non è consentita."
}
```
````

L’AI ha interpretato il testo, ma ha prodotto soltanto una **proposta verificabile**.

---

# 3B.3 — L’AI è esterna al nucleo autoritativo

Un punto importante: DSL Manager non affida all’AI l’accesso diretto al registry.

Il confine è:

```
DSL Manager                         AI esterna
     │                                  │
     ├── produce package ──────────────→│
     │                                  ├── interpreta
     │←──────── restituisce JSONL ──────┤
     │
     └── valida e importa autonomamente
```

L’AI:

- non scrive nelle tabelle `facts`;
- non scrive nelle tabelle `relations`;
- non conferma autonomamente i propri candidati;
- non modifica evidenze;
- non modifica revisioni;
- non esegue il merge.

Il design vieta esplicitamente a qualsiasi generatore di scrivere direttamente nel registro autoritativo. {line\_range\_start=57 line\_range\_end=65 path=.kb/documenti/documenti di design/run 2/design\_document\_v\_02.md git\_url="https://github.com/DanieleBarbiero/dsl\_manager-v1/blob/main/.kb/documenti/documenti di design/run 2/design\_document\_v\_02.md#L57-L65"}

Quindi l’AI non è “il cervello sovrano” del programma. È più simile a un **analista esterno che prepara proposte documentate**.

---

# 3B.4 — Perché usare l’AI se esistono le regole deterministiche?

Le regole deterministiche sono adatte a corrispondenze tecniche precise:

```
CREATE TABLE       → tabella tecnica
FOREIGN KEY        → relazione references
CALL procedura_x   → relazione calls
```

L’AI è utile quando bisogna interpretare linguaggio meno strutturato:

```
“La pratica viene trasferita all’ufficio rischi
quando il punteggio è inferiore alla soglia.”
```

Da questa frase potrebbero emergere candidati relativi a:

- entità di dominio;
- regole di business;
- relazioni concettuali;
- condizioni operative;
- mapping tra termini tecnici e concetti di dominio;
- domande o ambiguità da sottoporre a una persona.

La differenza è quindi:

```
deterministico:
“vedo una foreign key esplicita”

interpretativo:
“questa frase sembra descrivere una regola di business”
```

Il ramo AI amplia ciò che può essere proposto, ma non abbassa il livello di controllo.

---

# 3B.5 — L’output rientra tramite una inbox

L’AI restituisce un file JSONL associato al package, per esempio:

```
ai/inbox/AIPKG_000001_candidates.jsonl
```

DSL Manager non lo acquisisce implicitamente come verità. Prima controlla che:

- il package esista;
- sia quello corretto;
- le revisioni usate dal package siano ancora correnti;
- il file restituito sia associabile al package.

Il manuale prevede un controllo della inbox che distingue un package ancora valido da uno diventato `stale`.

---

# 3B.6 — Che cosa significa “package stale”?

Immaginiamo questa sequenza:

```
1. REV_000001 entra nel package AI
2. l’AI inizia a lavorare
3. il documento originale viene modificato
4. nasce REV_000002
5. l’AI restituisce candidati basati su REV_000001
```

I candidati non sono necessariamente privi di valore, ma sono stati prodotti su una revisione che non è più corrente.

DSL Manager segnala quindi:

```
AIPKG_000001
status: stale
reason: source_revision_not_current
```

La scelta ordinaria è:

```
rigenerare il package con REV_000002
        ↓
ripetere l’elaborazione AI
```

Questo controllo impedisce che una risposta tardiva venga scambiata silenziosamente per un’analisi delle fonti correnti.

Il flusso precedente contemplava anche un’importazione consapevole con `--allow-stale`, ma ciò non rende il contenuto aggiornato: segnala soltanto che l’operatore ha accettato esplicitamente il rischio.

---

# 3B.7 — Import e validazione dei candidati AI

Se il package è utilizzabile, DSL Manager importa il JSONL:

````
Bash


```
dsl-manager ai import <workspace> --package AIPKG_000001
```
````

L’importazione:

1. verifica il package;
2. verifica lo stato `stale`;
3. legge i record JSONL;
4. valida ogni record;
5. crea un candidate batch;
6. registra i candidati validi;
7. separa i rifiuti strutturali;
8. marca il package come importato.

Questo percorso è descritto nel manuale operativo.

Esempio:

```
CBATCH_000009
origin_type: ai_package
origin_ref: AIPKG_000001

├── CAND_REC_000031 → valido, pending
├── CAND_REC_000032 → valido, pending
└── record 3         → rifiuto strutturale:
                       evidence_text_not_found
```

L’importer non si fida del candidato soltanto perché proviene dall’AI. Controlla nuovamente:

- schema;
- revisione;
- chunk o frammento;
- appartenenza dell’evidenza alla revisione;
- citazione dell’evidenza;
- campi semantici richiesti.

---

# 3B.8 — Il punto di ricongiungimento

Dopo l’importazione, l’origine non cambia le regole fondamentali:

```
CAND_REC_000031
├── origin: ai_package/AIPKG_000001
├── evidence: CHK_000004
└── outcome corrente: pending
```

A fianco potrebbe esserci:

```
CAND_REC_000032
├── origin: deterministic_derivation/ddl_table_fact/1
├── evidence: FRAG_000001
└── outcome corrente: pending
```

Entrambi entrano nello stesso step 4:

```
CandidateReviewService
```

e possono ricevere:

```
confirmed
rejected
superseded tramite correzione
```

Non esiste quindi:

```
pipeline affidabile per candidati deterministici
pipeline privilegiata per candidati AI
```

Esiste invece:

```
più produttori di proposte
          ↓
un solo sistema di validazione e governo
```

---

# Riassunto del ramo alternativo

```
STEP 2
evidenze
   │
   ├──────────────────────────────────────┐
   │                                      │
STEP 3A                               STEP 3B
regole deterministiche                package AI
   │                                      ↓
   │                                  AI esterna
   │                                      ↓
   │                                  JSONL candidati
   │                                      ↓
   │                                  import/validazione
   │                                      │
   └───────────────┬──────────────────────┘
                   ↓
STEP 4
review comune
                   ↓
confirmed / rejected / superseded
```

La formula più sintetica è:

> **L’AI può proporre; DSL Manager conserva le prove, valida la proposta e governa la decisione.**

Da qui possiamo tornare al percorso principale con lo **step 5: il merge autoritativo**.

**Verifiche documentali**

- ✅ `nl -ba '.kb/documenti/manuali/manuale_utente_dsl_manager.md' | sed -n '299,445p'`
- ✅ `nl -ba '.kb/documenti/documenti di design/run 2/design_document_v_02.md' | sed -n '42,65p'`
- ✅ `nl -ba '.kb/documenti/documenti di design/run 2/design_document_v_02.md' | sed -n '599,629p'`
- ✅ `nl -ba src/dsl_mngr/core/ai_package.py | sed -n '1,230p'`
- ✅ `git status --short` — tour esclusivamente virtuale; nessuna modifica al repository o ai dati.

una domanda follow up extra percorso: l'utente di dsl manager può decidere (forse, \*deve\* decidere) quali evidenze sottoporre all'analisi deterministica e quali all'ai, per la produzione di candidati?
può darsi che mi sbagli, ma al momento l'impressione è che le evidenze vengano prodotte analizzando i file in una singola passata. quindi la scelta sembra essere se sottoporre l'insieme delle evidenze all'analisi deterministica, oppure all'ai, oppure a entrambi gli analizzatori, a prescindere dal contenuti (es. dati tecnici contro manuali / documenti). mi sbaglio?

Copy

Worked for 1m 16s

## Risposta breve: non serve una spartizione esclusiva

La tua impressione è **quasi corretta**, ma bisogna separare due decisioni:

1. **come vengono prodotte le evidenze**;
2. **a quali produttori di candidati vengono poi fornite**.

Il modello corretto è:

```
file
  ↓
estrazione delle evidenze
  ↓
insieme comune di evidenze
  ├── regole deterministiche compatibili
  └── eventuale package AI
```

L’utente **non deve necessariamente classificare ogni evidenza** come “solo deterministica” oppure “solo AI”. La stessa evidenza può essere utilizzata:

- soltanto dalle regole deterministiche;
- soltanto dall’AI;
- da entrambe;
- da nessuna, se nessun elaboratore applicabile viene eseguito.

---

## 1. Le evidenze vengono prodotte in una pipeline comune, ma non da un unico parser universale

La lavorazione può apparire come una singola passata perché il batch orchestra tutto, ma internamente instrada ogni revisione verso elaboratori differenti:

```
manuale.pdf ─→ Docling ─→ chunk
schema.sql ──→ parser DDL ─→ frammenti
form.xml ────→ parser XML ─→ frammenti
app.log ─────→ parser log ─→ frammenti
```

Il batch corrente effettua prima lo scan e poi pianifica le lavorazioni per le revisioni attive.

Quindi esiste un **deposito comune di evidenze**, ma le evidenze non sono tutte omogenee.

---

## 2. L’analisi deterministica seleziona automaticamente solo gli input compatibili

Le regole deterministiche non ricevono indiscriminatamente ogni evidenza.

Ogni regola dichiara:

- il parser da cui deve provenire l’input;
- lo schema richiesto;
- il tipo di osservazione necessario;
- il metodo per localizzare la prova.

Per esempio:

```
ddl_table_fact/1
```

si applica a un frammento `ddl_table`, non a un paragrafo generico di un PDF.

Analogamente:

```
log_event_observation/1
```

si applica a un evento prodotto dal parser dei log, non a una cella Excel.

Questo filtro di compatibilità fa parte del contratto delle regole deterministiche. {line\_range\_start=340 line\_range\_end=357 path=.kb/documenti/documenti di design/run 2/design\_document\_v\_02.md git\_url="https://github.com/DanieleBarbiero/dsl\_manager-v1/blob/main/.kb/documenti/documenti di design/run 2/design\_document\_v\_02.md#L340-L357"}

Perciò non accade normalmente:

```
tutte le evidenze
      ↓
ogni regola deterministica prova a interpretarle tutte
```

Accade invece:

```
tutte le evidenze
      ↓
selezione per parser + schema + tipo
      ↓
solo regole tecnicamente applicabili
```

L’utente può inoltre restringere esplicitamente la derivazione:

````
Bash


```
dsl-manager candidates derive <workspace> \
  --source-revision-id REV_000001 \
  --rule ddl_table_fact/1
```
````

La CLI v02 prevede infatti filtri per revisione e per regola. {line\_range\_start=363 line\_range\_end=365 path=.kb/documenti/documenti di design/run 2/design\_document\_v\_02.md git\_url="https://github.com/DanieleBarbiero/dsl\_manager-v1/blob/main/.kb/documenti/documenti di design/run 2/design\_document\_v\_02.md#L363-L365"}

---

## 3. Il ramo AI è più deliberato

La generazione del package AI è un’operazione separata. L’utente o il batch decide **se eseguirla** e può selezionare le revisioni da includere.

Il package può contenere:

```
chunk testuali
+
frammenti strutturali
```

Il codice del package prevede una lista di revisioni e opzioni distinte per includere chunk e frammenti.

Quindi si possono immaginare scelte come:

```
solo manuali → AI
solo frammenti di alcune revisioni tecniche → AI
manuali + DDL → AI
nessun package AI
```

Tuttavia, il contratto attualmente descritto offre soprattutto selezione per:

- revisione;
- inclusione di chunk;
- inclusione di frammenti.

Non risulta progettata una UI granulare con cui marcare manualmente ogni singola evidenza:

```
CHK_001 → AI sì
CHK_002 → AI no
FRAG_003 → AI sì
```

Perciò una selezione estremamente fine richiederebbe package separati, filtri ulteriori oppure un’estensione del contratto.

---

## 4. Deterministico e AI possono lavorare sulle stesse evidenze

Non sono alternative mutuamente esclusive.

Per esempio, un frammento DDL può essere usato:

```
FRAG_DDL_001
   ├── regola deterministica
   │     └── database_table = CLI_MSTR
   │
   └── package AI
         └── possibile mapping:
             CLI_MSTR ↔ Cliente
```

Qui i due analizzatori svolgono compiti diversi:

- la regola deterministica estrae ciò che è tecnicamente esplicito;
- l’AI propone un’interpretazione o un mapping semantico.

Potrebbero anche produrre candidati simili o duplicati. Questo non è automaticamente un errore: importer, canonicalizzazione, deduplicazione, review e merge devono governare il risultato.

---

## 5. Qual è il comportamento previsto del batch v02?

Il percorso automatico principale previsto dalla v02 è:

```
parser
  ↓
derive deterministico
  ↓
eventuali policy automatiche autorizzate
  ↓
merge degli eleggibili
  ↓
eventuale riconciliazione
```

La derivazione deterministica viene inserita automaticamente dopo i parser strutturali. {line\_range\_start=728 line\_range\_end=732 path=.kb/documenti/documenti di design/run 2/design\_document\_v\_02.md git\_url="https://github.com/DanieleBarbiero/dsl\_manager-v1/blob/main/.kb/documenti/documenti di design/run 2/design\_document\_v\_02.md#L728-L732"}

Il ramo AI rimane invece un circuito esplicito e asincrono:

```
costruisci package
  ↓
attendi risposta esterna
  ↓
importa candidati
```

Questo perché l’AI può essere:

- esterna;
- lenta;
- non disponibile;
- soggetta a un processo umano;
- non ammessa in determinati ambienti;
- non necessaria per un’estrazione puramente tecnica.

---

## Conclusione

Quindi:

- **sì**, le evidenze costituiscono un patrimonio comune prodotto prima dei candidati;
- **sì**, deterministico e AI possono entrambi ricevere evidenze provenienti dalla stessa revisione;
- **no**, l’utente non deve necessariamente dividere preventivamente ogni evidenza in due insiemi esclusivi;
- **no**, le regole deterministiche non elaborano indiscriminatamente tutto: si applicano solo agli input compatibili;
- **sì**, l’invio all’AI è una scelta separata e può essere circoscritto almeno per revisione e per categoria `chunks`/`fragments`;
- **no**, il design attuale non sembra offrire una selezione manuale nativa evidenza-per-evidenza.

La rappresentazione più fedele è dunque:

```
                         ┌─ derive automatico sulle
                         │  evidenze compatibili
evidenze comuni ─────────┤
                         └─ package AI esplicitamente
                            richiesto e selezionato
```

Non è una biforcazione “o l’uno o l’altro”, ma una biforcazione **componibile**.

**Verifiche documentali**

- ✅ `nl -ba '.kb/documenti/documenti di design/run 2/design_document_v_02.md' | sed -n '311,367p'`
- ✅ `nl -ba '.kb/documenti/documenti di design/run 2/design_document_v_02.md' | sed -n '714,758p'`
- ✅ `nl -ba src/dsl_mngr/core/ai_package.py | sed -n '1,230p'`
- ✅ `nl -ba src/dsl_mngr/core/batch.py | sed -n '1,260p'`
- ✅ `git status --short` — nessun file o dato modificato.

altra domanda extra percorso, alla quale forse hai già risposto: c'è un modo per selezionare le evidenze che sono eligibili per l'analisi AI (es. sulla base del fatto che \*non\* sono state prodotte dai parser specializzati, ad esempio) o tocca mettere mano al codice?

Copy

Worked for 47s

## Risposta breve

**Con il contratto attuale/v02, non esiste un filtro automatico del tipo:**

```
invia all’AI soltanto le evidenze
non prodotte dai parser specializzati
```

Le selezioni disponibili sono più grossolane:

1. **per revisione sorgente**, ripetendo `--revision`; la CLI consente infatti di scegliere quali `source_revision_id` includere nel package.
2. **per categoria di evidenza**, tramite il profilo:

   - `include_chunks`;
   - `include_fragments`.
     Il costruttore del package applica proprio questi due interruttori.

Quindi puoi ottenere facilmente, per esempio:

```
solo chunk dei manuali
```

selezionando le revisioni dei manuali e disabilitando i frammenti. Ma non puoi dichiarare direttamente:

```
escludi tutti i frammenti prodotti da parse_ddl
includi quelli XML
includi solo le evidenze non consumate da derive
```

Per una policy simile occorrerebbe **estendere il codice e il contratto del profilo**, aggiungendo filtri basati, per esempio, su:

- `parser_kind`;
- `source_type`;
- `fragment_type`;
- `rule applicability`;
- presenza o assenza di candidati deterministici già derivati.

### Una cautela concettuale

Eviterei però la regola generale:

```
se un parser specializzato ha prodotto l’evidenza,
allora non inviarla all’AI
```

Lo stesso frammento DDL potrebbe servire:

- alla derivazione deterministica per riconoscere `CLI_MSTR` come tabella tecnica;
- all’AI per proporre il mapping interpretativo `CLI_MSTR ↔ Cliente`.

Una policy probabilmente più utile sarebbe:

```
AI eligibility =
  tipo di sorgente
  + tipo di evidenza
  + obiettivo interpretativo richiesto
  + eventuale copertura delle regole deterministiche
```

In sintesi: **oggi puoi filtrare per revisione e per macro-categoria chunk/frammenti; per filtrare secondo provenienza, parser o copertura deterministica bisogna modificare il programma.**

**Verifiche documentali**

- ✅ `rg -n "ai package|package-batch|revision-id|include_chunks|include_fragments" src/dsl_mngr/cli src/dsl_mngr/core/ai_package.py src/dsl_mngr/core/batch.py`
- ✅ `nl -ba src/dsl_mngr/cli/app.py | sed -n '180,330p'`
- ✅ `nl -ba src/dsl_mngr/core/ai_package.py | sed -n '113,170p'`
- ✅ `git status --short` — nessuna modifica effettuata.

domanda/e extra percorso (in questo caso, ignora pure la regola sulle risposte brevi e prenditi tutto lo spazio che ti serve).
1. da interfaccia cli dell'applicazione, qual è il sistema per filtrare per revisione e per macro-categoria chunk/frammenti? lo considereresti sufficientemente facile / utilizzabile oppure il programma beneficerebbe di una procedura apposita?
2. sarebbe ipotizzabile una slice 30 (mi pare) che preveda una procedura per selezionare le evidenze sulla base dei criteri che hai descritto? nel qual caso, consiglieresti una modifica del documento di design o la scrittura di un prompt che modifichi il documento di design?

Copy

Worked for 2m 51s

# 1. Come si filtra oggi dalla CLI?

Ci sono due livelli di selezione, ma hanno un’esperienza d’uso diversa:

1. selezione delle **revisioni**, direttamente dalla CLI;
2. selezione della macro-categoria **chunk/frammenti**, indirettamente mediante un profilo YAML.

---

## 1.1 Selezione per revisione: direttamente con `--revision`

Per costruire un package contenente soltanto determinate revisioni:

````
Bash


```
dsl-manager ai package <workspace> \
  --revision REV_000001 \
  --revision REV_000002
```
````

L’opzione è ripetibile. La CLI raccoglie quindi una lista di `source_revision_id`.

Senza `--revision`:

````
Bash


```
dsl-manager ai package <workspace>
```
````

il package viene costruito sull’insieme applicabile delle revisioni che possiedono evidenze attive.

Il manuale documenta entrambi gli utilizzi.

### Package unico contro package separati

Il comando:

````
Bash


```
dsl-manager ai package <workspace> \
  --revision REV_000001 \
  --revision REV_000002
```
````

crea **un unico package** che comprende le evidenze delle revisioni selezionate.

Esiste anche:

````
Bash


```
dsl-manager ai package-batch <workspace> \
  --revision REV_000001 \
  --revision REV_000002
```
````

che crea invece **un package distinto per ogni revisione**. Le revisioni senza evidenze attive vengono saltate con `no_active_evidence`.

Questa distinzione è utile:

```
ai package
REV_1 + REV_2 + REV_3
        ↓
un solo package

ai package-batch
REV_1 + REV_2 + REV_3
        ↓
package 1
package 2
package 3
```

---

## 1.2 Come fa l’utente a conoscere gli ID delle revisioni?

Qui si presenta già il primo problema di usabilità.

Il comando richiede valori come:

```
REV_000017
REV_000024
REV_000031
```

ma un operatore normalmente ragiona in termini di:

```
manuale_clienti.pdf
schema_ordini.sql
form_affidamento.xml
```

Non dovrebbe essere costretto a:

1. consultare un report o il registry;
2. associare ogni nome file al relativo `source_revision_id`;
3. copiare gli ID;
4. comporre manualmente una lunga riga di comando.

Per due revisioni è tollerabile. Per un corpus realistico di decine o centinaia di fonti diventa macchinoso e soggetto a errori.

Il problema aumenta perché l’ID richiesto è quello della **revisione**, non quello stabile della fonte. Se un documento cambia:

```
manuale_clienti.pdf
REV_000001 → superseded
REV_000042 → active
```

una selezione precedentemente annotata potrebbe puntare alla revisione vecchia.

### Valutazione

Il filtro per revisione è:

- **preciso**;
- **riproducibile**;
- **adatto agli script**;
- **scomodo per la selezione esplorativa umana**.

Lo definirei una buona primitiva tecnica, non ancora una procedura ergonomica completa.

---

# 1.3 Selezione chunk/frammenti: mediante profilo

Non risultano flag CLI come:

````
Bash


```
--include-chunks
--exclude-fragments
```
````

La scelta viene fatta attraverso il profilo worker indicato con:

````
Bash


```
--profile <nome>
```
````

I profili si trovano nel workspace:

```
<workspace>/configs/workers/
```

e vengono caricati da:

```
configs/workers/<profile>.yaml
```

Il loader cerca precisamente quel percorso e verifica le sezioni richieste.

Il profilo predefinito contiene:

````
YAML


```
worker:
  name: build_ai_package
  version: 1.0

ai_package:
  include_chunks: true
  include_fragments: true
  include_candidate_schema: true
  include_output_template: true
  max_evidence_chars: 20000
  strict_options_fail_on_unsupported_option: true
  package_format: markdown_plus_json
```
````

Questi sono i valori generati dal workspace iniziale.

---

## 1.4 Esempi di profili custom

### Soltanto chunk

Si potrebbe creare:

```
<workspace>/configs/workers/ai_package.chunks_only.yaml
```

con:

````
YAML


```
worker:
  name: build_ai_package
  version: 1.0

ai_package:
  include_chunks: true
  include_fragments: false
  include_candidate_schema: true
  include_output_template: true
  max_evidence_chars: 20000
  strict_options_fail_on_unsupported_option: true
  package_format: markdown_plus_json
```
````

e poi invocare:

````
Bash


```
dsl-manager ai package <workspace> \
  --revision REV_000001 \
  --revision REV_000002 \
  --profile ai_package.chunks_only
```
````

### Soltanto frammenti

Analogamente:

```
<workspace>/configs/workers/ai_package.fragments_only.yaml
```

````
YAML


```
worker:
  name: build_ai_package
  version: 1.0

ai_package:
  include_chunks: false
  include_fragments: true
  include_candidate_schema: true
  include_output_template: true
  max_evidence_chars: 20000
  strict_options_fail_on_unsupported_option: true
  package_format: markdown_plus_json
```
````

Comando:

````
Bash


```
dsl-manager ai package <workspace> \
  --revision REV_000010 \
  --profile ai_package.fragments_only
```
````

Il costruttore legge dal profilo `include_chunks` e `include_fragments`, quindi carica dal registry soltanto le categorie abilitate.

---

# 1.5 Quanto è facile da utilizzare?

## Per un operatore tecnico occasionale: non abbastanza

L’operatore deve sapere:

- che cosa sia una `source_revision`;
- come trovare il suo ID corrente;
- la differenza tra chunk e frammenti;
- che la selezione delle macro-categorie non è un flag ma un profilo;
- dove creare il profilo;
- quale struttura YAML utilizzare;
- che il nome passato con `--profile` corrisponde a un file sotto `configs/workers`.

Inoltre, una richiesta umanamente semplice come:

> “Manda all’AI i manuali correnti, ma non il DDL già coperto dalle regole deterministiche”

richiede oggi lavoro preparatorio esterno.

## Per automazione e pipeline: accettabile

Per uno script controllato è invece ragionevole:

````
Bash


```
dsl-manager ai package ... --revision ...
```
````

offre una selezione deterministica e il profilo versiona le opzioni del package.

Quindi direi:

| Scenario | Valutazione |
| --- | --- |
| Uno o due file noti | Sufficiente |
| Pipeline automatizzata | Buono come primitiva |
| Corpus medio/grande | Macchinoso |
| Selezione esplorativa | Insufficiente |
| Policy ripetibile basata su semantica/provenienza | Insufficiente |
| Utente non tecnico | Poco utilizzabile |

---

# 1.6 Il problema non è solo ergonomico

Una procedura apposita non servirebbe soltanto ad abbreviare i comandi.

Oggi una selezione manuale implica che la logica risieda nella testa dell’operatore:

```
Ho scelto queste revisioni perché erano manuali
e ho escluso queste altre perché erano DDL.
```

Il package registra quali evidenze contiene, ma non necessariamente una **policy dichiarativa completa che spieghi perché quelle evidenze sono state selezionate**.

Per una pipeline auditabile sarebbe preferibile registrare qualcosa come:

````
JSON


```
{
  "selection_policy_id": "business_interpretation_v1",
  "selection_policy_version": "1",
  "criteria": {
    "source_types": ["legacy_document", "xml_form"],
    "evidence_kinds": ["chunk", "fragment"],
    "exclude_parser_kinds": ["ddl"],
    "deterministic_coverage": "exclude_fully_covered"
  }
}
```
````

Così si potrebbe riprodurre non solo il package, ma anche la **decisione con cui è stato composto**.

Perciò sì: il programma beneficerebbe di una procedura apposita.

---

# 2. È ipotizzabile una slice 30?

## Tecnicamente sì, ma non dentro la v02 senza modificarla

Una slice dedicata sarebbe sensata. Tuttavia il documento v02 dice esplicitamente:

> il lavoro è suddiviso **esattamente** nelle slice 20–29 e non sono previste slice ulteriori. {line\_range\_start=8 line\_range\_end=22 path=.kb/documenti/documenti di design/run 2/design\_document\_v\_02.md git\_url="https://github.com/DanieleBarbiero/dsl\_manager-v1/blob/main/.kb/documenti/documenti di design/run 2/design\_document\_v\_02.md#L8-L22"}

Inoltre la roadmap dichiara che la slice 29 chiude l’intero percorso. {line\_range\_start=776 line\_range\_end=790 path=.kb/documenti/documenti di design/run 2/design\_document\_v\_02.md git\_url="https://github.com/DanieleBarbiero/dsl\_manager-v1/blob/main/.kb/documenti/documenti di design/run 2/design\_document\_v\_02.md#L776-L790"}

Quindi un prompt di implementazione intitolato direttamente:

```
Implementa slice 30
```

sarebbe in conflitto con la specifica vincolante che i prompt devono implementare.

Non consiglierei di ignorare silenziosamente il conflitto.

---

# 2.1 Prima va aggiornata la specifica, poi scritto il prompt di implementazione

La sequenza corretta sarebbe:

```
1. richiesta di modifica del design
2. revisione/approvazione del design
3. generazione del prompt della nuova slice
4. implementazione della slice
```

Non:

```
1. inventare direttamente la slice 30
2. implementarla
3. correggere il design a posteriori
```

Questo repository usa il documento di design come specifica implementativa vincolante. La slice deve quindi discendere dal contratto, non sostituirlo implicitamente.

---

# 2.2 Modificare v02 oppure creare v03?

La mia raccomandazione è:

## Preferibile: creare `design_document_v_03.md`

Dato che v02:

- contiene una roadmap chiusa;
- stabilisce esplicitamente che non esistono slice successive;
- incorpora già i prompt delle slice 20–29;
- verrà usato come base di implementazione;

aggiungere retroattivamente una slice 30 rischierebbe di rendere meno chiaro che cosa fosse stato originariamente approvato.

Una v03 potrebbe dichiarare:

```
Baseline: design v02 + implementazione slice 20–29
Scopo: selezione e governance delle evidenze destinate all’AI
Roadmap: slice 30
```

Questo preserva la storia:

```
v02 → chiusura del ciclo di governo e temporalità
v03 → estensione del handoff AI
```

## Alternativa: emendamento formale della v02

Se le slice 20–29 non sono ancora state generate o eseguite e si vuole deliberatamente cambiare il piano prima dell’avvio, è anche possibile emendare v02.

In quel caso bisognerebbe aggiornare almeno:

- la sintesi, eliminando “esattamente 20–29”;
- la matrice delle slice;
- l’indice, se vengono aggiunte sezioni;
- la roadmap;
- i criteri globali;
- la tracciabilità;
- i test e fixture;
- la sezione dei prompt;
- la dichiarazione che la slice 29 chiude tutto.

Non basterebbe appendere in fondo un “Prompt Slice 30”, perché il documento rimarrebbe internamente contraddittorio.

### Scelta raccomandata

| Stato del lavoro | Scelta |
| --- | --- |
| Slice 20–29 non ancora avviate e v02 ancora modificabile | Emendamento v02 possibile |
| Prompt 20–29 già consolidati o distribuiti | Meglio v03 |
| Implementazione 20–29 già iniziata | Decisamente v03 |
| Estensione considerata opzionale | V03 separata |

Nel vostro caso, dato che state proprio per generare i prompt ma v02 è già una proposta vincolante e auto-verificata, **preferirei comunque una v03 breve e focalizzata**, oppure un documento di design supplementare esplicitamente dipendente da v02.

---

# 2.3 Consiglierei un prompt per modificare il design?

**Sì.** Non consiglierei ancora un prompt d’implementazione.

Il primo prompt dovrebbe chiedere di produrre una revisione progettuale, per esempio:

> Analizza il contratto AI package esistente e progetta una selezione dichiarativa, deterministica e auditabile delle evidenze eleggibili per l’AI. Produci `design_document_v_03.md` e il relativo report. Non modificare il codice applicativo. Definisci CLI, configurazione, modello dati, canonicalizzazione, report, compatibilità, sicurezza, test, migrazione e prompt della slice 30.

Questo consente di chiarire prima alcune decisioni non banali.

---

# 2.4 Che cosa dovrebbe progettare la slice 30?

Una buona slice 30 non dovrebbe limitarsi ad aggiungere dieci flag CLI. Dovrebbe introdurre un concetto esplicito di:

```
AI evidence selection
```

o:

```
AI eligibility policy
```

## A. Una procedura di anteprima

Per esempio:

````
Bash


```
dsl-manager ai evidence plan <workspace> \
  --policy business_interpretation
```
````

Output:

```
Eligible revisions: 12
Eligible chunks: 184
Eligible fragments: 37
Excluded fragments: 96

Reasons:
  included_source_type:             151
  included_interpretive_evidence:    70
  excluded_deterministic_covered:    62
  excluded_parser_kind:              21
  excluded_stale:                    13
```

Questa procedura non dovrebbe ancora creare il package: dovrebbe permettere di vedere e comprendere la selezione.

## B. Una procedura di ispezione

````
Bash


```
dsl-manager ai evidence list <workspace> \
  --policy business_interpretation \
  --outcome included
```
````

oppure:

````
Bash


```
dsl-manager ai evidence explain <workspace> FRAG_000042
```
````

Output:

```
FRAG_000042
Outcome: excluded
Reason: deterministic_coverage_complete
Matched rule: ddl_table_fact/1
Policy: business_interpretation/1
```

## C. Costruzione del package dalla selezione

````
Bash


```
dsl-manager ai package <workspace> \
  --selection-policy business_interpretation
```
````

Il package dovrebbe registrare:

- ID e versione della policy;
- configurazione risolta;
- criteri;
- evidenze incluse;
- evidenze escluse;
- motivazione per ciascuna inclusione/esclusione;
- hash semantico del piano di selezione.

---

# 2.5 Criteri che avrebbe senso supportare

## Criteri sulla fonte

```
source_type
source_subtype
extension
authority_level
current revision only
```

## Criteri sull’evidenza

```
chunk | fragment
fragment_type
parser_kind
parser_version
has_complete_locator
active/stale
```

## Criteri sulla copertura deterministica

```
nessuna regola applicabile
regola applicabile ma evidenza insufficiente
candidato deterministico prodotto
candidato deterministico pending
candidato deterministico confirmed
copertura completa o parziale
```

## Criteri sull’obiettivo

Per esempio:

```
technical_extraction
domain_interpretation
mapping_discovery
conflict_analysis
question_generation
temporal_interpretation
```

Questo punto è particolarmente importante. L’eleggibilità per l’AI non è una proprietà assoluta dell’evidenza:

```
FRAG_000001 è AI-eligible: sì/no
```

Dipende dall’attività:

```
FRAG_000001
├── per technical_extraction: no, già coperto
├── per domain_mapping: sì
└── per temporal_interpretation: forse no
```

---

# 2.6 Attenzione a “non prodotto da parser specializzati”

Non userei questo criterio come regola principale.

I chunk documentali non sono necessariamente più adatti all’AI dei frammenti tecnici. Un frammento prodotto da un parser può contenere informazioni utili per attività interpretative.

Esempio:

```
parser DDL:
  tabella CLI_MSTR
```

La copertura tecnica è completa:

```
database_table = CLI_MSTR
```

Ma rimane aperta una domanda interpretativa:

```
CLI_MSTR rappresenta l’entità di dominio Cliente?
```

Quindi la policy dovrebbe distinguere:

```
evidenza già coperta tecnicamente
```

da:

```
evidenza priva di qualsiasi possibile valore interpretativo
```

La seconda conclusione è molto più difficile e spesso falsa.

Suggerirei criteri positivi come:

```
includi frammenti tecnici per domain_mapping
escludili per technical_extraction se già coperti
```

piuttosto che:

```
escludi sempre ciò che proviene da un parser
```

---

# 2.7 Il rischio della dipendenza dallo stato della review

Un filtro come:

```
includi soltanto evidenze che non hanno prodotto
candidati deterministici confirmed
```

è utile, ma introduce una conseguenza:

> il contenuto del package dipende dallo stato corrente del registry e della review.

Se oggi un candidato è `pending`, l’evidenza potrebbe entrare nel package. Domani, dopo la conferma, la stessa policy potrebbe escluderla.

Questo comportamento può essere corretto, ma deve essere esplicito e riproducibile. Il piano dovrebbe quindi registrare almeno:

- testa decisionale osservata;
- candidato deterministico osservato;
- versione delle regole;
- versione della policy di selezione;
- hash dello stato rilevante;
- momento logico o snapshot del piano.

Il ciclo v02 insiste sul fatto che solo le decisioni correnti positive rendono un candidato autoritativo e che `pending`, `rejected` e `superseded` non devono esserlo. {line\_range\_start=8 line\_range\_end=20 path=.kb/documenti/documenti di design/run 2/design\_document\_v\_02.md git\_url="https://github.com/DanieleBarbiero/dsl\_manager-v1/blob/main/.kb/documenti/documenti di design/run 2/design\_document\_v\_02.md#L8-L20"}

---

# Raccomandazione finale

## Nell’immediato

Userei le primitive esistenti così:

```
--revision
+
profili chunks_only / fragments_only / all
```

Sono sufficienti per prove controllate e corpus piccoli.

## Per un uso reale e ripetibile

Progetterei una nuova capacità dedicata:

```
plan → inspect/explain → package
```

con policy versionate, report di inclusione/esclusione e hash del piano.

## Per la documentazione

Non scriverei subito un prompt d’implementazione della slice 30.

Scriverei prima un **prompt di design** che produca preferibilmente:

```
design_document_v_03.md
```

oppure, se decidete esplicitamente che v02 non è ancora congelata, un suo emendamento completo e coerente.

Solo dopo l’approvazione di quel design genererei il prompt eseguibile della slice 30.

**Verifiche documentali**

- ✅ `rg -n "ai package|package-batch|revision-id|include_chunks|include_fragments" src/dsl_mngr/cli src/dsl_mngr/core/ai_package.py src/dsl_mngr/core/batch.py`
- ✅ `nl -ba src/dsl_mngr/cli/app.py | sed -n '180,330p'`
- ✅ `nl -ba src/dsl_mngr/core/config.py | sed -n '60,115p'`
- ✅ `nl -ba src/dsl_mngr/cli/commands/ai.py | sed -n '175,390p'`
- ✅ `nl -ba src/dsl_mngr/core/ai_package.py | sed -n '113,170p'`
- ✅ `nl -ba src/dsl_mngr/core/workspace.py | sed -n '123,134p'`
- ✅ `nl -ba '.kb/documenti/manuali/manuale_utente_dsl_manager.md' | sed -n '770,830p'`
- ✅ `nl -ba '.kb/documenti/documenti di design/run 2/design_document_v_02.md' | sed -n '8,25p'`
- ✅ `nl -ba '.kb/documenti/documenti di design/run 2/design_document_v_02.md' | sed -n '776,810p'`
- ✅ `git diff --stat && git status --short` — nessuna modifica effettuata.

verrà creato un prompt per produrre design\_document\_v3.md (fortunamente la procedura riguarda un punto secondario e separato della pipeline). proseguiamo sul percorso principale con lo step 5 (integrerò questo tutorial a v3 implementata).

Copy

Worked for 7m 18s

## Step 5 — Il merge autoritativo

Alla fine della review il registry contiene candidati in condizioni differenti:

```
CBATCH_000001
├── CAND_REC_000001 → confirmed
├── CAND_REC_000002 → pending
├── CAND_REC_000003 → rejected
├── CAND_REC_000004 → superseded
└── CAND_REC_000010 → confirmed, foglia di una correzione
```

Ora DSL Manager deve trasformare le proposte approvate in oggetti del modello autoritativo:

```
candidati confermati ed eleggibili
                  ↓
          merge autoritativo
                  ↓
             facts
             relations
      evidenze di supporto
```

Questo è il punto in cui una proposta smette di essere soltanto una proposta e viene **materializzata nel registry semantico**.

---

# 1. Il merge non riesamina il significato

La review rispondeva:

> “Approviamo questa proposta?”

Il merge risponde invece:

> “Come rappresentiamo nel registry questa proposta già approvata?”

Quindi il merge non dovrebbe:

- reinterpretare il documento;
- chiedere nuovamente all’AI;
- rivalutare liberamente la correttezza;
- modificare il significato del candidato;
- inventare nuovi concetti.

Il suo compito è più meccanico:

```
leggere candidato approvato
        ↓
normalizzare conservativamente
        ↓
trovare o creare fact/relation
        ↓
collegare il supporto
```

---

# 2. Prima di agire, il merge ricontrolla l’eleggibilità

Non basta che il candidato fosse `confirmed` quando il batch è stato preparato.

Il merge rilegge, nella propria transazione:

1. la testa decisionale corrente;
2. la posizione corrente nella linea di correzione.

Un candidato entra nel merge soltanto se è ancora:

```
foglia corrente
+
testa corrente confirmed
```

Questa verifica protegge da una situazione come:

```
10:00 candidato confermato
10:01 batch pianificato
10:02 candidato rifiutato o corretto
10:03 merge avviato
```

Alle 10:03 il merge non deve fidarsi della decisione osservata alle 10:01. Deve vedere lo stato corrente e saltare il candidato non più eleggibile.

La v02 stabilisce esplicitamente che solo la foglia confermata è merge-eligible e che il merge rilegge testa e foglia dentro la propria transazione. {line\_range\_start=120 line\_range\_end=133 path=.kb/documenti/documenti di design/run 2/design\_document\_v\_02.md git\_url="https://github.com/DanieleBarbiero/dsl\_manager-v1/blob/main/.kb/documenti/documenti di design/run 2/design\_document\_v\_02.md#L120-L133"}

---

# 3. Che cosa viene materializzato?

I candidati principali per il modello semantico sono:

```
candidate_fact     → fact
candidate_relation → relation
```

Gli altri record, come domande, mapping o segnalazioni di conflitto, possono essere conservati e governati, ma non diventano automaticamente fatti o relazioni.

Il modello preesistente distingue già:

- `facts`: proprietà o regole relative a entità;
- `relations`: collegamenti tra entità;
- `conflicts`: divergenze tra fatti incompatibili.

---

# 4. Materializzazione di un fatto

Prendiamo un candidato confermato:

```
CAND_REC_000001
├── fact_type: database_table
├── entity_name: CLIENTE
├── property_name: physical_name
├── property_value: CLIENTE
├── assertion_type: explicit
└── evidence: FRAG_000001
```

Il merge costruisce un’identità canonica del fatto.

Concettualmente:

```
nome entità       → cliente
nome proprietà    → physical_name
valore proprietà  → cliente
```

e calcola una chiave stabile basata sul contenuto semantico:

```
fact_identity =
  entity canonica
  + proprietà canonica
  + valore normalizzato
```

Se il fatto non esiste:

```
crea FACT_000001
```

Se esiste già:

```
riutilizza FACT_000001
```

L’implementazione precedente mostra già questo meccanismo: normalizza entità, proprietà e valore, calcola un hash d’identità, cerca un fatto esistente e lo crea soltanto se necessario.

---

# 5. Materializzazione di una relazione

Prendiamo:

```
CAND_REC_000002
├── source_entity: ORDINE
├── relation_type: references
├── target_entity: CLIENTE
└── evidence: FRAG_000007
```

Il merge produce o individua:

```
REL_000001
ORDINE ──references──→ CLIENTE
```

Anche qui l’identità viene costruita conservativamente da elementi canonici:

```
sorgente
+
tipo di relazione
+
destinazione
```

Due candidati semanticamente equivalenti non devono necessariamente generare due relazioni distinte.

---

# 6. Il merge separa l’oggetto dai suoi supporti

Questa è la parte più importante dello step.

Supponiamo che la stessa regola sia attestata da due documenti:

```
CAND_REC_000020
evidenza: manuale_operativo.pdf

CAND_REC_000031
evidenza: regolamento_clienti.docx
```

Entrambi propongono:

```
Cliente.deletion_constraint =
“vietata se esistono ordini aperti”
```

Il merge non deve necessariamente creare due fatti identici.

Crea o riutilizza un solo fatto:

```
FACT_000010
Cliente.deletion_constraint =
“vietata se esistono ordini aperti”
```

e gli collega due supporti:

```
FACT_000010
├── supporto A
│   ├── CAND_REC_000020
│   ├── REV_000005
│   └── CHK_000021
│
└── supporto B
    ├── CAND_REC_000031
    ├── REV_000008
    └── CHK_000044
```

Quindi:

```
fatto
≠
singola evidenza
```

Un fatto rappresenta il contenuto canonico; i supporti spiegano perché il sistema lo considera sostenuto.

Il merge preserva infatti i collegamenti a candidato, revisione, fonte, chunk o frammento ed evidence hash.

---

# 7. Perché i supporti multipli sono essenziali?

Immaginiamo che il supporto A venga successivamente rifiutato o superato:

```
CAND_REC_000020 → rejected
```

Il supporto B rimane confermato:

```
CAND_REC_000031 → confirmed
```

Il fatto continua a essere effettivo:

```
FACT_000010
├── supporto A → non più positivo
└── supporto B → ancora positivo
```

La regola della v02 è:

> un fatto o una relazione resta effettivo finché possiede almeno un supporto positivo corrente. {line\_range\_start=128 line\_range\_end=133 path=.kb/documenti/documenti di design/run 2/design\_document\_v\_02.md git\_url="https://github.com/DanieleBarbiero/dsl\_manager-v1/blob/main/.kb/documenti/documenti di design/run 2/design\_document\_v\_02.md#L128-L133"}

Questo permette di revocare una singola giustificazione senza cancellare automaticamente una conclusione ancora sostenuta da altre fonti indipendenti.

---

# 8. “Materializzato” ed “effettivo” non sono sinonimi

Dopo il merge il database può contenere fisicamente:

```
FACT_000010
```

Ma la domanda importante per il DSL v2 non è soltanto:

> “Esiste una riga nella tabella `facts`?”

È:

> “Questo fatto possiede ancora almeno un supporto derivato da una foglia con testa corrente `confirmed`?”

La distinzione è:

```
materializzato
= esiste fisicamente nel registry

effettivo
= è ancora sostenuto da almeno una decisione positiva corrente
```

Le viste:

```
effective_fact_evidence
effective_relation_evidence
effective_facts
effective_relations
```

calcolano questa prospettiva corrente.

Le prime due selezionano soltanto i supporti provenienti da candidati che sono ancora foglie confermate; le seconde includono fatti e relazioni con almeno un supporto positivo. {line\_range\_start=203 line\_range\_end=207 path=.kb/documenti/documenti di design/run 2/design\_document\_v\_02.md git\_url="https://github.com/DanieleBarbiero/dsl\_manager-v1/blob/main/.kb/documenti/documenti di design/run 2/design\_document\_v\_02.md#L203-L207"}

---

# 9. Perché non cancellare subito gli oggetti non più sostenuti?

Perché il registry deve conservare storia e audit.

Supponiamo:

```
ieri:
CAND_A confirmed
        ↓
FACT_X materializzato ed effettivo

oggi:
CAND_A rejected
```

Cancellare fisicamente `FACT_X` renderebbe più difficile ricostruire:

- quando fu materializzato;
- da quale candidato;
- sulla base di quale evidenza;
- perché in seguito cessò di essere effettivo;
- quali snapshot storici lo contenevano.

La v02 preferisce quindi distinguere:

```
storia fisica conservata
+
vista effettiva corrente
```

È un modello simile a un registro contabile: non si cancella il passato; si registrano eventi successivi che cambiano lo stato corrente.

---

# 10. Un batch può contenere candidati misti

Un candidate batch può contenere:

```
confirmed
pending
rejected
superseded
non-leaf
```

Per impostazione predefinita, il merge:

- materializza soltanto gli eleggibili;
- salta gli altri;
- conta separatamente i motivi dello skip;
- considera l’operazione riuscita se almeno un candidato è stato unito e non ci sono errori.

Esempio:

```
CBATCH_000001
├── 4 merged
├── 2 skipped_pending
├── 1 skipped_rejected
├── 1 skipped_superseded
└── 1 skipped_non_leaf
```

Questi skip non diventano automaticamente errori dell’intero batch.

Se invece non esiste nessun candidato eleggibile:

```
no_merge_eligible_candidates
exit 4
nessuna mutazione
```

La modalità esplicita:

````
Bash


```
--strict-review
```
````

richiede invece che il batch non contenga alcun candidato da saltare; incontrarne uno provoca il rollback dell’intero tentativo. {line\_range\_start=191 line\_range\_end=201 path=.kb/documenti/documenti di design/run 2/design\_document\_v\_02.md git\_url="https://github.com/DanieleBarbiero/dsl\_manager-v1/blob/main/.kb/documenti/documenti di design/run 2/design\_document\_v\_02.md#L191-L201"}

---

# 11. Il merge è transazionale

Il merge autoritativo non dovrebbe lasciare il registry a metà.

Supponiamo che debba:

1. creare un fatto;
2. collegare un supporto;
3. creare una relazione;
4. aggiornare una riconciliazione.

Se un errore interrompe l’operazione dopo il punto 2, il sistema non deve fingere che il batch sia stato completato.

Il nucleo del merge opera quindi in una transazione:

```
BEGIN
  verifica eleggibilità corrente
  crea o riutilizza oggetti
  collega supporti
  aggiorna riconciliazioni
COMMIT
```

oppure:

```
ROLLBACK
```

L’implementazione pre-v02 già avvolge la materializzazione del batch in una transazione con rollback su errore; la v02 aggiunge a quel confine la verifica di review e lineage.

---

# 12. Il merge deve essere idempotente

Se il processo viene ripetuto dopo un crash o per prudenza:

````
Bash


```
dsl-manager facts merge <workspace> --batch CBATCH_000001
```
````

non deve creare copie ulteriori degli stessi fatti, relazioni o supporti.

Il risultato deve convergere:

```
prima esecuzione:
crea FACT_1 + supporto A

seconda esecuzione:
trova FACT_1 + supporto A già esistente

risultato finale:
sempre un solo FACT_1 e un solo supporto A
```

La v02 richiede che i replay convergano sugli stessi supporti grazie a chiavi e vincoli stabili. {line\_range\_start=191 line\_range\_end=201 path=.kb/documenti/documenti di design/run 2/design\_document\_v\_02.md git\_url="https://github.com/DanieleBarbiero/dsl\_manager-v1/blob/main/.kb/documenti/documenti di design/run 2/design\_document\_v\_02.md#L191-L201"}

---

# 13. Che cosa succede in presenza di valori incompatibili?

Immaginiamo due candidati confermati:

```
CAND_A:
Cliente.retention_period = 5 anni

CAND_B:
Cliente.retention_period = 10 anni
```

Le entità e le proprietà coincidono, ma i valori sono differenti.

Il merge non dovrebbe:

- scegliere arbitrariamente uno dei due;
- sostituire silenziosamente il primo;
- fondere i valori;
- chiedere all’AI di decidere.

Può materializzare entrambi i fatti e registrare un conflitto:

```
FACT_A: retention_period = 5 anni
FACT_B: retention_period = 10 anni

CONFLICT_1:
different_values_same_property
```

Il comportamento storico del programma già registra conflitti quando due fatti sulla stessa entità e proprietà hanno valori normalizzati diversi.

La presenza di due decisioni positive non dimostra che i valori siano conciliabili: dimostra che esistono due affermazioni approvate ma discordanti, e la discordanza deve rimanere visibile.

---

# 14. Il merge temporale segue lo stesso confine

Un candidato temporale confermato può essere:

```
CAND_TIME_000001
├── target: FACT_000010
├── start: 2025-01-01
├── end: 2025-12-31
├── precision: day
└── testa: confirmed
```

Il merge temporale materializza:

```
temporal_interval
└── target: FACT_000010
```

Solo l’intervallo risolto e confermato può raggiungere la rappresentazione autoritativa e, successivamente, DSL v2 e grafo dinamico.

Anche qui:

```
timestamp grezzo
≠
candidato temporale
≠
intervallo materializzato
```

La pipeline temporale prevede esplicitamente la materializzazione soltanto dalla foglia `confirmed`. {line\_range\_start=430 line\_range\_end=442 path=.kb/documenti/documenti di design/run 2/design\_document\_v\_02.md git\_url="https://github.com/DanieleBarbiero/dsl\_manager-v1/blob/main/.kb/documenti/documenti di design/run 2/design\_document\_v\_02.md#L430-L442"}

---

# 15. Che cos’è la riconciliazione?

La riconciliazione diventa necessaria quando la storia fisicamente materializzata e lo stato effettivo divergono.

Esempio:

```
1. CAND_A confirmed
2. merge → FACT_X materializzato
3. CAND_A viene corretto
4. CAND_A diventa superseded
5. CAND_B corretto diventa confirmed
```

Subito dopo il punto 4:

```
FACT_X esiste fisicamente
ma il suo vecchio supporto non è più effettivo
```

DSL Manager apre allora una voce persistente:

```
reconciliation_required
```

La riconciliazione serve a:

- materializzare l’eventuale sostituzione;
- disattivare o compensare il vecchio supporto;
- riportare lo stato fisico in coerenza con le decisioni correnti;
- chiudere la voce di riconciliazione.

La coda non è un semplice flag temporaneo in memoria: è persistita nel registry e sopravvive a crash e retry. {line\_range\_start=203 line\_range\_end=207 path=.kb/documenti/documenti di design/run 2/design\_document\_v\_02.md git\_url="https://github.com/DanieleBarbiero/dsl\_manager-v1/blob/main/.kb/documenti/documenti di design/run 2/design\_document\_v\_02.md#L203-L207"}

Finché rimane una riconciliazione aperta, render, diff ed export sono normalmente bloccati, per evitare di pubblicare un risultato ambiguo. {line\_range\_start=128 line\_range\_end=136 path=.kb/documenti/documenti di design/run 2/design\_document\_v\_02.md git\_url="https://github.com/DanieleBarbiero/dsl\_manager-v1/blob/main/.kb/documenti/documenti di design/run 2/design\_document\_v\_02.md#L128-L136"}

---

# Risultato dello step 5

Dopo il merge, possiamo avere:

```
FACT_000001
├── contenuto: database_table CLIENTE
└── supporti:
    └── CAND_REC_000001 / FRAG_000001 / confirmed

FACT_000002
├── contenuto: Cliente.deletion_constraint
└── supporti:
    ├── CAND_REC_000020 / CHK_000021 / confirmed
    └── CAND_REC_000031 / CHK_000044 / confirmed

REL_000001
├── contenuto: ORDINE references CLIENTE
└── supporti:
    └── CAND_REC_000002 / FRAG_000007 / confirmed

CAND_REC_000003
└── rejected: non materializzato

CAND_REC_000004
└── superseded: non materializzato
```

Le viste effettive vedono:

```
effective_facts
├── FACT_000001
└── FACT_000002

effective_relations
└── REL_000001
```

A questo punto DSL Manager possiede finalmente un **modello autoritativo corrente**, sostenuto da decisioni ed evidenze tracciabili.

## Formula mentale aggiornata

```
STEP 1: Quali byte abbiamo?
STEP 2: Che cosa è osservabile dentro quei byte?
STEP 3: Quali affermazioni possiamo proporre?
STEP 4: Quali proposte approviamo?
STEP 5: Come materializziamo le proposte approvate
        senza perdere prove e storia?
```

Il prossimo step sarà la costruzione dell’output:

```
effective_facts + effective_relations + intervalli
                         ↓
                      DSL v2
                         ↓
                  snapshot immutabile
```

Vedremo quindi la differenza fra:

- registry autoritativo;
- vista effettiva corrente;
- documento DSL;
- snapshot storico.

**Verifiche documentali**

- ✅ `nl -ba '.kb/documenti/documenti di design/run 2/design_document_v_02.md' | sed -n '105,160p'`
- ✅ `nl -ba '.kb/documenti/documenti di design/run 2/design_document_v_02.md' | sed -n '191,209p'`
- ✅ `nl -ba src/dsl_mngr/core/merge.py | sed -n '1,340p'`
- ✅ `nl -ba '.kb/documenti/manuali/manuale_utente_dsl_manager.md' | sed -n '174,214p'`
- ✅ `nl -ba '.kb/documenti/manuali/manuale_utente_dsl_manager.md' | sed -n '401,424p'`
- ✅ `git status --short` — nessun dato o file creato, modificato o cancellato.

splendido. procedi con lo step 6.

Copy

Worked for 2m 25s

## Step 6 — Dalla vista effettiva allo snapshot DSL

Alla fine dello step 5 il registry contiene:

- fatti;
- relazioni;
- supporti probatori;
- decisioni;
- conflitti;
- eventuali intervalli temporali.

Ma il registry è ancora un insieme di tabelle operative e storiche. Non è il documento finale destinato a descrivere il sistema.

Il passaggio successivo è:

```
registry completo
      ↓
viste effettive
      ↓
renderer DSL
      ↓
snapshot DSL immutabile
```

La parola centrale di questo step è **snapshot**.

---

# 1. Registry e DSL non sono la stessa cosa

Il registry conserva tutto ciò che serve per governare il processo:

```
fonti
revisioni
evidenze
candidati
decisioni
correzioni
fatti
relazioni
supporti
conflitti
riconciliazioni
run
snapshot precedenti
```

Il DSL, invece, è una **proiezione organizzata della conoscenza effettiva**.

Possiamo visualizzare la differenza così:

```
REGISTRY
“Conserva il processo, la storia e le prove”

             ↓ selezione + proiezione

DSL
“Descrive il modello risultante in una forma stabile”
```

Quindi il DSL non sostituisce il database e non è la sorgente primaria di verità. È un prodotto derivato e riproducibile del registry.

---

# 2. Prima di renderizzare, si seleziona lo stato effettivo

Il renderer v2 non legge indiscriminatamente tutte le righe fisicamente presenti nelle tabelle `facts` e `relations`.

Legge:

```
effective_facts
effective_relations
```

cioè gli oggetti che possiedono ancora almeno un supporto derivato da:

```
candidato foglia
+
testa corrente confirmed
```

Esempio:

```
FACT_A
└── un supporto confirmed
    → incluso

FACT_B
├── supporto 1 superseded
└── supporto 2 confirmed
    → incluso

FACT_C
└── unico supporto rejected
    → escluso

FACT_D
└── unico supporto pending
    → escluso
```

Questo rende il DSL v2 una fotografia delle decisioni correnti, non dell’intera storia fisica del database.

Il design stabilisce che DSL v2, diff v2 ed export dinamici usino le viste effettive. {line\_range\_start=203 line\_range\_end=207 path=.kb/documenti/documenti di design/run 2/design\_document\_v\_02.md git\_url="https://github.com/DanieleBarbiero/dsl\_manager-v1/blob/main/.kb/documenti/documenti di design/run 2/design\_document\_v\_02.md#L203-L207"}

---

# 3. Il controllo delle riconciliazioni

Prima di produrre l’output, DSL Manager controlla se esistono riconciliazioni aperte.

Una riconciliazione aperta indica:

> “Le decisioni correnti sono cambiate, ma il processo di riallineamento della materializzazione non è ancora terminato.”

In tale situazione potrebbero coesistere:

```
stato fisico precedente
+
vista effettiva aggiornata
+
sostituzione non ancora completamente materializzata
```

Per impostazione predefinita, il renderer si ferma:

```
reconciliation_required
```

Questo comportamento evita di emettere uno snapshot formalmente completo durante una transizione incompleta. Render, diff ed export sono bloccati per default quando esistono riconciliazioni aperte. {line\_range\_start=128 line\_range\_end=136 path=.kb/documenti/documenti di design/run 2/design\_document\_v\_02.md git\_url="https://github.com/DanieleBarbiero/dsl\_manager-v1/blob/main/.kb/documenti/documenti di design/run 2/design\_document\_v\_02.md#L128-L136"}

---

# 4. Che cos’è concretamente il DSL?

Nel progetto, il DSL è un documento strutturato che organizza il modello in elementi come:

```
metadata
entities
facts
relations
conflicts
traceability
```

Un esempio concettuale molto semplificato potrebbe essere:

````
JSON


```
{
  "metadata": {
    "schema_version": "2"
  },
  "entities": [
    {
      "name": "Cliente",
      "facts": [
        {
          "fact_id": "FACT_000001",
          "type": "database_table",
          "property": "physical_name",
          "value": "CLIENTE",
          "intervals": []
        }
      ]
    },
    {
      "name": "Ordine",
      "facts": []
    }
  ],
  "relations": [
    {
      "relation_id": "REL_000001",
      "source": "Ordine",
      "type": "references",
      "target": "Cliente",
      "intervals": []
    }
  ],
  "conflicts": [],
  "traceability": {
    "facts": {},
    "relations": {}
  }
}
```
````

Il renderer preesistente già organizza il documento in entità, fatti, relazioni, conflitti e tracciabilità; il Markdown, per esempio, contiene sezioni distinte per questi elementi.

La v02 modifica però la sorgente logica del rendering: lo schema v2 usa soltanto lo stato effettivo e la temporalità risolta.

---

# 5. Il comando di rendering

Il comando previsto è:

````
Bash


```
dsl-manager dsl render <workspace> --schema-version 2
```
````

Il default rimane lo schema 1 per compatibilità:

````
Bash


```
dsl-manager dsl render <workspace>
```
````

equivale concettualmente a:

````
Bash


```
dsl-manager dsl render <workspace> --schema-version 1
```
````

La scelta esplicita della v2 è quindi importante durante la transizione.

Il documento v2 deve dichiarare esattamente:

````
JSON


```
{
  "metadata": {
    "schema_version": "2"
  }
}
```
````

Il contratto del comando e del campo `schema_version` è definito dal design. {line\_range\_start=461 line\_range\_end=467 path=.kb/documenti/documenti di design/run 2/design\_document\_v\_02.md git\_url="https://github.com/DanieleBarbiero/dsl\_manager-v1/blob/main/.kb/documenti/documenti di design/run 2/design\_document\_v\_02.md#L461-L467"}

---

# 6. Che cosa cambia fra DSL v1 e DSL v2?

## DSL v1

Lo schema 1 viene mantenuto per compatibilità con:

- output precedenti;
- snapshot storici;
- GEXF statico;
- strumenti che conoscono soltanto il vecchio formato.

Continua a seguire la semantica fisica legacy prevista dal contratto esistente.

## DSL v2

Lo schema 2 introduce principalmente:

1. uso delle viste effettive;
2. governance delle decisioni correnti;
3. supporti semanticamente hashati;
4. temporalità esplicita;
5. compatibilità con GEXF dinamico.

In sintesi:

```
DSL v1
≈ rappresentazione legacy dello stato materializzato

DSL v2
≈ rappresentazione governata dello stato effettivo corrente
```

---

# 7. La temporalità nel DSL v2

Ogni fatto e ogni relazione possiede sempre:

````
JSON


```
"intervals": []
```
````

anche quando non esiste alcuna informazione temporale.

Per esempio:

````
JSON


```
{
  "fact_id": "FACT_000001",
  "property": "physical_name",
  "value": "CLIENTE",
  "intervals": []
}
```
````

Se esiste un intervallo confermato e materializzato:

````
JSON


```
{
  "fact_id": "FACT_000010",
  "property": "deletion_constraint",
  "value": "vietata con ordini aperti",
  "intervals": [
    {
      "start": "2025-01-01",
      "end": "2025-12-31",
      "original_precision": "day",
      "bounds_semantics": "inclusive"
    }
  ]
}
```
````

Il fatto che `intervals` sia sempre presente evita un’ambiguità:

```
campo assente
```

potrebbe significare:

- il renderer non supporta la temporalità;
- il dato non è stato calcolato;
- non esistono intervalli;
- si è verificato un errore.

Con:

````
JSON


```
"intervals": []
```
````

il significato è esplicito:

> lo schema supporta gli intervalli, ma per questo oggetto non ne è presente nessuno.

La v02 prescrive che ogni fatto e relazione abbia la collezione `intervals`, anche vuota. Dopo il consolidamento temporale, la collezione può contenere più intervalli ordinati canonicamente. {line\_range\_start=463 line\_range\_end=467 path=.kb/documenti/documenti di design/run 2/design\_document\_v\_02.md git\_url="https://github.com/DanieleBarbiero/dsl\_manager-v1/blob/main/.kb/documenti/documenti di design/run 2/design\_document\_v\_02.md#L463-L467"}

---

# 8. Profilo temporale globale

Nei metadata, DSL v2 dichiara come interpretare le date dell’intero documento.

Per esempio:

````
JSON


```
{
  "metadata": {
    "schema_version": "2",
    "temporal": {
      "representation": "interval",
      "base": "day",
      "gexf_timeformat": "date",
      "timezone": "unknown"
    }
  }
}
```
````

Oppure, con timestamp:

````
JSON


```
{
  "metadata": {
    "temporal": {
      "representation": "interval",
      "base": "timestamp",
      "gexf_timeformat": "dateTime",
      "timezone": "Europe/Rome"
    }
  }
}
```
````

I vincoli sono:

```
base day       ↔ GEXF date
base timestamp ↔ GEXF dateTime
```

Non si devono mescolare o convertire silenziosamente i due modelli.

Il contratto temporale del DSL v2 definisce rappresentazione a intervalli, base, `gexf_timeformat` e timezone esplicita oppure `unknown`. {line\_range\_start=463 line\_range\_end=467 path=.kb/documenti/documenti di design/run 2/design\_document\_v\_02.md git\_url="https://github.com/DanieleBarbiero/dsl\_manager-v1/blob/main/.kb/documenti/documenti di design/run 2/design\_document\_v\_02.md#L463-L467"}

---

# 9. La tracciabilità rimane nell’output

Il DSL non dovrebbe contenere soltanto:

```
Cliente.deletion_constraint =
“vietata con ordini aperti”
```

Dovrebbe permettere di risalire a:

```
FACT_000010
   ↓
supporto effettivo
   ↓
CAND_REC_000020
   ↓
decisione confirmed
   ↓
CHK_000021
   ↓
REV_000005
   ↓
manuale_operativo.pdf
```

Per ogni supporto effettivo, il DSL v2 include nel proprio contenuto autoritativo almeno gli elementi di governance rilevanti:

- hash semantico;
- outcome della testa corrente;
- eventuali `policy_id` e `policy_version`;
- eventuale contenuto corretto.

Non include invece nel proprio hash semantico informazioni operative prive di significato, come:

- ID della run;
- timestamp operativi;
- percorsi assoluti;
- retry;
- note puramente di audit.

Questa separazione è specificata nel contratto degli hash autoritativi. {line\_range\_start=330 line\_range\_end=338 path=.kb/documenti/documenti di design/run 2/design\_document\_v\_02.md git\_url="https://github.com/DanieleBarbiero/dsl\_manager-v1/blob/main/.kb/documenti/documenti di design/run 2/design\_document\_v\_02.md#L330-L338"}

---

# 10. Ordinamento e canonicalizzazione

Un DSL riproducibile deve essere indipendente da dettagli accidentali come:

- ordine di restituzione delle query SQLite;
- ordine di inserimento;
- macchina su cui viene eseguito;
- composizione Unicode equivalente;
- formattazione JSON;
- spazi superflui.

Per questo gli elementi vengono ordinati secondo regole stabili e serializzati con una rappresentazione JSON canonica.

Il profilo condiviso prevede, fra l’altro:

- UTF-8;
- normalizzazione Unicode NFC;
- chiavi degli oggetti ordinate;
- nessuno spazio o indentazione nei byte canonici;
- distinzione fra campo assente e `null`;
- numeri canonici;
- ordine semantico delle liste;
- ordinamento esplicito degli insiemi. {line\_range\_start=311 line\_range\_end=328 path=.kb/documenti/documenti di design/run 2/design\_document\_v\_02.md git\_url="https://github.com/DanieleBarbiero/dsl\_manager-v1/blob/main/.kb/documenti/documenti di design/run 2/design\_document\_v\_02.md#L311-L328"}

Il principio è:

```
stesso stato effettivo
        ↓
stesso contenuto canonico
        ↓
stesso hash DSL
```

---

# 11. Registry hash e DSL hash

Il renderer produce almeno due impronte concettualmente differenti.

## Registry hash

Rappresenta lo stato autoritativo rilevante letto dal registry:

```
effective facts
+
effective relations
+
supporti effettivi
+
decisioni semanticamente rilevanti
+
temporalità risolta
```

## DSL hash

Rappresenta il documento DSL canonico risultante.

Possiamo visualizzarlo così:

```
registry effettivo
      ↓ canonicalizzazione
registry_hash
      ↓ rendering DSL
documento canonico
      ↓ hash
dsl_hash
```

Questi hash permettono di verificare:

- che lo snapshot corrisponda allo stato da cui è stato prodotto;
- che due rendering equivalenti abbiano contenuto equivalente;
- che un file non sia stato modificato silenziosamente;
- che diff ed export facciano riferimento allo snapshot corretto.

Il renderer esistente già costruisce una vista del registry, ne calcola l’hash, genera il contenuto DSL e calcola un secondo hash sul documento.

---

# 12. Lo snapshot viene persistito

Il risultato non è soltanto un file temporaneo.

DSL Manager assegna un’identità allo snapshot:

```
DSL_000001
```

e registra:

- `snapshot_id`;
- `dsl_hash`;
- `registry_hash`;
- contenuto JSON;
- percorsi degli output;
- conteggi;
- stato;
- run associata.

Il comportamento esistente registra già questi elementi nella tabella `dsl_snapshots`.

La v02 aggiunge una precauzione importante:

```
scrivi snapshot v2
      ↓
rileggilo
      ↓
verifica che sia coerente
      ↓
solo allora dichiara successo
```

Il renderer deve persistere e rileggere lo snapshot prima di confermare il completamento. {line\_range\_start=463 line\_range\_end=467 path=.kb/documenti/documenti di design/run 2/design\_document\_v\_02.md git\_url="https://github.com/DanieleBarbiero/dsl\_manager-v1/blob/main/.kb/documenti/documenti di design/run 2/design\_document\_v\_02.md#L463-L467"}

---

# 13. Perché lo snapshot è immutabile?

Supponiamo di produrre:

```
DSL_000001
```

Poi, il giorno seguente:

- viene aggiunta una fonte;
- un candidato viene corretto;
- un fatto perde l’ultimo supporto positivo;
- una relazione temporale viene confermata.

Il sistema non riscrive `DSL_000001`.

Produce:

```
DSL_000002
```

La storia diventa:

```
DSL_000001 → fotografia dello stato al momento A
DSL_000002 → fotografia dello stato al momento B
```

Questo è indispensabile per:

- audit;
- confronto;
- rollback conoscitivo;
- riproducibilità;
- tracciamento dell’evoluzione;
- modernizzazione progressiva.

Il design stabilisce come invariante che snapshot ed export già registrati non cambiano. {line\_range\_start=128 line\_range\_end=137 path=.kb/documenti/documenti di design/run 2/design\_document\_v\_02.md git\_url="https://github.com/DanieleBarbiero/dsl\_manager-v1/blob/main/.kb/documenti/documenti di design/run 2/design\_document\_v\_02.md#L128-L137"}

---

# 14. Formati prodotti

Il renderer può produrre più rappresentazioni dello stesso snapshot:

```
exports/dsl/
├── DSL_000001.json
├── DSL_000001.yaml
└── DSL_000001.md
```

## JSON

È il formato principale:

- strutturato;
- validabile;
- destinato ad automazione e interoperabilità;
- base canonica del contenuto.

## YAML

È una proiezione più leggibile, utile per operatori e configurazioni.

## Markdown

È una vista documentale, adatta alla lettura umana.

Il manuale chiarisce che JSON è il formato principale, mentre YAML e Markdown sono viste di supporto.

Questi file non rappresentano tre snapshot diversi: sono tre rappresentazioni dello stesso snapshot logico.

---

# 15. Modalità incompleta

Normalmente, con una riconciliazione aperta, il renderer si blocca.

DSL v2 offre però un’eccezione esplicita:

````
Bash


```
dsl-manager dsl render <workspace> \
  --schema-version 2 \
  --allow-incomplete
```
````

In questo caso il renderer:

- omette gli oggetti che non sono più effettivi;
- produce warning;
- riporta conteggi delle omissioni;
- marca chiaramente l’output come incompleto.

Non deve fingere che si tratti di uno snapshot ordinario e completo.

La modalità non è permessa per DSL v1: `--allow-incomplete` è una capacità esclusiva dello schema v2. {line\_range\_start=128 line\_range\_end=136 path=.kb/documenti/documenti di design/run 2/design\_document\_v\_02.md git\_url="https://github.com/DanieleBarbiero/dsl\_manager-v1/blob/main/.kb/documenti/documenti di design/run 2/design\_document\_v\_02.md#L128-L136"}

Il significato è:

```
default:
“non pubblico finché lo stato non è riconciliato”

allow-incomplete:
“pubblico consapevolmente una proiezione parziale,
 dichiarando omissioni e avvertimenti”
```

---

# Risultato dello step 6

Alla fine possiamo avere:

```
Registry
├── storia completa
├── evidenze
├── candidati
├── decisioni
├── fatti e relazioni materializzati
└── viste effettive

                 ↓ render

DSL_000001
├── metadata schema 2
├── profilo temporale
├── entità e fatti effettivi
├── relazioni effettive
├── intervalli confermati
├── conflitti
├── tracciabilità
├── registry_hash
└── dsl_hash
```

Ora disponiamo di una fotografia:

- deterministica;
- verificabile;
- tracciabile;
- governata;
- temporalmente esplicita;
- immutabile.

## Formula mentale aggiornata

```
STEP 1: Quali byte abbiamo?
STEP 2: Che cosa è osservabile dentro quei byte?
STEP 3: Quali affermazioni possiamo proporre?
STEP 4: Quali proposte approviamo?
STEP 5: Come materializziamo le proposte approvate?
STEP 6: Come fotografiamo lo stato effettivo
        in un documento stabile e riproducibile?
```

Il prossimo step naturale sarà il confronto fra snapshot:

```
DSL_000001
     ↕ diff
DSL_000002
```

Vedremo come DSL Manager distingue cambiamenti:

- strutturali;
- di governance;
- temporali.

**Verifiche documentali**

- ✅ `nl -ba '.kb/documenti/documenti di design/run 2/design_document_v_02.md' | sed -n '311,340p'`
- ✅ `nl -ba '.kb/documenti/documenti di design/run 2/design_document_v_02.md' | sed -n '461,488p'`
- ✅ `nl -ba src/dsl_mngr/core/dsl_renderer.py | sed -n '1,360p'`
- ✅ `nl -ba '.kb/documenti/manuali/manuale_utente_dsl_manager.md' | sed -n '424,515p'`
- ✅ `git status --short` — nessun dato o file creato, modificato o cancellato.

procedi pure allo step 7.

Copy

Worked for 2m 35s

## Step 7 — Confrontare due snapshot: il DSL diff

Alla fine dello step 6 abbiamo una successione di fotografie immutabili:

```
DSL_000001 → stato del sistema al momento A
DSL_000002 → stato del sistema al momento B
DSL_000003 → stato del sistema al momento C
```

Ora vogliamo rispondere a una nuova domanda:

> **Che cosa è cambiato tra due fotografie del modello, e perché?**

Il passaggio è:

```
DSL_000001
     │
     ├── confronto semantico
     │
DSL_000002
     ↓
diff strutturato e tracciabile
```

La parola importante dello step è **cambiamento spiegabile**.

---

# 1. Il diff confronta snapshot, non il filesystem

DSL Manager non si limita a confrontare testualmente due file JSON riga per riga.

Un confronto testuale potrebbe segnalare differenze irrilevanti:

- ordinamento;
- spazi;
- formattazione;
- ID operativi;
- timestamp;
- disposizione delle chiavi.

Il DSL diff confronta invece i contenuti semantici degli snapshot:

```
entità
fatti
relazioni
conflitti
governance
intervalli temporali
```

Il comando virtuale è:

````
Bash


```
dsl-manager dsl diff <workspace> \
  --from DSL_000001 \
  --to DSL_000002
```
````

Il flusso esistente produce sia una rappresentazione JSON sia una vista Markdown del confronto.

---

# 2. Prima il comando verifica gli snapshot

Il diff non considera affidabile qualunque JSON che dichiari di essere un DSL.

Per ciascuno snapshot controlla almeno:

- esistenza nel registry;
- validità del contenuto JSON;
- presenza dei metadata;
- coerenza tra `metadata.dsl_hash` e l’hash registrato;
- presenza delle sezioni previste;
- presenza della tracciabilità.

Il diff preesistente controlla, per esempio, che l’hash nei metadata coincida con quello registrato e che `entities`, `relations`, `conflicts` e `traceability` abbiano la struttura richiesta.

Quindi il confronto parte da due fotografie registrate e verificabili:

```
snapshot A valido
+
snapshot B valido
        ↓
confronto
```

---

# 3. Primo caso: nessun cambiamento semantico

Supponiamo di renderizzare due volte senza modificare lo stato effettivo:

```
DSL_000001
DSL_000002
```

Gli ID degli snapshot sono differenti perché si tratta di due emissioni distinte, ma possono avere:

```
stesso registry_hash
stesso dsl_hash
```

Il risultato sarà:

```
Changes: 0
Added: 0
Removed: 0
Modified: 0
```

Il manuale specifica che due rendering dello stesso registry producono snapshot con ID diversi ma con lo stesso `dsl_hash` e `registry_hash`.

Questo consente di distinguere:

```
nuova esecuzione
```

da:

```
nuovo stato semantico
```

---

# 4. Le tre operazioni fondamentali

Ogni cambiamento viene classificato innanzitutto come:

```
added
removed
modified
```

## Added

Un oggetto non era presente nello snapshot precedente ed è presente in quello successivo:

```
prima: assente
dopo: presente
```

## Removed

Un oggetto era effettivo prima e non lo è più dopo:

```
prima: presente
dopo: assente
```

## Modified

L’oggetto concettuale continua a esistere, ma cambia qualche proprietà confrontabile:

```
prima: valore A
dopo: valore B
```

Il diff registra conteggi complessivi e per categoria. Il renderer Markdown preesistente produce già un riepilogo distinto per entità, fatti, relazioni e conflitti.

---

# 5. Cambiamenti strutturali

I cambiamenti strutturali riguardano ciò che il DSL afferma sul sistema.

Esempi:

## Nuova entità

```
DSL_000001:
Cliente
Ordine

DSL_000002:
Cliente
Ordine
Pagamento
```

Diff:

```
added_entity: Pagamento
```

## Nuovo fatto

```
prima:
Cliente.physical_table = CLIENTE

dopo:
Cliente.physical_table = CLIENTE
Cliente.retention_period = 10 anni
```

Diff:

```
added_fact:
Cliente.retention_period = 10 anni
```

## Fatto rimosso

```
prima:
Cliente.legacy_code = CLI

dopo:
il fatto non è più effettivo
```

Diff:

```
removed_fact:
Cliente.legacy_code = CLI
```

## Relazione aggiunta

```
added_relation:
Ordine references Cliente
```

## Relazione rimossa

```
removed_relation:
Cliente uses IndirizzoLegacy
```

## Conflitto comparso

```
added_conflict:
Cliente.retention_period
5 anni vs 10 anni
```

Il diff esistente possiede già categorie ordinate per entità, fatti, relazioni e conflitti aggiunti, rimossi o modificati.

---

# 6. Una modifica non è sempre rappresentata come `modified`

Questo aspetto richiede attenzione.

Supponiamo che l’identità canonica di un fatto includa anche il suo valore:

```
Cliente.retention_period = 5 anni
```

e che venga corretto in:

```
Cliente.retention_period = 10 anni
```

A seconda del contratto di identità, il diff può rappresentarlo come:

```
removed:
Cliente.retention_period = 5 anni

added:
Cliente.retention_period = 10 anni
```

oppure come:

```
modified:
Cliente.retention_period
before = 5 anni
after  = 10 anni
```

La scelta dipende da quali campi definiscono l’identità dell’oggetto e quali vengono considerati attributi modificabili.

L’importante è che il diff sia:

- deterministico;
- coerente;
- documentato;
- non dipendente dalla somiglianza testuale;
- capace di mostrare `before` e `after`.

Il diff preesistente costruisce percorsi semantici, confronta insiemi ordinati di fatti e produce valori `before` e `after`, anziché confrontare semplicemente le righe dei file.

---

# 7. Cambiamenti di governance

Con DSL v2 può cambiare non soltanto il fatto, ma anche il modo in cui viene sostenuto.

Consideriamo:

```
DSL_000001
FACT_X
└── supporto A, confirmed da reviewer_anna
```

Successivamente viene aggiunto un secondo supporto:

```
DSL_000002
FACT_X
├── supporto A, confirmed da reviewer_anna
└── supporto B, confirmed da policy ddl_explicit/1
```

Il contenuto principale del fatto può essere identico:

```
FACT_X non è stato aggiunto, rimosso o modificato
```

ma è cambiata la sua governance:

```
nuovo supporto
nuova decisione corrente
nuova policy
nuovo hash semantico del supporto
```

Un altro esempio:

```
prima:
supporto A confirmed

dopo:
supporto A superseded
supporto B confirmed
```

Il fatto rimane effettivo, ma è cambiato **perché** viene considerato effettivo.

La v02 richiede che hash e diff includano, per ogni supporto effettivo:

- hash semantico;
- outcome della testa corrente;
- policy e versione;
- eventuale contenuto corretto.

Esclude invece rumore operativo come timestamp, run ID, retry e percorsi assoluti. {line\_range\_start=330 line\_range\_end=338 path=.kb/documenti/documenti di design/run 2/design\_document\_v\_02.md git\_url="https://github.com/DanieleBarbiero/dsl\_manager-v1/blob/main/.kb/documenti/documenti di design/run 2/design\_document\_v\_02.md#L330-L338"}

Perciò il diff v2 può distinguere:

```
cambiamento del modello
```

da:

```
cambiamento della giustificazione del modello
```

---

# 8. Cambiamenti temporali

Con DSL v2 anche gli intervalli fanno parte del confronto.

Esempio:

```
DSL_000001:
FACT_X.intervals = []

DSL_000002:
FACT_X.intervals = [
  2025-01-01 → 2025-12-31
]
```

Il fatto non è nuovo; è stata aggiunta una qualificazione temporale:

```
temporal change:
intervallo aggiunto
```

Altro esempio:

```
prima:
2025-01-01 → 2025-12-31

dopo:
2025-01-01 → 2026-06-30
```

Diff:

```
temporal change:
end 2025-12-31 → 2026-06-30
```

Oppure:

```
prima:
un intervallo continuo

dopo:
due intervalli disgiunti
```

Il confronto deve preservare:

- date normalizzate;
- precisione originale;
- timezone;
- `timeformat`;
- semantica dei limiti;
- intervalli multipli e relativi gap.

Il contratto stabilisce che soltanto la temporalità risolta e sottoposta a review contribuisca agli hash e al diff. L’evidenza temporale grezza rimane tracciata ma non modifica direttamente il DSL. {line\_range\_start=330 line\_range\_end=338 path=.kb/documenti/documenti di design/run 2/design\_document\_v\_02.md git\_url="https://github.com/DanieleBarbiero/dsl\_manager-v1/blob/main/.kb/documenti/documenti di design/run 2/design\_document\_v\_02.md#L330-L338"}

---

# 9. Il diff deve spiegare la causa

DSL Manager non vuole limitarsi a dire:

```
FACT_X è stato rimosso
```

Vuole anche permettere di ricostruire:

```
quale candidato sosteneva FACT_X?
quale revisione lo aveva originato?
quale fonte?
quale chunk o frammento?
quale evidenza?
su quale lato del confronto?
```

Un cambiamento può quindi avere cause come:

```
removed_fact
├── side: before
├── candidate_record_id: CAND_REC_000020
├── source_revision_id: REV_000005
├── source_id: SRC_000003
├── chunk_id: CHK_000021
└── evidence_text_hash: ...
```

Oppure, per un’aggiunta:

```
added_relation
├── side: after
├── candidate_record_id: CAND_REC_000031
├── source_revision_id: REV_000008
├── fragment_id: FRAG_000044
└── evidence_text_hash: ...
```

Il diff preesistente richiede già per una causa candidato, revisione, fonte, percorso ed evidence hash, con eventuale chunk o frammento.

Nel report Markdown, ogni cambiamento espone `before`, `after` e le cause collegate ai due lati del confronto.

---

# 10. Se manca la tracciabilità, il diff fallisce

Supponiamo che lo snapshot B contenga un nuovo fatto, ma non sia possibile risalire a:

- candidato;
- revisione;
- fonte;
- evidenza.

DSL Manager non dovrebbe produrre tranquillamente:

```
added_fact: X
cause: unknown
```

Il cambiamento violerebbe uno dei principi fondamentali dell’applicazione.

Perciò il diff fallisce se un cambiamento semantico non può essere ricondotto alle evidenze richieste. Il manuale descrive espressamente questo vincolo.

Questo trasforma il diff anche in un controllo di qualità:

> Se non sappiamo spiegare da dove viene un cambiamento, il modello non è sufficientemente tracciabile.

---

# 11. Esempio completo

Supponiamo di partire da:

```
DSL_000001

Entità:
  Cliente
  Ordine

Fatti:
  Cliente.physical_table = CLIENTE
  Cliente.retention_period = 5 anni

Relazioni:
  Ordine references Cliente

Intervalli:
  retention_period: nessuno
```

Dopo nuove fonti, review e merge otteniamo:

```
DSL_000002

Entità:
  Cliente
  Ordine
  Pagamento

Fatti:
  Cliente.physical_table = CLIENTE
  Cliente.retention_period = 10 anni
  Pagamento.physical_table = PAGAMENTO

Relazioni:
  Ordine references Cliente
  Pagamento belongs_to Ordine

Intervalli:
  retention_period:
    2025-01-01 → 2026-12-31
```

Il diff potrebbe organizzare il risultato come:

```
Structural changes
├── added_entity: Pagamento
├── removed_fact:
│   Cliente.retention_period = 5 anni
├── added_fact:
│   Cliente.retention_period = 10 anni
├── added_fact:
│   Pagamento.physical_table = PAGAMENTO
└── added_relation:
    Pagamento belongs_to Ordine

Governance changes
└── supporto di Cliente.physical_table:
    aggiunta conferma indipendente dal manuale

Temporal changes
└── Cliente.retention_period:
    aggiunto intervallo 2025-01-01 → 2026-12-31
```

Per ogni cambiamento vengono conservate le cause pertinenti.

---

# 12. Confronti fra versioni dello schema

## Confronto ordinario

Il caso più semplice è:

```
DSL v2 ↔ DSL v2
```

oppure, per compatibilità legacy:

```
DSL v1 ↔ DSL v1
```

In questi casi gli snapshot condividono lo stesso contratto strutturale.

## Confronto v1 contro v2

Un confronto implicito tra:

```
DSL v1 ↔ DSL v2
```

sarebbe ambiguo perché alcune differenze dipenderebbero semplicemente dal cambio di schema:

- presenza di `intervals`;
- nuove informazioni di governance;
- uso delle viste effettive;
- metadata temporali;
- differente rappresentazione dei supporti.

Per questo il confronto cross-schema deve essere esplicito:

````
Bash


```
dsl-manager dsl diff <left> <right> --cross-schema
```
````

La slice 26 introduce inizialmente soltanto diff fra snapshot dello stesso schema; la slice 27 aggiunge il confronto cross-schema esplicito e separa variazioni strutturali, di governance e temporali. {line\_range\_start=461 line\_range\_end=467 path=.kb/documenti/documenti di design/run 2/design\_document\_v\_02.md git\_url="https://github.com/DanieleBarbiero/dsl\_manager-v1/blob/main/.kb/documenti/documenti di design/run 2/design\_document\_v\_02.md#L461-L467"}{line\_range\_start=752 line\_range\_end=762 path=.kb/documenti/documenti di design/run 2/design\_document\_v\_02.md git\_url="https://github.com/DanieleBarbiero/dsl\_manager-v1/blob/main/.kb/documenti/documenti di design/run 2/design\_document\_v\_02.md#L752-L762"}

La modalità esplicita impedisce di scambiare:

```
“il sistema è cambiato”
```

con:

```
“è cambiato il modo in cui rappresentiamo il sistema”
```

---

# 13. Il diff non modifica nulla

Il DSL diff è un’operazione derivata e di sola lettura rispetto al contenuto semantico:

```
legge snapshot A
legge snapshot B
produce report
```

Non:

- modifica fatti;
- cambia decisioni;
- risolve conflitti;
- applica correzioni;
- aggiorna snapshot;
- esegue merge.

Produce artefatti separati, per esempio:

```
exports/dsl_diff/
├── DSL_000001__DSL_000002.json
└── DSL_000001__DSL_000002.md
```

Il codice preesistente carica i due snapshot, costruisce il diff e scrive JSON e Markdown in una directory di export distinta.

---

# 14. Perché il diff è importante nel processo di modernizzazione?

Il DSL descrive il sistema.

Il diff descrive **l’evoluzione della nostra conoscenza del sistema**.

Può rispondere a domande come:

- Quali entità sono state scoperte dopo l’analisi del nuovo corpus?
- Quali fatti sono stati ritirati dopo una correzione?
- Quali relazioni sono ora sostenute da fonti aggiuntive?
- Quali informazioni sono cambiate perché una policy è stata aggiornata?
- Quali intervalli temporali sono stati aggiunti o corretti?
- Quali conflitti sono comparsi o sono scomparsi?
- Il nuovo snapshot è semanticamente identico al precedente?
- Una migrazione ha cambiato il significato o soltanto il formato?

Il diff è quindi utile sia come prodotto informativo sia come controllo di regressione.

---

# Risultato dello step 7

Alla fine otteniamo:

```
DSL_000001
      │
      ├── confronto deterministico
      │
DSL_000002
      ↓
DSL_000001__DSL_000002.json
DSL_000001__DSL_000002.md
```

Il report contiene:

```
metadata del confronto
hash degli snapshot
riepilogo dei cambiamenti
cambiamenti strutturali
cambiamenti di governance
cambiamenti temporali
before / after
cause e tracciabilità
```

## Formula mentale aggiornata

```
STEP 1: Quali byte abbiamo?
STEP 2: Che cosa è osservabile dentro quei byte?
STEP 3: Quali affermazioni possiamo proporre?
STEP 4: Quali proposte approviamo?
STEP 5: Come materializziamo le proposte approvate?
STEP 6: Come fotografiamo lo stato effettivo?
STEP 7: Che cosa è cambiato fra due fotografie,
        e quali evidenze spiegano il cambiamento?
```

Il prossimo step naturale sarà l’altra proiezione dello snapshot:

```
snapshot DSL
      ↓
grafo GEXF
```

Vedremo come fatti, entità e relazioni diventano nodi e archi e, con DSL v2, come gli intervalli diventano dinamica temporale.

**Verifiche documentali**

- ✅ `rg -n "diff|cross-schema|variazioni strutturali|governance|tempor" '.kb/documenti/documenti di design/run 2/design_document_v_02.md'`
- ✅ `nl -ba '.kb/documenti/documenti di design/run 2/design_document_v_02.md' | sed -n '461,469p'`
- ✅ `nl -ba '.kb/documenti/documenti di design/run 2/design_document_v_02.md' | sed -n '752,766p'`
- ✅ `nl -ba src/dsl_mngr/core/dsl_diff.py | sed -n '1,470p'`
- ✅ `nl -ba '.kb/documenti/manuali/manuale_utente_dsl_manager.md' | sed -n '1038,1085p'`
- ✅ `git status --short` — nessun dato o file creato, modificato o cancellato.

procedi allo step 8.

Copy

Worked for 2m 32s

## Step 8 — Dallo snapshot al grafo

Alla fine dello step 7 possediamo:

```
registry autoritativo
        ↓
snapshot DSL
        ↓
eventuale diff fra snapshot
```

Il DSL è già l’output principale del programma. Tuttavia, per comprendere un sistema complesso può essere utile trasformarlo in una rete visualizzabile:

```
snapshot DSL
      ↓
proiezione grafica
      ↓
nodi + archi
      ↓
file GEXF
```

La parola importante di questo step è **proiezione**.

Il grafo non è una nuova fonte di verità e non effettua una nuova analisi: è un’altra rappresentazione di uno snapshot DSL già consolidato.

---

# 1. Il grafo parte da uno snapshot preciso

Il comando previsto è:

````
Bash


```
dsl-manager graph export <workspace> \
  --snapshot DSL_000001
```
````

Per l’export temporale v2:

````
Bash


```
dsl-manager graph export <workspace> \
  --snapshot DSL_000001 \
  --dynamic
```
````

Il punto fondamentale è la presenza di:

```
--snapshot DSL_000001
```

L’export non legge semplicemente “qualunque cosa si trovi ora nel registry”. Legge una fotografia specifica.

Quindi:

```
GEXF_000001
└── deriva esattamente da DSL_000001
```

Se il registry cambia dopo la creazione dello snapshot, l’export di `DSL_000001` deve continuare a rappresentare quello snapshot, non lo stato più recente.

L’export preesistente carica infatti lo snapshot indicato, conserva `snapshot_id`, `dsl_hash` e `registry_hash`, e registra l’associazione nel record dell’export.

---

# 2. Dal modello tabellare al modello a rete

Nel DSL potremmo avere:

```
Entità:
  Cliente
  Ordine
  Pagamento

Relazioni:
  Cliente places Ordine
  Pagamento belongs_to Ordine
  Ordine references Cliente
```

Il grafo le rappresenta come:

```
[Cliente] ──places─────→ [Ordine]
                            ↑
                            │ belongs_to
                       [Pagamento]

[Ordine] ──references──→ [Cliente]
```

Le entità diventano nodi e le relazioni diventano archi orientati.

Questo permette di visualizzare:

- dipendenze;
- concentrazioni di relazioni;
- componenti isolate;
- cicli;
- oggetti centrali;
- relazioni tecniche e di dominio;
- provenienza delle informazioni;
- conflitti.

---

# 3. Quali nodi può contenere?

Il grafo non deve necessariamente limitarsi alle entità.

Può includere più categorie di nodi.

## Nodi entità

```
[Cliente]
[Ordine]
[Pagamento]
```

Rappresentano gli oggetti principali del modello.

## Nodi fatto

Alcuni fatti, in particolare regole di business, possono essere rappresentati come nodi separati:

```
[Cliente]
    │
    └── has_rule ─→ [Cancellazione vietata con ordini aperti]
```

Questo è utile quando un fatto non è soltanto un’etichetta descrittiva, ma un oggetto che si vuole esplorare visivamente.

## Nodi sorgente

Le fonti possono diventare nodi:

```
[manuale_clienti.pdf]
       │
       └── derives_from ─→ [Cliente]
```

oppure, a seconda della direzione stabilita dal contratto:

```
[Cliente] ──derives_from──→ [manuale_clienti.pdf]
```

Servono a mostrare quali parti del modello sono sostenute da quali documenti.

## Nodi conflitto

Un conflitto può essere rappresentato come nodo:

```
                 ┌── [retention = 5 anni]
[Conflitto] ─────┤
                 └── [retention = 10 anni]
```

Il manuale del comportamento legacy elenca come contenuti possibili del grafo:

- entità;
- fatti di tipo business rule;
- fonti;
- conflitti;
- archi semantici;
- archi `mentions`;
- archi `derives_from`;
- archi `conflicts_with`.

---

# 4. Quali informazioni porta un nodo?

Un nodo non è soltanto un cerchio con un’etichetta.

Per esempio, un nodo entità può avere attributi come:

```
node_id
label
node_type
canonical_name
status
source_count
fact_count
source_ids
fact_ids
```

Concettualmente:

```
Nodo:
  id: entity:cliente
  label: Cliente
  type: domain_entity
  facts: 4
  sources: 3
  status: active
```

Il modello legacy dell’exporter già raccoglie sul nodo dell’entità il nome canonico, il numero e gli ID dei fatti, il numero e gli ID delle fonti e lo stato.

Questo consente agli strumenti di visualizzazione di:

- colorare i nodi per tipo;
- dimensionarli per numero di fatti;
- filtrare per stato;
- evidenziare gli oggetti sostenuti da più fonti;
- distinguere entità, fatti, sorgenti e conflitti.

---

# 5. Quali informazioni porta un arco?

Una relazione come:

```
Ordine references Cliente
```

può essere esportata come:

```
edge_id: relation:REL_000001
source: entity:ordine
target: entity:cliente
label: references
```

con attributi aggiuntivi:

```
relation_id
assertion_type
status
source_ids
source_revision_ids
confidence
```

L’arco non rappresenta soltanto la connessione grafica. Mantiene abbastanza informazioni per ricondurlo all’oggetto DSL che lo ha originato.

Il contratto legacy dell’exporter prevede già attributi come ID della relazione, assertion, confidence, stato, entità sorgente e destinazione, fonti e revisioni.

---

# 6. Il grafo è diretto

DSL Manager utilizza un grafo orientato.

La relazione:

```
Ordine references Cliente
```

non equivale a:

```
Cliente references Ordine
```

Analogamente:

```
Procedura writes_to Tabella
```

non equivale a:

```
Tabella writes_to Procedura
```

Il grafo conserva quindi una direzione:

```
source ──relation_type──→ target
```

Il manuale dichiara espressamente che il grafo è diretto.

---

# 7. GEXF statico e GEXF dinamico

Esistono due modalità principali.

## GEXF statico

È la modalità legacy, associata a DSL v1.

Descrive una rete come se tutti i suoi elementi fossero contemporaneamente presenti:

```
graph mode = static
```

Esempio:

```
Cliente ──places──→ Ordine
```

Non esprime quando l’entità o la relazione siano valide.

## GEXF dinamico

È la modalità introdotta per DSL v2.

Descrive anche gli intervalli temporali:

```
graph mode = dynamic
timerepresentation = interval
```

Esempio:

```
Cliente ──places──→ Ordine
          valido:
          2025-01-01 → 2026-12-31
```

La modalità dinamica accetta esclusivamente snapshot DSL v2, perché soltanto la v2 possiede il contratto temporale necessario. {line\_range\_start=463 line\_range\_end=471 path=.kb/documenti/documenti di design/run 2/design\_document\_v\_02.md git\_url="https://github.com/DanieleBarbiero/dsl\_manager-v1/blob/main/.kb/documenti/documenti di design/run 2/design\_document\_v\_02.md#L463-L471"}

---

# 8. Come vengono rappresentati gli intervalli?

Un nodo o un arco può possedere uno o più periodi di attività.

Per esempio:

```
SistemaLegacy
├── 2018-01-01 → 2021-12-31
└── 2023-01-01 → 2024-06-30
```

Nel GEXF dinamico vengono rappresentati tramite `spells`:

````
XML


```
<spells>
  <spell start="2018-01-01" end="2021-12-31"/>
  <spell start="2023-01-01" end="2024-06-30"/>
</spells>
```
````

Gli intervalli disgiunti rimangono disgiunti:

```
2018 ───────── 2021     2023 ───── 2024
                      ↑
                     gap
```

Il programma non deve inventare una continuità tra il 2021 e il 2023.

Nel contratto GEXF 1.3 usato dalla v02, `start` ed `end` sono inclusivi. Gli intervalli multipli vengono rappresentati come `spell` ordinati su nodi e archi. {line\_range\_start=469 line\_range\_end=476 path=.kb/documenti/documenti di design/run 2/design\_document\_v\_02.md git\_url="https://github.com/DanieleBarbiero/dsl\_manager-v1/blob/main/.kb/documenti/documenti di design/run 2/design\_document\_v\_02.md#L469-L476"}

---

# 9. `date` e `dateTime` non si mescolano liberamente

Ogni grafo dinamico usa un solo `timeformat`:

```
date
```

oppure:

```
dateTime
```

## Esempio `date`

````
XML


```
<graph mode="dynamic" timeformat="date">
```
````

con valori:

```
2025-01-01
2025-12-31
```

## Esempio `dateTime`

````
XML


```
<graph mode="dynamic" timeformat="dateTime">
```
````

con valori:

```
2025-01-01T08:30:00+01:00
2025-01-01T17:30:00+01:00
```

DSL Manager non deve:

- troncare silenziosamente un `dateTime` a `date`;
- inventare un’ora per trasformare una data in timestamp;
- inventare una timezone;
- mescolare profili temporali incompatibili nello stesso grafo.

Il profilo temporale globale viene ereditato dallo snapshot DSL v2, che dichiara `base`, `gexf_timeformat` e timezone. {line\_range\_start=463 line\_range\_end=467 path=.kb/documenti/documenti di design/run 2/design\_document\_v\_02.md git\_url="https://github.com/DanieleBarbiero/dsl\_manager-v1/blob/main/.kb/documenti/documenti di design/run 2/design\_document\_v\_02.md#L463-L467"}

---

# 10. Un arco non può esistere quando i suoi nodi non esistono

Supponiamo:

```
Nodo Ordine:
2025-01-01 → 2025-12-31

Nodo Cliente:
2025-01-01 → 2026-12-31
```

Una relazione fra i due può essere valida durante:

```
2025-03-01 → 2025-11-30
```

perché l’intervallo dell’arco è contenuto negli intervalli di entrambi i nodi.

Non può invece essere:

```
2026-02-01 → 2026-03-01
```

perché in quel periodo il nodo `Ordine` non è più attivo.

La regola è:

```
intervallo arco
⊆
intervallo nodo sorgente
∩
intervallo nodo destinazione
```

Questa condizione non è garantita soltanto dallo schema XML: DSL Manager deve verificarla semanticamente. Il design richiede esplicitamente il controllo di contenimento degli intervalli degli archi in quelli dei nodi. {line\_range\_start=469 line\_range\_end=476 path=.kb/documenti/documenti di design/run 2/design\_document\_v\_02.md git\_url="https://github.com/DanieleBarbiero/dsl\_manager-v1/blob/main/.kb/documenti/documenti di design/run 2/design\_document\_v\_02.md#L469-L476"}

---

# 11. Entità orfane

Una relazione potrebbe riferirsi a un’entità che non compare tra i nodi principali.

Esempio:

```
Ordine references SistemaEsterno
```

ma `SistemaEsterno` non esiste come entità nello snapshot.

Ci sono due possibili comportamenti.

## Modalità tollerante

DSL Manager crea un nodo orfano:

```
[SistemaEsterno]
status: orphan
```

e aggiunge un warning.

Il grafo rimane visualizzabile, ma dichiara l’incompletezza.

## Modalità stretta

Con:

````
Bash


```
--strict-orphans
```
````

l’export fallisce.

Il manuale distingue già questi due comportamenti nell’export statico.

In un modello governato è preferibile che gli orfani siano:

- visibili;
- contati;
- spiegati;
- mai creati silenziosamente come normali entità.

---

# 12. La validazione avviene a due livelli

Produrre XML ben formato non è sufficiente.

DSL Manager esegue due famiglie di controlli.

## Primo livello: validazione XSD

Il file deve rispettare lo schema ufficiale GEXF 1.3.

Vengono controllati, per esempio:

- namespace;
- elementi ammessi;
- attributi;
- tipi XML;
- struttura di nodi, archi e intervalli.

La validazione usa `lxml` con:

- rete disabilitata;
- DTD disabilitate;
- entity disabilitate;
- resolver limitato alle risorse locali.

## Secondo livello: validazione semantica

Vengono poi controllate proprietà che l’XSD da solo non può garantire:

- ID univoci;
- riferimenti source/target validi;
- modalità dinamica corretta;
- un solo `timeformat`;
- ordine degli intervalli;
- limiti temporali coerenti;
- nodi e archi ordinati stabilmente;
- tipi degli attributi;
- intervallo dell’arco contenuto in quello dei nodi.

La v02 prescrive espressamente entrambi i livelli. {line\_range\_start=469 line\_range\_end=476 path=.kb/documenti/documenti di design/run 2/design\_document\_v\_02.md git\_url="https://github.com/DanieleBarbiero/dsl\_manager-v1/blob/main/.kb/documenti/documenti di design/run 2/design\_document\_v\_02.md#L469-L476"}

---

# 13. Tutto deve funzionare offline

Il validatore non scarica lo schema GEXF da Internet durante l’export.

Gli XSD vengono distribuiti insieme all’applicazione:

```
src/dsl_mngr/resources/gexf/1.3/
├── gexf.xsd
├── dynamics.xsd
├── viz.xsd
└── manifest delle risorse
```

Per ciascuna risorsa vengono fissati:

- URL originale;
- versione;
- commit upstream;
- licenza;
- hash SHA-256 atteso.

Questo impedisce che due esecuzioni usino accidentalmente versioni differenti dello schema o che un export fallisca perché la rete non è disponibile.

Il design stabilisce il vendoring completo delle risorse, il controllo degli hash e l’assenza di download a runtime. {line\_range\_start=478 line\_range\_end=486 path=.kb/documenti/documenti di design/run 2/design\_document\_v\_02.md git\_url="https://github.com/DanieleBarbiero/dsl\_manager-v1/blob/main/.kb/documenti/documenti di design/run 2/design\_document\_v\_02.md#L478-L486"}

---

# 14. Anche il grafo ha un’identità e un hash

L’export non produce soltanto:

```
DSL_000001.gexf
```

Registra anche:

```
graph_export_id
snapshot_id
dsl_hash
registry_hash
graph_hash
node_count
edge_count
orphan_count
warning_count
opzioni
report
```

Possiamo quindi ricostruire:

```
GEXF_000001
   ↓ deriva da
DSL_000001
   ↓ deriva da
registry_hash ABC
```

Il codice legacy già calcola un `graph_hash`, scrive il GEXF e il relativo report e registra conteggi, warning e collegamento allo snapshot.

Come per il DSL:

```
stesso snapshot
+
stesse opzioni
        ↓
stesso contenuto semantico del grafo
+
stesso graph_hash
```

---

# 15. Il grafo non sostituisce il DSL

È importante non invertire la direzione.

La catena corretta è:

```
registry
   ↓
DSL snapshot
   ↓
GEXF
```

Non:

```
GEXF
   ↓
ricostruzione autoritativa del DSL
```

Il GEXF è ottimizzato per:

- visualizzazione;
- navigazione;
- analisi di rete;
- importazione in strumenti come Gephi;
- esplorazione temporale.

Il DSL conserva invece meglio:

- struttura semantica completa;
- tracciabilità;
- governance;
- dettaglio dei fatti;
- metadati;
- contratti di schema;
- contenuto canonico.

Il grafo può omettere o comprimere informazioni che rimangono disponibili nello snapshot.

---

# 16. Che cosa può fare una persona con il grafo?

Una volta importato in uno strumento compatibile, può esplorare domande come:

- Quali entità hanno più dipendenze?
- Quali tabelle sono lette o scritte da più procedure?
- Quali concetti dipendono da una singola fonte?
- Dove compaiono cicli?
- Quali componenti sono isolate?
- Quali relazioni appartengono soltanto al sistema legacy?
- Quali elementi esistevano in un certo periodo?
- Quali relazioni appaiono o scompaiono nel tempo?
- Dove si concentrano i conflitti?
- Quali sorgenti sostengono una particolare area del modello?

Il valore del grafo non è quindi creare nuova conoscenza, ma rendere **navigabile e visibile** quella già governata.

---

# Risultato dello step 8

Alla fine possiamo avere:

```
DSL_000001
├── JSON
├── YAML
└── Markdown
       │
       └── graph export
              ↓
exports/graph/
├── DSL_000001.gexf
└── DSL_000001_report.json
```

Il file GEXF contiene:

```
nodi
archi
attributi
provenienza
eventuali conflitti
eventuali intervalli temporali
```

ed è:

- legato a uno snapshot preciso;
- deterministico;
- validato;
- tracciabile;
- utilizzabile offline;
- statico per DSL v1;
- dinamico per DSL v2.

## Formula mentale aggiornata

```
STEP 1: Quali byte abbiamo?
STEP 2: Che cosa è osservabile dentro quei byte?
STEP 3: Quali affermazioni possiamo proporre?
STEP 4: Quali proposte approviamo?
STEP 5: Come materializziamo le proposte approvate?
STEP 6: Come fotografiamo lo stato effettivo?
STEP 7: Che cosa è cambiato fra due fotografie?
STEP 8: Come rendiamo una fotografia esplorabile
        come rete statica o temporale?
```

Con questo step siamo arrivati all’**output finale esterno** della pipeline principale:

```
dato grezzo
   ↓
evidenza
   ↓
candidato
   ↓
decisione
   ↓
fatto/relazione
   ↓
snapshot DSL
   ↓
diff e grafo
```

Rimarrebbe eventualmente un ultimo step trasversale dedicato a **run, report, log, batch e UI**, cioè a come DSL Manager rende osservabile e operabile l’intero viaggio senza modificare la semantica del risultato.

**Verifiche documentali**

- ✅ `nl -ba '.kb/documenti/documenti di design/run 2/design_document_v_02.md' | sed -n '463,487p'`
- ✅ `nl -ba '.kb/documenti/manuali/manuale_utente_dsl_manager.md' | sed -n '1081,1168p'`
- ✅ `nl -ba src/dsl_mngr/core/graph_export.py | sed -n '1,390p'`
- ✅ `git status --short` — nessun dato o file creato, modificato o cancellato.

procedi pure con lo step 9.

Copy

Worked for 2m 57s

## Step 9 — Governare il viaggio: batch, run, report, log e UI

Gli step 1–8 descrivono il flusso semantico:

```
byte
 ↓
evidenze
 ↓
candidati
 ↓
decisioni
 ↓
fatti e relazioni
 ↓
snapshot DSL
 ↓
diff e grafo
```

Ma un’applicazione reale deve rispondere anche a domande operative:

- Quali passaggi sono stati eseguiti?
- Con quale configurazione?
- Quali file sono riusciti e quali no?
- Dove si è fermato il processo?
- Posso riprenderlo senza duplicare risultati?
- Quali candidati aspettano una review?
- Esistono riconciliazioni aperte?
- Un errore ha lasciato mutazioni parziali?
- Quali artefatti sono stati prodotti?

DSL Manager risponde attraverso un livello trasversale:

```
batch
run
worker
report
result catalog
log
UI di sola lettura
```

Questi strumenti non aggiungono nuova semantica al DSL. Rendono il processo **osservabile, ripetibile e operabile**.

---

# 1. Il batch è l’orchestratore

Finora abbiamo descritto il viaggio come una sequenza ordinata:

```
scan
  ↓
parse/normalize
  ↓
derive
  ↓
review
  ↓
merge
  ↓
reconcile
  ↓
render
```

Una persona potrebbe eseguire ogni comando separatamente, ma su un corpus reale sarebbe scomodo.

Il batch coordina più operazioni:

```
batch principale
├── elabora revisione A
├── elabora revisione B
├── elabora revisione C
├── deriva candidati
├── applica policy automatiche autorizzate
├── unisce candidati eleggibili
└── esegue eventuale riconciliazione
```

La v02 inserisce esplicitamente la derivazione dopo i parser strutturali, fa passare la review automatica dal servizio comune, controlla l’eleggibilità al momento del merge e può eseguire la riconciliazione come fase finale. {line\_range\_start=728 line\_range\_end=732 path=.kb/documenti/documenti di design/run 2/design\_document\_v\_02.md git\_url="https://github.com/DanieleBarbiero/dsl\_manager-v1/blob/main/.kb/documenti/documenti di design/run 2/design\_document\_v\_02.md#L728-L732"}

Il batch quindi non dovrebbe duplicare la logica dei singoli componenti. Non deve avere:

```
una propria review
un proprio merge
un proprio parser
```

Deve chiamare i servizi canonici già descritti.

---

# 2. Un batch non è una transazione gigantesca

È utile distinguere due livelli.

## Transazione applicativa locale

Operazioni come una correzione o un merge usano transazioni atomiche:

```
tutto riesce
oppure
rollback
```

## Orchestrazione batch

Un batch può contenere molti file e molte fasi, alcune delle quali possono riuscire e altre fallire:

```
revisione A → completed
revisione B → failed
revisione C → skipped
revisione D → partial
```

Non sarebbe sempre ragionevole annullare ore di elaborazione valida perché l’ultimo file è malformato.

Perciò il batch:

- registra ogni fase;
- conserva i risultati completati;
- distingue gli errori;
- permette retry;
- aggrega lo stato finale;
- evita di duplicare ciò che è già stato completato.

Il comportamento può essere configurato affinché continui dopo un errore oppure si arresti. Nel sistema preesistente, `--stop-on-error` ferma gli item successivi e li marca come saltati.

---

# 3. Ogni operazione significativa è una run

Quando DSL Manager esegue un’attività, crea una **run**:

```
RUN_000001
```

Una run è la busta operativa che documenta:

```
che cosa volevamo fare
con quali parametri
con quale configurazione
quale componente è stato eseguito
che cosa ha prodotto
come è terminato
```

Una directory di run ha una struttura simile a:

```
artifacts/runs/RUN_000001/
├── input.json
├── output.json
├── process_report.json
├── resolved_config.yaml
├── config_hash.txt
└── log.jsonl
```

Questi artefatti permettono di ricostruire parametri, configurazione, output, stato e log di dettaglio.

---

# 4. Run padre e sub-run

Un batch crea normalmente una run padre:

```
RUN_000100
type: batch
```

e più sub-run:

```
RUN_000100 batch
├── RUN_000101 normalize REV_000001
├── RUN_000102 chunk REV_000001
├── RUN_000103 parse_ddl REV_000002
├── RUN_000104 derive
├── RUN_000105 review_policy
├── RUN_000106 merge
└── RUN_000107 reconcile
```

Ogni sub-run conserva:

```
parent_run_id = RUN_000100
```

Questo permette di osservare sia:

- l’esito aggregato del batch;
- il dettaglio di ogni singola fase.

Il manuale specifica che i batch creano una run padre e sub-run operative collegate mediante `parent_run_id`.

---

# 5. I worker isolano le elaborazioni specializzate

Le attività più tecniche vengono affidate a worker specializzati:

```
normalize_docling
chunk_docling
parse_ddl
parse_xml_form
parse_db_code
parse_log
build_ai_package
preflight OOXML
estrazione temporale
validazione GEXF
```

Il modello è:

```
processo principale
       ↓ input JSON
worker isolato
       ↓ output JSON/JSONL
validazione dell’output
       ↓
mutazione controllata del registry
```

Il worker non dovrebbe modificare liberamente il database mentre sta ancora elaborando.

Il parent:

1. prepara l’input;
2. avvia il worker;
3. raccoglie l’output;
4. lo valida;
5. soltanto dopo applica le mutazioni previste.

Nel modello preesistente, se un worker fallisce il registry non riceve mutazioni applicative parziali.

---

# 6. Gli stati non sono soltanto “successo” ed “errore”

Una pipeline di questo tipo ha bisogno di un vocabolario più ricco.

Esempi:

```
completed
failed
rejected
pending
blocked
conflict
partial
skipped
```

Questi stati esprimono situazioni diverse.

## `completed`

L’operazione è terminata secondo il contratto.

## `failed`

Si è verificato un errore operativo o di precondizione.

## `rejected`

L’input è stato deliberatamente respinto, per esempio perché non sicuro o strutturalmente invalido.

## `pending`

Il processo ha prodotto qualcosa, ma occorre una decisione o nuova evidenza.

## `blocked`

L’operazione non può proseguire finché non viene risolta una condizione esterna:

```
nessun candidato merge-eligible
riconciliazione aperta
```

## `conflict`

Esiste un conflitto di concorrenza o idempotenza:

```
testa di review stantia
chiave riutilizzata con payload diverso
```

## `partial`

Parte dell’elaborazione è utilizzabile, ma il risultato non è completo.

Uno stato ricco permette di distinguere:

```
“puoi riprovare”
```

da:

```
“devi correggere il dato”
```

e da:

```
“serve una decisione umana”
```

---

# 7. `reason` spiega lo stato

Uno stato da solo non è sufficiente.

Per esempio:

```
status: blocked
```

potrebbe significare molte cose.

Il campo `reason` aggiunge una causa stabile e machine-readable:

```
status: blocked
reason: no_merge_eligible_candidates
```

oppure:

```
status: blocked
reason: reconciliation_required
```

Altri esempi:

```
review_head_conflict
candidate_schema_invalid
source_revision_changed
ooxml_security_violation
temporal_conflict
temporal_timezone_unknown
gexf_xsd_invalid
gexf_semantic_invalid
```

Questi valori sono in lowercase `snake_case` e non dipendono dal testo descrittivo rivolto all’utente.

La v02 introduce un catalogo condiviso di status, outcome, reason ed exit code per review, derivazione, merge, Excel, temporalità e GEXF. {line\_range\_start=563 line\_range\_end=597 path=.kb/documenti/documenti di design/run 2/design\_document\_v\_02.md git\_url="https://github.com/DanieleBarbiero/dsl\_manager-v1/blob/main/.kb/documenti/documenti di design/run 2/design\_document\_v\_02.md#L563-L597"}

---

# 8. Un report dice anche se ci sono state mutazioni

Un errore può avvenire:

```
prima di qualsiasi scrittura
```

oppure:

```
dopo avere completato una fase precedente
```

Per questo il report deve dichiarare:

```
mutations: true | false
```

e anche:

```
retryable: true | false
```

Esempio:

````
JSON


```
{
  "status": "conflict",
  "reason": "review_head_conflict",
  "mutations": false,
  "retryable": true,
  "exit_code": 4
}
```
````

Significa:

> Nessuna decisione è stata scritta. Ricarica la testa corrente e riprova.

Altro esempio:

````
JSON


```
{
  "status": "rejected",
  "reason": "ooxml_security_violation",
  "mutations": false,
  "retryable": false,
  "exit_code": 3
}
```
````

Significa:

> Il workbook è stato rifiutato come input non sicuro; ripetere lo stesso comando sullo stesso file non risolverà il problema.

Ogni report v02 contiene almeno versione del catalogo, condizione, stato, outcome, reason, severità, mutazioni, retry, exit code, run, soggetti, artefatti e contatori. {line\_range\_start=563 line\_range\_end=566 path=.kb/documenti/documenti di design/run 2/design\_document\_v\_02.md git\_url="https://github.com/DanieleBarbiero/dsl\_manager-v1/blob/main/.kb/documenti/documenti di design/run 2/design\_document\_v\_02.md#L563-L566"}

---

# 9. L’exit code serve agli script

Il messaggio umano può dire:

```
Nessun candidato eleggibile per il merge.
```

Uno script ha bisogno di un codice stabile:

```
exit 4
```

Il catalogo distingue, per esempio:

- `0`: operazione completata;
- `2`: errore di utilizzo o configurazione, come attore mancante;
- `3`: input respinto o output non valido;
- `4`: conflitto o blocco risolvibile;
- `5`: fallimento operativo;
- `6`: successo parziale esplicito.

In particolare, la v02 evita di trasformare automaticamente un successo parziale in un generico fallimento: `exit 6` conserva il significato di risultato parziale. {line\_range\_start=567 line\_range\_end=597 path=.kb/documenti/documenti di design/run 2/design\_document\_v\_02.md git\_url="https://github.com/DanieleBarbiero/dsl\_manager-v1/blob/main/.kb/documenti/documenti di design/run 2/design\_document\_v\_02.md#L567-L597"}

---

# 10. Esempio di report di batch

Immaginiamo un corpus con quattro file:

```
manuale.pdf
schema.sql
form.xml
workbook.xlsx
```

Un report aggregato potrebbe essere:

````
JSON


```
{
  "catalog_version": "result_catalog_v1",
  "status": "partial",
  "reason": "batch_completed_with_partial_items",
  "mutations": true,
  "retryable": true,
  "exit_code": 6,
  "counters": {
    "items_total": 4,
    "completed": 3,
    "partial": 1,
    "failed": 0,
    "skipped": 0,
    "candidates_pending": 7,
    "candidates_confirmed": 12,
    "merged": 12
  },
  "items": [
    {
      "source": "manuale.pdf",
      "status": "completed"
    },
    {
      "source": "schema.sql",
      "status": "completed"
    },
    {
      "source": "form.xml",
      "status": "completed"
    },
    {
      "source": "workbook.xlsx",
      "status": "partial",
      "reason": "normalization_partial"
    }
  ]
}
```
````

Il lettore può comprendere:

- il batch non è completamente fallito;
- tre fonti sono state elaborate;
- una è parziale;
- sono avvenute mutazioni valide;
- un retry mirato può essere utile;
- esistono candidati ancora pending.

---

# 11. Retry e convergenza

DSL Manager deve sopportare interruzioni in punti diversi:

```
crash dopo il parser
crash dopo la derivazione
crash dopo una decisione
crash durante il merge
crash prima della chiusura della riconciliazione
```

La ripresa non deve:

- duplicare candidati semanticamente identici;
- creare due decisioni uguali;
- creare due supporti uguali;
- creare due fatti identici;
- cambiare l’hash finale soltanto a causa del retry.

Il risultato desiderato è:

```
esecuzione continua
             \
              → stesso effective hash
             /
esecuzione interrotta + retry
```

La slice 22 richiede esplicitamente checkpoint, retry per fase e convergenza degli effective hash indipendentemente dalle ripetizioni. {line\_range\_start=728 line\_range\_end=732 path=.kb/documenti/documenti di design/run 2/design\_document\_v\_02.md git\_url="https://github.com/DanieleBarbiero/dsl\_manager-v1/blob/main/.kb/documenti/documenti di design/run 2/design\_document\_v\_02.md#L728-L732"}

---

# 12. Il log applicativo

Il workspace possiede un log generale:

```
logs/app.jsonl
```

Ogni record contiene normalmente:

```
timestamp
level
event
message
run_id opzionale
worker opzionale
```

Esempio:

````
JSON


```
{
  "timestamp": "2026-09-02T10:15:00Z",
  "level": "INFO",
  "event": "candidate_derivation_completed",
  "message": "Derived 12 candidates",
  "run_id": "RUN_000104",
  "worker": "candidate_derivation"
}
```
````

Il log è utile per seguire cronologicamente ciò che è accaduto.

Il manuale descrive questa struttura e distingue il log applicativo dai log specifici delle singole run.

---

# 13. Log e report non sono la stessa cosa

## Log

Risponde:

> “Che cosa è accaduto, in ordine cronologico?”

Esempio:

```
10:00 worker started
10:01 parsed 12 fragments
10:01 warning on unsupported statement
10:02 worker completed
```

## Report

Risponde:

> “Qual è l’esito strutturato dell’operazione?”

Esempio:

```
status: completed
fragments: 12
warnings: 1
reason: success
```

La distinzione è:

```
log = narrazione operativa
report = contratto dell’esito
```

Uno script dovrebbe basarsi principalmente sui campi strutturati del report e sull’exit code, non interpretare il testo libero dei log.

---

# 14. Consultare una run

Una persona può chiedere lo stato di una run:

````
Bash


```
dsl-manager run status <workspace> RUN_000104
```
````

e ottenere:

```
Run: RUN_000104
Type: candidate_derivation
Status: completed
Started: ...
Finished: ...
Artifact directory: artifacts/runs/RUN_000104
```

Da quella directory può poi ispezionare:

- input;
- configurazione risolta;
- hash della configurazione;
- output;
- report;
- log.

Il comando e l’output operativo sono documentati nel manuale.

---

# 15. Configurazione risolta

La presenza di:

```
resolved_config.yaml
config_hash.txt
```

è importante perché il comportamento non dipende soltanto dal comando.

Per esempio:

````
Bash


```
dsl-manager candidates derive <workspace>
```
````

può comportarsi diversamente se cambiano:

```
derive.rule_set_version
review.automatic_policies
limiti Excel
policy timezone
profilo GEXF
```

La run registra la configurazione effettivamente risolta, non soltanto il nome generico del profilo.

La v02 richiede inoltre che gli override applicati siano riportati nei report e che non possano disabilitare protezioni fondamentali come:

- no-network;
- blocco macro;
- blocco DTD/entity;
- controllo dell’hash della revisione. {line\_range\_start=524 line\_range\_end=561 path=.kb/documenti/documenti di design/run 2/design\_document\_v\_02.md git\_url="https://github.com/DanieleBarbiero/dsl\_manager-v1/blob/main/.kb/documenti/documenti di design/run 2/design\_document\_v\_02.md#L524-L561"}

---

# 16. L’interfaccia locale di sola lettura

La CLI è precisa, ma consultare numerosi file JSON e comandi può diventare scomodo.

DSL Manager possiede quindi una UI locale per l’ispezione.

Concettualmente:

````
Bash


```
dsl-manager ui serve <workspace>
```
````

e poi:

```
http://127.0.0.1:8765/
```

La UI permette di navigare:

- dashboard;
- run;
- dettagli delle run;
- log;
- candidati rifiutati;
- conflitti;
- snapshot;
- diff.

Queste rotte sono già presenti nell’implementazione della UI locale.

---

# 17. Perché la UI è di sola lettura?

La UI apre SQLite in modalità:

```
mode=ro
PRAGMA query_only = ON
```

e accetta soltanto richieste:

```
GET
HEAD
```

Rifiuta metodi di scrittura.

Questa scelta riduce il rischio che una pagina web locale:

- confermi accidentalmente candidati;
- modifichi decisioni;
- avvii merge;
- alteri il registry;
- crei divergenze rispetto alla CLI.

L’implementazione apre esplicitamente il database in sola lettura e abilita `query_only`; il router HTTP consente soltanto `GET` e `HEAD`.

Con la v02, le decisioni umane continuano quindi a passare dal servizio canonico di review e dai relativi comandi, anziché essere introdotte informalmente dalla vecchia UI.

---

# 18. La UI non è il motore della pipeline

È importante non confondere:

```
UI
```

con:

```
orchestratore
```

La UI mostra ciò che esiste nel workspace. Non è responsabile di:

- scansione;
- parsing;
- derivazione;
- review;
- merge;
- riconciliazione;
- rendering;
- export.

Questa separazione permette di chiudere la UI senza interrompere il processo e di usare DSL Manager interamente da CLI o automazione.

---

# 19. Esempio del viaggio osservato dall’esterno

Immaginiamo un batch completo:

```
RUN_000100 — batch
│
├── RUN_000101 — scan
│   └── completed: 4 revisioni attive
│
├── RUN_000102 — normalize manuale.pdf
│   └── completed: normalized.json + normalized.md
│
├── RUN_000103 — parse schema.sql
│   └── completed: 18 frammenti
│
├── RUN_000104 — derive
│   └── completed:
│       12 candidati
│       8 auto-confirmed
│       4 pending
│
├── RUN_000105 — merge
│   └── completed_with_skips:
│       8 merged
│       4 skipped_pending
│
└── RUN_000106 — reconcile
    └── completed: nessuna coda aperta
```

L’operatore può osservare:

## Dal report del batch

```
il risultato aggregato
```

## Dai report delle sub-run

```
il dettaglio strutturato di ogni fase
```

## Dai log

```
la cronologia degli eventi
```

## Dalla UI

```
una vista navigabile del workspace
```

## Dal registry

```
la storia persistente e autoritativa
```

## Dallo snapshot DSL

```
il modello effettivo risultante
```

Questi strumenti mostrano prospettive diverse dello stesso processo.

---

# 20. Il viaggio completo

A questo punto possiamo ricostruire l’intero programma.

```
STEP 1 — Custodia dei byte
file
  ↓
source
  ↓
source_revision con hash

STEP 2 — Osservazione
source_revision
  ↓
normalizzazione / parser / preflight
  ↓
chunk, frammenti, manifest, evidenza temporale grezza

STEP 3A — Derivazione deterministica
evidenza compatibile
  ↓
regola pura e versionata
  ↓
candidato tecnico

STEP 3B — Interpretazione AI
evidenze selezionate
  ↓
AI package
  ↓
AI esterna
  ↓
candidato interpretativo

STEP 4 — Governo
candidato valido pending
  ↓
review umana o policy autorizzata
  ↓
confirmed / rejected / superseded

STEP 5 — Materializzazione
foglia confirmed
  ↓
merge autoritativo
  ↓
facts, relations, supporti e intervalli

STEP 6 — Fotografia
viste effettive
  ↓
renderer
  ↓
snapshot DSL v2 immutabile

STEP 7 — Evoluzione
snapshot A + snapshot B
  ↓
diff strutturale, di governance e temporale

STEP 8 — Esplorazione
snapshot DSL
  ↓
GEXF statico o dinamico

STEP 9 — Osservabilità trasversale
batch + run + worker + report + log + UI
  ↓
processo controllabile, ripetibile e diagnosticabile
```

---

# La frase che riassume DSL Manager

DSL Manager non è semplicemente:

> “un convertitore di documenti in un DSL”.

È piuttosto:

> **un registro governato che trasforma byte versionati in affermazioni tracciabili, richiede una decisione prima di renderle autoritative e produce fotografie deterministiche ed esportabili dello stato effettivo della conoscenza.**

Oppure, nella forma più compatta:

```
byte
→ osservazione
→ proposta
→ decisione
→ conoscenza autoritativa
→ snapshot
→ confronto e visualizzazione
```

**Verifiche documentali**

- ✅ `nl -ba '.kb/documenti/documenti di design/run 2/design_document_v_02.md' | sed -n '488,599p'`
- ✅ `nl -ba '.kb/documenti/documenti di design/run 2/design_document_v_02.md' | sed -n '716,734p'`
- ✅ `nl -ba '.kb/documenti/manuali/manuale_utente_dsl_manager.md' | sed -n '126,173p'`
- ✅ `nl -ba '.kb/documenti/manuali/manuale_utente_dsl_manager.md' | sed -n '1134,1295p'`
- ✅ `nl -ba src/dsl_mngr/core/local_ui.py | sed -n '1,220p'`
- ✅ `git status --short` — nessun dato o file creato, modificato o cancellato.
