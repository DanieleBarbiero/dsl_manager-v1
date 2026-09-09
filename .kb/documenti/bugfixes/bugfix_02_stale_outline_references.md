# Bugfix 02 — riferimenti obsoleti all'outline sintetico

## Metadati

| Campo | Valore |
|---|---|
| ID | `BUGFIX_02` |
| Titolo | Riferimenti non aggiornati dopo il rename dell'outline sintetico |
| Stato | `verificato` |
| Severità | Bassa: blocco dei test documentali, nessun impatto runtime |
| Data di rilevazione | 2026-09-09 |
| Data di correzione | 2026-09-09 |
| Release interessata | `1.1.0` |
| Release corretta | `1.1.0` nel working tree; nessun bump di versione eseguito |
| Baseline | branch `main`, commit `a644ebb` |
| Componente | Test di consistenza release e documentazione canonica |
| Scenario | Verifica completa successiva a `BUGFIX_01` |
| Autore della correzione | Codex, su richiesta dell'utente |

## 1. Sintesi esecutiva

Tre test fallivano perché cercavano
`.kb/documenti/manuali/outline dsl manager flow from input to output.md`. Nel
commit `a644ebb` quel documento era stato rinominato aggiungendo il suffisso
`_riassunto`, mentre era stato creato un secondo documento distinto con suffisso
`_completo`. Il working tree aveva inoltre applicato la convenzione
`snake_case` al nome del riassunto, ma i test e cinque link Markdown erano
rimasti sul nome originario.

I due elenchi di documenti canonici e tutti i link attivi sono stati aggiornati
a `outline_dsl_manager_flow_from_input_to_output_riassunto.md`. I test mirati e
la suite completa sono ora verdi.

## 2. Impatto e perimetro

| Dimensione | Valutazione |
|---|---|
| Utenti o workflow coinvolti | Sviluppatori e CI durante i test di release/documentazione |
| Input interessati | Percorsi locali dell'outline sintetico |
| Fasi interessate | Test di consistenza versione e Slice 29 |
| Dati e persistenza | Nessuna mutazione runtime o database |
| Sicurezza | Nessun impatto |
| Compatibilità | Solo riferimenti interni Markdown e costanti dei test |

La CLI, il package Python, il corpus Aurora e gli artefatti runtime non sono
interessati.

## 3. Rilevazione ed evidenze

### 3.1 Sintomo

```text
FileNotFoundError: .kb/documenti/manuali/outline dsl manager flow from input to output.md
```

### 3.2 Evidenze verificabili

| Evidenza | Percorso o riferimento | Osservazione |
|---|---|---|
| Test release | `../../../tests/test_release_version_consistency.py` | `CANONICAL_DOCUMENTS` conteneva il vecchio nome |
| Test Slice 29 | `../../../tests/test_slice_29_documentation.py` | `ACTIVE_DOCUMENTS` conteneva il vecchio nome |
| Storia Git | commit `a644ebb` | rename dell'originale verso il riassunto e creazione separata del completo |
| Working tree | `.kb/documenti/manuali/` | presenti i file distinti `_riassunto.md` e `_completo.md` |
| Link check | test `test_slice_29_local_links_and_ordered_names_resolve` | dopo la prima correzione dei test ha individuato cinque link ancora obsoleti |

## 4. Riproduzione

### 4.1 Prerequisiti

- checkout basato sul commit `a644ebb` con il rename del riassunto;
- Python 3.12 e progetto installato in editable mode.

### 4.2 Procedura minima

```powershell
.\.venv\Scripts\python.exe -m pytest -q tests\test_release_version_consistency.py tests\test_slice_29_documentation.py
```

### 4.3 Risultato atteso

I documenti canonici devono esistere, riportare la release corrente e contenere
soltanto link locali risolvibili.

### 4.4 Risultato effettivo prima della correzione

Tre test della suite completa fallivano sul percorso precedente. Aggiornando
soltanto le due costanti al documento `_completo.md`, il controllo semantico dei
link evidenziava correttamente altri cinque riferimenti obsoleti; `_completo` era
inoltre il documento sbagliato per i riferimenti descritti come sintetici.

## 5. Analisi della causa radice

### 5.1 Catena di chiamate o eventi

```text
rename outline originale -> nuovo nome _riassunto
  -> test e link non aggiornati
  -> FileNotFoundError / link locali non risolvibili
```

### 5.2 Causa tecnica

Il rename non era stato applicato atomicamente a tutti i riferimenti testuali.
Le costanti nei test e i link Markdown conservavano il percorso precedente.

### 5.3 Fattori contribuenti

- Nello stesso commit erano comparsi due documenti, `_riassunto` e `_completo`,
  rendendo necessario distinguere la loro funzione e non solo la loro esistenza.
- Il nome del riassunto ha attraversato due normalizzazioni: aggiunta del
  suffisso e successivo passaggio completo a `snake_case`.

### 5.4 Perché i test non lo rilevavano

I test lo rilevavano correttamente, ma il commit del rename era già la baseline
del lavoro corrente e la suite non era verde prima di `BUGFIX_01`.

## 6. Risoluzione

### 6.1 Decisione

