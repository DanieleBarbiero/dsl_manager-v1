# Guida completa — Laboratorio Vega Ricambi — PowerShell

Questa guida presume volutamente pochissimo. Se un passaggio sembra ovvio,
viene comunque spiegato. L'obiettivo non è dimostrare abilità con PowerShell:
è ottenere un test di DSL Manager che sia **ripetibile**, **diagnosticabile** e
abbastanza piccolo da poter essere eseguito spesso.

---

## 0. Cosa stai per fare, in una frase

Prenderai sei file fittizi, ne farai una copia in un workspace temporaneo,
registrerai le fonti, farai lavorare i parser appropriati, produrrai lo stato
governato di DSL Manager e controllerai che il risultato sia esportabile.

Il flusso mentale è:

```text
file
  -> source/revision
  -> parser appropriato
  -> chunk o fragment
  -> candidate
  -> review governata
  -> fact/relation
  -> snapshot DSL
  -> grafo / viste
```

**Un file non diventa automaticamente una verità.**
Lo scan registra una revisione. I parser producono evidenze. Le regole creano
candidati. Solo le policy autorizzate o una decisione umana possono promuoverli.

---

## 1. Perché Vega ha soltanto sei file

Aurora e Orione sono ottimi per la copertura, ma un corpus largo è costoso
quando vuoi sapere soltanto: "la pipeline di oggi funziona ancora?".

Vega usa questa matrice:

| File | Cosa collauda | Docling? | Operazioni attese |
|---|---|---:|---|
| `database/schema_vega.sql` | DDL | no | `parse_ddl` |
| `plsql/logica_vega.sql` | procedure/trigger | no | `parse_db_code` |
| `forms/frm_richiesta.xml` | Oracle Forms XML | no | `parse_xml_form` |
| `logs/vega_2026.log` | log applicativo | no | `parse_log` |
| `documenti/manuale_operativo_vega_2026.docx` | documento narrativo | **sì** | `normalize`, `chunk` |
| `documenti/matrice_priorita_vega_2026.xlsx` | workbook strutturato | **sì** | `normalize`, `chunk` |

Totale: **6 fonti, 8 operazioni di processing, 2 sole normalizzazioni Docling**.

Questa scelta non prova ogni formato supportato. Prova invece ogni **famiglia
di parser** della pipeline corrente con il minimo numero ragionevole di file.

---

## 2. Vocabolario minimo

### Repository
La directory del codice `dsl_manager-v1`.

### Fixture / corpus canonico
I sei file dentro questa cartella di laboratorio. Sono il materiale originale.
Non modificarli durante il test.

### Workspace
La directory operativa creata da DSL Manager. Contiene configurazione,
database, corpus copiato, artefatti, report, AI outbox/inbox ed export.

### Source
L'identità logica di una fonte.

### Revision
Una versione immutabile dei byte di una source. Se cambi il file e rifai scan,
deve apparire una nuova revisione.

### Chunk
Una porzione testuale localizzabile, tipicamente prodotta dopo normalizzazione.

### Fragment
Una porzione strutturale prodotta da parser specializzati come DDL, XML, log.

### Candidate
Una proposta. Non è ancora necessariamente vera.

### Fact / relation
Conoscenza materializzata dopo il governo della review.

### Run
Un'esecuzione auditabile con ID simile a `RUN_000123`.

### Snapshot DSL
Una fotografia immutabile del registro, con ID `DSL_...`.

---

## 3. La strada più semplice: usa il tutor interattivo

### 3.1 Apri PowerShell nella root del repository

La root corretta contiene almeno:

```text
AGENTS.md
pyproject.toml
.codex\
src\
```

Puoi controllare:

```powershell
Get-Item .\AGENTS.md, .\pyproject.toml, .\.codex\config.toml
```

Se uno dei tre manca, probabilmente sei nella cartella sbagliata.

### 3.2 Consenti lo script soltanto per questa finestra

```powershell
Set-ExecutionPolicy -Scope Process Bypass
```

`-Scope Process` significa: la modifica vale soltanto per questa sessione di
PowerShell. Non stai cambiando permanentemente la policy del computer.

### 3.3 Avvia lo script

