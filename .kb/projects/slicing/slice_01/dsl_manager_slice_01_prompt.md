Implementa solo la Slice 1 per DSL Manager v1.

Prima di iniziare, leggi e segui:
- `AGENTS.md`
- `.kb/documenti/documenti di design/run 1/design_document_v_01.md`

Task:
Implementare la minima vertical slice funzionante per "inizializzare un workspace locale con config e logging".

Scope:
- creare il codice minimo necessario per supportare un comando CLI `dsl-manager init`
- mantenere compatibile anche `python -m dsl_mngr init`
- creare una struttura workspace locale valida
- generare file di configurazione iniziali
- implementare un loader di configurazione minimale
- implementare logging JSONL applicativo
- aggiungere un comando base per esportare/visualizzare i log in formato tabellare semplice
- aggiungere test automatici per il comportamento implementato

Expected behavior:
- `dsl-manager init <workspace>` crea il workspace se non esiste
- se `<workspace>` non viene passato, il comando inizializza il workspace nella directory corrente
- il workspace contiene almeno:
  - `.env`
  - `configs/project.yaml`
  - `configs/workers/`
  - `corpus/incoming/`
  - `corpus/active/`
  - `corpus/deleted/`
  - `corpus/ignored/`
  - `ai/outbox/`
  - `ai/inbox/`
  - `ai/imported/`
  - `artifacts/runs/`
  - `exports/dsl/`
  - `exports/dsl_diff/`
  - `exports/graph/`
  - `exports/logs/`
  - `logs/app.jsonl`
- `configs/project.yaml` contiene una configurazione minima coerente con il design v2
- `.env` contiene valori di default coerenti con il workspace locale
- il loader config applica una precedenza minimale:
  - default interni
  - `configs/project.yaml`
  - `.env`
  - opzioni CLI, dove già presenti
- il logging scrive record JSONL validi in `logs/app.jsonl`
- ogni record JSONL contiene almeno:
  - timestamp ISO 8601
  - level
  - event
  - message
  - `run_id`, se disponibile
  - worker, se disponibile
- il comando base di log table legge `logs/app.jsonl` e produce una tabella leggibile o un CSV/HTML minimale, scegliendo la soluzione più piccola e testabile

Constraints:
- non implementare SQLite, migrazioni, registry, source scan, candidate import, merge, renderer DSL o diff
- non implementare Docling, parser DDL/XML/SQL/log o handoff AI
- non aggiungere web UI, API, auth o integrazioni esterne
- non usare ORM
- non aggiungere dipendenze runtime se la standard library è sufficiente
- se serve YAML, preferire un formato minimale scrivibile/leggibile senza introdurre complessità; se viene aggiunta una dipendenza, motivarla chiaramente
- mantenere separati CLI, config, logging e workspace setup
- usare import assoluti dal package `dsl_mngr`
- non importare mai da `src`
- mantenere l’implementazione piccola, leggibile e deterministica
- i test devono usare `tmp_path`
- i test non devono dipendere da path assoluti o dallo stato della macchina locale

Suggested modules:
- `src/dsl_mngr/cli/app.py`
- `src/dsl_mngr/cli/commands/init.py`
- `src/dsl_mngr/cli/commands/log.py`
- `src/dsl_mngr/core/config.py`
- `src/dsl_mngr/core/logging_setup.py`
- `src/dsl_mngr/core/workspace.py`

Questi nomi sono suggeriti: adatta la struttura se il repository esistente richiede una soluzione più semplice, ma mantieni chiari i confini tra CLI, core config, logging e workspace.

Tests:
- `test_init_workspace`
- `test_load_config_precedence`
- `test_jsonl_log_record`
- un test smoke per `python -m dsl_mngr init <tmp_path>`
- un test per il comando log table/export minimale

Done when:
- `dsl-manager init` o l’equivalente entry point configurato crea un workspace valido
- `python -m dsl_mngr init <workspace>` funziona
- la config minima viene creata e caricata
- il logging JSONL produce record validi
- il comando log table/export base funziona su log JSONL validi
- i test pertinenti esistono
- `python -m pytest` passa con l’interprete corretto indicato da `AGENTS.md`
- nessuna feature fuori scope della v1 è stata aggiunta

Prima di modificare codice:
1. ispeziona `.codex/config.toml`, se presente, e usa `PROJECT_PYTHON` come unico interprete Python valido in ambiente VS Code Windows
2. installa il progetto con l’interprete corretto:
   `python -m pip install -e ".[dev]`
   riscrivendo il comando secondo `AGENTS.md`
3. dichiara brevemente i file che prevedi di toccare

Poi:
1. implementa la slice
2. aggiungi o aggiorna i test
3. esegui i test con l’interprete corretto
4. mostra il diff
5. riporta il risultato dei test, indicando quale interprete è stato usato
6. riassumi cosa è stato aggiunto e cosa è rimasto volutamente fuori scope