Usare ovunque il nome
`outline_dsl_manager_flow_from_input_to_output_riassunto.md` quando il testo
parla della mappa sintetica o concisa. Conservare `_completo.md` come documento
distinto e far sì che anch'esso punti al riassunto.

### 6.2 Alternative considerate

| Alternativa | Esito | Motivazione |
|---|---|---|
| Ripristinare il vecchio file con spazi | Scartata | Violerebbe la convenzione `snake_case` e duplicherebbe il documento |
| Puntare tutto a `_completo.md` | Scartata | Il completo è un documento distinto; i riferimenti parlano esplicitamente della versione breve/sintetica |
| Aggiornare test e link a `_riassunto.md` | Adottata | Rispetta intento, naming e topologia documentale |

### 6.3 Modifiche implementate

| File o componente | Modifica | Contratto preservato o aggiornato |
|---|---|---|
| `tests/test_release_version_consistency.py` | Percorso canonico aggiornato | Verifica release sul riassunto effettivo |
| `tests/test_slice_29_documentation.py` | Documento attivo aggiornato | Verifica esistenza, naming e link sul riassunto |
| `analisi_tecnica_dsl_manager.md` | Link aggiornato | La “mappa sintetica” punta al riassunto |
| `contratti_manifest_dsl_manager.md` | Link aggiornato | Riferimento verificabile risolvibile |
| `manuale_utente_dsl_manager.md` | Link aggiornato | La “mappa più breve” punta al riassunto |
| `outline_dsl_manager_flow_from_input_to_output_completo.md` | Link al riferimento sintetico aggiornato | Completo e riassunto restano distinti |
| `dsl_manager_slice_29_report.md` | Link aggiornato | Il documento “conciso” punta al riassunto |

## 7. Verifica

Interprete usato: `.venv\Scripts\python.exe`, Python `3.12.10`.

Installazione editable già eseguita:

```powershell
.\.venv\Scripts\python.exe -m pip install -e ".[dev]"
```

| Livello | Comando o test | Esito | Evidenza |
|---|---|---|---|
| Test mirati | `pytest -q tests\test_release_version_consistency.py tests\test_slice_29_documentation.py` | Passato | `7 passed in 1.14s` |
| Suite completa | `.\.venv\Scripts\python.exe -m pytest` | Passato | `179 passed in 330.96s` |
| Link locali | `test_slice_29_local_links_and_ordered_names_resolve` | Passato | Incluso nei 7 test mirati e nella suite completa |

Non rimangono failure noti collegati al rename.

## 8. Sicurezza, dati e compatibilità

- **Sicurezza:** nessun codice runtime o controllo di sicurezza modificato.
- **Dati:** nessuna migrazione, mutazione o operazione su workspace.
- **Compatibilità:** il vecchio percorso non viene mantenuto come alias; i
  riferimenti versionati usano il nome conforme alle convenzioni correnti.
- **Prestazioni:** nessun impatto.

## 9. Recupero operativo

Non è necessario alcun recupero di workspace. Per aggiornare checkout o branch
derivati occorre portare insieme il rename e le modifiche ai riferimenti.

## 10. Tracciabilità

| Tipo | Riferimento |
|---|---|
| Regola naming | `../../../AGENTS.md` |
| Test | `../../../tests/test_release_version_consistency.py`; `../../../tests/test_slice_29_documentation.py` |
| Documento rinominato | `../manuali/outline_dsl_manager_flow_from_input_to_output_riassunto.md` |
| Documento distinto | `../manuali/outline_dsl_manager_flow_from_input_to_output_completo.md` |
| Commit origine rename | `a644ebb` |
| Commit/PR correzione | Non ancora disponibile; modifiche nel working tree |
| Riepilogo progetto | `../project_summary.md` |

## 11. Rischi residui e follow-up

Non sono noti riferimenti attivi residui al vecchio percorso. Lo storico
testuale nei report può conservare nomi passati quando descrive fedelmente un
diff precedente e non costituisce un link operativo.

## 12. Rollback

Il rollback ripristinerebbe i percorsi precedenti nei test e nei link, ma
richiederebbe anche il ripristino fisico del vecchio file. Senza tale file il
rollback renderebbe nuovamente rossa la suite documentale.

## 13. Nota di rilascio proposta

> Aggiornati i riferimenti interni all'outline sintetico dopo la normalizzazione
> del nome file, ripristinando i controlli documentali e di release.

## 14. Checklist di chiusura

- [x] Causa radice identificata e supportata da evidenze.
- [x] Riproduzione minima documentata.
- [x] Correzione limitata al perimetro necessario.
- [x] Test di regressione esistente passato.
- [x] Suite pertinente eseguita.
- [x] Suite completa eseguita e passata.
- [x] Sicurezza, dati, compatibilità e rollback valutati.
- [x] Recupero operativo documentato.
- [x] Riepilogo del progetto aggiornato.
- [x] Modifiche estranee preservate.

## 15. Fonti esterne, se utilizzate

| Fonte | Data di consultazione | Punto supportato |
|---|---|---|
| Nessuna | 2026-09-09 | Storia Git, file locali e test erano fonti sufficienti e autorevoli |

