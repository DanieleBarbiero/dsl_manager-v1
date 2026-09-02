Implementa solo la Slice 18 per DSL Manager v1.

Prima di iniziare, leggi e segui:
- `AGENTS.md`
- `.kb/documenti/documenti di design/run 1/design_document_v_01.md`
- `.kb/template/template_slice_report.md`
- i report gia' prodotti in `.kb/projects/slicing/slice_01` ... `.kb/projects/slicing/slice_17`
- l'attuale codice sotto `src/dsl_mngr`
- gli attuali test sotto `tests`

Contesto:
- Il package Python e' `dsl_mngr`.
- Il progetto usa Python `>=3.12,<3.13`.
- In ambiente Codex dentro VS Code su Windows devi leggere `.codex/config.toml` e usare solo `PROJECT_PYTHON` per comandi Python, pip, pytest o entry point Python.
- Nel repository attuale esiste gia' una base logging della Slice 1: `src/dsl_mngr/core/logging_setup.py` legge JSONL e renderizza tabella testuale/CSV; `src/dsl_mngr/cli/commands/log.py` espone `dsl-manager log table <workspace> --format table|csv`.
- La directory workspace `exports/logs` esiste gia'.
- `RUN_TYPES` contiene gia' `log_table`.
- La Slice 18 nel design e' "Log Viewer": HTML statico, CSV, filtro client-side opzionale e link agli artifact.

Task:
Implementa il minimo vertical slice funzionante per rendere leggibili i log senza UI complessa.

Scope:
- completare il log viewer riusando quanto gia' esiste, senza rompere la compatibilita' con il comando `log table` introdotto nella Slice 1;
- aggiungere, se utile, un modulo core dedicato come `dsl_mngr.core.log_viewer`, mantenendo `logging_setup.py` focalizzato su scrittura/lettura log;
- leggere log JSONL sia da `logs/app.jsonl` sia da log per-run come `artifacts/runs/RUN_000001/log.jsonl`;
- supportare input come workspace o path JSONL, in modo compatibile con il codice attuale e con gli esempi del design:
  - `dsl-manager log table <workspace>`
  - `dsl-manager log table <workspace> --format html --output exports/logs/app_log.html`
  - `dsl-manager log table logs/app.jsonl`
  - `dsl-manager log table artifacts/runs/RUN_000001/log.jsonl --output exports/logs/RUN_000001_log_table.html`
  - `dsl-manager log csv logs/app.jsonl --output exports/logs/app.csv`
- mantenere compatibile il percorso legacy `dsl-manager log table <workspace> --format csv --output <file>`;
- rendere esplicita la selezione formato: `table` per stdout testuale, `html` per viewer statico e `csv` come alias legacy; se possibile, quando `--format` non e' indicato e `--output` termina con `.html`, inferire HTML per allinearsi agli esempi del design;
- produrre HTML statico UTF-8 con tabella semplice, escaping corretto, stile minimo per `level`, righe ordinate per timestamp quando possibile e filtro testuale client-side senza dipendenze esterne;
- produrre CSV deterministico con newline `\n`;
- includere colonne principali coerenti con il design, adattandole ai record attuali:
  - `timestamp`
  - `level`
  - `run_id`
  - `worker`
  - `event` / `event_type`
  - `source_id`
  - `source_revision_id`
  - `message`
  - `duration_ms`
  - `exit_code`
- quando un record contiene `run_id`, aggiungere nell'HTML link relativi agli artifact esistenti, per esempio `artifacts/runs/<run_id>/process_report.json` e `artifacts/runs/<run_id>/log.jsonl`;
- creare le directory di output quando serve;
- usare path relativi al workspace negli output/report quando il workspace e' noto;
- gestire log mancanti o vuoti con output valido e leggibile;
- gestire JSONL invalido con errore leggibile e return code non zero.

Expected behavior:
- `dsl-manager log table <workspace>` continua a stampare una tabella testuale leggibile su stdout.
- `dsl-manager log table <workspace> --format csv --output <file>` continua a funzionare per i test storici.
- `dsl-manager log table <workspace> --format html --output <file.html>` genera un HTML statico.
- `dsl-manager log table <path-jsonl> --output <file.html>` genera un HTML statico con tabella, filtro client-side e link agli artifact quando risolvibili.
- `dsl-manager log csv <path-jsonl> --output <file.csv>` genera CSV statico.
- L'HTML non carica asset esterni, non avvia server e non richiede rete.
- L'implementazione non introduce ORM, database server, web/API/auth o dipendenze runtime nuove.
- Il mini-server `dsl-manager log serve` resta fuori scope.
- La UI locale della Slice 19 resta fuori scope.
- Il parser di log sorgente della Slice 14 non va modificato salvo regressioni direttamente causate da questa slice.

Vincoli:
- mantieni CLI sottile e logica deterministica nel core;
- preferisci standard library (`json`, `csv`, `html`, `pathlib`) e non aggiungere framework frontend;
- non salvare contenuti sorgente lunghi nei log o negli artifact del viewer;
- non cambiare il significato pubblico di scan, parser, AI package, batch, merge, render DSL, diff o GEXF;
- evita migration schema, salvo motivazione forte e documentata;
- usa import assoluti da `dsl_mngr`;
- non importare mai `src` come package;
- non usare path assoluti negli artifact condivisibili se puoi evitarlo;
- preserva i test esistenti.

Test richiesti:
- aggiungi test deterministici per la Slice 18, almeno:
  - `test_log_table_render`
  - `test_log_csv_render`
- copri almeno:
  - render HTML da `logs/app.jsonl`;
  - render HTML da `artifacts/runs/<run_id>/log.jsonl`;
  - filtro client-side presente nell'HTML;
  - escaping HTML di messaggi con caratteri speciali;
  - link agli artifact quando `run_id` esiste;
  - CSV generato da path JSONL;
  - compatibilita' legacy `log table <workspace> --format csv`;
  - errore leggibile su JSONL invalido;
  - compatibilita' `python -m dsl_mngr`.

Controllo anti-drifting:
- effettua un controllo generale ad alto livello per discrepanze tra le slice descritte in `design_document_v_01.md` e l'attuale implementazione del progetto. il controllo serve a evitare il drifting. segnala qualsiasi deviazione dal progetto concordato.

Report:
- salva una copia del report che produci a fine dell'esecuzione del task nel file `.kb/projects/slicing/slice_18/dsl_manager_slice_18_report.md`, usando come template per il report il file `.kb/template/template_slice_report.md`.

Done when:
- la Slice 18 e' implementata nello scope sopra;
- i test della Slice 18 esistono e passano;
- i test storici rilevanti non regrediscono;
- `python -m pytest` passa con l'interprete corretto del progetto;
- se il test Docling storico citato nel report Slice 17 va di nuovo in timeout, non nasconderlo: riporta comando, interprete, durata, test impattato e verifica mirata alternativa eseguita;
- il diff e' ristretto alla slice;
- nessuna feature fuori scope v1 e' stata aggiunta;
- il report Slice 18 e' salvato nel path richiesto.

Prima di codare:
1. dichiara brevemente i file che prevedi di toccare;
2. implementa;
3. esegui install editable e test con l'interprete corretto;
4. mostra diff/status e risultato dei test;
5. riassumi cosa e' stato aggiunto e cosa e' rimasto fuori scope.
