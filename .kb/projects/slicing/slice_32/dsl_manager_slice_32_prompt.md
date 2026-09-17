# Prompt Slice 32

<!--
Slice correttiva post-Slice 31.

Origine:
- collaudo del Laboratorio Vega Ricambi;
- stato reale del runtime su `main` dopo la Slice 31.

Questa slice NON deve essere trasformata in una collezione di workaround Vega.
Le fixture Vega sono una prova di regressione leggibile; le correzioni appartengono
al core generale di DSL Manager.

Il report della Slice 32 NON deve essere creato preventivamente. Deve nascere
soltanto dopo implementazione e collaudo reali, usando
`.kb/template/template_slice_report.md`.
-->

## Nucleo normativo della Slice 32

### Task

Implementare solo la **Slice 32 — integrità semantica cross-parser per eventi, codice database e Oracle Forms, con risoluzione strutturale e regressione Vega**.

La direttiva di prodotto è:

> una evidenza strutturata non deve diventare conoscenza effettiva con identità,
> scope o riferimenti inventati dal parser/derivatore; allo stesso modo, due
> osservazioni che rappresentano eventi distinti non devono essere trasformate
> in un falso conflitto soltanto perché condividono il componente che le ha
> emesse.

La Slice 32 chiude i problemi resi visibili dal Laboratorio Vega Ricambi:

1. gli eventi di log `start`, `processed`, `warning`, `end`, ecc. vengono oggi
   derivati come valori concorrenti della stessa proprietà persistente del
   componente e possono creare falsi conflitti;
2. il conflict engine applica in modo troppo generale
   `different_values_same_property`, senza una semantica esplicita di
   cardinalità/tipo dell'osservazione;
3. il parser del codice database può qualificare identificatori presenti in una
   subquery `SELECT` come se appartenessero alla tabella target dell'`UPDATE`,
   producendo dipendenze impossibili;
4. il derivatore delle dipendenze DB non usa il DDL attivo come barriera di
   coerenza per distinguere riferimenti risolti, non risolti e incompatibili con
   lo schema osservato;
5. il parser XML Forms riconosce il formato generico `<field ...>` ma non la
   forma Oracle-like `<block table="..."><item column="...">`, perdendo quindi
   mapping tabella/colonna presenti esplicitamente nella sorgente;
6. `button/@operation`, per esempio
   `operation="PRC_PRENOTA_ARTICOLO"`, non viene preservato e trasformato in una
   relazione di chiamata verso il codice database;
7. il round-trip AI deve essere blindato contro la regressione
   `ai import -> review -> reconcile -> render` senza `facts merge`.
   Il tutor Vega v13 contiene già la correzione
   `ai import -> review -> merge -> reconcile -> render`: la Slice 32 deve
   verificarla e proteggerla con una prova di regressione, non creare una
   seconda pipeline AI o un nuovo comando soltanto per il laboratorio.

La verticale richiesta è:

```text
log line
  -> log_event fragment
  -> candidate event con identità propria
  -> review/merge
  -> evento effettivo
  -> nessun conflitto con altri eventi dello stesso componente

DDL attivo + PL/SQL/SQL
  -> parser scope-aware
  -> riferimenti raw
  -> risoluzione strutturale
       resolved | unresolved | inconsistent
  -> candidate relation solo quando semanticamente ammissibile
  -> auto-review solo quando la risoluzione soddisfa il contratto

Oracle-like XML Form
  -> block/item normalizzati nel modello XML esistente
  -> mapping item -> table.column
  -> button operation preservata
  -> relazione FORM.BUTTON --calls--> DB_CODE_UNIT
  -> risoluzione coerente con DDL/code units

AI package/import
  -> human review
  -> merge del CBATCH importato
  -> reconcile
  -> render/export
```

Non implementare scorciatoie specifiche per nomi, file o ID di Vega.

---

## Scope

### In scope

- correzione dell'identità semantica degli eventi di log derivati;
- hardening generale del conflict engine tramite una semantica esplicita e
  deterministica delle proprietà/osservazioni;
- parsing scope-aware almeno per gli `UPDATE` con espressioni e subquery
  `SELECT` supportate dal parser corrente;
- gestione corretta di alias, parametri PL/SQL e pseudo-record `:NEW` / `:OLD`
  nei casi coperti;
- indice/servizio di risoluzione strutturale riusabile fra DDL, codice database
  e XML Forms;
- validazione delle dipendenze DB contro DDL/code units osservati quando tali
  autorità sono disponibili;
- supporto Oracle-like `<block>/<item>` nel parser XML Forms senza rompere il
  formato generico `<field>`;
- preservazione di `button/@operation`;
- derivazione esplicita di una relazione `calls` fra bottone e unità di codice;
- reason/status deterministici per riferimenti `resolved`, `unresolved` e
  `inconsistent`;
- test mirati e una regressione E2E minima basata sul significato reso visibile
  da Vega;
