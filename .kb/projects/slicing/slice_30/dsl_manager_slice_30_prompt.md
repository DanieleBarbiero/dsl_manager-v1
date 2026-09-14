# Prompt Slice 30

<!--
Base progettuale:
- richiesta esplicita di una Slice 30 successiva alla chiusura della run 2;
- discussione "È ipotizzabile una slice 30?" e sezioni 2.1-2.7 in
  .kb/documenti/manuali/outline_dsl_manager_flow_from_input_to_output_completo.md;
- AI handoff della Slice 15, poi rafforzato dalle Slice 20-29.

Questo prompt è un'estensione post-v02 autorizzata. Non modifica retroattivamente il
design v02 e non è stato estratto dal suo nucleo normativo, che termina alla Slice 29.
-->

## Nucleo normativo della Slice 30

Implementa solo la Slice 30 — selezione dichiarativa, deterministica, riproducibile e
auditabile delle evidenze più adatte a una route AI, seguita dalla costruzione di un
package pronto per l'handoff esterno. Produci
`.kb/projects/slicing/slice_30/dsl_manager_slice_30_report.md`.

Leggi integralmente `AGENTS.md`, design v02, design v01, la discussione sulla Slice 30,
codice, test e report finali 01-29. Ispeziona il worktree, determina l'interprete soltanto
tramite `AGENTS.md` e preserva ogni modifica estranea.

La capacità non è greenfield. Il codice corrente possiede già l'embrione funzionale:
`dsl_mngr.core.ai_package.prepare_ai_package_input` raccoglie revisioni attive e applica i
filtri grossolani `include_chunks`/`include_fragments`; la CLI `ai package` accetta
`--revision` e `--profile`; il worker `build_ai_package` produce un outbox verificabile.
Rafforza e testa questo percorso. Non creare un secondo packager, un secondo registry o
una pipeline AI parallela.

Obiettivo verticale minimo verificabile:

```text
route AI versionata + policy di selezione versionata
  -> inventario delle evidenze e stato deterministico/review osservato
  -> piano immutabile con included/excluded, ranking e motivazioni
  -> plan/list/explain senza creare package
  -> package composto esattamente dagli item inclusi nel piano
  -> manifest con policy, route, hash e snapshot osservato
```

Nel presente contratto una **route AI** è un obiettivo di analisi dichiarato, per esempio
`technical_extraction`, `domain_interpretation`, `mapping_discovery`,
`conflict_analysis`, `question_generation` o `temporal_interpretation`. Non è un provider,
un modello, un endpoint, una credenziale o una chiamata di rete. L'eleggibilità non è una
proprietà assoluta dell'evidenza: la stessa evidenza può essere esclusa per una route già
coperta deterministicamente e inclusa per una route interpretativa.

### Contratto funzionale minimo

1. Introduci un motore core di `AI evidence selection` riusabile dal comando di anteprima
   e dal packager esistente. Il motore legge il registry senza modificarne facts,
   relations, decisioni o viste effettive.
2. Introduci policy locali versionate, separate dai profili del worker di packaging. Il
   nome passato dalla CLI deve risolversi in modo sicuro sotto una directory del workspace,
   preferibilmente `configs/ai_selection/`, senza path traversal. Ogni policy dichiara
   almeno `policy_id`, `policy_version`, `route_id`, `route_version`, tipi di evidenza
   ammessi, criteri di inclusione/esclusione, preferenze di ranking e budget.
3. Supporta almeno i criteri realmente osservabili nel registry corrente:
   `source_type`, `source_subtype`, estensione, `authority_level`, revisione corrente,
   `chunk|fragment`, `fragment_type`, producer/parser/chunker e relativa versione,
   locator completo, status dell'evidenza e copertura deterministica. Liste vuote devono
   avere semantica esplicita e non possono trasformarsi accidentalmente in “escludi tutto”.