Se la cartella Vega è stata messa, per esempio, sotto:

```text
.kb\projects\laboratorio_vega_ricambi\
```

esegui:

```powershell
.\.kb\projects\laboratorio_vega_ricambi\materiale_di_supporto\laboratorio_vega_ricambi_interattivo_v_02.ps1
```

Lo script:

1. trova la root;
2. legge `PROJECT_PYTHON` da `.codex\config.toml`;
3. verifica Python 3.12;
4. verifica che i sei file canonici esistano;
5. crea una directory di sessione;
6. salva `session_state.json`;
7. propone sempre come default il prossimo step incompleto.

Premere **Invio** al menu equivale a scegliere il percorso consigliato.

---

## 4. Salvataggio e ripresa

La sessione ha una directory separata dal workspace. Dentro trovi:

```text
session_state.json
logs\
journal.md
```

Dopo ogni cambiamento significativo lo stato viene salvato con sostituzione
atomica: prima si scrive un file temporaneo, poi lo si sostituisce.

Lo script stampa un comando simile a:

```powershell
.\laboratorio_vega_ricambi_interattivo_v_02.ps1 -Resume "C:\Users\...\session_state.json"
```

Per ripartire:

1. chiudi pure PowerShell;
2. riapri PowerShell;
3. torna nella root del repository;
4. imposta, se necessario, la policy `Process`;
5. incolla il comando di ripresa.

Non devi ricordare a quale fase eri arrivato. Lo stato contiene i passi
completati e gli ID osservati.

### Se hai cambiato il workspace

Prima che il workspace venga inizializzato puoi usare l'opzione **W** del menu.
Il nuovo percorso viene salvato immediatamente.

Dopo `init`/`db init`, lo script blocca il cambio di workspace. Questo non è un
capriccio: nel vecchio workspace esistono già database, revisioni, ID e report.
Cambiare soltanto la stringa del percorso farebbe sembrare che la sessione
continui, mentre in realtà starebbe puntando a un'altra storia.

Se desideri un altro workspace dopo l'inizializzazione, crea una **nuova
sessione**.

---

## 5. Come leggere l'output corto

Quando parte un comando vedrai qualcosa come:

```text
[004] Consolidamento
Comando: "...python.exe" -m dsl_mngr batch consolidate ...
Ancora in esecuzione... 30 s
Exit code: 0
Durata: 42.7 s
Run: RUN_000123
Status: completed
Report: artifacts/...
Log completo stdout: ...\004_consolidamento.stdout.log
```

Non vedrai il JSON completo.

Questo è intenzionale. Il JSON completo è nel log stdout. Gli errori completi
sono nel log stderr. `commands.jsonl` contiene metadati su ogni invocazione.

Se un comando fallisce, lo script mostra poche righe finali utili e ti indica
dove leggere il resto.

---

# PARTE II — Cosa fa ciascuna fase

## 6. Fase 1 — Preflight

### Cosa fa

Controlla senza mutare DSL Manager:

- root repository;
- interprete configurato;
- Python 3.12;
- esistenza dei sei file;
- checksum canonici.

### Perché

Se manca un file o usi il Python sbagliato, qualunque errore successivo diventa
ambiguo. Meglio fallire prima di creare database e artefatti.

### Problemi comuni

#### `PROJECT_PYTHON` assente

Non ripiegare automaticamente su `python`.

Il progetto dichiara un interprete preciso proprio per evitare che dipendenze
diverse producano risultati diversi.

#### Python non è 3.12

Correggi l'ambiente del repository. Non cambiare lo script per accettare una
versione casuale.

#### Checksum diverso

La fixture è stata modificata. Se la modifica è intenzionale, rigenera i
checksum come parte di una nuova versione della fixture. Se non lo è, ripristina
i file.

---

## 7. Fase 2 — Preparazione workspace

### Cosa fa

In ordine:

```text
dsl_mngr init
dsl_mngr db init
copia dei sei file
confronto hash
config review show
config review profiles
config review apply-profile conservative/1
config validate --profile conservative/1
```

### Perché copiare prima dello scan

Il corpus canonico deve rimanere immutabile. Tutte le prove devono accadere
nella copia del workspace.

### Perché applicare `conservative/1`

