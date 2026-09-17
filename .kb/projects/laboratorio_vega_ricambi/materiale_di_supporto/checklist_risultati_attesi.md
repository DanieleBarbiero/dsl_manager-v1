# Checklist risultati attesi — Vega Ricambi 1.0

Usa questa lista come controllo rapido. Non sostituisce i report.

## Ambiente

- [ ] Lo script ha trovato la root `dsl_manager-v1`.
- [ ] `PROJECT_PYTHON` esiste.
- [ ] La versione osservata è Python 3.12.x.
- [ ] Tutte le 6 fonti canoniche esistono.
- [ ] I checksum canonici coincidono.

## Preparazione

- [ ] Il workspace era nuovo prima di `init`.
- [ ] `dsl_mngr init` è terminato con exit 0.
- [ ] `dsl_mngr db init` è terminato con exit 0.
- [ ] Le 6 fonti sono state copiate byte-per-byte.
- [ ] Il profilo `conservative/1` è applicabile.
- [ ] `config validate --profile conservative/1` termina con exit 0.

## Scan

- [ ] Primo scan: `Added: 6`.
- [ ] Primo scan: `Modified: 0`.
- [ ] Primo scan: `Deleted: 0`.
- [ ] Secondo scan: `Unchanged: 6`.
- [ ] Il secondo scan non crea revisioni spurie.

## Processing

- [ ] `schema_vega.sql` passa dal parser DDL.
- [ ] `logica_vega.sql` passa dal parser DB code.
- [ ] `frm_richiesta.xml` passa dal parser XML form.
- [ ] `vega_2026.log` passa dal parser log.
- [ ] `manuale_operativo_vega_2026.docx` viene normalizzato e chunkato.
- [ ] `matrice_priorita_vega_2026.xlsx` viene normalizzata e chunkata.
- [ ] Il batch non ha item falliti.
- [ ] Solo due fonti del corpus normale richiedono normalizzazione Docling.

## Handoff AI

- [ ] Il piano `technical_extraction` produce un ID `AISEL_*`.
- [ ] Il piano `domain_interpretation` produce un ID `AISEL_*`.
- [ ] Il package prodotto usa un ID `AIPKG_*`.
- [ ] Nessuna chiamata AI esterna è necessaria per completare lo smoke test.

## Stato / export

- [ ] `facts reconcile` termina correttamente.
- [ ] `dsl render --schema-version 2` produce un `DSL_*`.
- [ ] `graph export` usa l'ID reale appena prodotto.
- [ ] Gli export dei log vengono generati.
- [ ] Lo smoke test UI, se eseguito, usa soltanto `127.0.0.1`.

## Chiusura

- [ ] Scan finale: `Unchanged: 6`.
- [ ] Gli hash nel workspace coincidono ancora con il corpus canonico.
- [ ] `session_state.json` contiene il workspace realmente usato.
- [ ] I log completi sono presenti nella cartella `logs`.
- [ ] Nessun file del corpus canonico è stato modificato.