4. Deriva la provenienza da campi persistiti e `metadata_json`: per i chunk usa
   `chunker`/`chunker_version`; per i frammenti usa `parser`/`parser_version`. Metadati
   assenti, invalidi o incompleti producono un esito/ragione stabile, non un'assunzione.
5. Classifica la copertura deterministica per evidenza usando le regole versionate e i
   candidati già persistiti. Distingui almeno: nessuna regola applicabile, regola
   applicabile senza candidato, candidato prodotto `pending`, testa corrente `confirmed`,
   testa corrente `rejected` e candidato `superseded`/non-leaf. Solo una decisione positiva
   corrente può rappresentare copertura confermata. Non equiparare `pending` a copertura
   autoritativa e non dedurre copertura completa dalla sola presenza di un candidate row.
6. La policy decide come trattare gli stati di copertura per la route. Non introdurre la
   regola globale “prodotto da parser specializzato = non adatto all'AI”: un frammento DDL
   può essere coperto per `technical_extraction` e restare utile per
   `domain_interpretation` o `mapping_discovery`.
7. Per le evidenze eleggibili calcola un ranking deterministico guidato esclusivamente
   dalle preferenze ordinate della policy. Applica tie-break stabili basati su dati
   canonici, con ultimo livello almeno
   `source_revision_id, evidence_kind, sequence, evidence_id`. Non usare embeddings,
   similarità vettoriale, LLM, nomi “intelligenti” o euristiche non dichiarate. Registra
   rank e criteri matched, così “più adatto” è spiegabile e testabile.
8. Applica budget riproducibili almeno su numero di evidenze esaminate, numero di evidenze
   selezionate e caratteri totali destinati al package. I limiti hard devono fallire prima
   di pubblicare output parziali; i limiti di selezione devono escludere deterministicamente
   gli item oltre soglia con una reason stabile. Definisci precisamente il conteggio dei
   caratteri dopo normalizzazione newline e in relazione al `max_evidence_chars` del
   profilo package.
9. Un comando di plan crea una run dedicata e un piano persistito, ma non crea directory
   `AIPKG_*`, record `ai_packages` o file candidati. Il piano registra sia gli inclusi sia
   gli esclusi, con una o più reason code ordinate e dati sufficienti per `list` ed
   `explain`, senza duplicare il testo sorgente nel database o nei log.
10. `list` e `explain` leggono il piano persistito e non lo ricalcolano silenziosamente.
    `explain` mostra route/policy, outcome, rank, reason code, criteri matched e stato di
    copertura osservato per l'ID richiesto. ID mancanti o ambigui falliscono con messaggio
    leggibile e senza traceback.
11. Il packaging policy-driven deve usare il costruttore e il worker esistenti e includere
    **esattamente** gli item `included` del piano, nello stesso ordine canonico. Non deve
    rieseguire una selezione diversa dentro il worker. Il worker resta isolato dal database
    e riceve il piano/insieme già risolto dall'orchestratore.
12. Estendi il package con `selection_plan.json` e con riferimenti coerenti in
    `package_manifest.json`/`source_manifest.json`: plan ID/hash, route ID/version, policy
    ID/version, hash della configurazione risolta, relevant-state hash, contatori
    inclusi/esclusi e reason summary. `selection_plan.json` entra nel `package_hash` senza
    self-reference. Tutti i path condivisibili sono relativi al workspace e usano `/`.
13. Prima di riusare un piano persistito per il package, verifica che revisioni, status/hash
    delle evidenze e stato di derivazione/review rilevante coincidano con lo snapshot del
    piano. Se divergono, rifiuta con `selection_plan_stale`; non ricalcolare, non aggiornare
    e non “aggiustare” il piano storico.
14. Introduci una migrazione append-only successiva alla v10 per persistere almeno piani,
    item di piano e legame package→piano. Usa ID ordinati stabili, per esempio
    `AISEL_000001`; conserva la leggibilità dei database e package legacy. I piani completati
    e i loro item sono snapshot storici e non vengono riscritti.