Un workspace nuovo parte prudente. Le policy automatiche non devono essere
inventate dalla shell. Il profilo built-in espone la decisione di governance in
modo versionato e verificabile.

### Se `init` dice che la directory esiste già

Non cancellarla automaticamente.

Hai due casi:

- è il workspace della stessa sessione: riprendi lo stato;
- è un workspace estraneo o vecchio: scegli un percorso nuovo / crea una nuova
  sessione.

---

## 8. Fase 3 — Doppio scan

Lo script esegue:

```powershell
python -m dsl_mngr corpus scan WORKSPACE
python -m dsl_mngr corpus scan WORKSPACE
```

### Primo risultato atteso

```text
Added: 6
Modified: 0
Deleted: 0
Unchanged: 0
```

### Secondo risultato atteso

```text
Added: 0
Modified: 0
Deleted: 0
Unchanged: 6
```

### Perché due volte

Il secondo scan è un test di idempotenza. Se nulla è cambiato, non deve
inventarsi nuove revisioni.

### Se il secondo scan mostra `Modified`

Fermati. Confronta gli hash della copia e della fixture. Non proseguire
"vedendo poi cosa succede", perché da quel momento i conteggi e gli ID non
rappresentano più il laboratorio canonico.

---

## 9. Fase 4 — Consolidamento

Comando:

```powershell
python -m dsl_mngr batch consolidate WORKSPACE --reconcile
```

Questa è la fase più pesante.

### Cosa deve succedere

Per i quattro file strutturali:

- DDL -> parser DDL;
- PL/SQL -> parser database code;
- XML -> parser Forms XML;
- `.log` -> parser log.

Per i soli due documenti:

- DOCX -> normalizzazione Docling + chunk;
- XLSX -> preflight/workbook + normalizzazione + chunk.

### Perché non ci sono PDF/PPTX/HTML/TXT/XLSM

Non perché non siano importanti. Perché lo scopo di Vega è controllare
rapidamente che la pipeline continui a funzionare.

Quando vuoi copertura formato-per-formato usa Aurora/Orione.

### Se Docling sembra fermo

Lo script emette soltanto heartbeat periodici.

Non significa che abbia smesso di lavorare.

Controlla:

- il file stdout del comando;
- il file stderr;
- il report di run;
- `run status` con l'ID reale.

Non lanciare cinque retry sovrapposti.

### Se il batch fallisce

Lo script prova a estrarre il `RUN_*` reale e te lo mostra. La strada
diagnostica è:

```powershell
python -m dsl_mngr run status WORKSPACE RUN_REALE
```

Se il run è effettivamente riprendibile, un solo tentativo:

```powershell
python -m dsl_mngr batch consolidate WORKSPACE --reconcile --resume RUN_REALE
```

Non usare un ID copiato da questa guida.

---

## 10. Fase 5 — Handoff AI, senza chiamare una AI

Lo scenario veloce verifica che DSL Manager sappia:

1. pianificare le evidenze;
2. creare un package;
3. scriverlo nell'outbox.

Comandi concettuali:

```powershell
python -m dsl_mngr ai evidence plan WORKSPACE --policy technical_extraction
python -m dsl_mngr ai evidence plan WORKSPACE --policy domain_interpretation
python -m dsl_mngr ai package WORKSPACE --selection-plan AISEL_REALE
```

### Cosa non fa Vega per default

Non invia il package a un modello esterno.
Non include una risposta AI congelata con ID fragili.

Questo evita che una minima modifica ai chunk renda il laboratorio "rotto" per
motivi che non riguardano la pipeline principale.

Se vuoi collaudare il replay AI completo, Orione rimane il laboratorio più
adatto.

### `package stale`

Un piano di evidenza fotografa uno stato. Se nel frattempo cambia una revisione
o un elemento rilevante, il package può essere rifiutato come stale.

La soluzione non è forzarlo. Crea un nuovo piano.

---

## 11. Fase 6 — Ispezione della review

Lo script chiede a DSL Manager l'elenco dei candidati pending.

Se ce ne sono, seleziona automaticamente **il primo** per mostrartelo.
Non ti chiede quale ID scegliere.

Il default è: **osserva e lascia pending**.

