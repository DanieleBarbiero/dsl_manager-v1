# Prompt Slice 31

<!--
Questo prompt deriva dal template canonico delle slice e dal protocollo
operativo consolidato nelle Slice 20-30. Deve essere applicato come una
verticale autonoma. Il report della Slice 31 non deve essere creato prima
dell'installazione: nascerà dal template canonico soltanto dopo implementazione
e collaudo reali.
-->

## Nucleo normativo della Slice 31

### Task

Implementare solo la **Slice 31 — governo pubblico di configurazione, promozione temporale e diagnostica controllata**.

La direttiva di prodotto è questa:

> un utente non deve essere costretto a usare PowerShell, un altro guscio, un
> adapter locale o la modifica manuale di YAML per eseguire un'operazione che
> appartiene al flusso principale di DSL Manager. Nel tutorial il guscio può
> restare soltanto per aspetti secondari, come creare directory temporanee,
> copiare fixture, calcolare checksum o orchestrare una sessione interattiva.

La slice deve chiudere, in un'unica verticale coerente, quattro limiti emersi
dal collaudo del laboratorio Orione Assistenza:

1. esporre come comando pubblico la propagazione temporale già governata dal
   servizio `dsl_mngr.core.temporal_consolidation.propagate_temporal_intervals`;
2. esporre come comandi pubblici l'ispezione, la validazione e l'applicazione
   conservativa della allowlist di auto-review;
3. offrire una diagnostica pubblica, sicura e ripetibile dello stato
   `partial_success`, senza worker arbitrari e senza alterare gli artefatti di
   produzione;
4. correggere la tracciabilità di materializzazione quando due candidati
   temporali confermati sostengono lo stesso intervallo semantico, così che il
   riuso dell'intervallo non faccia fallire il merge e non perda il supporto
   multiplo.

La verticale richiesta è:

```text
profilo di review pubblico
  -> estrazione deterministica governata
  -> propagazione temporale pubblica
  -> candidati temporal_interval pending
  -> review umana comune
  -> intervallo materializzato o riusato con tutti i supporti
  -> merge/reconcile
  -> DSL v2 e GEXF dinamico temporalmente non vuoti

fixture registrata
  -> diagnostica pubblica controllata
  -> worker interno allowlisted
  -> run partial + exit code 6 + artefatti diagnostici isolati
```

Non implementare scorciatoie specifiche per Orione. Le nuove capacità devono
essere generali, governate dal workspace e utilizzabili da qualunque progetto.

### Scope

In scope:

- una migrazione append-only `v12` per rappresentare più supporti confermati
  dello stesso intervallo temporale senza duplicare l'intervallo;
- aggiornamento della materializzazione, del merge, della riconciliazione e
  delle letture effettive degli intervalli al nuovo modello di supporto;
- un gruppo CLI pubblico `temporal` con il leaf `propagate`;
- un gruppo CLI pubblico `config review` per profili e allowlist;
- un profilo built-in, conservativo e versionato `conservative/1`;
- un gruppo CLI pubblico `diagnostics normalization` per lo scenario
  allowlisted `controlled_partial_success/1`;
- output strutturati, result catalog, help, logging, process report e
  artefatti coerenti con i contratti correnti;
- test unitari, di integrazione e CLI della Slice 31;
- il report della Slice 31 creato dal template canonico soltanto dopo
  l'implementazione, con gli esiti reali dell'installazione e del collaudo.

Fuori scope:

- modifiche al corpus, alle guide o al tutor Orione durante l'applicazione
  della slice;
- modifica dei documenti di design, dei manuali generali, del project summary
  o degli indici solo per registrare l'esistenza della Slice 31;
- una sintassi generica per caricare o eseguire worker scelti dall'utente;
- esecuzione di macro, rete, external link OOXML o codice incorporato nelle
  fixture;
- auto-conferma dei candidati temporali;
- propagazione implicita della validità della sorgente a fatti o relazioni;
- modifica globale dei cataloghi storici non necessaria ai nuovi comandi;
- correzioni non correlate a progress reporting Docling, stale plan o
  rappresentazioni GEXF già conformi ai contratti delle slice precedenti.

### Expected behavior

#### A. Migrazione `v12` e supporto multiplo degli intervalli