15. Riusa `canonical_json_v1`/`canonical_sha256_v1`. Il `selection_plan_hash` deve escludere
    plan ID, run ID, timestamp e path operativi e includere route/policy versionate,
    configurazione risolta, scope, proiezione ordinata di tutti gli esiti e
    `relevant_state_hash`. Quest'ultimo include solo lo stato che può cambiare il risultato:
    revisioni/fonti, status e hash delle evidenze, regole applicabili, candidati
    deterministici pertinenti e teste di review osservate.
16. Conserva integralmente il comportamento legacy di `ai package` e `ai package-batch`
    quando non viene richiesta una policy o un piano. I filtri legacy `--revision`,
    `--profile`, `include_chunks` e `include_fragments` continuano a funzionare. In modalità
    policy-driven evita doppi filtri impliciti: valida e documenta la composizione fra scope
    revisioni, policy e profilo package; combinazioni incompatibili devono fallire con una
    reason stabile.

### CLI richiesta

Implementa, mantenendo anche la compatibilità `python -m dsl_mngr`:

```text
dsl-manager ai evidence plan <workspace> --policy <nome> [--revision REV_...]... [--profile ai_package.default]
dsl-manager ai evidence list <workspace> --plan AISEL_000001 [--outcome included|excluded]
dsl-manager ai evidence explain <workspace> --plan AISEL_000001 <evidence_id>
dsl-manager ai package <workspace> --selection-policy <nome> [--revision REV_...]... [--profile ai_package.default]
dsl-manager ai package <workspace> --selection-plan AISEL_000001 [--profile ai_package.default]
```

Semantica obbligatoria:

- `ai evidence plan` persiste un piano e stampa almeno plan ID, route, policy, conteggi,
  reason summary, relevant-state hash, plan hash e report path; non crea package;
- `ai evidence list` ordina per outcome/rank/ID e consente di vedere l'insieme incluso o
  escluso senza stampare contenuti sorgente estesi;
- `ai evidence explain` spiega una decisione presa nello snapshot indicato;
- `ai package --selection-policy` crea e persiste un nuovo piano sullo stato corrente,
  quindi costruisce atomicamente il package da quel piano;
- `ai package --selection-plan` riusa esattamente un piano già completato, dopo il controllo
  stale;
- `--selection-policy` e `--selection-plan` sono mutuamente esclusivi;
- una selezione valida con zero item inclusi termina con esito catalogato non-zero e non
  pubblica un package vuoto;
- `ai package-batch` non acquisisce nuove semantiche policy-driven in questa Slice, salvo il
  minimo adeguamento strettamente necessario per preservare il percorso legacy.

### Configurazione e motivazioni

Fornisci almeno due policy di workspace minimali e controllate che dimostrino la dipendenza
dalla route, per esempio una per `technical_extraction` e una per
`domain_interpretation`. Usa il parser/config loader corrente o una sua estensione minima;
non aggiungere un secondo parser YAML o una dipendenza runtime.

Il catalogo delle reason code deve essere versionato, stabile e condiviso fra core, CLI,
artifact e test. Come minimo copri le famiglie:

```text
included_by_policy
not_current_revision
inactive_source
inactive_evidence
evidence_kind_excluded
source_type_excluded
source_subtype_excluded
extension_excluded
authority_level_excluded
fragment_type_excluded
producer_excluded
producer_version_excluded
incomplete_locator
deterministic_coverage_excluded
selection_item_budget_exceeded
selection_char_budget_exceeded
selection_plan_stale
no_ai_eligible_evidence
invalid_selection_policy
selection_profile_conflict
```

I nomi finali possono essere affinati solo per allinearsi a un catalogo già esistente, ma
devono conservare distinzione semantica, essere documentati e comparire nei test. Nessun
errore atteso deve lasciare migrazioni, piani o package parziali pubblicati.

### Test e criteri di accettazione specifici

Aggiungi test deterministici mirati, preferibilmente in
`tests/test_slice_30_ai_evidence_selection.py`, rafforzando anche i test della Slice 15
quando serve a provare la compatibilità. Copri almeno:

- upgrade reale v10→nuova migrazione, idempotenza, atomicità e rollback;
- policy invalida, chiave sconosciuta in modalità strict, nome/path non sicuro e valori non
  ammessi;
- stessa evidenza con outcome diverso fra route tecnica e route interpretativa;
- chunk documentali e frammenti prodotti da DDL/XML/DB code/log/Excel con producer e locator
  reali, senza confondere metadati con verità di dominio;
- distinzione fra regola applicabile, nessun candidato, `pending`, testa `confirmed`, testa
  `rejected` e candidato superseded/non-leaf;
- ranking, tie-break, budget at/over e ordine di input inverso;
- due plan sullo stesso snapshot con stesso hash semantico e stessa proiezione, pur avendo
  plan/run ID e timestamp differenti;
- `plan` senza package, `list`/`explain` read-only e output CLI stabile;
- package da policy e da plan con esattamente gli evidence ID inclusi, ordine invariato,
  `selection_plan.json`, manifest coerenti e hash verificabili;
- stale dopo cambio revisione/evidence hash e, per policy che usa coverage, dopo cambio
  della testa di review o delle regole pertinenti;
- zero inclusi, conflitto col profilo package e failure atomiche senza outbox parziale;
- compatibilità byte/semantica dei package legacy e di `ai package-batch` senza opzioni di
  selezione;
- entrambi gli entry point, `--help`, exit code, stdout/stderr e assenza di traceback;
- divieto di rete tramite monkeypatch/fake; nessuna AI reale necessaria.

Acceptance criteria:

```text
stesso registry rilevante + stessa route/policy/config/versioni
  = stessa selezione, stesso ordine e stesso selection_plan_hash

package policy-driven
  = esattamente gli item inclusi nel piano verificato

ogni item incluso o escluso
  = almeno una motivazione stabile e spiegabile
```

Sono fuori scope: invocare provider AI; scegliere modelli o endpoint; inviare package;
embeddings/vector database; classificazione probabilistica; apprendimento automatico;
modifica diretta di candidati/facts/relations/DSL; UI web per la selezione; scheduler;
modifica retroattiva del design v02; correzione dei gap GEXF/result-catalog documentati
dalla Slice 29, salvo dipendenza minima e inevitabile dimostrata.

## Protocollo operativo comune obbligatorio

Le istruzioni di questa sezione integrano il nucleo normativo della Slice 30 e applicano il
protocollo consolidato dei prompt 20-29. Non trasformare abbreviazioni o ambiguità in nuove
decisioni progettuali.

### Autorità delle fonti e stato del design

Applica questa regola:

- `AGENTS.md` governa ambiente, processo e convenzioni del repository;
- un eventuale `.kb/documenti/documenti di design/run 3/design_document_v_03.md`, se
  presente e approvato al momento dell'esecuzione, governa i requisiti funzionali della
  run 3 e deve essere letto integralmente;
- il presente prompt governa il contratto funzionale e operativo della Slice 30 in quanto
  estensione post-v02 espressamente autorizzata;
- `.kb/documenti/documenti di design/run 2/design_document_v_02.md` resta la baseline
  vincolante per le capacità 20-29 e non va riscritto per fingere che includesse la 30;
- la sezione “È ipotizzabile una slice 30?” del manuale completo costituisce la motivazione
  progettuale specifica per `plan → inspect/explain → package`;
- il design v01 resta baseline concettuale per registry-first, evidence-or-reject, worker
  isolati e AI black-box;
- codice, schema e test correnti sono stato osservato, non autorità per ridefinire
  silenziosamente il contratto;
- report precedenti sono storia implementativa e non prova sufficiente di conformità.

Il vincolo del design v02 “esattamente 20-29” è noto e non va ignorato: descrive la chiusura
della run 2. La decisione esplicita di creare questo prompt autorizza una Slice 30 separata,
senza emendare retroattivamente v02. Se al momento dell'esecuzione esiste un design v03 che
contraddice in modo sostanziale il presente contratto, documenta il conflitto e fermati
prima della modifica interessata; non arbitrare silenziosamente.

