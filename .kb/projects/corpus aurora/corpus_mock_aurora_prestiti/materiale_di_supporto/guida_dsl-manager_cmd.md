# Guida per a `dsl-manager`

Questa guida accompagna una persona senza esperienza attraverso un ciclo completo:

```text
fonti grezze
  → registry locale
  → normalizzazione, chunk e frammenti
  → package per un'AI esterna
  → candidati restituiti dall'AI
  → validazione e merge
  → snapshot DSL e diff
  → grafo GEXF, log e UI locale
```

L'esempio usa il file `corpus_mock_aurora_prestiti.zip`, presente nella root del progetto. Il corpus descrive una piccola applicazione legacy Oracle Forms/PL/SQL per la gestione di prestiti personali.

## 1. Le tre idee da capire prima di iniziare

`dsl-manager` non chiede a un'AI di modificare direttamente il DSL.

Il suo funzionamento si basa su tre regole:

1. Il registry SQLite è la memoria primaria. Conserva fonti, revisioni, evidenze, candidati, fatti, relazioni, conflitti, run e snapshot.
2. I parser deterministici estraggono chunk o frammenti verificabili. Non trasformano automaticamente ogni elemento in conoscenza di dominio.
3. L'AI propone candidati. `dsl-manager` li accetta soltanto se citano un'evidenza letterale presente nel registry.

Il DSL, il diff e il grafo sono viste prodotte dal registry. Non sono la fonte primaria.

## 2. Che cosa contiene il corpus

Lo ZIP contiene:

- documentazione nuova e utile;
- documentazione vecchia ma ancora utile;
- documentazione nuova o vecchia non pertinente, inserita come rumore intenzionale;
- un dump DDL Oracle con quattro tabelle;
- tre semplici form esportate in XML;
- un trigger e due procedure PL/SQL nel sottoinsieme gestito dal parser;
- due log applicativi;
- un foglio XLSX utile ma non supportato dal batch v1;
- un inventario con classificazione e risultati attesi.

I dati sono tutti fittizi.

Le form XML sono facsimili leggibili, non file binari Oracle Forms `.fmb`.

## 3. Preparare il Prompt dei comandi e il progetto

Aprire il Prompt dei comandi (`cmd.exe`) nella root di `dsl_manager-v1`.

Il progetto richiede Python 3.12. In questo repository l'unico interprete corretto è quello indicato da `.codex/config.toml`:

```bat
chcp 65001 >nul
set "PY=%CD%\.venv\Scripts\python.exe"
"%PY%" --version
"%PY%" -m pip install -e ".[dev]"
```

Il primo comando deve mostrare Python 3.12.

In tutta la guida viene usato `"%PY%" -m dsl_mngr`. È equivalente al comando pubblico `dsl-manager`, ma evita di invocare per errore un Python globale.

## 4. Creare un workspace di laboratorio

Scegliere una directory nuova. Non riutilizzare un workspace che contiene già run o fonti, altrimenti gli identificativi saranno diversi dagli esempi.

```bat
set "WS=%CD%\laboratorio_aurora"
set "ZIP=%CD%\corpus_mock_aurora_prestiti.zip"

mkdir "%WS%"
"%PY%" -m zipfile -e "%ZIP%" "%WS%"
```

Inizializzare il workspace e il database:

```bat
"%PY%" -m dsl_mngr init "%WS%"
"%PY%" -m dsl_mngr db init "%WS%"
```

Il primo comando crea directory, configurazioni e log mancanti senza cancellare il corpus già estratto. Il secondo crea `workspace.sqlite` e applica le migrazioni.

Controllare la struttura:

```bat
dir "%WS%"
dir "%WS%\corpus\active" /s /b /a-d
```

Prima di processare le fonti è utile leggere:

```bat
type "%WS%\LEGGIMI_PRIMA.md"
type "%WS%\materiale_di_supporto\inventario_fonti.csv"
```

## 5. Registrare le fonti

Eseguire lo scan:

```bat
"%PY%" -m dsl_mngr corpus scan "%WS%"
```

In un workspace pulito il risultato atteso è:

```text
Added: 16
Modified: 0
Deleted: 0
Unchanged: 0
```

Lo scan:

- calcola l'hash dei byte originali;
- crea una `source` e una `source_revision`;
- salva percorsi relativi al workspace;
- registra eventi `source_added`, `source_modified` o `source_deleted`;
- non interpreta ancora il contenuto.

Rieseguendo subito lo stesso comando, le fonti devono risultare `Unchanged`.

## 6. Processare il corpus

Il modo più semplice è il batch:

```bat
"%PY%" -m dsl_mngr batch process-dir "%WS%"
```

Il comando pianifica automaticamente:

- `normalize` e `chunk` per Markdown, TXT, HTML e DOCX;
- `parse-ddl` per il dump SQL;
- `parse-xml-form` per le form;
- `parse-db-code` per trigger e procedure;
- `parse-log` per i log;
- `skipped` per XLSX, che non è gestito dal batch v1.

La normalizzazione usa Docling in modalità senza immagini e può richiedere diversi minuti, soprattutto alla prima esecuzione. Non chiudere il Prompt dei comandi mentre lavora.

Nel corpus fornito lo XLSX saltato è intenzionale e non rappresenta un errore. Il riepilogo atteso non deve contenere item `failed`.

Il comando stampa l'ID della run batch, per esempio `RUN_000001`, e il percorso del report. Aprirlo con:

```bat
type "%WS%\artifacts\runs\RUN_000001\batch_report.json"
```

Se l'ID è diverso, sostituirlo nel percorso.

## 7. Esplorare gli artefatti

I documenti normalizzati sono sotto `normalized`:

```bat
dir "%WS%\normalized" /s /b /a-d
```

Ogni revisione documentale può avere:

- `normalized.md`;
- `normalized.json`;
- `source_hash.txt`;
- `docling_report.json`.

I chunk sono sotto `chunks`:

```bat
dir "%WS%\chunks\chunks.jsonl" /s /b /a-d
```

Ogni riga di `chunks.jsonl` contiene un `chunk_id`, la revisione, il testo, gli offset e l'hash.

Le fonti strutturate producono frammenti sotto `fragments`:

```bat
dir "%WS%\fragments\fragments.jsonl" /s /b /a-d
```

I tipi principali che si possono incontrare sono:

- `ddl_table`, `ddl_column`, `ddl_constraint`;
- `xml_form`, `xml_field`, `xml_button`;
- `sql_trigger`, `sql_procedure`, `sql_statement`;
- `log_event`.

Un parser che termina correttamente non ha ancora creato fatti di dominio. Ha creato evidenze verificabili che potranno essere citate dai candidati.

## 8. Vedere lo stato senza interrogare SQLite

La UI locale è facoltativa e di sola lettura:

```bat
"%PY%" -m dsl_mngr ui serve "%WS%"
```

Aprire nel browser:

```text
http://127.0.0.1:8765/
```

Le viste mostrano run, log, candidati rifiutati, conflitti, snapshot e diff già prodotti.

La UI non avvia parser e non modifica il registry. Lasciare aperto il server solo durante la consultazione e interromperlo con `Ctrl+C`.

## 9. Preparare un package per l'AI

Tornare a un Prompt dei comandi libero e creare un package unico con tutte le evidenze attive:

```bat
"%PY%" -m dsl_mngr ai package "%WS%"
```

In un workspace pulito il primo package si chiama `AIPKG_000001`:

```text
laboratorio_aurora/
  ai/
    outbox/
      AIPKG_000001/
        instructions.md
        content.md
        source_manifest.json
        candidate_schema.json
        output_template.jsonl
        package_manifest.json
```

Leggere i file prima di passarli all'AI:

```bat
type "%WS%\ai\outbox\AIPKG_000001\instructions.md"
type "%WS%\ai\outbox\AIPKG_000001\content.md"
```

`content.md` contiene blocchi di evidenza con gli ID reali. `candidate_schema.json` descrive i campi ammessi. `output_template.jsonl` è soltanto un modello tecnico.

## 10. Chiedere i candidati a un'AI esterna