Il modello attuale lega `temporal_intervals` a un solo
`source_candidate_record_id`. Quando la materializzazione trova un intervallo
semanticamente identico già presente per lo stesso soggetto, lo riusa ma non
registra il nuovo candidato come supporto. Il candidato è confermato, ma il
merge successivo può terminare con:

```text
Confirmed temporal candidate has no materialized interval
```

La Slice 31 deve eliminare questa incoerenza senza creare intervalli duplicati.

1. Aggiungere con la migrazione `v12` una relazione append-only tra intervallo,
   candidato confermato e decisione di review. Il nome consigliato è
   `temporal_interval_supports`; un nome differente è ammesso soltanto se il
   preflight dimostra una convenzione esistente più appropriata.
2. Ogni riga deve identificare almeno:
   - l'intervallo materializzato;
   - il `candidate_record_id` che lo sostiene;
   - la decisione di review che ne ha causato la materializzazione;
   - il timestamp di creazione.
3. Imporre integrità referenziale e unicità almeno per il candidato e per la
   coppia intervallo/candidato. Un candidato temporale confermato non può
   materializzare o sostenere due intervalli differenti.
4. Eseguire il backfill delle righe legacy da
   `temporal_intervals.source_candidate_record_id` e `decision_id`. Conservare
   le colonne legacy nella v12: non ricostruire tabelle né rompere snapshot o
   reader preesistenti.
5. Rendere atomica la materializzazione:
   - se il candidato ha già un supporto, restituire lo stesso intervallo;
   - se l'intervallo semantico non esiste, crearlo e associare il candidato;
   - se esiste, riusarlo e aggiungere l'associazione del nuovo candidato;
   - un retry non deve aggiungere righe duplicate né cambiare l'identità
     dell'intervallo.
6. Il merge deve verificare la nuova associazione, con compatibilità leggibile
   per i dati v11 migrati, e non deve più assumere che ogni candidato possieda
   un intervallo esclusivo.
7. Un intervallo è effettivo finché possiede almeno un supporto la cui foglia
   di review corrente è confermata. Invalidare o sostituire un supporto non
   deve nascondere l'intervallo se ne resta un altro confermato; quando non ne
   resta alcuno, l'intervallo non deve apparire nelle viste effettive.
8. Provenance, explain, DSL v2, diff e GEXF devono poter ricondurre l'intervallo
   a tutti i supporti effettivi in ordine deterministico. Il formato pubblico
   esistente va esteso in modo backward-compatible: non eliminare campi già
   pubblicati.
9. Il vincolo di unicità semantica dell'intervallo per soggetto resta valido.
   Il supporto multiplo non autorizza la duplicazione di spell o interval.
10. La migrazione deve essere transazionale, idempotente secondo il migration
    runner corrente e verificata sia da database nuovo sia da un reale v11.

Se l'ispezione del codice mostra che invalidazione e riconciliazione hanno una
semantica diversa già contrattualizzata, non scegliere silenziosamente una
scorciatoia: documentare il conflitto nel report e adottare la minima estensione
che preservi l'invariante “almeno un supporto confermato rende effettivo
l'intervallo”.

#### B. Leaf pubblico `temporal propagate`

Esporre il servizio governato esistente con questa interfaccia pubblica:

```text
dsl-manager temporal propagate WORKSPACE \
  --source-revision-id REV_ID \
  --target-subject-type fact|relation \
  --target-subject-id TARGET_ID \
  --source-subject TYPE:ID \
  [--source-subject TYPE:ID ...] \
  --policy explicit_copy|intersection|aggregation|conflict
```

Il comando deve essere disponibile con entrambe le entry point canoniche:

```text
dsl-manager ...
python -m dsl_mngr ...
```

Contratto minimo:

- `--source-subject` è ripetibile e obbligatorio;
- ogni valore contiene esattamente un tipo ammesso e un ID separati dal primo
  `:`; valori vuoti, tipi ignoti, duplicati ambigui e ID inesistenti sono
  rifiutati prima della mutazione;
- i tipi sorgente ammessi devono coincidere con quelli realmente supportati
  dal servizio e dallo schema degli intervalli, non con una lista inventata
  nella CLI;
- il target è limitato in questa slice a `fact` o `relation`;
- le policy sono esclusivamente quelle elencate nel comando e mantengono la
  semantica versionata della Slice 27;
- il comando apre una run del tipo pubblico più specifico e riusabile
  compatibile con il registry corrente, registra input canonici, log e process
  report, poi invoca il servizio core: la CLI non duplica l'algoritmo;
