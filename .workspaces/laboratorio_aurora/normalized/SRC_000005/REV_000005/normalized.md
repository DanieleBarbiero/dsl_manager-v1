## Manuale dell'ufficio crediti

Edizione operativa del 12 dicembre 2024.

### Apertura della pratica

L'operatore identifica il Cliente tramite codice fiscale e registra una nuova PraticaPrestito con importo, durata e tasso proposto.

La pratica appena salvata assume lo stato INSERITA. Dopo il controllo dei documenti passa allo stato IN\_ISTRUTTORIA.

### Delibera

L'approvazione è consentita soltanto per clienti maggiorenni e per durate comprese fra 6 e 84 mesi.

Il pulsante Conferma approvazione della form FRM\_PRATICA imposta lo stato APPROVATA. La data di approvazione è valorizzata automaticamente.

### Piano di rimborso

Per una pratica APPROVATA il processo PRC\_GENERA\_PIANO prepara le Rate. L'operatore consulta il risultato nella form FRM\_PIANO\_RATE.

### Eccezioni

Un pagamento duplicato sulla stessa rata deve essere segnalato e non deve produrre una seconda contabilizzazione.
