# Report Slice 32

Stato: **parziale**.

La verticale runtime richiesta dalla Slice 32 è implementata e i test mirati,
storici direttamente coinvolti e tutti i test eseguibili con le risorse presenti
sono verdi. La slice non viene dichiarata `completata` perché l'esecuzione non
filtrata della suite resta bloccata da risorse canoniche Aurora assenti dal
repository corrente: 11 test delle Slice 28-29 terminano con
`FileNotFoundError` prima di esercitare il runtime della Slice 32.

## Preflight e autorità

- Interprete canonico letto da `.codex/config.toml`:
  `.\.venv\Scripts\python.exe`, Python `3.12.10`.
- Install editable eseguita prima delle modifiche con
  `.\.venv\Scripts\python.exe -m pip install -e ".[dev]"`.
- Stato Git iniziale pulito; `HEAD` e `origin/main` erano entrambi
  `1164154` (`lab 13`).
- Ricostruito il percorso
  `parser -> fragment -> derivation -> candidate import -> review -> merge -> reconcile -> render/export`.
- Letti i contratti, i prompt/report storici, i moduli core, i test indicati e
  le sei fonti Vega senza usare `.wb/`.
- Il file obbligatorio
  `.kb/projects/laboratorio_vega_ricambi/materiale_di_supporto/DIAGNOSI_E_PIANO_CORREZIONI_VEGA.md`
  non è presente. Il gap è stato classificato non bloccante per la verticale
  runtime perché il prompt Slice 32, i contratti canonici, il codice, i test e
  le altre fonti Vega definivano il comportamento senza ambiguità. Il file non
  è stato inventato né sostituito con materiale `.wb/`.
- Il tutor Vega v13 conteneva già la sequenza corretta; non è stato modificato
  e non è stato aggiunto un comando di orchestrazione alternativo.

## Decisioni di progetto

### Versionamento delle derivation rule

Le rule `/1` sono contratti immutabili. Sono rimaste leggibili ed eseguibili
senza modifica semantica. Le correzioni sono state introdotte con:

- `log_event_observation/2`;
- `db_code_dependency/2`;
- `xml_form_structure/2`;
- `xml_table_usage/2`;
- nuova `xml_button_operation/1`.

`db_code_unit/1` non è stata cambiata perché la sua semantica non richiedeva una
correzione. La mappa di consolidamento usa le versioni nuove per i parser
coinvolti. Il profilo built-in `conservative/1` e le sue 13 policy non sono
stati modificati; le nuove rule riusano una policy esistente solo per candidati
strutturalmente `resolved`, mentre `xml_button_operation/1` nasce pending.

### Migrazione e dipendenze

- **Migrazione DB:** no. Gli stati di risoluzione restano nel payload candidato
  e la semantica dei conflitti è risolta da un catalogo core versionato.
- **Nuova dipendenza SQL/AST:** no. Il parser esistente è stato esteso con scope,
  bilanciamento delle parentesi e risoluzione degli alias; non era giustificato
  introdurre un parser universale o una dipendenza runtime pesante.
- `pyproject.toml` e schema v12 restano invariati.

## Implementazione

### Eventi e conflict semantics

`log_event_observation/2` usa l'identità:

```text
log_event:<source_revision_id>:<fragment_id>
```

L'identità è stabile al retry e distinta fra frammenti. `component`, timestamp,
level, event kind, message e identificatori osservati restano nel candidato e
nella relativa provenance.

Il nuovo catalogo `conflict_semantics` versione `1` applica:

```text
default                         -> single_value
entity_alias/*                  -> multi_value
log_event/*                     -> event
```

Il merge crea `different_values_same_property` soltanto quando entrambi i fact
coinvolti sono `single_value`. Non esiste uno special-case Vega o un
`if log_event` nel merge. Un vero stato business incompatibile continua a
generare conflitto.

I conflitti storici non sono stati cancellati o riscritti: il modello corrente
non espone un contratto sicuro per reinterpretarli semanticamente. La correzione
impedisce la creazione di nuovi falsi conflitti.

### Parser DB scope-aware

L'analisi di `UPDATE` ora:

- separa `SET` e `WHERE` allo scope superiore;
- individua subquery `SELECT` bilanciando parentesi e string literal;
- costruisce scope locali da `FROM` e `JOIN`;
- risolve alias locali e riferimenti correlati qualificati;
- non trasforma nomi di tabella, alias, keyword o funzioni in colonne;
- esclude i parametri PL/SQL dalle colonne lette;
- conserva `:NEW` e `:OLD` come pseudo-record del trigger, poi il derivatore li
  esclude dalle relazioni database-column;
- mantiene ordine deterministico e compatibilità con l'`UPDATE` semplice.

Riproduzione Vega prima della correzione:

```text
P_ID_RICHIESTA
ARTICOLO.ID_RICHIESTA
ARTICOLO.RICHIESTA_RICAMBIO
```

venivano esposti come letture spurie. Dopo la correzione, le relazioni minime
osservate includono:

```text
PRC_PRENOTA_ARTICOLO writes_to ARTICOLO.QTA_DISPONIBILE
PRC_PRENOTA_ARTICOLO reads_from ARTICOLO.QTA_DISPONIBILE
PRC_PRENOTA_ARTICOLO writes_to RICHIESTA_RICAMBIO.STATO
PRC_PRENOTA_ARTICOLO reads_from RICHIESTA_RICAMBIO.ID_ARTICOLO
PRC_PRENOTA_ARTICOLO reads_from RICHIESTA_RICAMBIO.ID_RICHIESTA
```

I tre target spuri sopra non compaiono.

### Risoluzione strutturale

Il nuovo `StructuralIndex` read-only viene costruito deterministicamente dai
fragment attivi:

- `ddl_table`;
- `ddl_column`;
- `sql_function`;
- `sql_procedure`;
- `sql_trigger`.

Il resolver restituisce raw target, canonical target, status, reason e basis:

```text
resolved      autorità attiva conferma il riferimento
unresolved    autorità insufficiente, senza inferire inesistenza
inconsistent  DDL pertinente presente ma incompatibile
```

Un riferimento `inconsistent` produce un
`structural_reference_inconsistent` e non una candidate relation. Un
`unresolved` resta candidato tracciabile ma la barriera candidate-level di
`CandidateReviewService` e il consolidamento automatico ne impediscono la
conferma automatica. La sola allowlist della policy non basta.

### Oracle Forms XML

Il parser unico XML continua a gestire `<field>` e normalizza anche:

```xml
<block name="..." table="...">
  <item name="..." column="..." required="..." />
</block>
```

Per ogni item conserva field/column/table, required, block name e
`source_element_kind = item`. Il locator include block e item, quindi item
omonimi in blocchi diversi restano distinti. Una `table` esplicita sull'item è
accettata solo se coerente con quella del block; una contraddizione genera
errore di parsing.

`button/@operation` viene conservato. `xml_button_operation/1` produce:

```text
FORM.BUTTON --calls--> DB_CODE_UNIT
```

con locator, provenance e stato strutturale. Un bottone senza operation non
inventa una chiamata.

### Round-trip AI

La regressione usa API pubbliche e due CBATCH distinti:

```text
AI import -> human review -> merge -> reconcile -> DSL v2 render -> GEXF export
```

Verifica che:

- i candidati confirmed non siano effettivi prima del merge;
- dopo il merge siano effettivi;
- reconcile non sostituisca merge;
- pending e rejected restino fuori dall'effettivo;
- i due batch conservino identità e provenance separate;
- lo snapshot DSL v2 e il GEXF dinamico siano prodotti dopo il merge.

Il tutor
`laboratorio_vega_ricambi_interattivo_v_13.ps1` è stato verificato testualmente:
`facts merge` precede `facts reconcile`, che precede `dsl render`, che precede
`graph export`.

## Regressione Vega

La prova crea un workspace temporaneo, registra tutte le sei fonti canoniche e
processa i quattro formati direttamente pertinenti a questa slice. Le fonti
originali non vengono scritte.

Esito osservato:

- 5 righe log -> 5 eventi con identità e provenance distinte;
- retry della stessa evidenza -> stessi candidate ID e 5 fact effettivi, senza
  duplicazione;
- 0 conflitti fra gli eventi;
- 4 item Oracle riconosciuti e associati alle colonne DDL corrette;
- `BTN_PRENOTA` conserva `PRC_PRENOTA_ARTICOLO` e produce una relation `calls`
  `resolved`;