### Letture obbligatorie prima del codice

Leggi integralmente, nell'ordine utile al task:

- `AGENTS.md`;
- `.kb/documenti/documenti di design/run 2/design_document_v_02.md`;
- `.kb/documenti/documenti di design/run 1/design_document_v_01.md`;
- l'eventuale `.kb/documenti/documenti di design/run 3/design_document_v_03.md`;
- `.kb/template/template_slice.md`;
- `.kb/template/template_slice_report.md`;
- `.kb/documenti/project_summary.md`;
- `.kb/documenti/documenti tecnici/analisi_tecnica_dsl_manager.md`;
- `.kb/documenti/documenti tecnici/contratti_manifest_dsl_manager.md`;
- `.kb/documenti/manuali/manuale_utente_dsl_manager.md`;
- `.kb/documenti/manuali/outline_dsl_manager_flow_from_input_to_output_riassunto.md`;
- `.kb/documenti/manuali/outline_dsl_manager_flow_from_input_to_output_completo.md`, in
  particolare l'intera discussione che inizia con “È ipotizzabile una slice 30?” e termina
  con la raccomandazione `plan → inspect/explain → package`;
- `.kb/documenti/documenti di design/run 2/materiale di supporto/analisi_presenza_funzione_candidati_deterministici.md`;
- `.kb/documenti/documenti di design/run 2/materiale di supporto/discussione_su_candidati_deterministici_01.md`;
- `.kb/documenti/documenti di design/run 2/materiale di supporto/discussione_su_candidati_deterministici_02.md`.

Leggi inoltre **integralmente tutti i report precedenti**, in ordine numerico, usando
esattamente questi file:

- `.kb/projects/slicing/slice_01/dsl_manager_slice_01_report.md`
- `.kb/projects/slicing/slice_02/dsl_manager_slice_02_report.md`
- `.kb/projects/slicing/slice_03/dsl_manager_slice_03_report.md`
- `.kb/projects/slicing/slice_04/dsl_manager_slice_04_report.md`
- `.kb/projects/slicing/slice_05/dsl_manager_slice_05_report.md`
- `.kb/projects/slicing/slice_06/dsl_manager_slice_06_report.md`
- `.kb/projects/slicing/slice_07/dsl_manager_slice_07_report.md`
- `.kb/projects/slicing/slice_08/dsl_manager_slice_08_report.md`
- `.kb/projects/slicing/slice_09/dsl_manager_slice_09_report.md`
- `.kb/projects/slicing/slice_10/dsl_manager_slice_10_report.md`
- `.kb/projects/slicing/slice_11/dsl_manager_slice_11_report.md`
- `.kb/projects/slicing/slice_12/dsl_manager_slice_12_report.md`
- `.kb/projects/slicing/slice_13/dsl_manager_slice_13_report.md`
- `.kb/projects/slicing/slice_14/dsl_manager_slice_14_report.md`
- `.kb/projects/slicing/slice_15/dsl_manager_slice_15_report.md`
- `.kb/projects/slicing/slice_16/dsl_manager_slice_16_report.md`
- `.kb/projects/slicing/slice_17/dsl_manager_slice_17_report.md`
- `.kb/projects/slicing/slice_18/dsl_manager_slice_18_report.md`
- `.kb/projects/slicing/slice_19/dsl_manager_slice_19_report.md`
- `.kb/projects/slicing/slice_20/dsl_manager_slice_20_report.md`
- `.kb/projects/slicing/slice_21/dsl_manager_slice_21_report.md`
- `.kb/projects/slicing/slice_22/dsl_manager_slice_22_report.md`
- `.kb/projects/slicing/slice_23/dsl_manager_slice_23_report.md`
- `.kb/projects/slicing/slice_24/dsl_manager_slice_24_report.md`
- `.kb/projects/slicing/slice_25/dsl_manager_slice_25_report.md`
- `.kb/projects/slicing/slice_26/dsl_manager_slice_26_report.md`
- `.kb/projects/slicing/slice_27/dsl_manager_slice_27_report.md`
- `.kb/projects/slicing/slice_28/dsl_manager_slice_28_report.md`
- `.kb/projects/slicing/slice_29/dsl_manager_slice_29_report.md`