- `explicit_copy`, `intersection` e `aggregation` producono candidati
  `temporal_interval` in stato pending quando la policy ha un risultato;
- `conflict`, o una policy che rileva vincoli inconciliabili, produce un
  conflitto governato e non un intervallo fittizio;
- nessun candidato viene confermato, materializzato o unito automaticamente;
- stdout restituisce JSON UTF-8 strutturato con almeno `run_id`, `policy`,
  target, sorgenti canoniche, `candidate_record_ids`, eventuali
  `candidate_batch_ids`, `conflict_id`, stato ed exit code semantico;
- gli ID sono quelli realmente persistiti e possono essere passati senza
  parsing testuale fragile ai normali comandi `candidates review ...`;
- stderr è riservato alla diagnostica; non mescolare banner umani a stdout
  quando si richiede output strutturato;
- exit code `0` indica candidati prodotti o riuso idempotente riuscito;
  l'exit code di conflitto deve usare il codice semantico già catalogato dal
  progetto per i conflitti governati; errori di uso, workspace o integrità
  usano i codici pubblici correnti, senza introdurre sovrapposizioni;
- un errore dopo l'apertura della run deve lasciare una run fallita
  diagnosticabile e non una mutazione parziale non registrata.

Il servizio core resta l'unica autorità semantica. Non introdurre SQL nella
CLI e non mantenere l'adapter del laboratorio come dipendenza del prodotto.

Il test verticale deve dimostrare almeno:

- `explicit_copy` da una `source_revision` confermata verso due fatti e una
  relazione;
- review umana e merge dei tre candidati;
- intervallo dell'arco contenuto nei bounds dei nodi estremi;
- almeno una `intersection` di vincoli indipendenti oppure una `aggregation`
  di intervalli disgiunti;
- almeno un conflitto governato;
- collezioni `intervals` non vuote nel DSL schema 2;
- almeno uno spell di nodo e uno di arco nel GEXF dinamico;
- assenza di promozione automatica dal solo intervallo della sorgente.

#### C. Comandi pubblici per configurazione e allowlist di review

Esporre almeno i seguenti leaf pubblici:

```text
dsl-manager config review show WORKSPACE
dsl-manager config review profiles WORKSPACE
dsl-manager config review apply-profile WORKSPACE --profile conservative/1
dsl-manager config review set-allowlist WORKSPACE [--policy POLICY ...]
dsl-manager config validate WORKSPACE
```

La forma finale può seguire più precisamente la grammatica già usata dalla
CLI se il preflight lo richiede, ma deve conservare tutte le capacità sopra e
il report deve registrare la sintassi scelta con la motivazione. Non ridurre il
risultato a un comando che stampa istruzioni per modificare YAML a mano.

Contratto del profilo `conservative/1`:

- è una risorsa built-in immutabile e versionata del package, non un file
  scaricato dalla rete e non un template arbitrariamente modificabile nel
  workspace;
- contiene esattamente le policy deterministiche che il catalogo della Slice
  21 marca come ammesse all'auto-review al momento della Slice 31;
- l'elenco è statico per la versione `1`: nuove policy future non entrano
  silenziosamente nel profilo;
- esclude esplicitamente policy pending, inferite, ambigue, temporali, AI ed
  Excel reference, compresa `explicit_excel_reference_pending/1`;
- l'allowlist di default di un workspace nuovo resta vuota: l'applicazione del
  profilo è intenzionale e opt-in.

Comportamento dei leaf:

- `show` mostra valore effettivo, origine, ordine canonico e hash della
  configurazione rilevante;
- `profiles` elenca ID/versione, descrizione, policy e hash dei soli profili
  built-in riconosciuti;
- `apply-profile` valida prima l'intero risultato e sostituisce soltanto
  `review.automatic_policies` con la lista del profilo;
- `set-allowlist` accetta `--policy` ripetibile e sostituisce atomicamente la
  lista; zero occorrenze significa lista vuota soltanto se questa semantica è
  inequivocabile nell'help;
- policy inesistenti, duplicate in forma incoerente o non marcate
  `automatic_review_allowed` sono rifiutate prima di scrivere;
- scrittura su `configs/project.yaml` atomica, UTF-8 e preservante tutte le
  chiavi non coinvolte; nessun aggiornamento parziale se la validazione fallisce;