- tutte le dipendenze DB Vega prodotte dalla rule `/2` sono `resolved`;
- nessun target spurio `P_ID_RICHIESTA`, `ARTICOLO.ID_RICHIESTA` o
  `ARTICOLO.RICHIESTA_RICAMBIO`;
- il ciclo AI materializza soltanto i due candidati confermati;
- snapshot DSL v2 e GEXF dinamico prodotti con successo.

Gli SHA-256 delle sei fonti coincidono con
`materiale_di_supporto/checksums.json` prima e dopo la prova.

## File modificati o aggiunti

```text
M  src/dsl_mngr/core/batch_consolidation.py
M  src/dsl_mngr/core/candidate_derivation.py
M  src/dsl_mngr/core/candidate_review.py
M  src/dsl_mngr/core/db_code_parser.py
M  src/dsl_mngr/core/merge.py
M  src/dsl_mngr/core/xml_form_parser.py
A  src/dsl_mngr/core/conflict_semantics.py
A  src/dsl_mngr/core/schema_resolution.py
A  tests/test_slice_32_semantic_integrity.py
A  tests/test_slice_32_vega_regression.py
A  .kb/projects/slicing/slice_32/dsl_manager_slice_32_report.md
```

Nessuna fixture, golden, fonte Vega, configurazione, migrazione, dipendenza,
tutor o documento generale è stato modificato.

Il `git diff --stat` dei sei file già tracciati, prima del report e senza i
nuovi file non ancora tracciati, riportava:

```text
6 files changed, 720 insertions(+), 27 deletions(-)
```

## Test e verifiche

Interprete usato:

```text
.\.venv\Scripts\python.exe
Python 3.12.10
```

Install editable:

```powershell
.\.venv\Scripts\python.exe -m pip install -e ".[dev]"
```

### Test Slice 32 finali

```powershell
.\.venv\Scripts\python.exe -m pytest -q `
  tests/test_slice_32_semantic_integrity.py `
  tests/test_slice_32_vega_regression.py
```

```text
5 passed in 22.16s
```

### Test storici direttamente coinvolti

Eseguiti Slice 06, 12, 13, 14, 20, 21, 22, 27, 31 e 32:

```text
56 passed in 189.32s
```

### Suite completa non filtrata

```powershell
.\.venv\Scripts\python.exe -m pytest -q
```

```text
205 passed, 11 failed in 734.90s
```

Tutti gli 11 failure sono accessi a file assenti sotto:

```text
.kb/projects/corpus aurora/corpus_mock_aurora_prestiti/
```

In particolare mancano il corpus active, `checksums.json`, la fixture malformed
e le guide v02. La directory non compare in `HEAD` né nel workspace corrente.
Non sono stati creati surrogati o modificati test storici per mascherare il
blocco.

### Tutti i test eseguibili con le risorse presenti

Eseguita la stessa suite deselezionando esclusivamente gli 11 node ID che
falliscono sui file Aurora assenti:

```text
205 passed, 11 deselected in 1074.57s
```

### Verifiche aggiuntive

- `git diff --check`: exit code `0`; solo avvisi informativi Git LF/CRLF.
- `.\.venv\Scripts\python.exe -m compileall -q ...`: exit code `0`.
- `.\.venv\Scripts\dsl-manager.exe --help`: exit code `0`.
- `.\.venv\Scripts\python.exe -m dsl_mngr --help`: exit code `0`.
- ricerca dei nomi Vega nel package `src/`: nessun nome scenario-specifico.
- nessun accesso di rete nei test Slice 32.

## Limiti residui e chiusura

- Il parser SQL resta intenzionalmente bounded: copre gli `UPDATE`, gli scope
  `SELECT`, alias, JOIN, parametri e pseudo-record richiesti; non è un parser
  universale Oracle/PLSQL.
- I conflitti storici non vengono eliminati automaticamente; manca un contratto
  sicuro per reinterpretare e chiudere record preesistenti senza riscrivere la
  storia.
- Il file diagnostico Vega obbligatorio indicato dal prompt non è presente.
- La suite completa non può diventare verde finché non viene ripristinato il
  corpus/supporto Aurora canonico. Per questo la Slice 32 resta `parziale`
  nonostante la verticale implementata e tutti i test disponibili verdi.

