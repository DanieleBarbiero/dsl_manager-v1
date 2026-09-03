# Prompt Slice 23

<!--
Core normativo estratto deterministicamente da:
.kb/documenti/documenti di design/run 2/design_document_v_02.md
Slice: 23
Il core sotto è conservato letteralmente; protocollo e integrazioni lo rendono operativo senza reinterpretarne il perimetro.
-->

## Nucleo normativo originale v02

Implementa solo la Slice 23 — ingest trasparente e sicuro `.xlsx`/`.xlsm` con Docling 2.97.0. Produci `.kb/projects/slicing/slice_23/dsl_manager_slice_23_report.md`.

Leggi integralmente `AGENTS.md`, design v02, analisi/contratti/manuale, report 10–11 e 22, fonti ufficiali Docling v2.97.0 ed ECMA-376 Part 2 indicate nella sezione 20. Ispeziona dipendenze e worktree. Usa il Python 3.12 configurato; mantieni `docling==2.97.0`; installa editable dev senza upgrade non richiesti.

Obiettivo verticale minimo: una source revision Excel valida viene letta una volta, preflightata e passata a Docling come stream con lo stesso hash, producendo `normalized.json`, `normalized.md` e report; input malevoli falliscono prima della conversione.

Estendi routing a `.xlsx` e `.xlsm`. Carica una sequenza byte limitata, confronta SHA-256 con `source_revisions.content_hash`, crea due cursori e non riaprire il path. Implementa il preflight minimo della sezione 11.2 senza estrazione su disco, DTD/entity o rete. `.xlsm` deve superare content type macro-enabled ed essere inoltrato esplicitamente come `InputFormat.XLSX` con nome `.xlsm`; prova un file reale. Isola il worker con timeout/output/memory hard dove supportato o monitored+kill dichiarato. Pubblica artefatti atomici e usa reason/status del catalogo. Nessun ricalcolo, macro, link/query o conversione.

Non implementare manifest completo, regioni o candidati Excel. Se il test Docling `.xlsm` fallisce, marca la slice bloccata con evidenza: non introdurre LibreOffice, openpyxl come normalizzatore sostitutivo, rinomina o downgrade.

Test obbligatori: `.xlsx` reale; `.xlsm` reale; byte identity/mismatch; estensione-content type; traversal/absolute/duplicate/case-fold; zip bomb/entry e streaming limits; DTD/entity; relationship duplicate/target invalido; parti minime mancanti; external link mai dereferenziato; at/over ogni limite rilevante; timeout/output/memory mode; partial distinto; no-network; due run stessi output. Esegui suite completa.

Done: i due formati seguono il percorso trasparente autorizzato, gli attacchi hanno esiti stabili e nessun path viene riaperto. Dichiara file prima del codice e riporta test/diff.

## Protocollo operativo comune obbligatorio

Le istruzioni di questa sezione **integrano** il nucleo normativo v02 senza modificarne il perimetro funzionale. Servono a rendere il prompt autonomo e operativo come i prompt maturi della run 1. Non trasformare abbreviazioni o ambiguità del nucleo in nuove decisioni progettuali.

### Autorità delle fonti

Applica questa regola senza creare una graduatoria concorrente:

- `AGENTS.md` governa ambiente, processo e convenzioni del repository;
- `.kb/documenti/documenti di design/run 2/design_document_v_02.md` governa requisiti funzionali, invarianti e confini della run 2;
- il presente prompt governa l'esecuzione operativa della Slice 23;
- codice, schema e test correnti rappresentano lo **stato osservato** e non possono modificare implicitamente il design;
- report precedenti e `.kb/documenti/documenti di design/run 1/design_document_v_01.md` sono storia implementativa/baseline concettuale, salvo richiami normativi espliciti del design v02.

Se due fonti producono una contraddizione non risolvibile con queste responsabilità, **non scegliere silenziosamente una variante e non introdurre una nuova decisione progettuale**: documenta il conflitto e fermati prima della modifica che lo renderebbe concreto.

### Letture obbligatorie prima del codice

Leggi integralmente, nell'ordine utile al task:

- `AGENTS.md`;
- `.kb/documenti/documenti di design/run 2/design_document_v_02.md`;
- `.kb/documenti/documenti di design/run 1/design_document_v_01.md` come baseline concettuale nei soli punti non sostituiti dal v02;
- `.kb/template/template_slice_report.md`;
- i documenti pertinenti della Slice 23:
- `.kb/documenti/documenti tecnici/analisi_tecnica_dsl_manager.md`
- `.kb/documenti/documenti tecnici/contratti_manifest_dsl_manager.md`
- `.kb/documenti/manuali/manuale_utente_dsl_manager.md`

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
2. confronta il perimetro e le precondizioni della Slice 23 con design v02 e matrice di tracciabilità;
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

### Tracciabilità minima della Slice 23

Prima del codice costruisci una checklist `requisito → implementazione prevista → test previsto` usando **tutte** le righe della sezione 17 del design assegnate alla Slice 23. Come minimo considera:

- byte singoli → `test_slice_23_single_byte_sequence`
- `.xlsm` diretto → `test_slice_23_real_xlsm_docling`
- preflight sicuro → `test_slice_23_ooxml_attacks`
- due viste Excel (responsabilità condivisa con Slice 24)

Alla fine completa la stessa checklist con file/test/esito. Una riga pertinente non verificata impedisce di dichiarare la Slice completata.

### Esecuzione, test e chiusura

Procedura obbligatoria:

1. dopo il preflight, implementa soltanto il perimetro della Slice 23;
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

`.kb/projects/slicing/slice_23/dsl_manager_slice_23_report.md`

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

## Integrazioni operative specifiche — Slice 23

- Interpreta “diretto” in senso stretto: gli stessi byte immutabili della source revision devono entrare nel preflight e poi in Docling; non sono consentiti pre-conversione, rinomina, LibreOffice, fallback di normalizzazione o riapertura del path sorgente.
- Registra nel report la versione Docling realmente importata/eseguita e il risultato del test reale `.xlsm`; se il backend non soddisfa il contratto, la Slice è `bloccata`, non “completata con fallback”.
- Registra SHA-256 dei fixture binari usati e dimostra che il source path non viene riaperto dopo l’acquisizione del buffer.
- Distingui esplicitamente `memory_limit_mode=hard` da `memory_limit_mode=monitored`; non presentare un limite monitorato come garanzia hard.
- Aggiungi regressioni sui formati legacy già supportati, così l’estensione del routing Excel non modifica accidentalmente il comportamento precedente.

## Regola finale di accettazione

La Slice 23 può essere dichiarata `completata` soltanto se soddisfa **sia** il nucleo normativo v02 **sia** il protocollo operativo comune e le integrazioni specifiche sopra. Le integrazioni operative possono rafforzare verifiche e audit, ma non possono ampliare il perimetro funzionale, spostare feature fra Slice, rendere opzionale un requisito del design o introdurre fallback non autorizzati.
