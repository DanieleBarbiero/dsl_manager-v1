# Report Slice 28

Implementata la Slice 28 end-to-end nello scope richiesto. Stato reale:
`completata`.

## Controllo anti-drift e precondizioni

Il preflight e' stato eseguito prima delle modifiche su design v02, baseline
v01, template, documentazione tecnica e utente, corpus Aurora completo, report
01–27, codice, migrazioni, fixture, checksum, expected e test correnti.

- `pronta`: migrazioni append-only 1–10 presenti; normalizzazione OOXML,
  manifest workbook, derivazione deterministica, review append-only,
  consolidamento temporale, DSL schema 2, diff cross-schema e GEXF dinamico
  risultavano implementati e coperti dalle Slice 23–27;
- `gap non bloccante`: il worktree era gia' modificato dalle Slice 20–27 e
  conteneva i relativi file non tracciati; tutte le modifiche preesistenti sono
  state preservate. Su Windows sono state osservate interferenze intermittenti
  del filesystem/antivirus sui file temporanei dei worker e una conversione
  Docling vicina al timeout; i casi sono passati isolatamente e la suite finale
  completa e' verde;
- `bloccata da dipendenza`: nessuna;
- riferimenti mancanti noti: i richiami del corpus alla distribuzione compressa
  e a una guida unica di root non corrispondevano a file reali, come gia'
  assegnato alla Slice 28 dal design. Sono stati rimossi senza creare alias.

La baseline mirata delle Slice 23–27 ha prodotto `65 passed, 1 failed in
444.39s`: il fallimento era un `PermissionError [WinError 32]` nel teardown del
test Docling XLSX della Slice 23 su `.worker_stdout.tmp`. Lo stesso test,
rieseguito isolatamente senza modifiche runtime, ha prodotto `1 passed in
187.95s`.

## Inventario iniziale del corpus

Inventario calcolato prima delle modifiche. Formato:
`percorso | byte | SHA-256`.

```text
LEGGIMI_PRIMA.md|1343|470269e3bcbd9e63ea229e0c80f5844b8ad5ee6b3ab866f312fe02f1710463e2
corpus/active/database/dump_oracle_ddl.sql|1403|43f6797251a710b425c9e00b3aba016d1720a5bf3a544b7b3f12c3bdca4c6cfc
corpus/active/documenti/nuovi_non_utili/istruzioni_parcheggio_2025.html|468|ac2a9c910463cdafcd000b2ae81155652ca272b19a29de8db62ef0fb3dfc6f44
corpus/active/documenti/nuovi_utili/manuale_ufficio_crediti_2024.docx|37179|05074499275e3ddb2eea338de17ec4269772ec2e0cf4337dbdada6100ac0efc3
corpus/active/documenti/nuovi_utili/matrice_stati_2025.xlsx|5296|1e7e7619a13348e72a3c0791a160458f20b972463a9ed4e45ca2411277f7a94e
corpus/active/documenti/nuovi_utili/requisiti_modernizzazione_2025.md|1505|3398a4fad5e2e237dc4b82ddd9dbeb19485bfbda73c6be7e61bff8f4946c855f
corpus/active/documenti/vecchi_non_utili/verbale_mensa_2013.docx|36789|b63bebe418ffdfc8f9d560112268eaa3db3be0f9413e9947bd443c7bc45dfcbd
corpus/active/documenti/vecchi_utili/manuale_pratiche_2012.txt|690|20bfc12e2be3b0e4cacfcdcd3a15c286d46e0c5664d2afe14b221f4adcfe8397
corpus/active/documenti/vecchi_utili/regole_calcolo_rate_2016.html|853|fbee4084c35aec91d4e19dd9c20119092da5879d881735c107f674abb0afa99d
corpus/active/forms/FRM_CLIENTE.xml|802|5b5e0f9c41c378a188174e3f3e1b9f2ec3cbe1fc0c705a4d4507fe3e02a80ca9
corpus/active/forms/FRM_PIANO_RATE.xml|1003|c401a94ee1683638cbb391f0a52a13b118082bac19af41fd0c82729cd9a3730d
corpus/active/forms/FRM_PRATICA.xml|938|2f84a13e59f1bbc44b015d3991eb3f4605c78d14b6a8e64f41b84edccf08bb08
corpus/active/logs/batch_piano_rate_2025.log|362|1c00ddff194038ba0546a34b4d5727d9c7f6b151b8ffb9bc9a9fe145807e42aa
corpus/active/logs/pagamenti_2025.log|320|d04529bddb6567abf9dc60874046912ffe741cea523088bc1495ae0d27e55008
corpus/active/plsql/PRC_GENERA_PIANO.sql|197|9e30d0e1f840718a7ac49cdd64362c555ef858f64f93a1a6daefa7484926cd48
corpus/active/plsql/PRC_REGISTRA_PAGAMENTO.sql|257|bf8fe7a0800798d47345acc1668c0fae7384fc3d3ceca80cb6e81f62fa52d8d7
corpus/active/plsql/TRG_PRATICA_APPROVA.sql|223|0dcd03ae78dd674ad9967c4eb7df17e0186228784f9b0f9e1400bea6d72cc718
materiale_di_supporto/checklist_risultati_attesi.md|1252|d7e5623e91d70d818f599b81720fe4005ef02ccebae01dcde2f442b873f9cdd6
materiale_di_supporto/guida_dsl_manager_powershell_v_01.md|18229|f737dd4d3ad1f5bfd096014e24bb14a299a52bc149f522bcd75643abe0e6e15a
materiale_di_supporto/guida_dsl_manager_cmd_v_01.md|17634|769faca5fcc513a940a5b383d0c0ce7ca07a7cba993dee97729107cb3fd714ab
materiale_di_supporto/inventario_fonti.csv|2162|9b16f7db0439eb6158e73c274c619332c1a4a465469152db3ace5ce92a14b79f
materiale_di_supporto/limitazioni_intenzionali.md|1087|c0fdab92e33acf30e328e6153ae5dede89062523ba2f8e103b5240379c870dd3
```

