# Bugfix 03 — liste YAML multilinea nella configurazione

## Metadati

| Campo | Valore |
|---|---|
| ID | `BUGFIX_03` |
| Titolo | Supporto alle liste scalari YAML multilinea nel parser di configurazione |
| Stato | `verificato` |
| Severità | Media: blocco del consolidamento Aurora prima della creazione della run |
| Data di rilevazione | 2026-09-11 |
| Data di correzione | 2026-09-11 |
| Release interessata | `1.1.0` |
| Release corretta | `1.1.0` nel working tree; nessun bump di versione eseguito |
| Baseline | branch `main`, commit `0218ea7` |
| Componente | `dsl_mngr.core.config.parse_simple_yaml` |
| Scenario | Guida Aurora v02, configurazione auto-review prima di `batch consolidate` |
| Autore della correzione | Codex, su richiesta dell'utente |

## 1. Sintesi esecutiva

Il blocco `automatic_policies` documentato dalle guide Aurora è una lista YAML
leggibile su più righe. Il parser minimale interpretava invece la chiave vuota
come stringa e ignorava le righe introdotte da `-`; la validazione fermava
quindi il batch con `review.automatic_policies must be a list`.

Il parser ora riconosce liste scalari indentate sotto una chiave di sezione,
senza cambiare il supporto alle liste inline e senza interpretare come lista un
valore vuoto quale `default_actor_id:`. Test unitari e documentali collegano
direttamente il formato delle due guide al parser effettivo.

## 2. Impatto e perimetro

| Dimensione | Valutazione |
|---|---|
| Utenti o workflow coinvolti | Utenti che configurano liste leggibili in `configs/project.yaml` |
| Input interessati | Liste scalari indentate con una voce `- valore` per riga |
| Fasi interessate | Caricamento configurazione; Aurora `batch consolidate` |
| Dati e persistenza | Nessuna migrazione o mutazione; il fallimento precedeva la creazione della run |
| Sicurezza | La validazione tipizzata delle policy resta invariata |
| Compatibilità | Liste JSON inline e configurazioni generate restano supportate |

Il cambiamento non introduce un parser YAML generale: estende deliberatamente
il sottoinsieme già supportato alle sole liste scalari annidate nelle sezioni.

## 3. Rilevazione ed evidenze

### 3.1 Sintomo

```text
Error: Invalid project configuration: review.automatic_policies must be a list of non-empty policy identifiers.
```

### 3.2 Evidenze verificabili

| Evidenza | Percorso o riferimento | Osservazione |
|---|---|---|
| Configurazione Aurora | `.workspaces/laboratorio_aurora_v_02_cmd/configs/project.yaml` | 13 policy correttamente espresse come lista YAML multilinea |
| Parser precedente | `../../../src/dsl_mngr/core/config.py` | le righe indentate senza `:` venivano ignorate |
| Guide Aurora | guide PowerShell e CMD v02 | entrambe usano il formato multilinea con trattino |
| Validazione | `_validate_slice_20_config` | rifiuto corretto del valore stringa prodotto dal vecchio parser |

## 4. Riproduzione

### 4.1 Prerequisiti

- Python 3.12 e progetto installato in modalità editable;
- workspace inizializzato;
- `automatic_policies` nel formato mostrato dalle guide Aurora.

### 4.2 Procedura minima

```powershell
& $PY -c "from dsl_mngr.core.config import load_config; import sys; load_config(sys.argv[1])" $WS
```

### 4.3 Risultato atteso

La configurazione viene caricata e `automatic_policies` contiene una lista di
13 stringhe.

### 4.4 Risultato effettivo prima della correzione

La chiave veniva letta come stringa vuota e il caricamento falliva prima della
creazione della run di consolidamento.

## 5. Analisi della causa radice

### 5.1 Catena di chiamate o eventi

```text
project.yaml multilinea
  -> parse_simple_yaml ignora le righe "- policy"
  -> automatic_policies diventa ""
  -> validazione tipizzata
  -> ProjectConfigError
```

### 5.2 Causa tecnica

`parse_simple_yaml` gestiva soltanto mapping a due livelli e scalari o liste
JSON inline. Non conservava la chiave contenitore e l'indentazione necessarie a
collegare le righe successive di una sequenza YAML.

### 5.3 Fattori contribuenti

- Il formato generato dal programma usa `[]` o JSON inline e non esercitava la
  sintassi più leggibile usata dalla guida.
- I test documentali verificavano il contenuto delle guide, ma non passavano il
  relativo blocco YAML al parser runtime.

### 5.4 Perché i test non lo rilevavano

I test caricavano configurazioni prodotte da `dump_simple_yaml`, che serializza
le liste su una sola riga. Mancava una regressione con sequenze indentate.