### Perché il default non approva

Un tutor può scegliere quale record mostrarti.
Non deve scegliere per te se un'affermazione di dominio sia vera.

Se vuoi provare `confirm`, `reject` o `correct`, usa il candidato realmente
mostrato e fornisci una motivazione consapevole.

---

## 12. Fase 7 — Reconcile

Lo script esegue il comando pubblico di riconciliazione.

Serve a verificare che lo stato effettivo sia coerente con le decisioni
correnti.

Non scrive SQL manuale nel database e non importa moduli interni.

---

## 13. Fase 8 — Snapshot DSL e grafo

Lo script produce uno snapshot schema 2 e ne ricava l'ID vero:

```powershell
python -m dsl_mngr dsl render WORKSPACE --schema-version 2 --output-dir exports/vega_v2
```

Poi:

```powershell
python -m dsl_mngr graph export WORKSPACE --snapshot-id DSL_REALE
```

### Se non trova `DSL_*`

Non inventarlo.

Apri il log stdout del render. Se il comando ha exit `0` ma il formato
dell'output è cambiato, il tutor deve essere aggiornato: il prodotto potrebbe
essere perfettamente funzionante.

---

## 14. Fase 9 — Log e UI locale

Il tutor esporta i log in HTML/CSV con i comandi pubblici.

Poi può fare uno smoke test della UI su `127.0.0.1` usando una porta libera.

Regole di sicurezza:

- solo loopback;
- non uccidere processi estranei;
- stdout/stderr della UI in file;
- chiudere il processo avviato dal tutor;
- se una porta è occupata, sceglierne un'altra.

Lo smoke test non pretende di verificare l'estetica della UI. Verifica soltanto
che alcune route rispondano.

---

## 15. Fase 10 — Chiusura

Alla fine:

1. rifai scan;
2. pretendi `Unchanged: 6`;
3. ricontrolla gli hash;
4. stampa i percorsi di:
   - stato;
   - workspace;
   - log;
   - export.

Non copiare il database del workspace dentro questa fixture.

---

# PARTE III — Procedura manuale minima

La procedura manuale è utile se vuoi capire cosa fa il tutor o se il tutor
stesso ha un bug.

## 16. Trova il Python del progetto

Dalla root:

```powershell
$config = Get-Content .\.codex\config.toml -Raw
$rel = [regex]::Match($config, '(?m)^\s*PROJECT_PYTHON\s*=\s*"([^"]+)"\s*$').Groups[1].Value
if (-not $rel) { throw "PROJECT_PYTHON non trovato" }

$PY = if ([IO.Path]::IsPathRooted($rel)) {
    (Resolve-Path $rel).Path
} else {
    (Resolve-Path (Join-Path $PWD $rel)).Path
}

& $PY --version
```

Se non ottieni Python 3.12, fermati.

---

## 17. Scegli un workspace nuovo

Esempio:

```powershell
$WS = Join-Path $env:TEMP ("vega_workspace_" + [guid]::NewGuid().ToString("N"))
```

Non è importante che sia in `%TEMP%`; è importante che sia nuovo e che tu
sappia dov'è.

---

## 18. Inizializza

```powershell
& $PY -m dsl_mngr init $WS
if ($LASTEXITCODE -ne 0) { throw "init fallito" }

& $PY -m dsl_mngr db init $WS
if ($LASTEXITCODE -ne 0) { throw "db init fallito" }
```

---

## 19. Copia le fonti

Imposta `$VEGA` al percorso reale della cartella `laboratorio_vega_ricambi`.

```powershell
$SOURCE = Join-Path $VEGA "corpus\active"
$DEST = Join-Path $WS "corpus\active"

Copy-Item -Path (Join-Path $SOURCE "*") -Destination $DEST -Recurse
```

Verifica gli hash. Il tutor lo fa automaticamente.

---

## 20. Applica il profilo review

```powershell
& $PY -m dsl_mngr config review show $WS
& $PY -m dsl_mngr config review profiles $WS
& $PY -m dsl_mngr config review apply-profile $WS --profile "conservative/1"
& $PY -m dsl_mngr config validate $WS --profile "conservative/1"
```

