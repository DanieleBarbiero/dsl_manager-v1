Implementa solo la Slice 19 per DSL Manager v1.

Prima leggi e segui:
- `AGENTS.md`
- `.kb/documenti/documenti di design/run 1/design_document_v_01.md`
- i report gia' prodotti in `.kb/projects/slicing/slice_<NN>/dsl_manager_slice_<NN>_report.md` per le slice `01`-`18`, con `<NN>` espresso con due cifre e zero-padding
- il codice attuale in `src/dsl_mngr` e i test attuali in `tests`

Task:
Implementare la UI locale opzionale read-only per consultare lo stato del workspace senza spostare logica applicativa nella UI.

Contesto:
- La Slice 18 ha gia' introdotto il log viewer statico HTML/CSV.
- La Slice 19 e' la prima slice v1.1: deve aggiungere un mini server locale, non una web app enterprise.
- La UI deve essere una vista read-only sopra registry, snapshot, diff gia' prodotti, log e artifact esistenti.
- Il core continua a produrre stato, validazione, merge, DSL, export e audit; la UI deve solo leggere e mostrare.

Scope:
- aggiungi un comando CLI `dsl-manager ui serve <workspace>`;
- esponi un mini server HTTP locale basato solo su standard library Python;
- usa host di default `127.0.0.1` e porta di default `8765`;
- supporta `--host` e `--port`;
- se `--port 0` viene usato, stampa l'URL con la porta effettivamente assegnata;
- aggiungi un piccolo core separato per routing/rendering/query, ad esempio `dsl_mngr.core.local_ui`;
- aggiungi un comando separato, ad esempio `dsl_mngr.cli.commands.ui`;
- collega il comando in `src/dsl_mngr/cli/app.py`;
- aggiungi test deterministici in `tests/test_slice_19_local_ui.py`.

Viste minime richieste:
- `/` dashboard con riepilogo workspace e link alle viste principali;
- `/runs` lista read-only delle run con `run_id`, `run_type`, `status`, timestamp, parent run e link al dettaglio;
- `/runs/<run_id>` dettaglio run con input/output JSON, process report se presenti, worker runs e link log run;
- `/logs` log viewer dell'application log, riusando o allineando il comportamento della Slice 18;
- `/logs?run_id=RUN_000001` log viewer del log della run indicata;
- `/rejected-candidates` lista dei candidati rifiutati con batch, run, line number, candidate id, record type, reason e message;
- `/conflicts` lista dei conflitti aperti e non aperti presenti nel registry;
- `/snapshots` lista degli snapshot DSL con conteggi, hash, status e path relativi degli export;
- `/diff` pagina che consente di scegliere o indicare `from` e `to`;
- `/diff?from=DSL_000001&to=DSL_000002` vista read-only del diff gia' esistente in `exports/dsl_diff`, se presente; se il file non esiste, mostra un messaggio leggibile che invita a eseguire `dsl-manager dsl diff`, senza generare diff automaticamente.

Expected behavior:
- `dsl-manager ui serve <workspace>` avvia un server locale e stampa un URL apribile nel browser;
- le rotte richieste rispondono con HTML UTF-8 valido e leggibile;
- i contenuti provenienti da database, log, JSON o path sono sempre HTML-escaped;
- gli unknown route rispondono con `404`;
- metodi diversi da `GET` e `HEAD` rispondono con `405`;
- il server non crea, modifica o cancella record del database;
- il server non crea nuove run, snapshot, diff, graph export, candidate batch o artifact;
- la UI funziona anche quando alcune sezioni sono vuote, mostrando uno stato vuoto leggibile;
- gli errori di workspace non inizializzato o database non migrato sono leggibili da CLI e non producono traceback utente;
- i path mostrati restano relativi al workspace quando possibile e usano `/`;
- non viene servito alcun file arbitrario fuori dal workspace.

Constraints:
- non implementare login, autenticazione, autorizzazione o multiutente;
- non aggiungere web framework, template engine, ORM o nuove dipendenze runtime;
- non introdurre API mutative;
- non chiamare provider AI o servizi esterni;
- non rilanciare parser, merge, render DSL, diff, graph export o batch dalla UI;
- non duplicare la logica di validazione/merge/rendering gia' esistente;
- mantieni HTML/CSS/JS minimale e inline, senza asset esterni;
- mantieni il comando `log table` e `log csv` compatibile con la Slice 18;
- non aggiungere nuove migrazioni salvo necessita' reale e motivata; la slice dovrebbe poter leggere le tabelle esistenti.

Suggerimento di implementazione:
- preferisci `http.server.ThreadingHTTPServer` e `BaseHTTPRequestHandler`;
- tieni il rendering HTML in funzioni pure testabili senza server long-running;
- prevedi un helper testabile per risolvere una request in status, headers e body;
- per i test del server usa una porta effimera o il routing core, evitando processi che restano appesi;
- riusa `dsl_mngr.core.database.resolve_database_settings`, `open_database`, `validate_database_migrations`, `run_artifact_paths` e il log viewer esistente dove ha senso;
- usa query SQLite esplicite, ordinate e limitate in modo ragionevole per le liste;
- per il diff read-only leggi solo artifact esistenti sotto `exports/dsl_diff/<from>__<to>.json` o i path equivalenti gia' prodotti dalla Slice 8.

Test minimi:
- `test_ui_routes_smoke` verifica almeno `/`, `/runs`, `/logs`, `/rejected-candidates`, `/conflicts`, `/snapshots` e `/diff?from=...&to=...`;
- verifica che HTML escape funzioni con testo contenente `<`, `>`, `&` e virgolette;
- verifica che la UI non modifichi il database confrontando conteggi o record principali prima e dopo le request;
- verifica `404` per una route sconosciuta e `405` per un metodo mutativo;
- verifica il comando CLI in smoke test senza lasciare server appesi, usando un hook o una modalita' testabile se necessario;
- verifica compatibilita' `python -m dsl_mngr ui serve ...` quando praticabile senza bloccare il test.

Controllo anti-drifting:
- effettua un controllo generale ad alto livello per discrepanze tra le slice descritte in `design_document_v_01.md` e l'attuale implementazione del progetto. il controllo serve a evitare il drifting. segnala qualsiasi deviazione dal progetto concordato.

Report richiesto:
- salva una copia del report che produci a fine dell'esecuzione del task nel file `.kb/projects/slicing/slice_19/dsl_manager_slice_19_report.md`, usando come template per il report il file `.kb/template/template_slice_report.md`.

Done when:
- la Slice 19 e' implementata nello scope read-only;
- il comando `dsl-manager ui serve <workspace>` esiste e stampa l'URL locale;
- le viste minime richieste sono disponibili;
- i test della Slice 19 esistono e passano;
- la suite esistente continua a passare o ogni eventuale test non eseguito/fallito e' spiegato nel report;
- nessuna feature fuori scope v1.1 e' stata aggiunta;
- il report della slice e' stato salvato nel path richiesto.

Prima di codare:
1. dichiara brevemente quali file prevedi di toccare;
2. effettua il controllo anti-drifting ad alto livello;
3. implementa;
4. esegui i test;
5. mostra diff e risultato dei test;
6. salva il report finale della slice nel path richiesto.