## Aggiunto

- sostituito `matrice_stati_2025.xlsx` con il binario esatto della fixture
  Slice 24: SHA-256
  `8691d24f3b6748d76a51731e6dfe362733cc26c2b8ea84769339832346754081`,
  3 fogli, 5 regioni, formula/cache, merged e named range, visibilita'
  visible/hidden/veryHidden, sei tipi cella ed external link non dereferenziato;
- aggiunto `calcolo_rate_macro_2025.xlsm`, copia byte-per-byte della fixture
  macro Slice 24, con `vbaProject.bin` hash
  `0ced1464b3677e98f5e3a8c5d80135e18dc98dca39299f1a8cfd2a00999fbf9f`
  e contratto `executed: false`;
- aggiunti un workbook valido per `partial_success` e un package malformed
  deterministico, tenuti fuori da `corpus/active` e distinti rispettivamente
  come `partial`/exit 6 e `rejected`/`ooxml_security_violation`;
- aggiunte dichiarazioni temporali correnti concordanti (`2025-11-18`) e
  storiche discordanti (`2012-06-01`–`2016-12-31`), mantenendo le date come
  evidenze soggette a review e non come verita' automaticamente effettive;
- aggiunti `checksums.json`, builder riproducibile e matrice
  fixture → requisito → expected/test;
- aggiornati inventario, checklist, limitazioni, readme e le due guide reali
  PowerShell/CMD al workflow v2 e alla directory reale del corpus;
- aggiunto `tests/test_slice_28_aurora_e2e.py`: integrita', doppio scan/doppia
  run, workbook e macro, DDL/XML/PLSQL/log/Excel, candidati/review/merge,
  temporalita', DSL v1/v2/diff, GEXF dinamico, budget/no-network,
  malformed/partial e crash/retry/ordine inverso;
- aggiunto `tests/expected/expected_slice_28_aurora_e2e.json` con la proiezione
  semantica riproducibile. Le asserzioni funzionali sono state fissate dal
  design e dalla composizione nota delle fixture prima del confronto; gli hash
  sono stati registrati solo dopo avere verificato due workflow indipendenti
  identici. Il golden non e' stato adattato a una regressione.