- verifica del round-trip AI corretto `import -> review -> merge -> reconcile ->
  render`;
- report Slice 32 creato soltanto dopo implementazione e test reali.

### Fuori scope

- riscrivere l'intero parser SQL con un parser universale o introdurre un AST
  engine pesante senza necessità dimostrata dal preflight;
- supportare in questa slice ogni costrutto SQL/PLSQL esistente;
- trasformare DSL Manager in un compilatore Oracle;
- introdurre euristiche probabilistiche, LLM, embeddings o rete per risolvere
  identificatori;
- cambiare il corpus Vega per far sparire i difetti del runtime;
- aggiungere `if scenario == Vega`, nomi hard-coded come `ARTICOLO`,
  `RICHIESTA_RICAMBIO`, `PRC_PRENOTA_ARTICOLO`, `BTN_PRENOTA` o simili nel
  package;
- introdurre una seconda pipeline AI, un secondo importer, un secondo merge o
  un comando di orchestrazione duplicato;
- cambiare il contratto temporale della Slice 31;
- modificare il profilo `conservative/1` della Slice 31 in modo implicito:
  quel profilo è versionato e immutabile;
- refactoring generalizzati non necessari alla verticale;
- modificare `.wb/` o usarla come fonte;
- aggiornare design, manuali generali o project summary soltanto per registrare
  l'esistenza della Slice 32 durante l'implementazione. Eventuali allineamenti
  documentali post-slice vanno separati dal runtime e riportati esplicitamente.

---

# Expected behavior

## A. Eventi di log: identità osservazionale, non stato persistente

Lo stato corrente di `log_event_observation/1` usa sostanzialmente:

```text
entity_name    = component
property_name  = event_kind
property_value = start|processed|warning|end|...
```

Questo trasforma osservazioni successive in valori concorrenti della stessa
proprietà.

### Contratto richiesto

1. Ogni evento deve avere una **identità semantica distinta e stabile** derivata
   da evidenza persistita, non dal solo componente.
2. L'identità deve essere deterministica a input invariato e deve distinguere
   almeno revisioni/frammenti differenti. Una forma ammessa è:

   ```text
   log_event:<source_revision_id>:<fragment_id>
   ```

   Un'altra forma è ammessa soltanto se usa gli stessi principi di stabilità,
   unicità e provenance ed è motivata nel report.
3. `component`, `timestamp`, `level`, `event_kind`, message e
   `observed_identifiers` restano attributi/provenance dell'evento; il
   componente non diventa l'identità dell'evento.
4. Due righe identiche nel significato ma osservate in due momenti/frammenti
   distinti restano due osservazioni distinte.
5. Il retry sulla stessa evidenza deve produrre la stessa candidate identity e
   non duplicare il fatto effettivo.
6. La derivazione non deve inventare una relazione al componente se il
   contratto corrente non la richiede. Una eventuale relazione
   `event --emitted_by--> component` è ammessa solo se il preflight dimostra che
   esiste già un vocabolario coerente e la sua introduzione resta minima.
7. Una sequenza:

   ```text
   scanner start
   scanner processed
   scanner warning
   scanner end
   ```

   deve produrre eventi distinti e **zero conflitti fra loro** soltanto perché
   `event_kind` differisce.
8. La provenance di ciascun evento deve continuare a puntare al proprio locator
   e frammento.

### Versionamento

Il preflight deve verificare se le regole `DerivationRule.rule_version` sono
considerate contratti semantici immutabili. Se il progetto richiede un bump per
questa correzione, creare una versione successiva della regola e aggiornare il
rule-set in modo controllato. Non cambiare silenziosamente un contratto
versionato se i documenti/test correnti lo vietano.

Il report deve registrare la decisione: `bugfix compatibile in-place` oppure
`nuova rule version`, con evidenza del contratto che la giustifica.

---

## B. Conflict engine: cardinalità e semantica esplicite

La correzione dell'identità degli eventi è la barriera primaria, ma il merge non
deve continuare ad assumere per sempre:

```text
stessa entity + stessa property + valore diverso = conflitto
```

per qualsiasi tipo di osservazione.

### Contratto richiesto

1. Introdurre una semantica deterministica e centralizzata almeno per:

   ```text
   single_value
   multi_value
   event
   ```

2. Il comportamento legacy resta il default per proprietà non classificate:

   ```text
   default = single_value
   ```

   così la Slice 32 non rende improvvisamente non conflittuali i fact storici.
3. `event` significa che osservazioni distinte non confliggono per la sola
   diversità del valore osservato.
4. `multi_value` significa che più valori possono coesistere per lo stesso
   soggetto/proprietà secondo il contratto dichiarato.
5. `single_value` mantiene il controllo di incompatibilità corrente.
6. La classificazione deve vivere in un catalogo/servizio riusabile e testabile,
   non in una catena di `if fact_type == ...: skip`.