- i retry identici sono no-op osservabili e producono lo stesso contenuto;
- se il framework corrente offre un controllo di concorrenza tramite hash o
  revisione, riusarlo; altrimenti aggiungere un'opzione
  `--expect-config-hash` ai comandi mutanti per rifiutare lost update;
- `validate` verifica schema completo del progetto, profilo richiesto e
  ammissibilità delle policy senza mutare il workspace;
- ogni leaf offre JSON strutturato e un riepilogo umano secondo le convenzioni
  già pubbliche, oltre a logging e result catalog coerenti.

Le policy attualmente attese nel profilo sono quelle allowlisted realmente
registrate nel catalogo deterministico. Durante il preflight ricavarle dal
codice e bloccare con test l'elenco esatto; non duplicare alla cieca questo
testo se il catalogo autorevole dimostra una differenza. La risorsa del profilo
e il test devono comunque rendere evidente ogni futura deriva.

#### D. Diagnostica controllata di `partial_success`

Esporre una rotta pubblica sicura con questa capacità:

```text
dsl-manager diagnostics normalization run WORKSPACE \
  --revision REV_ID \
  --scenario controlled_partial_success/1
```

Se la grammatica consolidata della CLI suggerisce di omettere `run`, è ammessa
la forma `diagnostics normalization WORKSPACE ...`; una sola forma deve
diventare canonica, essere mostrata nell'help e registrata nel report.

Lo scenario non è un parser alternativo di produzione. Serve a collaudare con
un comando pubblico il contratto trasversale `partial` senza dipendere da un
esito non deterministico di Docling.

Requisiti di sicurezza e isolamento:

- accettare soltanto scenari built-in allowlisted e versionati; in questa
  slice esiste solo `controlled_partial_success/1`;
- non offrire opzioni per percorso worker, modulo Python, comando, eseguibile,
  import dinamico, shell o payload arbitrario;
- usare un worker interno packaged, richiamabile soltanto dalla rotta
  diagnostica e non selezionabile da `corpus normalize`, batch o profili;
- richiedere una revisione sorgente realmente registrata nel workspace e
  verificarne esistenza, hash e formato ammesso;
- eseguire il preflight sicuro pertinente al formato quando applicabile, senza
  rete, macro, external link, OLE o dereferenziazione di relazioni esterne;
- produrre artefatti esclusivamente sotto il namespace della run diagnostica,
  per esempio `artifacts/runs/<RUN_ID>/diagnostics/normalization/`;
- non modificare `source_revisions.normalized_hash`, registri workbook,
  frammenti, chunk, candidati, fatti, relazioni o artefatti normalizzati di
  produzione;
- attraversare davvero il runner pubblico dei worker e la macchina a stati
  delle run: non simulare il risultato soltanto nella CLI;
- il worker termina con exit code `6`, la run termina `partial` e stdout
  restituisce un documento strutturato con `run_id`, scenario, stato, exit
  code worker/CLI, hash input, artefatti e catalogo delle ragioni;
- artefatti e output devono dichiarare chiaramente
  `controlled_simulation: true`: il test dimostra la gestione applicativa del
  partial, non che Docling produrrebbe partial su quella fonte;
- retry e resume seguono il contratto corrente delle run senza ciclo infinito
  e senza convertire il diagnostico in dato operativo.

La diagnostica deve essere utilizzabile da CMD, PowerShell e qualunque client
che invochi la CLI. PowerShell non è parte del contratto funzionale.

### Constraints

- Preservare le Slice 01-30 e i loro contratti pubblici.
- Non modificare `.wb/` e non usarla come fonte, fixture o dipendenza.
- Usare Python `>=3.12,<3.13` e l'interprete di progetto previsto da
  `AGENTS.md` e `.codex/config.toml` nell'ambiente Windows locale.
- Usare import assoluti da `dsl_mngr` e rispettare il layout `src/`.
- Riutilizzare servizi, validator, registry, runner, result catalog e modelli
  esistenti; evitare algoritmi duplicati nei comandi CLI.
- Nessun SQL diretto dalla CLI e nessuna scrittura diretta del database da
  script tutorial.
- Nessuna rete, nessuna esecuzione di macro, nessun caricamento dinamico di
  codice scelto dall'utente.