Caricare nell'AI i sei file del package, oppure fornire almeno:

- `instructions.md`;
- `content.md`;
- `candidate_schema.json`;
- `source_manifest.json`;
- `output_template.jsonl`.

La richiesta può essere:

```text
Analizza questo package in sola lettura.
Produci esclusivamente record JSONL conformi allo schema.
Usa soltanto evidenze presenti in content.md.
Copia esattamente source_revision_id, chunk_id o fragment_id.
evidence_text deve essere una sottostringa letterale dell'evidenza citata.

Individua:
- entità Cliente, PraticaPrestito, Rata e Pagamento;
- relazioni fra queste entità;
- stati e regole di approvazione;
- mapping fra concetti di dominio, tabelle e form;
- comportamenti di procedure, trigger e log;
- conflitti fra manuale storico e requisiti correnti;
- domande aperte quando l'evidenza è ambigua.

Non trasformare i documenti su mensa e parcheggio in fatti di dominio.
Restituisci soltanto JSONL, senza recinti Markdown e senza testo introduttivo.
```

Salvare la risposta come:

```text
laboratorio_aurora/ai/inbox/AIPKG_000001_candidates.jsonl
```

Ogni riga deve essere un oggetto JSON completo. Non usare un array JSON esterno e non inserire righe come ````json`.

### Esercizio senza un'AI

Per provare soltanto il meccanismo di andata e ritorno si può copiare il template:

```bat
copy /Y ^
  "%WS%\ai\outbox\AIPKG_000001\output_template.jsonl" ^
  "%WS%\ai\inbox\AIPKG_000001_candidates.jsonl"