7. Il catalogo deve avere ordine e serializzazione deterministici e, se esposto
   in artefatti/report, una versione esplicita.
8. Non è richiesto introdurre una migrazione DB se la semantica può essere
   determinata dal catalogo e dai fact esistenti. Una migrazione è ammessa solo
   se il preflight dimostra che è indispensabile.
9. Due veri fact `single_value` incompatibili devono continuare a produrre
   `different_values_same_property`.
10. Gli eventi di log non devono essere salvati da una eccezione speciale nel
    merge: devono essere corretti sia nell'identità sia nella semantica.

### Stato dei conflitti storici

Il preflight deve verificare cosa accade a conflitti già persistiti con la
vecchia semantica. Non cancellare storia.

Se il modello corrente possiede un meccanismo di reconcile/chiusura coerente,
usarlo o estenderlo minimamente per rendere chiudibili i conflitti che non sono
più validi secondo la semantica corrente. Se non esiste un contratto sicuro per
farlo, lasciare intatta la storia ma documentare chiaramente nel report che la
correzione impedisce nuovi falsi conflitti; non cancellare o riscrivere record
storici ad hoc.

---

## C. Parser DB code: scope SQL reale nelle subquery

Il parser corrente di `UPDATE` tratta molti identificatori non qualificati
nell'espressione come colonne della tabella target. Questo è errato quando
l'espressione contiene una subquery.

Esempio:

```sql
UPDATE ARTICOLO
SET QTA_DISPONIBILE = QTA_DISPONIBILE - 1
WHERE ID_ARTICOLO = (
    SELECT ID_ARTICOLO
    FROM RICHIESTA_RICAMBIO
    WHERE ID_RICHIESTA = P_ID_RICHIESTA
);
```

Il risultato NON può contenere:

```text
ARTICOLO.ID_RICHIESTA
ARTICOLO.RICHIESTA_RICAMBIO
```

### Contratto minimo scope-aware

1. Separare l'analisi dello scope `UPDATE` dagli scope `SELECT` annidati.
2. Individuare le subquery bilanciando parentesi e string literal, riusando gli
   helper correnti dove possibile.
3. Per ogni scope `SELECT`, estrarre almeno:
   - tabelle introdotte da `FROM`;
   - tabelle introdotte da `JOIN`;
   - alias;
   - colonne qualificate;
   - colonne non qualificate quando la risoluzione nello scope è
     deterministica.
4. Un nome introdotto da `FROM`, `JOIN`, `UPDATE`, `INTO` o come alias non può
   diventare una colonna letta.
5. Parametri PL/SQL non diventano colonne.
6. Supportare correttamente parametri con prefissi/forme già ammesse dal parser
   e i pseudo-record `:NEW` / `:OLD` dei trigger.
7. Le colonne nell'espressione `SET` restano nello scope dell'`UPDATE`, salvo
   sottoscope espliciti.
8. Le colonne nella subquery appartengono allo scope della subquery, salvo
   riferimenti correlati esplicitamente qualificati verso lo scope esterno.
9. Alias espliciti devono essere risolti al relativo oggetto senza lasciare
   l'alias come nome di tabella finale.
10. L'ordine di `reads` e `writes` deve restare deterministico.
11. Non peggiorare il caso semplice `UPDATE T SET A = A - 1`.
12. Non richiedere rete o parsing AI.
13. Non introdurre una dipendenza SQL/AST nuova senza:
    - verifica del supporto reale Oracle/PLSQL;
    - compatibilità Python 3.12;
    - licenza;
    - peso/runtime motivati;
    - confronto con l'estensione minima del parser esistente.
    La scelta deve essere documentata nel report prima di aggiungere la
    dipendenza.

### Minimo risultato Vega atteso

Per la procedura campione, il parser/derivazione deve poter rappresentare
almeno:

```text
PRC_PRENOTA_ARTICOLO writes_to ARTICOLO.QTA_DISPONIBILE
PRC_PRENOTA_ARTICOLO reads_from  ARTICOLO.QTA_DISPONIBILE
PRC_PRENOTA_ARTICOLO writes_to RICHIESTA_RICAMBIO.STATO
PRC_PRENOTA_ARTICOLO reads_from  RICHIESTA_RICAMBIO.ID_ARTICOLO
PRC_PRENOTA_ARTICOLO reads_from  RICHIESTA_RICAMBIO.ID_RICHIESTA
```

Il parametro `P_ID_RICHIESTA` non deve diventare una colonna.

Non fissare questi nomi nel codice: sono soltanto un acceptance example.

---

## D. Risoluzione strutturale condivisa: DDL ↔ DB code ↔ Forms

La Slice 32 deve introdurre una barriera generale fra "parser ha osservato una
stringa" e "derivatore può considerarla un riferimento strutturale affidabile".

### Indice di simboli osservati

Costruire o estendere un servizio core che, a partire da evidenze **attive**,
conosca almeno:

```text
database tables
database columns per table
database code units
```

Le fonti autoritative osservate sono almeno:

- fragment DDL attivi per tabelle/colonne;
- fragment DB code attivi per procedure/function/trigger supportati;
- le strutture XML devono consumare questo indice, non definirne la verità.

Il servizio deve essere deterministico, read-only durante la derivazione e
riusabile da più regole.

### Stati minimi

Ogni riferimento verificabile deve ricadere in uno dei tre stati:

```text
resolved
unresolved
inconsistent
```

Semantica:

- `resolved`: l'autorità disponibile conferma oggetto/colonna/unità;
- `unresolved`: manca copertura autoritativa sufficiente per confermare o
  smentire;
- `inconsistent`: esiste copertura autoritativa pertinente e il riferimento è
  incompatibile con essa.

Esempi generali:

```text
DDL contiene T(A) e target = T.A       -> resolved
DDL contiene T(A) e target = T.B       -> inconsistent
nessun DDL attivo per T e target T.B   -> unresolved
code unit P presente e button calls P  -> resolved
nessuna evidenza code-unit per P       -> unresolved
```

### Candidate behavior

1. `resolved` può seguire la normale policy di review della regola.
2. `unresolved` può essere conservato come candidato tracciabile ma **non deve
   essere auto-confermato** soltanto perché la rule è allowlisted.
3. `inconsistent` non deve diventare una relation effettiva affidabile:
   produrre un `DerivationIssue` stabile e non auto-materializzare il
   riferimento.
4. Il candidate payload/artefatto deve conservare, dove pertinente:
   - raw target;
   - canonical target;
   - resolution status;
   - resolution reason/basis;
   - evidence locator.
5. L'auto-review deve applicare una barriera candidate-level:
   una policy allowlisted non basta se il candidato dichiara uno stato
   strutturale che richiede review umana.
6. Non modificare `conservative/1` per includere silenziosamente nuove policy.
   Se la slice introduce nuove policy automatiche o una nuova combinazione
   sicura, usare una nuova versione/profilo soltanto se realmente necessario e
   documentarlo; altrimenti lasciare i nuovi candidati pending.
7. La risoluzione non deve dipendere da maiuscole/minuscole accidentali quando
   il parser corrente normalizza gli identificatori in modo case-insensitive.
8. Evitare false certezze: assenza di DDL non significa automaticamente che una
   colonna sia inesistente.

---

## E. Oracle Forms XML: `<block>/<item>` e `button/@operation`

Il parser corrente deve continuare a supportare il formato generico:

```xml
<form name="...">
  <field name="..." table="..." column="..." required="true" />
</form>
```

e aggiungere il formato Oracle-like:

```xml
<form name="FRM_RICHIESTA">
  <block name="RICHIESTA_RICAMBIO" table="RICHIESTA_RICAMBIO">
    <item name="ID_RICHIESTA" column="ID_RICHIESTA" required="true" />
  </block>
  <button
    name="BTN_PRENOTA"
    operation="PRC_PRENOTA_ARTICOLO"
  />
</form>
```

### Normalizzazione block/item

1. Non creare un secondo pipeline parser.
2. Normalizzare l'`<item>` nel modello strutturale già consumato dal derivatore
   quando questo è sufficiente.
3. Per ogni item conservare almeno:
   - `field_name` dall'item;
   - `column_name`;
   - `table_name` ereditata dal block;
   - `required`;
   - block name;
   - `source_element_kind = "item"`.
4. Un attributo table esplicito sull'item, se supportato, può prevalere sul
   block soltanto con una regola chiara e testata; una contraddizione non deve
   essere risolta silenziosamente.
5. Il locator deve distinguere blocco e item, per esempio:

   ```text
   /form[@name='...']/block[@name='...']/item[@name='...']
   ```

6. Item omonimi in blocchi diversi devono restare distinguibili.
7. `table_column_references` ed `edit_relations` devono includere i mapping
   realmente osservati negli item.
8. I mapping devono attraversare la barriera di risoluzione della sezione D.

### Button operation

1. Estendere il modello/metadata del bottone per conservare `operation`.
2. Un bottone senza `operation` non deve inventare una chiamata.
3. Introdurre una derivazione esplicita e versionata, preferibilmente:

   ```text
   xml_button_operation/1
   ```

4. La relazione canonica deve riusare il vocabolario già esistente:

   ```text
   FORM.BUTTON --calls--> DB_CODE_UNIT
   ```

   Non introdurre contemporaneamente `invokes` se `calls` è già il tipo usato
   dal codice database.
5. La relazione deve portare locator/provenance dell'elemento button.
6. Il target deve attraversare la risoluzione strutturale:
   `resolved | unresolved | inconsistent`.
7. La nuova regola deve partire pending salvo un contratto di auto-review
   esplicito e sicuro. Non aggiornare `conservative/1` implicitamente.

