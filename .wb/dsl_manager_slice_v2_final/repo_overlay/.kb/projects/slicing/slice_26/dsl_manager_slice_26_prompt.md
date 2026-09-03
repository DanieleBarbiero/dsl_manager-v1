# Prompt Slice 26

<!--
Core normativo estratto deterministicamente da:
.kb/documenti/documenti di design/run 2/design_document_v_02.md
Slice: 26
Il core sotto è conservato letteralmente; protocollo e integrazioni lo rendono operativo senza reinterpretarne il perimetro.
-->

## Nucleo normativo originale v02

Implementa solo la Slice 26 — nucleo temporale completo, DSL schema 2, hashing e GEXF 1.3 dinamico validato offline. Produci `.kb/projects/slicing/slice_26/dsl_manager_slice_26_report.md`.

Leggi integralmente `AGENTS.md`, design v02, documento metadata chat, proposta temporale, design v01, contratti snapshot/diff/GEXF, report 17 e 20–25 e tutte le fonti ufficiali della sezione 20. Il prompt/design v02 prevale sulla proposta di supporto in caso di conflitto. Usa Python 3.12 configurato; aggiungi il pin `lxml==6.1.2`; installa editable dev; preserva il worktree.

Obiettivo verticale minimo: evidenza OOXML grezza→candidato temporale pending→review comune→intervallo validato→DSL v2 persistito/riletto→GEXF 1.3 dinamico valido XSD e semanticamente, tutto offline.

Implementa migrazione v9 e modello della sezione 8.3. Estrai almeno core properties, app properties e timestamp ZIP separati, con tutti i campi raw/metodo/versione/precisione/timezone/reliability/warning. Estendi `candidate_records` al tipo temporale e usa esclusivamente `CandidateReviewService`. Supporta target source_revision/source_fragment/candidate_record/fact/relation e zero/un intervallo. Non ereditare automaticamente l'intervallo sorgente.

Implementa `dsl render --schema-version 2`, default v1, `metadata.schema_version="2"`, `metadata.temporal.base="day"|"timestamp"`, timezone esplicita/`unknown` e `intervals` sempre presenti; usa effective views, hash semantico e roundtrip snapshot. Diff solo same-schema. Export dinamico solo v2, namespace/version/mode/timeformat/intervalli inclusivi.

Vendi `gexf.xsd`, `dynamics.xsd`, `viz.xsd` nel path e con commit/URL/licenza/SHA esatti della sezione 13.2. Usa lxml no-network con resolver allowlist locale; aggiungi validazione semantica di riferimenti, tipi, ordine e bounds. Testa packaging via `importlib.resources` e SHA. Un unico timeformat per file; day e dateTime timezone-resolved; unknown/incompatible non esportato silenziosamente.

Non aggiungere ancora fonti PDF/HTML/nome/contenuto, multi-intervallo o cross-schema diff. Non usare filesystem timestamp, alta confidenza come conferma, rete o XSD scaricati a runtime.

Test obbligatori: migrazioni/rollback; raw fields; proprietà concordanti/contraddittorie; timezone; common review; un interval max; `intervals=[]`; v2 hash/golden/persist-re-read; v1 immutabile/default; reconciliation block e allow-incomplete solo v2; tre SHA XSD, package, no-network; namespace/mode/timeformat; edge bounds/ref/type; output non registrato su errore. Esegui suite completa.

Done: solo interval resolved+confirmed appare nel DSL/grafo, XSD e semantic validation passano offline e v1 resta compatibile. Elenca file prima; riporta test/diff dopo.

## Protocollo operativo comune obbligatorio

Le istruzioni di questa sezione **integrano** il nucleo normativo v02 senza modificarne il perimetro funzionale. Servono a rendere il prompt autonomo e operativo come i prompt maturi della run 1. Non trasformare abbreviazioni o ambiguità del nucleo in nuove decisioni progettuali.

### Autorità delle fonti

Applica questa regola senza creare una graduatoria concorrente:

- `AGENTS.md` governa ambiente, processo e convenzioni del repository;
- `.kb/documenti/documenti di design/run 2/design_document_v_02.md` governa requisiti funzionali, invarianti e confini della run 2;
- il presente prompt governa l'esecuzione operativa della Slice 26;
- codice, schema e test correnti rappresentano lo **stato osservato** e non possono modificare implicitamente il design;
- report precedenti e `.kb/documenti/documenti di design/run 1/design_document_v_01.md` sono storia implementativa/baseline concettuale, salvo richiami normativi espliciti del design v02.

Se due fonti producono una contraddizione non risolvibile con queste responsabilità, **non scegliere silenziosamente una variante e non introdurre una nuova decisione progettuale**: documenta il conflitto e fermati prima della modifica che lo renderebbe concreto.

### Letture obbligatorie prima del codice

Leggi integralmente, nell'ordine utile al task:

- `AGENTS.md`;
- `.kb/documenti/documenti di design/run 2/design_document_v_02.md`;
- `.kb/documenti/documenti di design/run 1/design_document_v_01.md` come baseline concettuale nei soli punti non sostituiti dal v02;
- `.kb/template/template_slice_report.md`;
- i documenti pertinenti della Slice 26:
- `.kb/documenti/documenti tecnici/analisi_tecnica_dsl_manager.md`
- `.kb/documenti/documenti tecnici/contratti_manifest_dsl_manager.md`
- `.kb/documenti/manuali/manuale_utente_dsl_manager.md`
- `.kb/documenti/chat/quanto possiamo fidarci dei metadati dei file.md`
- `.kb/documenti/documenti di design/run 2/materiale di supporto/dsl_manager_estensione_temporalita_semantica_v_01.md`
- `.kb/documenti/chat/formati file e temporalità semantica - produce design per marcatori temporali run 2.md`

Leggi inoltre **integralmente tutti i report precedenti**, in ordine numerico, usando esattamente questi file:

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

Infine:

- ispeziona il codice corrente sotto `src/dsl_mngr`;
- ispeziona i test correnti sotto `tests`, incluse fixture, golden e expected pertinenti;
- verifica schema e migrazioni effettivamente presenti;
- verifica i comandi e le opzioni pubbliche correnti con il relativo `--help` quando la Slice li usa o li modifica;
- cerca prima componenti/API già esistenti e riusabili; non assumere l'assenza di un componente senza verificarla nel worktree.

I report sono storia utile, registro di scostamenti e verifiche passate, **non prova sufficiente** che il worktree corrente sia conforme o che la suite corrente sia verde.

### Controllo anti-drift e gate delle dipendenze

Prima di modificare file:

1. mostra `git status --short --branch` e preserva ogni modifica preesistente non correlata;
2. confronta il perimetro e le precondizioni della Slice 26 con design v02 e matrice di tracciabilità;
3. confronta design → report precedenti → schema/migrazioni → codice → test/fixture/golden correnti;
4. verifica nel codice e nei test che le capacità richieste dalle dipendenze della Slice siano realmente presenti e funzionanti;
5. registra i gap distinguendo `pronta`, `gap non bloccante` e `bloccata da dipendenza`;
6. dichiara brevemente i file che prevedi di modificare.

Se emerge una precondizione appartenente a una Slice precedente che manca o viola il contratto:

- non dichiarare la Slice corrente completata;
- non introdurre silenziosamente una correzione fuori scope;
- identifica la Slice proprietaria del difetto;
- applica una correzione soltanto se è minima, indispensabile per la verticalità corrente e compatibile con il design, documentandola esplicitamente;
- altrimenti dichiara la Slice `parziale` o `bloccata` con evidenza riproducibile;
- non modificare test, fixture o golden per nascondere la deviazione.

### Interprete e ambiente

Usa Python `>=3.12,<3.13` e determina l'interprete **esclusivamente** secondo le regole environment-specific di `AGENTS.md`. Non introdurre una seconda selezione, un fallback al Python globale o una regola concorrente.

Qualunque formulazione environment-specific contenuta nel nucleo originale — inclusi riferimenti diretti a `.codex/config.toml` — va interpretata attraverso l'`AGENTS.md` corrente: in VS Code/Windows si applica `PROJECT_PYTHON`; in Codex cloud si usa il runtime cloud e si ignora la configurazione locale, come prescritto da `AGENTS.md`.

Prima di modificare codice, installa il progetto in editable mode con extra dev usando l'interprete così determinato:

```text
python -m pip install -e ".[dev]"
```

Usa **lo stesso interprete** per test e comandi Python successivi e riportalo nel report.

### Vincoli trasversali

- usa import assoluti da `dsl_mngr`; non importare `src` come package;
- mantieni separate CLI, core/domain/service, persistence, worker e test secondo l'architettura corrente;
- non introdurre ORM, servizi esterni o dipendenze runtime non richieste; motiva nel report ogni nuova dipendenza;
- non modificare migrazioni già applicate: aggiungi soltanto migrazioni append-only previste dal design;
- usa path relativi al workspace e `/` negli artifact condivisibili;
- non inserire path assoluti, timestamp operativi, run ID o note audit negli hash semantici;
- non salvare contenuti sorgente lunghi o sensibili in log/report;
- conserva compatibilità pubblica e leggibilità degli artifact/snapshot storici salvo modifica esplicita del design;
- nessuna rete o chiamata AI reale nei percorsi/test in cui il design le vieta;
- non sostituire silenziosamente dipendenze, algoritmi, versioni o formati richiesti con fallback non autorizzati.

### Tracciabilità minima della Slice 26

