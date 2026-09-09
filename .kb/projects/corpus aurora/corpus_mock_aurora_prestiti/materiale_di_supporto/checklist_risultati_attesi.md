# Checklist dei risultati attesi

Questa checklist traduce la sezione 16.4 del design v02 in verifiche osservabili.
Gli expected sono fissati dal contratto e dalla semantica delle fixture, non
copiati da un output corrente per rendere verde un test.

## Integrita' e ingest

- [ ] `checksums.json` valida tutte le 18 fonti attive e le due fixture
  controllate senza file mancanti o file extra nel perimetro dichiarato.
- [ ] Due scan di uno stesso corpus assegnano lo stesso ordine alle revisioni;
  il secondo scan non crea nuove revisioni.
- [ ] Ogni fonte attiva e' registrata come originale immutabile.

## Excel e normalizzazione

- [ ] `matrice_stati_2025.xlsx` ha SHA-256
  `8691d24f3b6748d76a51731e6dfe362733cc26c2b8ea84769339832346754081`.
- [ ] Il manifest contiene tre fogli `Résumé`, `隐 藏`, `非常`, rispettivamente
  visible, hidden e veryHidden, cinque regioni, `A3:B3` merged, due named range
  e 21 celle di tipo string/number/bool/date/error/blank.
- [ ] La formula `B2+C2` conserva cached value `3.5`; la formula `B2*C2` senza
  cache resta distinta.
- [ ] L'external link resta registrato con disposizione `not_dereferenced`.
- [ ] Ogni workbook valido esercitato produce `normalized.json`, `normalized.md`,
  `workbook_manifest.json`, `workbook_fragments.jsonl` e
  `workbook_report.json`.
- [ ] `calcolo_rate_macro_2025.xlsm` e' realmente macro-enabled, espone
  `xl/vbaProject.bin`, registra il suo hash e dichiara `executed: false`.
- [ ] Il malformed e' `rejected` in preflight con `ooxml_security_violation`; il
  controlled partial resta un package valido, restituisce status `partial`,
  exit code 6 e artefatti leggibili.
- [ ] I limiti a soglia passano e quelli oltre soglia falliscono con
  `ooxml_budget_exceeded`; nessun percorso apre rete.

## Candidati, review e merge

- [ ] DDL, XML form, PL/SQL, log ed Excel producono batch candidati
  deterministici con evidenza e locator verificabili.
- [ ] Le regole fact consentite sono auto-confermate; le relazioni Excel e le
  asserzioni temporali restano pending finche' non interviene una review umana.
- [ ] Il merge materializza soltanto candidati con decisione positiva e non
  duplica supporti dopo retry o inversione dell'ordine di input.
- [ ] Restano visibili i conflitti legacy: 50000 contro 60000 euro, stati
  storici contro correnti e annotazione manuale contro trigger automatico.

## Temporalita', DSL ed export

- [ ] Le dichiarazioni `2025-11-18` indipendenti risultano concordanti ma non
  vengono auto-promosse; `2012-06-01` contro `2025-11-18` produce conflitto
  aperto/pending e nessun intervallo efficace falso.
- [ ] Sono prodotti snapshot DSL schema 1 e schema 2; il diff cross-schema e'
  esplicito e separa governance e temporalita'.
- [ ] Due run logiche equivalenti producono gli stessi hash semantici per
  normalized, manifest/fragments, candidate payload, DSL e GEXF.
- [ ] Il GEXF dinamico 1.3 e' validato sia contro XSD vendorizzato sia con i
  controlli semantici; nessun intervallo di edge esce dai nodi estremi.
- [ ] Gli artefatti e i report non includono path assoluti, rete, macro eseguite
  o contenuto sorgente lungo/sensibile.

La proiezione esatta usata dai test e' in
`tests/expected/expected_slice_28_aurora_e2e.json`; la matrice di tracciabilita'
e' in `matrice_fixture_attesi.md`.