---

## F. Round-trip AI: regressione di orchestrazione, non nuova pipeline

Il problema osservato storicamente era:

```text
ai import
-> review
-> reconcile
-> render
```

senza materializzazione dei normali `candidate_fact` / `candidate_relation`.

La sequenza corretta è:

```text
ai import
-> review
-> facts merge del/dei CBATCH AI con candidate confirmed
-> facts reconcile
-> dsl render
-> graph export
```

### Requisiti Slice 32

1. Verificare nel preflight il tutor Vega più recente e il runtime corrente.
2. Se `laboratorio_vega_ricambi_interattivo_v_13.ps1` conserva già la sequenza
   corretta, **non creare un nuovo comando core** e non modificare il tutor
   soltanto per cambiare numero di versione.
3. Aggiungere una regressione automatica o uno smoke deterministico che dimostri
   che:
   - un candidate AI importato e confermato non compare nell'effettivo prima
     del merge;
   - dopo `facts merge` compare nell'effettivo;
   - `reconcile` non sostituisce `merge`;
   - pending e rejected non entrano nell'effettivo;
   - due CBATCH AI distinti restano tracciabili separatamente.
4. Se il tutor corrente fosse invece divergente, correggerlo dopo il core,
   preservando la versione precedente e aggiornando soltanto i materiali Vega
   strettamente necessari.
5. Non aggiungere una API "one click AI round-trip" in questa slice.

---

# Invarianti trasversali

La Slice 32 deve preservare:

- candidate-first;
- review prima della materializzazione;
- provenance completa;
- ID acquisiti dagli output/registry, non presunti;
- output deterministici;
- nessuna rete;
- nessuna macro/OLE/external link eseguita;
- nessun SQL diretto dalla CLI;
- nessuna scrittura ad hoc nel DB dai test E2E, salvo test mirati di schema se
  realmente necessari;
- compatibilità delle entry point `dsl-manager` e `python -m dsl_mngr`;
- comportamento temporale e multi-supporto della Slice 31;
- compatibilità Excel delle Slice 23-25;
- comportamento legacy dei parser generici non coinvolti;
- `conservative/1` immutabile.

Quando una correzione modifica expected/golden, l'expected deve essere derivato
dal contratto della Slice 32, non copiato dall'output ottenuto.

---

# Constraints

- Python `>=3.12,<3.13`.
- Layout `src/`; import assoluti da `dsl_mngr`.
- Usare il project interpreter definito da `AGENTS.md` per l'ambiente corrente.
- Su Windows/VS Code leggere `PROJECT_PYTHON` da `.codex/config.toml`.
- Installare editable prima delle modifiche:
  `<PROJECT_PYTHON> -m pip install -e ".[dev]"`.
- Riutilizzare parser, derivator, review, merge, reconciliation, registry e
  result catalog esistenti.
- Non modificare `.wb/`.
- Non cambiare fixture Vega per rendere verdi i test.
- Non nascondere riferimenti inconsistenti convertendoli in stringhe
  "unresolved" senza conseguenze sulla review.
- Non marcare `resolved` ciò che è soltanto sintatticamente ben formato.
- Non degradare un riferimento `inconsistent` a `unresolved` quando esiste
  autorità DDL sufficiente a smentirlo.
- Non considerare l'assenza di autorità come prova di inconsistenza.
- Non aggiungere dipendenze runtime se una estensione piccola e leggibile del
  codice esistente è sufficiente.
- Non fare refactoring cosmetico di moduli estranei.
- Non creare il report della Slice 32 prima della conclusione dei test.
- Non aggiornare la documentazione generale durante l'implementazione solo per
  dichiarare la slice presente.

---

# Done

La Slice 32 è completata soltanto quando tutte le condizioni seguenti sono vere:

1. eventi successivi dello stesso componente sono facts/eventi distinti e non
   generano falsi `different_values_same_property`;
2. un vero caso `single_value` incompatibile continua a generare conflitto;
3. il conflict engine usa una semantica centralizzata, non uno special-case
   `log_event`;
4. `UPDATE` semplice continua a funzionare;
5. `UPDATE` con subquery non attribuisce alla tabella target identificatori
   appartenenti allo scope interno;
6. parametri PL/SQL e `:NEW`/`:OLD` non diventano colonne spurie;
7. alias e colonne qualificate/non qualificate dei casi supportati sono risolti
   deterministicamente;
8. dipendenze DB sono classificate `resolved | unresolved | inconsistent`;
9. un target smentito da DDL attivo non diventa relation effettiva affidabile;
10. un target senza sufficiente autorità non viene falsamente dichiarato
    inesistente;
11. `<field>` legacy continua a funzionare;
12. `<block>/<item>` Oracle-like produce mapping tabella/colonna equivalenti;
13. `button/@operation` viene preservato;
14. il bottone può produrre una relation `calls` verso il code unit, con
    provenance e resolution status;