Prima del codice costruisci una checklist `requisito → implementazione prevista → test previsto` usando **tutte** le righe della sezione 17 del design assegnate alla Slice 26. Come minimo considera:

- evidenza temporale grezza → `test_slice_26_raw_evidence_fields`
- review temporale comune → `test_slice_26_common_review`
- DSL v2 → `test_slice_26_dsl_v2_roundtrip`
- GEXF 1.3 offline → `test_slice_26_gexf_offline`
- precisione e timezone (responsabilità condivisa con Slice 27)
- immutabilità snapshot storici → `test_slice_26_historical_snapshot_immutable`

Alla fine completa la stessa checklist con file/test/esito. Una riga pertinente non verificata impedisce di dichiarare la Slice completata.

### Esecuzione, test e chiusura

Procedura obbligatoria:

1. dopo il preflight, implementa soltanto il perimetro della Slice 26;
2. se esiste già un test mirato pertinente alla baseline che stai per modificare, eseguilo prima del cambiamento e registra l'esito; se non esiste, registralo senza inventare un test baseline artificiale;
3. aggiungi/aggiorna i test richiesti dal design e dal nucleo;
4. esegui prima i test mirati della Slice;
5. esegui poi l'intera suite con l'interprete di progetto;
6. per ogni comando CLI nuovo o modificato verifica l'entry point `dsl-manager`, l'equivalente `python -m dsl_mngr`, `--help`, exit code e stdout/stderr; gli errori attesi non devono produrre traceback utente;
7. esegui `git diff --check`;
8. mostra `git diff --stat`, `git status --short` e revisiona il diff completo pertinente alla Slice;
9. verifica che non siano entrate modifiche non correlate o feature di Slice successive;
10. esegui un'autoverifica finale contro perimetro, non-obiettivi, invarianti, matrice di tracciabilità, failure mode, compatibilità legacy, determinismo e Definition of Done.

Non dichiarare un test passato se non è stato eseguito. Per ogni test fallito, saltato, interrotto o non eseguibile riporta comando esatto, interprete/versione, exit code/esito, causa osservata, classificazione (`preesistente`, `introdotto dalla Slice`, `limite ambiente`), eventuale verifica alternativa e impatto sulla Definition of Done.

La suite completa deve passare per dichiarare la Slice `completata`, salvo una limitazione ambientale dimostrata e chiaramente distinta da un difetto del codice; tale eccezione va motivata nel report e non può mascherare una regressione.

### Report obbligatorio

Al termine salva una copia del report in:

`.kb/projects/slicing/slice_26/dsl_manager_slice_26_report.md`

usando **integralmente come template** `.kb/template/template_slice_report.md`.

Il report deve includere almeno:

- stato reale della Slice: `completata`, `parziale` o `bloccata`;
- esito del controllo anti-drift e delle precondizioni;
- file modificati;
- migrazioni/schema, API/comandi e artifact interessati;
- checklist di tracciabilità requisito → file/test → esito;
- interprete Python/versione e comando di installazione editable;
- tutti i comandi di test/verifica con risultati;
- test falliti, saltati, interrotti o non eseguiti e relativa classificazione;
- `git diff --check`, diff stat e stato finale;
- scostamenti dal design, problemi preesistenti e correzioni appartenenti a Slice precedenti;
- funzionalità volutamente fuori scope.

Non creare o aggiornare golden/fixture soltanto per rendere verde la suite e non dichiarare completata una capacità che non hai verificato.

## Integrazioni operative specifiche — Slice 26

- Tratta la Slice 26 come gate ad alto rischio: prima del codice verifica lo stato reale delle Slice 20–25, in particolare review/effective views, batch, Excel e compatibilità legacy. Se review/effective views non rispettano il contratto v02, fermati prima di costruire DSL v2/GEXF sopra una baseline divergente.
- Risolvi sempre con path letterali il documento metadata, la proposta temporale e i contratti; design/prompt v02 prevalgono sui documenti di supporto quando questi divergono.
- Verifica e registra URL, commit upstream, licenza e SHA-256 esatti delle tre risorse XSD indicate nella sezione 13.2; nessun download a runtime.
- Produci cinque checklist indipendenti nel report: (1) migrazione/review, (2) evidenza temporale/intervallo, (3) DSL v2/hash/diff, (4) GEXF XSD+semantico, (5) packaging/resources/offline.
- Includi una matrice `schema version × render × diff × export × allow-incomplete` e una prova che snapshot v1 preesistenti restino byte/hash invariati.

## Regola finale di accettazione

La Slice 26 può essere dichiarata `completata` soltanto se soddisfa **sia** il nucleo normativo v02 **sia** il protocollo operativo comune e le integrazioni specifiche sopra. Le integrazioni operative possono rafforzare verifiche e audit, ma non possono ampliare il perimetro funzionale, spostare feature fra Slice, rendere opzionale un requisito del design o introdurre fallback non autorizzati.