```

Il template usa valori `REPLACE_*`: è tecnicamente valido, ma non produce un DSL semanticamente utile. Va bene solo per verificare la pipeline.

## 11. Controllare e importare la risposta

Controllare l'inbox:

```bat
"%PY%" -m dsl_mngr ai inbox scan "%WS%"
```

Importare il file collegandolo al package:

```bat
"%PY%" -m dsl_mngr ai import "%WS%" --package AIPKG_000001
```

L'output mostra:

- `Run`, la run di import;
- `Batch`, per esempio `CBATCH_000001`;
- numero totale;
- candidati accettati;
- candidati rifiutati.

Annotare il `CBATCH_*`: serve al merge.

L'import tramite `ai import` verifica anche che il package non sia diventato obsoleto. Il comando più generale:

```bat
"%PY%" -m dsl_mngr candidates validate "%WS%" --input "ai/inbox/un_altro_file.jsonl"
```

valida un file presente nel workspace, ma non applica il controllo di obsolescenza del package. Per il primo ritorno dall'AI è preferibile `ai import`.

## 12. Capire perché un candidato viene rifiutato

Le cause più comuni sono:

- JSON non valido;
- campo obbligatorio mancante;
- `source_revision_id` sconosciuto;
- `chunk_id` o `fragment_id` sconosciuto;
- evidenza appartenente a una revisione diversa;
- `evidence_text` non presente letteralmente nel chunk o frammento;
- `assertion_type` o `confidence` non ammessi.

La regola più importante è:

```text
evidence_text deve essere copiato, non parafrasato
```

I rifiuti restano nel registry per audit. Si possono vedere nella pagina `/rejected-candidates` della UI.

## 13. Fondere i candidati nel registry

Usare l'ID del batch restituito dall'import:

```bat
"%PY%" -m dsl_mngr facts merge "%WS%" --batch CBATCH_000001
```

Il merge è idempotente: rieseguire lo stesso batch non deve duplicare fatti o relazioni.

La versione corrente fonde nel registry:

- `candidate_fact`;
- `candidate_relation`.

I tipi `candidate_mapping`, `candidate_conflict` e `candidate_question` vengono validati e conservati come candidati, ma il merge v1 corrente li conta come `Skipped`. Questa è una limitazione dell'implementazione attuale, non un errore dell'utente.

Un conflitto può comunque nascere automaticamente quando due `candidate_fact` attribuiscono valori diversi alla stessa proprietà della stessa entità. Nel corpus, esempi utili sono:

- `PraticaPrestito.importo_massimo`: 50000 contro 60000 euro;
- `PraticaPrestito.stati_ammessi`: valori storici contro valori correnti;
- data di delibera manuale contro data di approvazione automatica.

## 14. Generare il primo snapshot DSL

Eseguire:

```bat
"%PY%" -m dsl_mngr dsl render "%WS%"
```

Il primo snapshot in un workspace pulito è `DSL_000001` e produce:

```text
exports/dsl/DSL_000001.json
exports/dsl/DSL_000001.yaml
exports/dsl/DSL_000001.md
```

Aprire la vista leggibile:

```bat
type "%WS%\exports\dsl\DSL_000001.md"
```

Verificare:

- entità e proprietà;
- relazioni;
- conflitti;
- `fact_id` e `relation_id`;
- riferimenti a fonte, revisione e chunk o frammento nella tracciabilità.

Se il DSL è vuoto ma i parser hanno prodotto frammenti, manca almeno uno fra import, validazione e merge.

## 15. Creare un secondo snapshot e un diff significativo

Chiedere all'AI una seconda risposta che aggiunga fatti o relazioni non presenti nel primo batch. Usare sempre gli ID e i testi del package.

Un record da adattare ha questa forma:

```json
{"record_type":"candidate_fact","candidate_id":"CAND_AURORA_100","source_revision_id":"REV_DA_COPIARE","chunk_id":"CHK_DA_COPIARE","fragment_id":null,"fact_type":"business_rule","entity_name":"PraticaPrestito","property_name":"importo_massimo","property_value":"60000 euro","assertion_type":"explicit","confidence":"high","evidence_text":"TESTO LETTERALE DA CONTENT.MD","notes":"Fonte corrente"}
```

Salvare i nuovi record in:

```text
ai/inbox/integrazione_aurora_candidates.jsonl
```

Validare, annotare il nuovo batch e fonderlo:

```bat
"%PY%" -m dsl_mngr candidates validate "%WS%" --input "ai/inbox/integrazione_aurora_candidates.jsonl"
"%PY%" -m dsl_mngr facts merge "%WS%" --batch CBATCH_000002
"%PY%" -m dsl_mngr dsl render "%WS%"
```

Il nuovo snapshot sarà normalmente `DSL_000002`.

Confrontare i due:

```bat
"%PY%" -m dsl_mngr dsl diff "%WS%" --from DSL_000001 --to DSL_000002
```

Gli output sono sotto:

```text
exports/dsl_diff/DSL_000001__DSL_000002.json
exports/dsl_diff/DSL_000001__DSL_000002.md
```

Se si renderizza due volte senza cambiare il registry, il diff con zero cambiamenti è corretto e dimostra la stabilità dell'hash.

## 16. Esportare il grafo

Esportare lo snapshot più recente:

```bat
"%PY%" -m dsl_mngr graph export "%WS%" --snapshot DSL_000002
```

Se esiste soltanto il primo snapshot, usare `DSL_000001`.

Il comando produce:

```text
exports/graph/DSL_000002.gexf
exports/graph/DSL_000002.graph_report.json
```

Il file GEXF può essere aperto con strumenti compatibili come Gephi.

Una relazione verso un'entità senza alcun fatto può generare un nodo `orphaned` e un warning. È utile creare prima almeno un `candidate_fact` per ciascuna entità citata dalle relazioni. L'opzione `--strict-orphans` trasforma questi warning in errore:

```bat
"%PY%" -m dsl_mngr graph export "%WS%" --snapshot DSL_000002 --strict-orphans
```

## 17. Esportare e leggere i log

Creare un visualizzatore HTML statico:

```bat
"%PY%" -m dsl_mngr log table "%WS%" --format html --output "exports/logs/app.html"
```

Creare un CSV:

```bat
"%PY%" -m dsl_mngr log csv "%WS%" --output "exports/logs/app.csv"
```

Gli output si trovano nel workspace. L'HTML non richiede un server e offre un semplice filtro testuale.

## 18. Provare revisioni e package obsoleti

Questa esercitazione è facoltativa e va eseguita dopo aver completato il ciclo principale.

Fare una copia del manuale storico:

```bat
set "MANUALE=%WS%\corpus\active\documenti\vecchi_utili\manuale_pratiche_2012.txt"
copy /Y "%MANUALE%" "%MANUALE%.bak"
"%PY%" -c "from pathlib import Path; import sys; p=Path(sys.argv[1]); p.write_text(p.read_text(encoding='utf-8') + '\nNota di revisione locale: limite storico da verificare.', encoding='utf-8')" "%MANUALE%"
"%PY%" -m dsl_mngr corpus scan "%WS%"
```

Lo scan deve mostrare una fonte modificata e creare una nuova revisione.

Un package creato prima della modifica può risultare `stale`:

```bat
"%PY%" -m dsl_mngr ai inbox scan "%WS%"
```

Per impostazione predefinita `ai import` blocca un package obsoleto. `--allow-stale` esiste per casi eccezionali, ma in un flusso normale è preferibile:

1. riprocessare la nuova revisione;
2. creare un nuovo package;
3. chiedere nuovi candidati;
4. importare il nuovo ritorno.

Il file `.bak` ha un'estensione non gestita e non va lasciato nel corpus durante ulteriori batch. Alla fine dell'esercizio ripristinare il file originale:

```bat
copy /Y "%MANUALE%.bak" "%MANUALE%"
del "%MANUALE%.bak"
"%PY%" -m dsl_mngr corpus scan "%WS%"
```

Questa cancellazione riguarda soltanto la copia di backup appena creata nel workspace di laboratorio.

## 19. Problemi frequenti

### Il batch è lento

La normalizzazione Docling viene eseguita in processi isolati. La prima esecuzione può essere lunga. Controllare il report batch e i file sotto `artifacts/runs`, senza rilanciare immediatamente lo stesso batch.

### Lo XLSX risulta `skipped`

È previsto. Il foglio dimostra che una fonte può essere utile alla modernizzazione ma non ancora supportata dalla pipeline automatica.

### Il package non contiene lo XLSX

È previsto: non esistono chunk o frammenti registrati per quella revisione.

### I parser hanno funzionato ma il DSL è vuoto

I parser producono evidenza, non conoscenza di dominio definitiva. Servono candidati validi, import, merge e render.

### `evidence_text_not_found`

Copiare una frase esattamente da un blocco di `content.md`. Anche differenze di punteggiatura o accenti possono causare il rifiuto.

### Il package è `stale`

Una fonte o una revisione inclusa è cambiata. Creare un nuovo package dopo aver riprocessato la revisione.

### Il grafo segnala nodi orfani

Una relazione cita un'entità che non compare fra i fatti. Aggiungere un fatto di tipo `business_entity` supportato da evidenza, importarlo, fonderlo e creare un nuovo snapshot.

### Gli indici Oracle non sono nel dump

È intenzionale. Il parser DDL v1 gestisce le tabelle, le colonne e i vincoli usati nell'esempio, ma `CREATE INDEX` non è ancora affidabile.

### Vedo caratteri accentati illeggibili

I file del corpus e della guida sono UTF-8. Nel Prompt dei comandi eseguire `chcp 65001 >nul` all'inizio della sessione, usare `type` per leggerli e salvare le risposte AI in UTF-8.

## 20. Checklist finale

Il ciclo è completo quando sono presenti:

- `workspace.sqlite`;
- fonti e revisioni registrate;
- documenti sotto `normalized`;
- chunk sotto `chunks`;
- frammenti sotto `fragments`;
- almeno un package sotto `ai/outbox`;
- una risposta sotto `ai/inbox`;
- un `CBATCH_*` importato e fuso;
- almeno uno snapshot sotto `exports/dsl`;
- un diff sotto `exports/dsl_diff`, se sono stati creati due snapshot;
- un GEXF sotto `exports/graph`;
- log HTML o CSV sotto `exports/logs`;
- tracciabilità dall'elemento DSL fino alla fonte originale.

Per una verifica più dettagliata confrontare il risultato con:

```text
materiale_di_supporto/checklist_risultati_attesi.md
```
