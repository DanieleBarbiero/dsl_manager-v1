# Template bugfix report

Usare questo template per documentare una correzione dalla rilevazione alla
verifica. Sostituire tutti i placeholder, eliminare le righe non applicabili e
non dichiarare un bug corretto finché i test pertinenti non sono passati.

## Metadati

| Campo | Valore |
|---|---|
| ID | `BUGFIX_<NN>` |
| Titolo | `<titolo breve e specifico>` |
| Stato | `<diagnosticato \| in_correzione \| corretto \| verificato \| rilasciato>` |
| Severità | `<critica \| alta \| media \| bassa>` |
| Data di rilevazione | `<YYYY-MM-DD>` |
| Data di correzione | `<YYYY-MM-DD oppure non_applicabile>` |
| Release interessata | `<versione, range o sconosciuta>` |
| Release corretta | `<versione, unreleased oppure non_applicabile>` |
| Baseline | `<branch e commit di partenza>` |
| Componente | `<package/modulo/comando>` |
| Scenario | `<scenario, workspace e run ID, se disponibili>` |
| Autore della correzione | `<nome, team o agente>` |

## 1. Sintesi esecutiva

Descrivere in poche righe:

- il comportamento errato;
- l'impatto osservabile;
- la causa radice;
- la soluzione adottata;
- lo stato della verifica.

## 2. Impatto e perimetro

| Dimensione | Valutazione |
|---|---|
| Utenti o workflow coinvolti | `<chi/cosa>` |
| Input interessati | `<formati, condizioni o casi limite>` |
| Fasi interessate | `<comandi o fasi della pipeline>` |
| Dati e persistenza | `<mutazioni, rollback, corruzione o nessun impatto>` |
| Sicurezza | `<impatto o nessun impatto noto>` |
| Compatibilità | `<API, CLI, schema, artefatti e versioni>` |

Indicare esplicitamente ciò che non è interessato, quando aiuta a delimitare il
problema.

## 3. Rilevazione ed evidenze

### 3.1 Sintomo

```text
<messaggio di errore o comportamento osservato>
```

### 3.2 Evidenze verificabili

| Evidenza | Percorso o riferimento | Osservazione |
|---|---|---|
| `<log/report/test>` | `<path, run ID o URL>` | `<dato rilevante>` |

Distinguere fatti osservati, inferenze e informazioni non disponibili.

## 4. Riproduzione

### 4.1 Prerequisiti

- `<versione/runtime/configurazione>`
- `<fixture o dati minimi>`

### 4.2 Procedura minima

```powershell
<comandi riproducibili con l'interprete previsto dal progetto>
```

### 4.3 Risultato atteso

`<comportamento corretto>`

### 4.4 Risultato effettivo prima della correzione

`<comportamento errato>`

## 5. Analisi della causa radice

### 5.1 Catena di chiamate o eventi

```text
<input> -> <componente> -> <condizione errata> -> <fallimento>
```

### 5.2 Causa tecnica

`<spiegazione precisa collegata al codice o alla configurazione>`

### 5.3 Fattori contribuenti

- `<assunzione incoerente, naming ambiguo, contratto incompleto, ecc.>`

### 5.4 Perché i test non lo rilevavano

`<lacuna di copertura o divergenza fra fixture e scenario reale>`

## 6. Risoluzione

### 6.1 Decisione

`<soluzione scelta e motivazione>`

### 6.2 Alternative considerate

| Alternativa | Esito | Motivazione |
|---|---|---|
| `<alternativa>` | `<scartata/adottata/parziale>` | `<trade-off>` |

### 6.3 Modifiche implementate

| File o componente | Modifica | Contratto preservato o aggiornato |
|---|---|---|
| `<path>` | `<descrizione>` | `<contratto>` |

## 7. Verifica

Interprete usato: `<PROJECT_PYTHON>` / Python `<versione>`.

Installazione editable:

```powershell
<PROJECT_PYTHON> -m pip install -e ".[dev]"
```

| Livello | Comando o test | Esito | Evidenza |
|---|---|---|---|
| Regressione | `<test mirato>` | `<pass/fail>` | `<conteggio e durata>` |
| Moduli coinvolti | `<suite mirata>` | `<pass/fail>` | `<conteggio e durata>` |
| Suite completa | `<comando canonico>` | `<pass/fail>` | `<conteggio e durata>` |
| Controlli statici | `<diff --check/lint/type check>` | `<pass/fail>` | `<dettaglio>` |

Registrare separatamente failure preesistenti, ambientali o non correlati, con
la prova usata per classificarli.

## 8. Sicurezza, dati e compatibilità

- **Sicurezza:** `<controlli preservati o nuovi rischi>`
- **Dati:** `<migrazioni, mutazioni, idempotenza e recuperabilità>`
- **Compatibilità:** `<CLI/API/schema/artefatti/versioni>`
- **Prestazioni:** `<impatto previsto o misurato>`

## 9. Recupero operativo

Spiegare come recuperare run o workspace già falliti, inclusi prerequisiti,
comando di resume/retry, effetti idempotenti e casi in cui serve ripartire da un
workspace pulito.

## 10. Tracciabilità

| Tipo | Riferimento |
|---|---|
| Requisito/design | `<path o issue>` |
| Codice | `<path e simbolo>` |
| Test | `<path e nome test>` |
| Report/runtime | `<path artefatto>` |
| Commit/PR | `<hash o non_ancora_disponibile>` |
| Riepilogo progetto | `<path aggiornato>` |

## 11. Rischi residui e follow-up

- `<rischio residuo, owner e criterio di chiusura>`
- `<test o miglioramento futuro>`

Se non esistono rischi noti, dichiararlo esplicitamente senza implicare assenza
assoluta di rischio.

## 12. Rollback

`<procedura o strategia di rollback e conseguenze>`

## 13. Nota di rilascio proposta

> `<una frase comprensibile agli utenti, senza dettagli implementativi superflui>`

## 14. Checklist di chiusura

- [ ] Causa radice identificata e supportata da evidenze.
- [ ] Riproduzione minima documentata.
- [ ] Correzione limitata al perimetro necessario.
- [ ] Test di regressione aggiunto e passato.
- [ ] Suite pertinente eseguita.
- [ ] Suite completa eseguita o impedimento documentato.
- [ ] Sicurezza, dati, compatibilità e rollback valutati.
- [ ] Recupero delle run già fallite documentato.
- [ ] Riepilogo del progetto aggiornato.
- [ ] Diff controllato e modifiche estranee preservate.

## 15. Fonti esterne, se utilizzate

| Fonte | Data di consultazione | Punto supportato |
|---|---|---|
| `<URL oppure Nessuna>` | `<YYYY-MM-DD>` | `<decisione supportata>` |

