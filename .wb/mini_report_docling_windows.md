# Mini report — instabilità ricorrente del worker Docling/Excel su Windows

- Data: 2026-09-14
- Ambiente osservato: Windows, Python 3.12.10, Docling 2.97.0
- Ambito: normalizzazione reale `.xlsx` nel worker isolato

## Sintomi distinti

1. **Rilascio tardivo dei file temporanei.** La suite ha prodotto
   `PermissionError [WinError 32]` durante la rimozione di
   `.worker_stdout.tmp`: il processo principale aveva già atteso il worker, ma
   Windows segnalava ancora il file come in uso.
2. **Durata superiore al default storico.** Eliminato il primo sintomo, lo
   stesso caso reale ha raggiunto esattamente il timeout configurato di 120 s
   (`termination_reason: timeout`, durata 120176 ms), con stdout/stderr vuoti e
   senza pressione di memoria osservabile.

I due sintomi appartengono allo stesso confine di processo, ma non dimostrano
una singola causa: il lock è un problema di quiescenza/cleanup, mentre il timeout
può essere semplicemente una durata valida superiore al budget.

## Evidenze e mitigazioni applicate

| Verifica | Esito |
|---|---|
| Suite iniziale | 1 failure (`WinError 32`), 193 pass |
| Rerun dopo cleanup con retry limitato | niente lock; timeout a 120 s |
| Rerun con timeout predefinito 300 s | pass in 183,85 s |
| Suite completa finale | 196 pass in 663,23 s |
| Suite completa dopo il fix UTF-8 | 197 pass in 1193,61 s; caso Excel vicino a 300 s |

Sono state applicate due modifiche circoscritte:

- retry con backoff limitato soltanto su `PermissionError` durante l'unlink dei
  file di capture; dopo 10 tentativi l'errore continua a propagarsi;
- default Excel/Docling portato da 120 a 300 s, mantenendo invariato l'hard
  maximum di 600 s.

Queste modifiche rendono il caso corrente affidabile, ma non spiegano da sole la
variabilità storica tra esecuzioni.

Una suite successiva ha confermato la variabilità: il medesimo caso reale ha
concluso prima del limite di 300 s, ma con margine sensibilmente inferiore al
rerun da 183,85 s. Non si propone un ulteriore aumento del timeout senza la
telemetria per fase descritta sotto.

## Ipotesi causali da verificare

- **Cold start costoso:** ogni worker ricrea import, converter e componenti
  Docling; l'avvio a freddo può dominare il tempo anche per un workbook piccolo.
- **Interferenza del filesystem Windows:** antivirus, indicizzazione o sync
  possono amplificare la latenza e trattenere brevemente handle sui file di
  input/output.
- **Processi discendenti o thread non ancora quiescenti:** `wait()` sul processo
  lanciato non garantisce necessariamente che ogni risorsa aperta da librerie o
  discendenti sia già stata rilasciata.
- **Fasi opache:** il solo tempo totale non distingue import, costruzione del
  converter, parsing OOXML, serializzazione e chiusura.

## Possibili soluzioni future — non implementate

La prima azione consigliata è aggiungere telemetria locale per fase, senza
registrare contenuti: timestamp monotoni per import/setup/convert/export/close,
PID e PID discendenti, motivo di terminazione e tempi cold/warm. Questo permette
di decidere sulla base di misure, non del solo timeout finale.

Se le misure confermassero che domina il cold start, una soluzione strutturale
sarebbe un **worker Docling locale persistente o un piccolo pool pre-riscaldato**
per il batch. Il processo caricherebbe una volta il converter e riceverebbe job
tramite IPC locale mantenendo hash check, limiti e pubblicazione atomica. Il
vantaggio atteso è ridurre tempi e variabilità; i costi sono maggiore memoria,
gestione dello stato tra job e necessità di riciclare il worker dopo errori o
soglie definite.

Se invece prevalessero handle/processi discendenti, l'alternativa sarebbe
gestire l'intero albero di processi con un **Windows Job Object**, attendere la
quiescenza del gruppo e chiudere esplicitamente gli handle prima del cleanup.
Un'altra opzione complementare è un heartbeat di avanzamento per distinguere un
job lento da uno bloccato e applicare timeout per fase o adattivi, sempre entro
l'hard maximum.

Nessuna di queste soluzioni architetturali è stata implementata in questo step.