Se una versione corrente della CLI supporta `--expect-config-hash`, usa l'hash
ottenuto da `show` per proteggerti da modifiche concorrenti.

---

## 21. Scan e batch

```powershell
& $PY -m dsl_mngr corpus scan $WS
& $PY -m dsl_mngr corpus scan $WS
& $PY -m dsl_mngr batch consolidate $WS --reconcile
```

Il primo scan deve aggiungere 6 fonti. Il secondo deve lasciarne 6 invariate.

---

# PARTE IV — Errori spiegati senza abbreviazioni

## 22. `No installed Python found`

Questo messaggio viene normalmente dal launcher `py`, non necessariamente dal
Python configurato dal repository.

Per Vega non devi indovinare: usa `PROJECT_PYTHON`.

---

## 23. `workspace already exists`

Non significa "cancella la cartella".

Significa che stai cercando di inizializzare una directory che ha già una
storia. Riprendi quella sessione o scegline una nuova.

---

## 24. `database is not initialized`

Hai probabilmente saltato:

```powershell
python -m dsl_mngr db init WORKSPACE
```

Eseguilo sullo stesso workspace, non su un altro.

---

## 25. Secondo scan non idempotente

Possibili cause:

- hai modificato un file nella copia;
- un programma ha riscritto un file;
- hai copiato fonti diverse;
- stai puntando al workspace sbagliato.

Non "correggere" il database. Prima verifica i byte.

---

## 26. `config hash conflict`

Qualcuno o qualcosa ha modificato la configurazione tra lettura e scrittura.

Rileggi `config review show`, controlla il nuovo stato e decidi consapevolmente
se riapplicare il profilo.

---

## 27. Worker / Docling timeout

Non aumentare il timeout come prima reazione.

Prima conserva:

- run ID;
- stdout;
- stderr;
- process report;
- batch report.

Se il processo è ancora vivo, aspetta che termini.
Se è fallito ed è retryable, fai un solo resume controllato.

---

## 28. Output JSON enorme

È il motivo per cui il tutor non lo stampa.

Apri il file `.stdout.log` del comando specifico, oppure usa strumenti JSON sul
file. Non aumentare il buffer della console sperando di leggere tutto a mano.

---

## 29. Nessun candidato pending

Può essere perfettamente normale.

Il profilo conservativo può avere già gestito i candidati deterministici
ammessi. Non creare candidati finti solo per far apparire una schermata.

---

## 30. Exit code utili

La CLI corrente usa comunemente:

- `0`: successo;
- `2`: errore d'uso o fallimento operativo;
- `3`: rifiuto semantico/security di alcuni input controllati;
- `4`: conflitto o precondizione non soddisfatta;
- `6`: partial success controllato in scenari diagnostici.

Leggi sempre il report associato. Il numero da solo non racconta abbastanza.

---

# PARTE V — Fixture diagnostica opzionale

## 31. Workbook malformato

In:

```text
materiale_di_supporto\fixture_controllate\
```

c'è un file con estensione `.xlsx` che **non è un vero XLSX**.

Serve soltanto a verificare che il preflight rifiuti input palesemente
malformati.

Non copiarlo nel corpus normale.

L'uso di questa fixture deve avvenire in un workspace diagnostico separato,
così il test quotidiano non viene contaminato da un fallimento intenzionale.

---

# PARTE VI — Quando il test è riuscito

Vega è riuscito se, almeno:

- i sei hash canonici coincidono;
- primo scan: sei aggiunte;
- secondo scan: sei invariati;
- DDL, DB code, XML form e log vengono processati;
- DOCX e XLSX vengono normalizzati e chunkati;
- il consolidamento termina senza item falliti;
- il piano AI e il package possono essere creati;
- lo snapshot DSL schema 2 viene prodotto;
- il grafo viene esportato;
- log/UI sono interrogabili;
- scan finale: sei invariati;
- nessuna fonte canonica è stata modificata.

I conteggi di candidati/fatti/frammenti non sono fissati in questa versione del
laboratorio. Possono cambiare legittimamente mentre migliora l'estrazione.
Sono vincolanti invece il numero delle fonti, il routing dei parser, gli hash e
gli esiti strutturali sopra elencati.