Infine:

- ispeziona integralmente il codice corrente sotto `src/dsl_mngr` e i test sotto `tests`,
  incluse fixture, golden ed expected pertinenti;
- verifica schema e migrazioni reali, in particolare `ai_packages`, chunks/fragments,
  `candidate_batches`, `candidate_records`, derivation runs, lineage, review heads e viste
  effettive;
- verifica l'help corrente di `ai package`, `ai package-batch`, `ai inbox`, `candidates
  derive` e `candidates review`;
- cerca e riusa almeno `core/ai_package.py`, `cli/commands/ai.py`,
  `workers/build_ai_package.py`, `core/candidate_derivation.py`,
  `core/candidate_review.py`, `core/canonical.py`, `core/config.py`, `core/migrations.py`,
  `core/runs.py`, `core/chunk_registry.py` e `core/fragment_registry.py`;
- verifica le modifiche locali correnti e non sovrascrivere la correzione YAML multilinea o
  altri cambi utente preesistenti.

### Controllo anti-drift e gate delle dipendenze

Prima di modificare file:

1. mostra `git status --short --branch` e preserva tutte le modifiche preesistenti non
   correlate;
2. confronta richiesta Slice 30 → discussione → design v01/v02/(eventuale v03) → report
   01-29 → schema/migrazioni → codice → test/fixture/golden;
3. verifica realmente le capacità AI package della 15, candidate/review/derivation delle
   20-21, batch della 22, Excel delle 23-25, temporalità della 26-27 e documentazione della
   29, limitatamente alle dipendenze usate dalla selezione;
4. classifica ogni precondizione come `pronta`, `gap non bloccante` o
   `bloccata da dipendenza`;
5. costruisci una checklist iniziale
   `requisito → implementazione prevista → test previsto`;
6. dichiara brevemente i file che prevedi di modificare.

Se una precondizione precedente manca, non dichiarare la Slice completata e non introdurre
un fix fuori scope silenzioso. Identifica la Slice proprietaria; correggi soltanto un gap
minimo indispensabile, compatibile col contratto e documentato. I gap GEXF budget e
`result_catalog_v1` già registrati dalla Slice 29 non bloccano di per sé questa Slice e non
devono diventare un pretesto per un refactor laterale.

### Interprete, ambiente e vincoli trasversali

Usa Python `>=3.12,<3.13` e determina l'interprete esclusivamente secondo le regole
environment-specific di `AGENTS.md`. Prima di modificare codice installa il progetto in
editable mode con extra dev usando quell'interprete:

```text
python -m pip install -e ".[dev]"
```

Usa lo stesso interprete per test e comandi successivi e riportalo nel report.

- usa import assoluti da `dsl_mngr`; non importare `src` come package;
- mantieni separate CLI, core/service, persistence, worker e test;
- non introdurre ORM, server, servizi esterni o nuove dipendenze runtime;
- aggiungi soltanto migrazioni append-only; non riscrivere v1-v10;
- riusa il profilo canonico v1 e gli helper di run/artifact/path esistenti;
- usa path relativi al workspace e `/` negli artifact condivisibili;
- non includere path, timestamp, run/plan/package ID o note audit negli hash semantici;
- non inserire testi sorgente lunghi o sensibili in log, reason o report;
- nessuna rete o AI reale a runtime o nei test della selezione;
- non modificare fixture/golden per mascherare regressioni;
- mantieni leggibili package, database e comandi legacy;
- non introdurre fallback o interpretazioni semantiche non dichiarate.

### Esecuzione, test e chiusura

Procedura obbligatoria:

1. esegui il preflight e dichiara i file previsti;
2. esegui eventuali test baseline mirati già esistenti per AI package, derivazione e review;
3. implementa soltanto il perimetro della Slice 30, rafforzando le funzioni esistenti;
4. aggiungi i test richiesti e una fixture/policy minima solo se necessaria;
5. esegui prima i test mirati della Slice 30 e le regressioni Slice 15/20/21 pertinenti;
6. esegui poi l'intera suite col Python di progetto;
7. verifica entrambi gli entry point, tutti i nuovi `--help`, exit code e stdout/stderr;
8. esegui `git diff --check`;
9. mostra `git diff --stat`, `git status --short` e revisiona il diff completo pertinente;
10. completa la checklist `requisito → file/test → esito`;
11. esegui un'autoverifica finale contro scope, non-obiettivi, determinismo, auditabilità,
    privacy, failure mode, compatibilità e Definition of Done.

Non dichiarare passato un test non eseguito. Per test falliti, saltati, interrotti o non
eseguibili registra comando, interprete/versione, exit code/esito, causa osservata,
classificazione (`preesistente`, `introdotto dalla Slice`, `limite ambiente`), verifica
alternativa e impatto. La suite completa deve passare per dichiarare la Slice `completata`,
salvo una limitazione ambientale dimostrata che non mascheri regressioni.

### Report obbligatorio

- salva una copia del report prodotto al termine del task nel file `.kb/projects/slicing/slice_30/dsl_manager_slice_30_report.md`, usando come template `.kb/template/template_slice_report.md`.

Il report deve includere almeno:

- stato reale `completata | parziale | bloccata`;
- esito del controllo anti-drift e delle precondizioni;
- prova che l'implementazione rafforza il packager esistente invece di duplicarlo;
- file modificati, migrazione/schema, API/CLI, configurazioni e artifact;
- matrice `route/policy/criterio → evidence state → outcome/reason → test`;
- contratto di canonicalizzazione, relevant-state hash, plan hash e stale detection;
- compatibilità del percorso legacy e combinazioni di opzioni rifiutate;
- checklist requisito → file/test → esito;
- interprete/versione, installazione editable e tutti i test/verifiche con risultato;
- failure, scostamenti, problemi preesistenti e funzionalità fuori scope;
- `git diff --check`, diff stat e stato Git finale.

## Integrazioni operative specifiche — Slice 30

- Parti da `prepare_ai_package_input` e dal worker esistenti: separa la decisione di
  selezione dalla materializzazione del package, ma non duplicare rendering, manifest,
  hash o stale check già affidabili.
- Nel preflight produci una matrice dello stato reale
  `dato richiesto dalla policy → tabella/campo/metadata/API esistente → gap → decisione`.
- Nel report produci una matrice
  `route → policy → evidenza → coverage osservata → rank → outcome → reason` che includa
  almeno un'evidenza con esito diverso fra route.
- Verifica che il piano sia una fotografia spiegabile: `list` ed `explain` devono mostrare
  la decisione storica anche se lo stato corrente cambia, mentre il riuso per packaging
  deve essere bloccato come stale.
- Verifica che il package non contenga evidenze escluse, che non perda evidenze incluse e
  che i suoi conteggi/hash siano ricostruibili dal piano.
- Mantieni `AI as candidate generator`: il risultato atteso dall'AI resta un batch di
  candidati sottoposto a validation/review; la Slice non autorizza scritture dirette nel
  DSL o nel registro autoritativo.

## Regola finale di accettazione

La Slice 30 può essere dichiarata `completata` soltanto se soddisfa il nucleo normativo, il
protocollo operativo comune e le integrazioni specifiche sopra, con suite completa verde.
Deve consegnare una singola verticalità `plan → inspect/explain → package`, riusando il
packager esistente. Ogni evidenza deve avere una decisione spiegabile; l'ordine e gli hash
devono essere riproducibili; un piano stale non deve essere riutilizzato; il percorso
legacy deve restare compatibile; nessun provider AI, rete o mutazione semantica diretta
deve essere introdotto.