- Tutte le scritture devono restare confinate nel workspace esplicitamente
  selezionato, eccetto le normali risorse statiche installate col package.
- Nessun ID presunto nei test end-to-end: acquisire gli ID dagli output
  strutturati o dalle API pubbliche.
- Mantenere output deterministici: ordine, serializzazione UTF-8, hash e
  artefatti stabili a input e configurazione invariati.
- Non usare il corpus Aurora né il workspace di un altro laboratorio per i
  test di accettazione della slice.
- Non correggere expected a posteriori senza prima giustificare il cambiamento
  di contratto nel report.
- Non fare refactoring generalizzati, rinominare comandi esistenti o ampliare
  gli enum oltre quanto necessario alla verticale.

### Done

La Slice 31 è completata soltanto quando tutte le condizioni seguenti sono
vere:

- migrazione v12, backfill e rollback transazionale sono verificati;
- due candidati temporali confermati possono sostenere un solo intervallo
  semantico e il merge riesce;
- invalidare un supporto conserva l'intervallo se ne resta uno confermato e
  invalidarli tutti lo rimuove dalle viste effettive;
- la provenance espone tutti i supporti in ordine deterministico;
- `temporal propagate` usa il servizio core, produce candidati pending o un
  conflitto e non auto-approva nulla;
- `config review` permette di vedere, validare, applicare il profilo
  `conservative/1` e impostare una allowlist esatta senza editor esterni;
- la modifica di configurazione è atomica, validata, idempotente e protetta
  da lost update;
- `diagnostics normalization` produce in modo sicuro run `partial`, exit `6`
  e artefatti isolati senza contaminare il flusso operativo;
- gli help delle due entry point mostrano la stessa grammatica;
- errori di input e conflitti restituiscono result catalog ed exit code
  coerenti con il contratto pubblico;
- i test nuovi e l'intera suite passano con l'interprete corretto;
- il diff non contiene cambiamenti estranei;
- il report della Slice 31, creato soltanto a installazione conclusa, contiene
  file modificati, comandi, exit code,
  conteggi test, verifiche verticali, scostamenti e limiti residui reali.

### Before coding

Prima di modificare codice:

1. leggere integralmente le fonti obbligatorie elencate nel protocollo sotto;
2. verificare `git status` e preservare ogni modifica preesistente;
3. ricostruire il flusso reale di migrazioni, review, materializzazione,
   merge, reconcile, render e worker status;
4. verificare nel codice corrente nomi dei comandi, exit code, result catalog,
   run type, checkpoint e formati JSON;
5. censire tutte le query che leggono direttamente
   `temporal_intervals.source_candidate_record_id`;
6. censire catalogo e flag `automatic_review_allowed` delle policy;
7. verificare come i worker traducono `partial_success` in exit `6` e stato
   `partial`;
8. dichiarare nel report il piano file-per-file prima di applicare modifiche
   oltre la prima patch sostanziale.

## Protocollo operativo comune obbligatorio

### 1. Autorità e ordine di precedenza

Applicare questo ordine:

1. istruzioni esplicite dell'utente;
2. `AGENTS.md`;
3. questo prompt di slice;
4. design document canonico più recente e contratti manifest;
5. codice e test correnti come prova del comportamento effettivo;
6. manuali e report precedenti come contesto storico.

Quando documentazione e runtime divergono, non adattare silenziosamente
l'expected. Registrare la divergenza, scegliere l'autorità secondo l'ordine
sopra e aggiungere un test che renda visibile la decisione.

### 2. Letture obbligatorie complete

Leggere integralmente almeno:

- `AGENTS.md`;
- `.codex/config.toml`;
- `.kb/template/template_slice.md`;
- `.kb/template/template_slice_report.md`;
- `.kb/documenti/project_summary.md`;
- `.kb/documenti/documenti di design/run 1/design_document_v_01.md`;
- `.kb/documenti/documenti di design/run 2/design_document_v_02.md`;
- `.kb/documenti/documenti tecnici/analisi_tecnica_dsl_manager.md`;
- `.kb/documenti/documenti tecnici/contratti_manifest_dsl_manager.md`;
- `.kb/documenti/manuali/manuale_utente_dsl_manager.md`;
- `.kb/projects/slicing/documenti tecnici/modifica_prompt_slice_v2.md`;
- tutti i prompt e tutti i report da
  `.kb/projects/slicing/slice_01/` a
  `.kb/projects/slicing/slice_30/`, usando i nomi zero-padded completi;