15. item omonimi in blocchi diversi hanno locator distinti;
16. l'auto-review non conferma candidate strutturalmente unresolved/inconsistent
    soltanto perché la policy è allowlisted;
17. il flusso AI dimostra `import -> review -> merge -> reconcile -> render`;
18. pending/rejected AI restano fuori dall'effettivo;
19. la fixture Vega non è stata modificata per mascherare i bug;
20. test mirati e suite completa passano con l'interprete corretto;
21. `git diff --check` passa;
22. il diff non contiene modifiche estranee;
23. il report Slice 32 viene creato dal template soltanto dopo il collaudo e
    registra esiti reali, deviazioni e limiti residui.

---

# Before coding

Prima della prima modifica:

1. leggere integralmente tutte le fonti obbligatorie sotto;
2. eseguire `git status --short` e preservare ogni modifica preesistente;
3. installare il progetto editable con l'interprete canonico;
4. ricostruire il percorso:
   `parser -> fragments -> derivation -> candidate import -> review -> merge ->
   conflict/reconcile -> render`;
5. censire tutte le regole e policy coinvolte:
   `log_event_observation`, `db_code_dependency`, `xml_form_structure`,
   `xml_table_usage` e relative automatic-review policy;
6. verificare il contratto di versionamento delle derivation rule;
7. censire tutte le chiamate a `_ensure_fact_conflicts` e il modo in cui fatti
   storici/conflicts vengono riconciliati;
8. censire il parsing SQL corrente di `UPDATE`, expression reads, alias,
   subquery e parametri;
9. censire il parsing XML corrente di `field`, `button`, locator e metadata;
10. verificare come il DDL attivo viene caricato oggi nel context di derivazione;
11. verificare il tutor Vega v13 e confermare se l'ordine AI è già corretto;
12. dichiarare nel report/piano di lavoro i file previsti prima di una patch
    sostanziale.

Il preflight deve classificare la slice:

```text
pronta
gap non bloccante
bloccata
```

Un gap non bloccante può cambiare il piano minimo ma non autorizza una
funzionalità fuori scope. Un conflitto progettuale non risolvibile con le fonti
obbligatorie blocca la relativa parte prima di inventare un nuovo contratto.

---

# Protocollo operativo comune obbligatorio

## 1. Autorità e ordine di precedenza

Applicare:

1. istruzioni esplicite dell'utente;
2. `AGENTS.md`;
3. questo prompt Slice 32;
4. design/documenti contrattuali canonici correnti;
5. codice e test correnti come evidenza del comportamento reale;
6. report e laboratori come evidenza storica/diagnostica.

La Slice 32 è una slice correttiva successiva al design originario: il design
v02 continua a governare i contratti delle capacità esistenti, mentre questo
prompt governa le correzioni qui elencate.

Quando runtime e documentazione divergono, non correggere gli expected in
silenzio. Registrare divergenza, autorità scelta e test che rende visibile la
decisione.

## 2. Letture obbligatorie complete

Leggere integralmente almeno:

```text
AGENTS.md
.codex/config.toml
.kb/template/template_slice.md
.kb/template/template_slice_report.md
.kb/documenti/project_summary.md
.kb/documenti/documenti di design/run 1/design_document_v_01.md
.kb/documenti/documenti di design/run 2/design_document_v_02.md
.kb/documenti/documenti tecnici/analisi_tecnica_dsl_manager.md
.kb/documenti/documenti tecnici/contratti_manifest_dsl_manager.md
.kb/documenti/manuali/manuale_utente_dsl_manager.md
.kb/projects/slicing/documenti tecnici/modifica_prompt_slice_v2.md
```

Leggere inoltre tutti i prompt e report reali da Slice 01 a Slice 31, con
particolare attenzione a:

```text
slice_06   merge/conflitti
slice_12   DDL
slice_13   XML Forms
slice_14   DB code e log
slice_20   review/materializzazione
slice_21   deterministic derivation
slice_22   consolidation
slice_27   evidence concordance / AI candidate handoff
slice_28   E2E
slice_30   AI evidence/package
slice_31   governance pubblica e stato corrente post-v12
```

Fonti Vega obbligatorie:

```text
.kb/projects/laboratorio_vega_ricambi/LEGGIMI_PRIMA.md
.kb/projects/laboratorio_vega_ricambi/materiale_di_supporto/DIAGNOSI_E_PIANO_CORREZIONI_VEGA.md
.kb/projects/laboratorio_vega_ricambi/materiale_di_supporto/checklist_risultati_attesi.md
.kb/projects/laboratorio_vega_ricambi/materiale_di_supporto/matrice_fixture_attesi.md
.kb/projects/laboratorio_vega_ricambi/materiale_di_supporto/limitazioni_intenzionali.md
.kb/projects/laboratorio_vega_ricambi/materiale_di_supporto/inventario_fonti.csv
.kb/projects/laboratorio_vega_ricambi/materiale_di_supporto/scenario_manifest.json
.kb/projects/laboratorio_vega_ricambi/materiale_di_supporto/laboratorio_vega_ricambi_interattivo_v_13.ps1
```