## 6. Risoluzione

### 6.1 Decisione

Estendere il parser minimale conservando temporaneamente chiave e livello di
indentazione di uno scalare vuoto. Le righe più indentate con `-` convertono
quel valore in lista e aggiungono elementi tramite il parser scalare esistente.

### 6.2 Alternative considerate

| Alternativa | Esito | Motivazione |
|---|---|---|
| Riscrivere le guide con una lista JSON inline | Scartata | Poco leggibile e onerosa da modificare manualmente |
| Introdurre una nuova dipendenza YAML | Scartata | Eccessiva rispetto al sottoinsieme di configurazione supportato |
| Estendere il parser minimale | Adottata | Modifica locale, retrocompatibile e coperta dai test |

### 6.3 Modifiche implementate

| File o componente | Modifica | Contratto preservato o aggiornato |
|---|---|---|
| `src/dsl_mngr/core/config.py` | parsing delle liste scalari indentate | liste inline e scalari preesistenti preservati |
| `tests/test_slice_01_workspace_config_logging.py` | test parser e `load_config` con lista multilinea | regressione runtime |
| `tests/test_slice_29_documentation.py` | parsing dei blocchi reali delle due guide Aurora | coerenza guida-runtime |

## 7. Verifica

Interprete usato: `.venv\Scripts\python.exe`, Python `3.12.10`.

```powershell
.\.venv\Scripts\python.exe -m pip install -e ".[dev]"
```

| Livello | Comando o test | Esito | Evidenza |
|---|---|---|---|
| Configurazione e consolidamento | test Slice 01 e Slice 22 | Passato | `16 passed in 42.93s` |
| Configurazione e guide | test Slice 01 e Slice 29 | Passato | `13 passed in 3.84s` |
| Workspace Aurora corrente | `load_config` in sola lettura | Passato | 13 policy riconosciute |
| Suite completa | `.\.venv\Scripts\python.exe -m pytest` | Passato | `184 passed in 793.59s` |

## 8. Sicurezza, dati e compatibilità

- **Sicurezza:** i valori continuano a passare dalla validazione delle policy;
  non vengono autorizzati identificatori vuoti.
- **Dati:** nessuna migrazione e nessuna scrittura sul workspace esistente.
- **Compatibilità:** il formato inline, i booleani, i numeri e gli scalari
  preesistenti restano invariati.
- **Prestazioni:** costo lineare trascurabile sul numero di righe del file.

## 9. Recupero operativo

Il comando fallito non ha creato una run perché il caricamento della
configurazione precede `_prepare_run`. Dopo l'aggiornamento del programma è
quindi sufficiente ripetere il punto 11 della guida; non serve `--resume` e non
occorre ricreare il workspace.

## 10. Tracciabilità

| Tipo | Riferimento |
|---|---|
| Codice | `../../../src/dsl_mngr/core/config.py`, `parse_simple_yaml` |
| Test unitari | `../../../tests/test_slice_01_workspace_config_logging.py` |
| Test guida-runtime | `../../../tests/test_slice_29_documentation.py` |
| Guide | `../../projects/corpus aurora/corpus_mock_aurora_prestiti/materiale_di_supporto/guida_dsl_manager_powershell_v_02.md`; equivalente CMD v02 |
| Commit/PR | Non ancora disponibile; modifiche nel working tree |
| Riepilogo progetto | `../project_summary.md` |

## 11. Rischi residui e follow-up

Il parser resta intenzionalmente un sottoinsieme YAML e non supporta strutture
arbitrarie o liste di mapping. Non sono noti rischi residui per le liste scalari
documentate e coperte dai test.

## 12. Rollback

Ripristinare la versione precedente di `parse_simple_yaml` e i tre test
reintrodurrebbe l'incompatibilità con le guide; i workspace e il database non
richiedono rollback.

## 13. Nota di rilascio proposta

> `project.yaml` accetta ora liste scalari leggibili su più righe, incluso il
> blocco `automatic_policies` documentato nello scenario Aurora.

## 14. Checklist di chiusura

- [x] Causa radice identificata e supportata da evidenze.
- [x] Riproduzione minima documentata.
- [x] Correzione limitata al perimetro necessario.
- [x] Test di regressione aggiunto e passato.
- [x] Suite pertinente eseguita.
- [x] Suite completa eseguita e passata.
- [x] Sicurezza, dati, compatibilità e rollback valutati.
- [x] Recupero delle run già fallite documentato.
- [x] Riepilogo del progetto aggiornato.
- [x] Diff controllato e modifiche estranee preservate.

## 15. Fonti esterne, se utilizzate

| Fonte | Data di consultazione | Punto supportato |
|---|---|---|
| Nessuna | 2026-09-11 | Codice, configurazione locale e test erano sufficienti |