- `.kb/projects/laboratorio_orione_assistenza/dsl_manager_laboratorio_orione_assistenza_prompt_v_01.md`;
- `.kb/projects/laboratorio_orione_assistenza/corpus_mock_orione_assistenza/materiale_di_supporto/limitazioni_intenzionali.md`;
- `.kb/projects/laboratorio_orione_assistenza/corpus_mock_orione_assistenza/materiale_di_supporto/diario_tecnico_validazione.md`;
- l'adapter e il tutor Orione soltanto per identificare le operazioni da
  sostituire con comandi pubblici, non per importarli nel package.

Se una fonte obbligatoria manca, fermarsi prima del codice e registrare il
blocco. Non usare `.wb/` come sostituto.

### 3. Preflight del codice e dei test

Ispezionare integralmente i moduli e i test pertinenti, includendo almeno:

- bootstrap e registro delle migrazioni SQLite;
- `core.temporal`, `core.temporal_consolidation`, review, merge,
  reconciliation, DSL renderer e GEXF;
- configurazione workspace, parser YAML, catalogo delle candidate policy e
  auto-review batch;
- CLI app e command modules, output JSON, error mapping e result catalog;
- run lifecycle, worker runner, normalizzazione Docling/OOXML e gestione
  `partial_success`;
- test delle Slice 20, 21, 23, 26, 27, 28 e 30;
- test che fissano l'ultima versione di schema o enumerano run type, comandi,
  manifest e artefatti.

Usare `rg` per censire riferimenti e dipendenze. Non limitarsi ai nomi suggeriti
in questo prompt: il codice corrente è l'autorità sulla topologia reale.

### 4. Anti-drift e compatibilità

- Aggiungere v12 in coda; non riscrivere le migrazioni 01-11.
- Testare upgrade reale v11 -> v12, database nuovo, seconda inizializzazione e
  rollback su errore indotto.
- Conservare i manifest e le versioni schema esistenti salvo estensione
  esplicitamente necessaria e backward-compatible.
- Non cambiare i default di sicurezza: allowlist vuota, candidati pending,
  rete e macro disabilitate.
- Non far dipendere il flusso principale da PowerShell, CMD, script Orione o
  modifica manuale dei file.
- Non trasformare il diagnostico controllato in un hook di esecuzione generico.
- Non confondere intervallo della sorgente, intervallo del fatto e intervallo
  della relazione: ogni promozione resta esplicita e candidate-first.
- Non confondere più supporti dello stesso intervallo con più intervalli dello
  stesso soggetto.

### 5. Ambiente e installazione

Nell'ambiente Windows locale:

1. leggere `PROJECT_PYTHON` da
   `[shell_environment_policy.set]` in `.codex/config.toml`;
2. risolvere quel percorso senza affidarsi a `python` globale;
3. verificare Python 3.12;
4. prima di modificare codice installare il progetto con:

   ```text
   <PROJECT_PYTHON> -m pip install -e ".[dev]"
   ```

5. eseguire ogni comando Python, CLI e pytest con lo stesso interprete.

Nel report indicare il percorso logico dell'interprete usato, senza pubblicare
path macchina non necessari.

### 6. Piano minimo dei test

Creare test Slice 31 focalizzati e aggiornare soltanto gli expected storici
che devono legittimamente conoscere v12 o i nuovi leaf.

Copertura minima:

1. **migrazione**: schema nuovo, v11 reale, backfill, idempotenza, vincoli e
   rollback;
2. **riuso temporale**: due candidate record distinti, due decisioni
   confermate, un solo intervallo, due supporti, merge ripetuto stabile;
3. **invalidazione**: un supporto sostituito, poi tutti sostituiti, con viste
   effettive e provenance corrette;
4. **CLI temporale**: help, input invalidi, sorgente senza intervallo,
   `explicit_copy`, una policy multi-source, conflitto, JSON, log, run e
   pending review;
5. **verticale temporale**: review, merge, reconcile, DSL v2 con interval e
   GEXF dinamico con spell di nodo/arco e containment valido;
6. **config**: show, profiles, profilo esatto, allowlist custom vuota/non
   vuota, policy vietata, YAML preesistente preservato, scrittura atomica,
   hash concorrente errato e retry idempotente;