Leggere le sei fonti/corpus Vega pertinenti ai casi sopra senza modificarle
prima di aver riprodotto il problema.

Se una fonte obbligatoria manca, registrare il blocco. Non usare `.wb/` come
sostituto.

## 3. Preflight del codice

Ispezionare integralmente almeno:

```text
src/dsl_mngr/core/log_parser.py
src/dsl_mngr/core/db_code_parser.py
src/dsl_mngr/core/ddl_parser.py
src/dsl_mngr/core/xml_form_parser.py
src/dsl_mngr/core/candidate_derivation.py
src/dsl_mngr/core/candidate_validation.py
src/dsl_mngr/core/candidate_review.py
src/dsl_mngr/core/merge.py
src/dsl_mngr/core/reconciliation.py
src/dsl_mngr/core/batch_consolidation.py
src/dsl_mngr/core/dsl_renderer.py
src/dsl_mngr/core/graph_export.py
src/dsl_mngr/core/config.py
```

Ispezionare anche il registry/schema/migration solo per determinare se la Slice
32 richiede davvero una migrazione. Non aggiungerla per abitudine.

Usare `rg` per censire almeno:

```text
log_event_observation
different_values_same_property
_ensure_fact_conflicts
_extract_reads_from_expression
_analyze_update_statement
xml_form_structure
xml_table_usage
automatic_review_allowed
automatic_policies
resolution_status
facts merge
facts reconcile
ai import
```

## 4. Preflight dei test

Leggere integralmente almeno:

```text
tests/test_slice_06_fact_merge.py
tests/test_slice_12_parse_ddl.py
tests/test_slice_13_parse_xml_form.py
tests/test_slice_14_parse_db_code_log.py
tests/test_slice_20_candidate_review.py
tests/test_slice_20_migration_and_derivation.py
tests/test_slice_21_deterministic_derivation.py
tests/test_slice_22_batch_consolidation.py
tests/test_slice_27_ai_candidate_handoff.py
tests/test_slice_28_aurora_e2e.py
tests/test_slice_30_ai_evidence_selection.py
tests/test_slice_31_public_governance.py
```

Censire golden/fixture che dipendono dai payload delle regole coinvolte.

## 5. Ambiente

Su Windows/VS Code:

1. leggere `PROJECT_PYTHON` da `.codex/config.toml`;
2. usare esclusivamente quell'interprete;
3. verificare Python 3.12;
4. installare:

   ```powershell
   <PROJECT_PYTHON> -m pip install -e ".[dev]"
   ```

5. usare lo stesso interprete per pytest e CLI.

In Codex cloud seguire `AGENTS.md` e usare il runtime cloud previsto.

## 6. Piano minimo file-per-file

Il piano reale va ricavato dal preflight. Come baseline, aspettarsi modifiche
concentrate in:

```text
src/dsl_mngr/core/candidate_derivation.py
src/dsl_mngr/core/merge.py
src/dsl_mngr/core/db_code_parser.py
src/dsl_mngr/core/xml_form_parser.py
```

e, se utile per non duplicare logica:

```text
src/dsl_mngr/core/schema_resolution.py      # nuovo, solo se giustificato
src/dsl_mngr/core/conflict_semantics.py     # nuovo, solo se giustificato
```

oltre a test:

```text
tests/test_slice_32_semantic_integrity.py
tests/test_slice_32_vega_regression.py
```

Rafforzare i test Slice 13/14/21 soltanto dove serve a preservare contratti
storici.

Non creare moduli nuovi se due piccole funzioni in un modulo esistente
producono una separazione più chiara; non concentrare invece tre domini diversi
in un'unica funzione gigante soltanto per minimizzare il numero di file.

---

# Matrice minima dei test Slice 32

## 1. Log/event identity

Coprire:

- `start -> processed -> end` stesso component: 3 eventi, 0 conflitti;
- due eventi con stesso `event_kind` ma timestamp/fragments diversi: 2 eventi;
- retry stesso fragment: idempotente;
- provenance distinta;
- un vero `single_value` incompatibile continua a confliggere.

## 2. Conflict semantics

Coprire:

- `single_value`: conflitto;
- `multi_value`: coesistenza;
- `event`: coesistenza;
- tipo non catalogato: comportamento legacy `single_value`;
- nessuno special-case hard-coded soltanto per Vega.

## 3. DB parser

Coprire:

- UPDATE semplice;
- UPDATE con subquery SELECT;
- subquery con alias;
- JOIN nello scope interno;
- colonna qualificata;
- colonna non qualificata deterministica;
- riferimento correlato qualificato;
- parametro PL/SQL;
- `:NEW` / `:OLD`;
- nome tabella dopo FROM/JOIN mai trattato come colonna;
- funzione/keyword/alias mai trattati come colonna;
- ordine deterministico con input equivalente.

