# Note di progettazione

Vega è stato derivato dai pattern osservati nei laboratori Aurora e Orione,
riducendo deliberatamente il corpus.

## Principi mantenuti

- corpus canonico immutabile;
- workspace separato;
- checksum prima/dopo;
- doppio scan per idempotenza;
- profilo review versionato;
- comandi pubblici `python -m dsl_mngr`;
- report/run ID reali;
- AI package separato dall'approvazione;
- export finali verificabili.

## Differenze volute

- 6 fonti invece di un corpus ampio;
- 2 sole fonti Docling;
- niente conteggi rigidi di candidati/fatti;
- niente replay AI congelato;
- niente temporalità complessa nel percorso rapido;
- console corta, log completo su file;
- stato di tutor atomico e riprendibile;
- workspace persistito nello stato;
- default automatici per file/step non semantici.
