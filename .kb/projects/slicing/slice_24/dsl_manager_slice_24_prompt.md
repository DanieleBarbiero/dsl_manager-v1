# Prompt Slice 24

<!--
Core normativo estratto deterministicamente da:
.kb/documenti/documenti di design/run 2/design_document_v_02.md
Slice: 24
Il core sotto è conservato letteralmente; protocollo e integrazioni lo rendono operativo senza reinterpretarne il perimetro.
-->

## Nucleo normativo originale v02

Implementa solo la Slice 24 — manifest OOXML canonico, struttura workbook, regioni e frammenti. Produci `.kb/projects/slicing/slice_24/dsl_manager_slice_24_report.md`.

Leggi integralmente `AGENTS.md`, design v02, contratti manifest/evidence, report 11–14 e 23, ECMA-376 Part 2. Ispeziona il parser preflight della slice 23 e riusalo: non crearne uno parallelo. Usa Python 3.12 configurato, installazione editable dev e preserva worktree estraneo.

Obiettivo verticale minimo: dallo stesso buffer validato ottenere un `workbook_manifest.json` autoritativo, riferimenti DB v8 e frammenti localizzati, deterministici e sufficienti a distinguere formula e cached value.

Implementa migrazione v8, schema/ordine della sezione 11.3, parsing streaming esteso, region detector versionato, fragments, hash e persistenza. Conserva sheet order/name/visibility, coordinate e tipi cella, formule/cached, merge, named ranges con scope, relazioni part+rId, external link e macro presence/part/hash/`executed:false`. Stabilizza i prodotti Docling in ordine e formato; `normalized.md` resta secondario. Escludi timestamp operativi e path assoluti. Applica limiti celle/regioni/relazioni/output e report catalogato.

Non interpretare dominio, non produrre candidati, non eseguire/recalcolare/aggiornare alcun contenuto e non copiare XML non limitato in memoria.

Test obbligatori con binari immutabili: multi-sheet/multi-region; formula con/senza cached; merged; named range workbook/sheet; visible/hidden/veryHidden; string/number/bool/date/error/blank; external link; xlsm macro; Unicode/ordine; at/over limits; DB roundtrip; manifest golden e hash uguali su due run/macchine logiche; no-network. Registra SHA dei binari e testa il checksum. Esegui suite completa.

Done: manifest/fragments coprono ogni campo obbligatorio e sono fonte primaria strutturale. Prima elenca file; dopo riporta test e diff.

## Protocollo operativo comune obbligatorio

Le istruzioni di questa sezione **integrano** il nucleo normativo v02 senza modificarne il perimetro funzionale. Servono a rendere il prompt autonomo e operativo come i prompt maturi della run 1. Non trasformare abbreviazioni o ambiguità del nucleo in nuove decisioni progettuali.

### Autorità delle fonti

Applica questa regola senza creare una graduatoria concorrente:

- `AGENTS.md` governa ambiente, processo e convenzioni del repository;
- `.kb/documenti/documenti di design/run 2/design_document_v_02.md` governa requisiti funzionali, invarianti e confini della run 2;
- il presente prompt governa l'esecuzione operativa della Slice 24;
- codice, schema e test correnti rappresentano lo **stato osservato** e non possono modificare implicitamente il design;
- report precedenti e `.kb/documenti/documenti di design/run 1/design_document_v_01.md` sono storia implementativa/baseline concettuale, salvo richiami normativi espliciti del design v02.

Se due fonti producono una contraddizione non risolvibile con queste responsabilità, **non scegliere silenziosamente una variante e non introdurre una nuova decisione progettuale**: documenta il conflitto e fermati prima della modifica che lo renderebbe concreto.

### Letture obbligatorie prima del codice

Leggi integralmente, nell'ordine utile al task:

- `AGENTS.md`;
- `.kb/documenti/documenti di design/run 2/design_document_v_02.md`;
- `.kb/documenti/documenti di design/run 1/design_document_v_01.md` come baseline concettuale nei soli punti non sostituiti dal v02;
- `.kb/template/template_slice_report.md`;
- i documenti pertinenti della Slice 24:
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
- `.kb/projects/slicing/slice_23/dsl_manager_slice_23_report.md`

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
2. confronta il perimetro e le precondizioni della Slice 24 con design v02 e matrice di tracciabilità;
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

### Tracciabilità minima della Slice 24

Prima del codice costruisci una checklist `requisito → implementazione prevista → test previsto` usando **tutte** le righe della sezione 17 del design assegnate alla Slice 24. Come minimo considera:

- due viste Excel → `test_slice_24_formula_cached`
- struttura workbook → `test_slice_24_manifest_golden`

Alla fine completa la stessa checklist con file/test/esito. Una riga pertinente non verificata impedisce di dichiarare la Slice completata.

### Esecuzione, test e chiusura

Procedura obbligatoria:

1. dopo il preflight, implementa soltanto il perimetro della Slice 24;
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

`.kb/projects/slicing/slice_24/dsl_manager_slice_24_report.md`

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

## Integrazioni operative specifiche — Slice 24

- Il preflight della Slice 23 è una precondizione obbligatoria e deve essere esteso/riusato: vietato introdurre un parser OOXML di sicurezza parallelo o una seconda pipeline di validazione incompatibile.
- Prima del codice, verifica che il preflight 23 sia realmente presente, testato e riusabile; se manca una proprietà necessaria, attribuisci il gap alla Slice 23 o documenta una minima estensione compatibile.
- Nel report collega lo schema concreto del manifest alle sezioni 11.3/8.2 del design e inventaria tutti gli artifact che vengono pubblicati.
- Registra checksum dei fixture binari prima e dopo; i binari immutabili non devono cambiare durante la Slice 24.

## Regola finale di accettazione

La Slice 24 può essere dichiarata `completata` soltanto se soddisfa **sia** il nucleo normativo v02 **sia** il protocollo operativo comune e le integrazioni specifiche sopra. Le integrazioni operative possono rafforzare verifiche e audit, ma non possono ampliare il perimetro funzionale, spostare feature fra Slice, rendere opzionale un requisito del design o introdurre fallback non autorizzati.