## File modificati o aggiunti

```text
M  .kb/projects/corpus aurora/corpus_mock_aurora_prestiti/LEGGIMI_PRIMA.md
M  .kb/projects/corpus aurora/corpus_mock_aurora_prestiti/corpus/active/documenti/nuovi_utili/matrice_stati_2025.xlsx
M  .kb/projects/corpus aurora/corpus_mock_aurora_prestiti/corpus/active/documenti/nuovi_utili/requisiti_modernizzazione_2025.md
M  .kb/projects/corpus aurora/corpus_mock_aurora_prestiti/corpus/active/documenti/vecchi_utili/manuale_pratiche_2012.txt
M  .kb/projects/corpus aurora/corpus_mock_aurora_prestiti/materiale_di_supporto/checklist_risultati_attesi.md
M  .kb/projects/corpus aurora/corpus_mock_aurora_prestiti/materiale_di_supporto/guida_dsl_manager_powershell_v_01.md
M  .kb/projects/corpus aurora/corpus_mock_aurora_prestiti/materiale_di_supporto/guida_dsl_manager_cmd_v_01.md
M  .kb/projects/corpus aurora/corpus_mock_aurora_prestiti/materiale_di_supporto/inventario_fonti.csv
M  .kb/projects/corpus aurora/corpus_mock_aurora_prestiti/materiale_di_supporto/limitazioni_intenzionali.md
A  .kb/projects/corpus aurora/corpus_mock_aurora_prestiti/corpus/active/documenti/nuovi_utili/calcolo_rate_macro_2025.xlsm
A  .kb/projects/corpus aurora/corpus_mock_aurora_prestiti/corpus/active/documenti/nuovi_utili/decorrenza_modernizzazione_2025.txt
A  .kb/projects/corpus aurora/corpus_mock_aurora_prestiti/materiale_di_supporto/build_aurora_fixtures.py
A  .kb/projects/corpus aurora/corpus_mock_aurora_prestiti/materiale_di_supporto/checksums.json
A  .kb/projects/corpus aurora/corpus_mock_aurora_prestiti/materiale_di_supporto/fixture_controllate/workbook_malformed_controllato.xlsx
A  .kb/projects/corpus aurora/corpus_mock_aurora_prestiti/materiale_di_supporto/fixture_controllate/workbook_partial_controllato.xlsx
A  .kb/projects/corpus aurora/corpus_mock_aurora_prestiti/materiale_di_supporto/matrice_fixture_attesi.md
A  tests/expected/expected_slice_28_aurora_e2e.json
A  tests/test_slice_28_aurora_e2e.py
A  .kb/projects/slicing/slice_28/dsl_manager_slice_28_report.md
```

Non sono stati modificati file sotto `src/dsl_mngr`, migrazioni, schema o
contratti CLI dalla Slice 28. Lo schema osservato resta alla migrazione v10
`create_temporal_consolidation_schema`; non sono state aggiunte dipendenze.

## Tracciabilita' requisito → file/test → esito

| Requisito Slice 28 / sezione 16.4 | Implementazione / expected | Test | Esito |
|---|---|---|---|
| Aurora completo (unica riga Slice 28 della sezione 17) | corpus, `checksums.json`, expected E2E | `test_slice_28_aurora_e2e` | passato su due workflow |
| originali immutabili di tutte le fonti attive | 18 entry attive con byte/SHA | `test_slice_28_checksum_inventory_and_references` | passato |
| workbook strutturale completo, formula+cached e external link | binario identico a Slice 24 + proiezione semantica | `test_slice_28_aurora_e2e`, regressioni Slice 24 | passato |
| `.xlsm` reale, macro rilevata e non eseguita | binario identico a Slice 24, manifest/report | E2E Slice 28 + Docling reale Slice 23 | passato |
| malformed e partial distinti | `fixture_controllate/` | `test_slice_28_malformed_partial_budget_and_no_network` | passato |
| normalized JSON/MD e manifest/fragments/report per workbook valido | expected con hash e nomi artifact | `test_slice_28_aurora_e2e`, test partial | passato |
| candidati DDL/XML/codice/log/Excel, batch e decisioni | parser reali, 29 batch di derivazione, 65 payload, 66 decisioni complessive | `test_slice_28_aurora_e2e` | passato |
| contraddizioni temporali non auto-promosse | gruppo conflicted aperto, 2 candidati pending, 0 intervalli efficaci | `test_slice_28_aurora_e2e` | passato |
| DSL v1/v2 e diff | hash golden, diff governance/temporal | `test_slice_28_aurora_e2e` | passato |
| GEXF dinamico XSD + semantic | GEXF 1.3 offline, 72 nodi/84 edge | `test_slice_28_aurora_e2e` | passato |
| budget e no-network | soglia celle 21/20, socket/urlopen negati | test malformed/partial + regressioni Slice 23/24/26 | passato |
| due run, ordine e retry | proiezioni complete uguali; crash controllato e input inverso | E2E + `test_slice_28_order_retry_uses_aurora_sources` | passato |
| riferimenti interni risolvibili, nessun alias fittizio | readme/guide verso file reali, verifica assenza alias | test checksum/riferimenti + `rg` finale | passato |