7. **diagnostica**: scenario ignoto, revisione inesistente o alterata,
   preflight, worker non iniettabile, exit 6, run partial, artefatti isolati e
   nessuna mutazione operativa;
8. **entry point**: parità fra `dsl-manager` e `python -m dsl_mngr`;
9. **regressione**: suite completa e controllo del diff.

I test del partial controllato devono usare la rotta pubblica introdotta dalla
slice. Monkeypatch o chiamata diretta al worker sono ammessi nei test unitari
interni, ma non valgono come prova di accettazione CLI.

### 7. Esecuzione, verifica e chiusura

Dopo il preflight:

1. implementare la minima verticale completa;
2. eseguire prima i test Slice 31 mirati;
3. eseguire l'intera suite con il project interpreter;
4. eseguire un smoke E2E su un workspace temporaneo nuovo usando soltanto i
   comandi pubblici;
5. verificare `--help` per i nuovi gruppi e leaf su entrambe le entry point;
6. verificare gli exit code reali, non solo il contenuto di stdout;
7. verificare assenza di path assoluti della macchina negli artefatti;
8. verificare `git diff --check`, file UTF-8 e stato del worktree;
9. preservare e distinguere nel report ogni modifica preesistente;
10. soltanto dopo implementazione e collaudo, creare
    `.kb/projects/slicing/slice_31/dsl_manager_slice_31_report.md` usando il
    template canonico e compilandolo con gli esiti reali dell'applicazione.

Il report, che non deve esistere in forma preventiva, deve includere almeno:

- sintassi CLI finale e scostamenti motivati da questo prompt;
- migrazione e invarianti adottati;
- profilo conservativo effettivo e relativo hash/versione;
- tabella di exit code osservati;
- comandi eseguiti e interprete usato;
- test mirati e suite completa con conteggi reali;
- smoke E2E e ID acquisiti dinamicamente;
- elenco dei file modificati;
- diff/status e modifiche preesistenti preservate;
- limiti residui e attività post-slice ancora da svolgere.

Non dichiarare “completata” la slice se uno dei quattro limiti resta aggirato da
uno script esterno o se DSL/GEXF temporali sono ottenuti con dati inseriti
direttamente nel database.

## Integrazioni operative specifiche — Slice 31

### Interfacce pubbliche richieste

La documentazione `--help` deve rendere evidente il seguente confine:

| Esigenza | Interfaccia DSL Manager | Ruolo residuo del guscio |
|---|---|---|
| Configurare auto-review | `config review ...` | nessuno |
| Promuovere temporalità | `temporal propagate ...` | nessuno |
| Confermare/rifiutare | comandi review esistenti | nessuno |
| Provare `partial` | `diagnostics normalization ...` | nessuno |
| Creare temporanei/copiare fixture | non necessario al dominio | ammesso nel tutorial |
| Conservare log di una lezione | non necessario al dominio | ammesso nel tutorial |

Ogni comando mutante deve distinguersi chiaramente dai leaf read-only e deve
stampare prima o restituire nel JSON il workspace canonico che sta per
modificare. Non introdurre prompt interattivi nel core CLI: l'interattività
resta responsabilità facoltativa del tutor.

### Criteri di progettazione preferiti

- Preferire una tabella di associazione ai campi multivalore o alla
  duplicazione di `temporal_intervals`.
- Preferire una risorsa profilo package-owned e versionata a una lista copiata
  nelle guide.
- Preferire un adapter CLI sottile sui servizi core a una seconda
  implementazione degli algoritmi.
- Preferire un worker diagnostico interno allowlisted a un'opzione di injection.
- Preferire output JSON completi e stabili all'estrazione di ID da frasi umane.
- Preferire test con workspace temporanei reali a fixture di database
  costruite con SQL diretto, salvo i test mirati della migrazione.

### Criterio finale di accettazione

Un principiante deve poter completare il nucleo del flusso seguente usando
soltanto DSL Manager:

1. applicare una allowlist conservativa nota;
2. validare la configurazione;
3. propagare un intervallo confermato a fatti e relazione;
4. vedere i candidati pending;
5. confermarli o rifiutarli con la review comune;
6. unire e renderizzare intervalli e spell reali;
7. collaudare in modo esplicito il comportamento `partial`.

Il guscio può orchestrare la dimostrazione, ma la sua rimozione non deve
togliere alcuna capacità applicativa dei sette passi.
