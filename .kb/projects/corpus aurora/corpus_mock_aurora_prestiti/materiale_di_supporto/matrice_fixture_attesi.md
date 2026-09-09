# Matrice fixture → requisito → expected/test

| Fixture o gruppo | Requisito design v02 | Expected verificabile | Test Slice 28 |
|---|---|---|---|
| tutte le 18 fonti attive | originali immutabili, ordine e due run | SHA-256 da `checksums.json`, scan idempotente, stessi hash semantici | `test_slice_28_aurora_e2e` |
| `matrice_stati_2025.xlsx` | multi-sheet/region, formula+cached, merged, named range, visibilita', tipi, external link | SHA origine Slice 24; 3 fogli, 5 regioni, 21 celle, cache `3.5`, link non dereferenziato | `test_slice_28_aurora_e2e` |
| `calcolo_rate_macro_2025.xlsm` | `.xlsm` reale inerte | macro presente, hash VBA noto, `executed: false` | `test_slice_28_aurora_e2e` |
| `workbook_malformed_controllato.xlsx` | malformed distinto dal partial | preflight `rejected`, reason `ooxml_security_violation`, nessun normalized | `test_slice_28_malformed_partial_budget_and_no_network` |
| `workbook_partial_controllato.xlsx` | partial controllato e ispezionabile | package valido, status `partial`, exit 6, normalized + manifest/fragments/report | `test_slice_28_malformed_partial_budget_and_no_network` |
| DDL, tre form, tre PL/SQL e due log | candidati deterministici strutturati | batch per regola, payload/evidence hash stabili, review prima del merge | `test_slice_28_aurora_e2e` |
| requisiti + addendum 2025 | evidenza temporale concordante significativa | assessment concordant; candidato medium ma pending fino a review | `test_slice_28_aurora_e2e` |
| manuale 2012 + requisiti 2025 | evidenza temporale discordante significativa | conflict open, zero intervalli effettivi e nessuna falsa promozione | `test_slice_28_aurora_e2e` |
| registry dopo review | DSL v1/v2 e diff | snapshot 1/2, diff cross-schema con governance e temporal | `test_slice_28_aurora_e2e` |
| snapshot DSL v2 | GEXF dinamico valido | GEXF 1.3 dynamic; validazione XSD e semantica true | `test_slice_28_aurora_e2e` |
| limiti e retry | budget, no-network, ordine/retry | esito a soglia, errore oltre soglia, convergenza dopo crash e ordine inverso | test Slice 28 + test di regressione Slice 24/27 richiamati nel report |

La proiezione contrattuale puntuale e' conservata in
`tests/expected/expected_slice_28_aurora_e2e.json`. I valori descrivono la
semantica intenzionale delle fixture; un cambiamento richiede una modifica di
contratto motivata, non la mera osservazione dell'output del programma.