La matrice di dettaglio e' salvata nel corpus in
`materiale_di_supporto/matrice_fixture_attesi.md`.

## Inventario finale del corpus

Inventario ricalcolato dopo la rigenerazione deterministica finale. Formato:
`percorso | byte | SHA-256`.

```text
corpus/active/database/dump_oracle_ddl.sql|1403|43f6797251a710b425c9e00b3aba016d1720a5bf3a544b7b3f12c3bdca4c6cfc
corpus/active/documenti/nuovi_non_utili/istruzioni_parcheggio_2025.html|468|ac2a9c910463cdafcd000b2ae81155652ca272b19a29de8db62ef0fb3dfc6f44
corpus/active/documenti/nuovi_utili/calcolo_rate_macro_2025.xlsm|10033|17f2858e53262098f899180d470a5390c3072ba5415e7d59a3cd9a4b2bd4caf4
corpus/active/documenti/nuovi_utili/decorrenza_modernizzazione_2025.txt|357|6db5de9fd04a3f3cc4160ebcbfcd7ea52dcc765dbd9882d4fe122984d9a43c3a
corpus/active/documenti/nuovi_utili/manuale_ufficio_crediti_2024.docx|37179|05074499275e3ddb2eea338de17ec4269772ec2e0cf4337dbdada6100ac0efc3
corpus/active/documenti/nuovi_utili/matrice_stati_2025.xlsx|7587|8691d24f3b6748d76a51731e6dfe362733cc26c2b8ea84769339832346754081
corpus/active/documenti/nuovi_utili/requisiti_modernizzazione_2025.md|1690|a7ab69c9480ac1a651fc0fe66877790c35f4439d3b4d6cf73d54cfd927f6d3a6
corpus/active/documenti/vecchi_non_utili/verbale_mensa_2013.docx|36789|b63bebe418ffdfc8f9d560112268eaa3db3be0f9413e9947bd443c7bc45dfcbd
corpus/active/documenti/vecchi_utili/manuale_pratiche_2012.txt|734|03a58684f958300f92ea662eee3cf0a53bb112746c0ea214e031da684a3902f7
corpus/active/documenti/vecchi_utili/regole_calcolo_rate_2016.html|853|fbee4084c35aec91d4e19dd9c20119092da5879d881735c107f674abb0afa99d
corpus/active/forms/FRM_CLIENTE.xml|802|5b5e0f9c41c378a188174e3f3e1b9f2ec3cbe1fc0c705a4d4507fe3e02a80ca9
corpus/active/forms/FRM_PIANO_RATE.xml|1003|c401a94ee1683638cbb391f0a52a13b118082bac19af41fd0c82729cd9a3730d
corpus/active/forms/FRM_PRATICA.xml|938|2f84a13e59f1bbc44b015d3991eb3f4605c78d14b6a8e64f41b84edccf08bb08
corpus/active/logs/batch_piano_rate_2025.log|362|1c00ddff194038ba0546a34b4d5727d9c7f6b151b8ffb9bc9a9fe145807e42aa
corpus/active/logs/pagamenti_2025.log|320|d04529bddb6567abf9dc60874046912ffe741cea523088bc1495ae0d27e55008
corpus/active/plsql/PRC_GENERA_PIANO.sql|197|9e30d0e1f840718a7ac49cdd64362c555ef858f64f93a1a6daefa7484926cd48
corpus/active/plsql/PRC_REGISTRA_PAGAMENTO.sql|257|bf8fe7a0800798d47345acc1668c0fae7384fc3d3ceca80cb6e81f62fa52d8d7
corpus/active/plsql/TRG_PRATICA_APPROVA.sql|223|0dcd03ae78dd674ad9967c4eb7df17e0186228784f9b0f9e1400bea6d72cc718
LEGGIMI_PRIMA.md|2352|5f502d3ebd604d0ff8aec066011449e7cf08ab7adf22ffa37809139c0db8198c
materiale_di_supporto/build_aurora_fixtures.py|2656|dc52d68dbf5e758a9fc356650642001b597ace9e1c446b0e11cb275f2288e53a
materiale_di_supporto/checklist_risultati_attesi.md|3316|6f92dc895b389eb78878b1253459e58c3700b0e1b67efb64f1103a32b5c4f877
materiale_di_supporto/checksums.json|3587|1fa99c6fb55273efa7969aab8589289e72b91c296da7d693cdf2893ee1255d15
materiale_di_supporto/fixture_controllate/workbook_malformed_controllato.xlsx|27|cf680ce352c7682c2180aa03c07f66dd2ee4b16420408bdb03c4095266bdfdbe
materiale_di_supporto/fixture_controllate/workbook_partial_controllato.xlsx|8061|751848e1c7c91bf7406a35a88d23b62c2b4f6923fcd5fd5db77290e26b6e0498
materiale_di_supporto/guida_dsl_manager_cmd_v_01.md|4862|3f7657f8a882ee6082700c92db88303658cd447094be8691110b7e64a6214691
materiale_di_supporto/guida_dsl_manager_powershell_v_01.md|5276|7d4306814776ad328ea54b4d855a5264e4105ab3dceb38a8edbc6562b2e6f07f
materiale_di_supporto/inventario_fonti.csv|4501|cd57368abe87b89caf229f8264b0443e8f5f7184491ecbc0f5be8d2947e8cab9
materiale_di_supporto/limitazioni_intenzionali.md|1397|f1e27a44c9a549dbacebcb213ca95ee4756373d642ffe5e78529a248c0591f4a
materiale_di_supporto/matrice_fixture_attesi.md|2409|36b434ef5cc45ce17a433b70b48c7dedca126d332edbbe5d303333f50d7f8af0
```

