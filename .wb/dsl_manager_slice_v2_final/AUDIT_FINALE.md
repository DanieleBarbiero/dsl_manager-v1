# Audit finale — trasformazione prompt Slice 20–29

## Esito

**PASS**.

Il pacchetto finale è stato costruito senza scritture sul repository GitHub.

### Gate automatici finali

- 10 prompt Slice 20–29 presenti: PASS
- 0 report Slice 20–29 presenti: PASS
- directory e naming zero-padded corretti: PASS
- core normativo originale presente una sola volta per prompt: PASS
- elenco report `01…NN-1` esatto per ogni Slice: PASS
- nessun report futuro accidentalmente citato come report precedente: PASS
- nessun placeholder del template v1 noto: PASS
- protocollo operativo comune: PASS
- autorità interprete demandata ad `AGENTS.md`: PASS
- equivalenza operativa v1: PASS
- marker/integratori specifici 20–29: PASS
- design: zero vecchi anchor `#prompt-slice-NN`: PASS
- design: zero blocchi `### Prompt Slice NN` embedded: PASS
- design: due riferimenti a ogni prompt esterno (piano + indice): PASS
- link relativi del design verso i dieci prompt: PASS
- auto-verifica design aggiornata: PASS
- patch sul checkpoint: `git apply --check`: PASS
- patch sul checkpoint: `git diff --check`: PASS
- risultato patch = design preview: PASS
- helper: baseline guard: PASS
- helper: dry-run e postcondizioni: PASS
- helper: scrittura atomica: PASS

Il secondo audit indipendente ha registrato **36 gate globali/strutturali PASS** e **10/10 Slice PASS**.

## Verifica remota dei core

Durante l'audit finale le sezioni `Prompt Slice 20` … `Prompt Slice 29` sono state rifetchate singolarmente dal file corrente su `main` tramite il collegamento GitHub. Il loro contenuto normativo è coerente con i core incorporati nei dieci prompt finali.

GitHub riporta per il design corrente:

```text
Git blob SHA: 8aa78b1210216b78d97e4e2554b075a7c1b462df
size:         89660 byte
```

## Anomalia di rappresentazione rilevata e mitigazione

Il checkpoint testuale locale materializzato dal connettore ha anch'esso `89660` byte ma, se passato a `git hash-object`, produce:

```text
a687c84207c8a3ace1a8e54a5928e1ae5b92e6a6
```

Per evitare di trasformare questa differenza di rappresentazione in una sostituzione integrale potenzialmente rumorosa, il pacchetto **non prescrive di copiare il preview del design nel clone**.

Metodo sicuro scelto:

- `tools/apply_design_update.py` lavora sul file reale presente nel clone;
- per default accetta soltanto il Git blob SHA remoto verificato `8aa78b…`;
- esegue sostituzioni puntuali con postcondizioni;
- fallisce senza scrivere se la baseline è diversa;
- scrive atomicamente.

Il preview e la patch sono quindi materiale di revisione/fallback, non la sorgente primaria da sovrascrivere.

## Audit semantico per Slice

- **20:** baseline 01–19, v7/review/effective views, solo `ddl_table_fact/1`, interprete mediato da `AGENTS.md`.
- **21:** gate reale sulla 20, inventario parser, regole pure/versionate, nessuna orchestrazione batch.
- **22:** API 20–21, contratti batch legacy, checkpoint/retry/exit/effective hash.
- **23:** stessi byte per preflight+Docling, `.xlsm` reale come gate, nessun fallback/conversione, hard vs monitored memory.
- **24:** riuso obbligatorio preflight 23, niente parser OOXML parallelo, manifest/fragments/checksum fixture.
- **25:** review/importer comune, matrice regole, nessuna semantica di dominio da celle/header/label.
- **26:** gate 20–25, v9, DSL2/GEXF offline, XSD URL/commit/licenza/SHA, compatibilità v1.
- **27:** v10, catena end-to-end delle evidenze, multipli intervalli/spells, fake-AI candidate-only obbligatoria.
- **28:** inventario+SHA Aurora, expected derivati dal contratto, nessun hidden fix runtime.
- **29:** documentazione verificata contro codice/test/`--help`, nessuna feature runtime nuova.

Non sono emerse contraddizioni fra le integrazioni operative aggiunte e il perimetro normativo originale delle rispettive slice.

## Test runtime

Non è stata eseguita la suite runtime di DSL Manager perché questo pacchetto modifica/crea esclusivamente documentazione e prompt di implementazione. I prompt finali contengono invece i gate di installazione, test mirati, suite completa, CLI, diff/status e report da eseguire durante l'implementazione effettiva di ciascuna slice.