## 4. Structural resolution

Coprire:

```text
T.A con DDL T(A)       -> resolved
T.B con DDL T(A)       -> inconsistent
T.B senza DDL T        -> unresolved
call P con code unit P -> resolved
call P senza P         -> unresolved
```

Verificare che unresolved non passi auto-review automatica e inconsistent non
diventi relation effettiva.

## 5. XML Forms

Coprire:

- `<field table= column=>` legacy invariato;
- `<block table=><item column=>`;
- required metadata conservato;
- block/item locator;
- item omonimi in blocchi diversi;
- mapping resolved/inconsistent/unresolved;
- button con operation;
- button senza operation;
- operation resolved/unresolved;
- relation type `calls`.

## 6. AI round-trip

Coprire con API/CLI pubbliche:

- import candidate AI;
- review confirmed;
- prima del merge assenza dall'effettivo;
- merge del batch corretto;
- dopo merge presenza;
- reconcile successivo;
- pending/rejected esclusi;
- due batch distinti non confusi.

## 7. Vega regression

Usare il laboratorio come acceptance esterna, senza cambiare le fonti per
ottenere il risultato.

Invarianti minime:

```text
- i cinque eventi log restano cinque osservazioni distinte;
- nessun falso conflitto fra eventi successivi dello stesso componente;
- i quattro item del form sono riconosciuti e associati alla tabella corretta;
- BTN_PRENOTA conserva l'operation e produce la chiamata alla procedure osservata;
- il PL/SQL non produce target inesistenti come ARTICOLO.ID_RICHIESTA;
- il nome di tabella RICHIESTA_RICAMBIO non diventa ARTICOLO.RICHIESTA_RICAMBIO;
- un AI candidate confirmed viene materializzato via merge prima del render;
- pending/rejected restano fuori dall'effettivo.
```

Questi nomi appartengono al test di accettazione; non sono costanti di dominio.

---

# Esecuzione e chiusura

Dopo il preflight:

1. implementare la minima verticale completa;
2. eseguire test Slice 32 mirati;
3. eseguire i test storici direttamente coinvolti;
4. eseguire l'intera suite;
5. eseguire un smoke E2E su workspace temporaneo nuovo;
6. eseguire la regressione Vega senza mutare le fixture;
7. verificare entrambe le entry point se un comportamento CLI è stato toccato;
8. verificare exit code reali;
9. verificare `git diff --check`;
10. verificare `git diff --stat` e `git status --short`;
11. rileggere il diff completo per cambiamenti estranei;
12. soltanto allora creare:

   ```text
   .kb/projects/slicing/slice_32/dsl_manager_slice_32_report.md
   ```

   usando il template canonico.

Il report deve includere almeno:

- stato `completata | parziale | bloccata`;
- preflight e decisione sul versionamento delle derivation rule;
- decisione su migrazione sì/no e motivazione;
- decisione su dependency SQL nuova sì/no e motivazione;
- file modificati;
- conflict semantics effettivamente adottata;
- struttura del resolver e stati `resolved/unresolved/inconsistent`;
- esempi DB parser prima/dopo;
- contratto XML block/item e button operation;
- policy auto-review coinvolte e comportamento unresolved/inconsistent;
- verifica del tutor Vega v13;
- test mirati con conteggi reali;
- suite completa con conteggi reali;
- smoke Vega e invarianti osservate;
- eventuali golden modificati e giustificazione;
- diff/status;
- limiti residui.

Non dichiarare “completata” la Slice 32 se:

- i falsi conflitti vengono soltanto filtrati con un `if log_event`;
- il parser continua a qualificare token di subquery con la tabella dell'UPDATE;
- un riferimento smentito dal DDL può ancora auto-confermarsi;
- gli item Oracle vengono gestiti trasformando la fixture Vega;
- `operation` viene conservata ma non è tracciabile come relazione candidata;
- il test AI salta il merge;
- la suite passa soltanto modificando expected per imitare il runtime difettoso.

---

# Criterio finale di accettazione

Un corpus misto che contenga DDL, PL/SQL, XML Forms e log deve poter essere
processato senza che DSL Manager confonda:

```text
evento        != stato persistente del componente
table name    != column name
PL/SQL param  != database column
inner SELECT  != UPDATE target scope
unresolved    != invalid
inconsistent  != unresolved
button action != semplice label
review        != merge
reconcile     != merge
```

e deve conservare per ogni conoscenza effettiva una catena verificabile:

```text
source bytes
  -> parser output
  -> fragment + locator
  -> candidate + resolution
  -> review
  -> merge
  -> effective fact/relation
  -> DSL / graph
```

La fixture Vega serve a rendere questi invarianti facili da vedere; la soluzione
deve restare generale anche quando Vega non esiste.