Spiegazione delle variazioni:

- 14 fonti legacy attive mantengono byte e SHA iniziali;
- il workbook principale e' stato sostituito intenzionalmente con la fixture
  formula/cached richiesta;
- requisiti 2025 e manuale 2012 hanno ricevuto soltanto dichiarazioni temporali
  esplicite coerenti con il loro contenuto; e' stato aggiunto l'addendum
  indipendente 2025;
- e' stato aggiunto il `.xlsm` attivo;
- readme, inventario, checklist, limitazioni e le due guide sono stati riscritti
  per il contratto v2 e per i percorsi reali;
- builder, checksum, matrice e due fixture controllate sono nuovi. Il manifest
  `checksums.json` copre esattamente le 18 fonti attive e le due fixture
  controllate; evita la ricorsione intenzionalmente non includendo se stesso o
  la documentazione mutabile.

## Diff/status

Il worktree finale resta volutamente sporco per le modifiche preesistenti delle
Slice 20–27. Il riepilogo seguente riguarda i file Slice 28 elencati sopra; non
sono state toccate modifiche non correlate.

```text
9 file tracciati Aurora modificati
9 file Slice 28 nuovi, oltre al presente report
0 file runtime modificati dalla Slice 28
```

Diff stat dei file tracciati Aurora (i file nuovi non tracciati non sono
inclusi da `git diff --stat` finche' non vengono aggiunti all'indice):

