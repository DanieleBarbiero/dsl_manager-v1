Implementa solo la Slice 3 per DSL Manager v1.

Prima leggi e segui:
- `AGENTS.md`
- `.kb/documenti/documenti di design/run 1/design_document_v_01.md`
- `pyproject.toml`
- i moduli e i test già presenti per Slice 1 e Slice 2

Contesto:
Il progetto usa il package Python `dsl_mngr` con layout `src/`.
Le Slice 1 e 2 hanno già introdotto workspace, config, logging JSONL, SQLite e migrazioni minime.
Non modificare o riscrivere lateralmente queste parti se non è necessario per integrare la Slice 3.

Task:
Implementare la minima slice verticale funzionante per "corpus scan e source registry".

Scope:
- aggiungere il calcolo hash SHA-256 dei file sorgente, usando i byte originali
- implementare un `source_registry` per registrare fonti e revisioni nel database SQLite
- aggiungere un comando CLI verificabile per scansionare il corpus attivo
- rilevare file added, modified, deleted
- creare record in `sources`, `source_revisions` e `source_events`
- salvare nel database solo path relativi al workspace, normalizzati con `/`
- impedire path traversal fuori dal workspace
- aggiungere test deterministici con `pytest` e `tmp_path`

Comando CLI atteso:
- `dsl-manager corpus scan <workspace>`
- il comando deve scansionare di default la directory configurata in `corpus.active_dir`, normalmente `corpus/active`
- è accettabile aggiungere un flag opzionale `--path` o `--corpus-dir` per scansionare un path relativo diverso, purché resti dentro il workspace

Expected behavior:
- alla prima scansione, ogni file regolare dentro `corpus/active` genera:
  - una riga in `sources`
  - una riga in `source_revisions`
  - un evento `source_added`
- per una fonte nuova:
  - `source_id` deve essere leggibile, ad esempio `SRC_000001`
  - `source_revision_id` deve essere leggibile, ad esempio `REV_000001`
  - `logical_name` può essere il path relativo normalizzato
  - `source_type` deve essere `unknown`
  - `source_subtype` può essere `NULL`
  - `authority_level` deve essere `unknown`
  - `status` deve essere `active`
  - `current_revision_id` deve puntare alla revisione attiva
- se un file già registrato cambia contenuto:
  - il vecchio record in `source_revisions` viene marcato `superseded`
  - viene creata una nuova revisione con `revision_number` incrementato
  - `sources.current_revision_id` punta alla nuova revisione
  - viene creato un evento `source_modified`
- se un file registrato non è più presente nel corpus:
  - non cancellare record dal database
  - `sources.status` diventa `deleted_from_corpus`
  - la revisione corrente può essere marcata `deleted`
  - viene creato un evento `source_deleted`
- se un file non cambia:
  - non creare nuove revisioni
  - non creare eventi duplicati
  - è ammesso aggiornare `last_seen_at` / `updated_at`
- il comando CLI stampa un riepilogo leggibile, ad esempio:
  - `Added: N`
  - `Modified: N`
  - `Deleted: N`
  - `Unchanged: N`
- il comando deve fallire con errore leggibile se:
  - il workspace non è inizializzato
  - il database non è inizializzato/migrato
  - il path del corpus esce dal workspace

Constraints:
- non implementare normalizzazione documentale
- non implementare chunking
- non implementare parser DDL/XML/SQL/log
- non implementare AI package, inbox/outbox, candidate import o validation
- non implementare DSL renderer, diff, graph export o UI
- non implementare ancora il run lifecycle completo della Slice 4
- lasciare `source_events.run_id` a `NULL`, salvo esista già una utility minimale adatta
- non aggiungere ORM
- usare solo runtime dependencies della standard library
- mantenere separati CLI, logica core e persistenza
- usare import assoluti da `dsl_mngr`
- non modificare la migration esistente in modo incompatibile con database già migrati; se serve cambiare schema, aggiungere una nuova migration versionata

Test richiesti:
- `test_scan_initial_corpus`
  - inizializza workspace e database
  - crea file fixture in `corpus/active`
  - esegue il comando scan
  - verifica `sources`, `source_revisions`, `source_events`
  - verifica hash SHA-256, path relativi e output CLI
- `test_source_modified_cascade_minimal`
  - esegue una prima scansione
  - modifica il contenuto di un file
  - esegue una seconda scansione
  - verifica nuova revisione, vecchia revisione `superseded`, evento `source_modified`
- `test_source_deleted_event`
  - esegue una prima scansione
  - rimuove un file dal corpus
  - esegue una seconda scansione
  - verifica `deleted_from_corpus`, revisione marcata `deleted` ed evento `source_deleted`
- aggiungi eventuali test piccoli per path normalization o path traversal se necessari

Done when:
- la Slice 3 è implementata end-to-end
- il comando `dsl-manager corpus scan <workspace>` funziona
- i test della Slice 3 esistono e sono deterministici
- tutti i test passano con `python -m pytest`, usando però l’interprete configurato in `.codex/config.toml` come richiesto da `AGENTS.md`
- non sono state aggiunte funzionalità fuori scope
- viene mostrato il diff finale
- viene riportato il risultato dei test, indicando l’interprete usato

Prima di modificare codice:
1. leggi `.codex/config.toml` e ricava `PROJECT_PYTHON`
2. installa il progetto in editable mode con quell’interprete:
   `.\.venv\Scripts\python.exe -m pip install -e ".[dev]"`
3. dichiara brevemente i file che prevedi di toccare
4. implementa
5. esegui:
   `.\.venv\Scripts\python.exe -m pytest`
6. mostra diff e risultato dei test
7. riassumi cosa è stato aggiunto
