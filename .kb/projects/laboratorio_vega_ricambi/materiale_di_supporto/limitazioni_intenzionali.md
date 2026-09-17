# Limitazioni intenzionali — Vega Ricambi

Vega non vuole sostituire Aurora e Orione.

La sua metrica principale è il **tempo di feedback**.

## 1. Copertura formato ridotta

DOCX e XLSX sono i soli documenti normalizzati nel corpus normale.

Questo significa che un bug specifico di PDF o PPTX può sfuggire a Vega.
È accettato intenzionalmente.

## 2. Nessun replay AI congelato

Gli ID di chunk/frammenti dipendono dal risultato della pipeline. Una fixture
AI congelata può diventare fragile dopo una modifica legittima.

Vega prova la creazione del package, non la risposta del modello.

## 3. Nessun giudizio semantico automatico del tutor

Il tutor può scegliere un candidato da mostrare, ma non decide se confermarlo o
rifiutarlo.

## 4. Nessun conteggio fisso di candidati/fatti

I conteggi possono cambiare con l'evoluzione delle regole.

Vega verifica routing, successo, idempotenza, integrità e capacità di esportare.

## 5. Fixture malformata separata

Un fallimento intenzionale non deve contaminare lo smoke test normale.

Per questo `workbook_malformed_controllato.xlsx` vive sotto
`fixture_controllate` e non in `corpus/active`.