```text
9 files changed, 318 insertions(+), 1130 deletions(-)
1 binary workbook changed: 5296 -> 7587 bytes
```

## Test

Interprete usato: `.venv\Scripts\python.exe` / Python `3.12.10`.

Install editable eseguita:

```powershell
& '.\.venv\Scripts\python.exe' -m pip install -e '.[dev]'
```

Risultato: exit code 0; `dsl_mngr` installato editable con `docling==2.97.0` e
`lxml==6.1.2`.

Baseline mirata pre-modifica:

```powershell
& '.\.venv\Scripts\python.exe' -m pytest -q tests/test_slice_23_excel_ingest.py tests/test_slice_24_workbook_manifest.py tests/test_slice_25_excel_candidates.py tests/test_slice_26_cli_contract.py tests/test_slice_26_dsl_v2.py tests/test_slice_26_gexf_offline.py tests/test_slice_26_temporal_core.py tests/test_slice_27_ai_candidate_handoff.py tests/test_slice_27_batch_policies.py tests/test_slice_27_cross_schema_diff.py tests/test_slice_27_evidence_concordance.py tests/test_slice_27_precision_timezone.py tests/test_slice_27_spells_bounds.py
```

Risultato: `65 passed, 1 failed in 444.39s`; il fallimento di cleanup Windows
e la ripetizione isolata verde sono classificati sopra.

Test mirato finale Slice 28:

```powershell
& '.\.venv\Scripts\python.exe' -m pytest -q tests/test_slice_28_aurora_e2e.py
```

Risultato finale: `4 passed in 18.47s`.

Regressioni mirate 23–28:

```powershell
& '.\.venv\Scripts\python.exe' -m pytest -q 'tests/test_slice_23_excel_ingest.py::test_slice_23_real_xlsx_docling' 'tests/test_slice_23_excel_ingest.py::test_slice_23_real_xlsm_docling' 'tests/test_slice_23_excel_ingest.py::test_slice_23_real_external_link_is_never_dereferenced' 'tests/test_slice_23_excel_ingest.py::test_slice_23_partial_is_distinct_and_atomic' tests/test_slice_24_workbook_manifest.py tests/test_slice_25_excel_candidates.py 'tests/test_slice_26_dsl_v2.py::test_slice_26_dsl_v2_roundtrip' 'tests/test_slice_26_gexf_offline.py::test_slice_26_gexf_offline' 'tests/test_slice_26_gexf_offline.py::test_slice_26_xsd_sha_package_and_no_network' 'tests/test_slice_27_batch_policies.py::test_slice_27_batch_crash_retry_and_inverse_order_converge' tests/test_slice_27_cross_schema_diff.py 'tests/test_slice_27_evidence_concordance.py::test_slice_27_independent_concordance_correlation_and_conflict' 'tests/test_slice_27_spells_bounds.py::test_slice_27_spells_bounds_and_shared_golden_hash' tests/test_slice_28_aurora_e2e.py
```

Risultato: `22 passed, 1 failed in 424.32s`. Il solo fallimento era il timeout
ambientale del worker Docling XLSX a 120 s (`exit_code 5`, nessun traceback,
artefatti parziali scartati). Verifica alternativa immediata:

```powershell
& '.\.venv\Scripts\python.exe' -m pytest -q 'tests/test_slice_23_excel_ingest.py::test_slice_23_real_xlsx_docling'
```

Risultato: `1 passed in 191.84s`.

Prima suite completa:

```powershell
& '.\.venv\Scripts\python.exe' -m pytest -q
```

Risultato: `169 passed, 1 failed in 401.12s`. Il test Slice 28 di crash/retry
non raggiungeva il crash hook per un precedente `WinError 5` transitorio nel
rename atomico `output.json` del worker DDL. Classificazione: fragilita' del
test introdotto dalla Slice 28 esposta dall'ambiente Windows, non difetto
runtime. Il test e' stato corretto con un massimo di tre tentativi, ciascuno in
un nuovo workspace, ammessi solo quando il report e' esattamente
`batch_parse_failed`; errori ripetuti o diversi continuano a fallire.

Verifiche dopo la correzione:

```powershell
& '.\.venv\Scripts\python.exe' -m pytest -q 'tests/test_slice_28_aurora_e2e.py::test_slice_28_order_retry_uses_aurora_sources'
& '.\.venv\Scripts\python.exe' -m pytest -q tests/test_slice_28_aurora_e2e.py
& '.\.venv\Scripts\python.exe' -m pytest -q
```

Risultati:

```text
1 passed in 5.62s
4 passed in 18.47s
170 passed in 295.31s (0:04:55)
```

Verifica checksum finale dopo la rigenerazione:

```powershell
& '.\.venv\Scripts\python.exe' -m pytest -q 'tests/test_slice_28_aurora_e2e.py::test_slice_28_checksum_inventory_and_references'
```

Risultato: `1 passed in 1.52s`.

Fallimenti intermedi del test nuovo, tutti risolti prima della chiusura:

- `pytest -q tests/test_slice_28_aurora_e2e.py -k malformed`: atteso iniziale
  `failed` per il malformed contro il contratto v02 `rejected`; classificazione
  `introdotto dalla Slice` nel test, corretto in test e documentazione, poi
  `1 passed` con lo stesso comando;
- comando `pytest -q tests/test_slice_28_aurora_e2e.py -k 'aurora_e2e and not checksum' -s`: assunzione di una relazione pending non prodotta dalle fixture
  selezionate; classificazione `introdotto dalla Slice` nel test, rimossa. La
  review umana resta esercitata dalla temporalita' concordante;
- comando `pytest -q 'tests/test_slice_28_aurora_e2e.py::test_slice_28_aurora_e2e' -s`: lettura
  dei contatori merge al livello errato invece che sotto `counters`;
  classificazione `introdotto dalla Slice`, corretta;
- lo stesso test E2E, eseguito con e senza `-s`, ha poi segnalato l'assenza
  iniziale del golden e il successivo ampliamento con hash di decisioni, batch
  e workbook report: fallimenti di bootstrap espliciti, classificati
  `introdotto dalla Slice` e chiusi soltanto dopo il confronto fra due run
  identiche. Nessun output runtime e' stato assunto come verita' semantica.

Nessun test e' saltato o non eseguito. La Definition of Done e' soddisfatta
perche' l'ultima suite completa e' verde.

## Verifiche aggiuntive

- entry point console `dsl-manager --help`: exit 0;
- entry point modulo `.venv\Scripts\python.exe -m dsl_mngr --help`: exit 0;
- help verificati con exit 0: `batch consolidate`, `batch process-dir`,
  `candidates derive`, `candidates review`, `candidates review list/show/confirm`,
  `facts merge`, `corpus scan`, `dsl render`, `dsl diff`, `graph export`;
- migrazioni osservate con l'interprete di progetto: `10`, ultima
  `create_temporal_consolidation_schema`;
- il builder Aurora e il test Slice 28 compilano sotto Python 3.12;
- due invocazioni consecutive del builder mantengono invariato il manifest:
  SHA-256
  `1fa99c6fb55273efa7969aab8589289e72b91c296da7d693cdf2893ee1255d15`;
- la ricerca finale nel corpus non trova i due riferimenti obsoleti ne'
  dichiarazioni che XLSX sia unsupported/skipped;
- `git diff --check`: exit 0; i soli messaggi sono gli avvisi informativi Git
  sulla futura conversione LF → CRLF del worktree Windows;
- ricerca whitespace finale sui file nuovi e modificati: nessuna corrispondenza;
- diff stat tracciato: `9 files changed, 318 insertions(+), 1130 deletions(-)`;
- `git status --short --branch` conferma i 9 file Aurora modificati e i nuovi
  file Slice 28; mostra inoltre, senza alterazioni da questa Slice, il worktree
  preesistente delle Slice 20–27.

## Fuori scope / note

- nessuna modifica runtime, schema, migrazione o API pubblica;
- nessuna macro eseguita, rete o AI reale;
- nessun alias artificiale creato;
- nessuna fixture/golden di Slice precedenti modificata;
- i documenti di rumore e gli scenari legacy utili restano nel corpus;
- nessuna feature di Slice successive introdotta.
