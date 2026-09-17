# Matrice fixture e routing atteso — Vega Ricambi 1.0

Questa matrice descrive il routing **atteso con il codice corrente di
dsl_manager-v1**.

| Fonte | Famiglia | Routing atteso | Perché esiste |
|---|---|---|---|
| `database/schema_vega.sql` | DDL | `parse_ddl` | tabelle, PK, FK, colonne |
| `plsql/logica_vega.sql` | DB code | `parse_db_code` | procedure, trigger, read/write dependency |
| `forms/frm_richiesta.xml` | XML Forms | `parse_xml_form` | form, campi required, bottone/operazione |
| `logs/vega_2026.log` | log | `parse_log` | eventi nominati e warning |
| `documenti/manuale_operativo_vega_2026.docx` | legacy document | `normalize` + `chunk` | testo narrativo e tabella |
| `documenti/matrice_priorita_vega_2026.xlsx` | workbook | `normalize` + `chunk` | struttura workbook/tabella e testo |

## Conteggi strutturali del laboratorio

- fonti operative: **6**
- operazioni di processing attese: **8**
- fonti che richiedono normalizzazione Docling: **2**
- file intenzionalmente malformati nel corpus operativo: **0**

## Fixture fuori corpus

`fixture_controllate/workbook_malformed_controllato.xlsx` non è un workbook
valido. Serve soltanto a testare il rifiuto preflight in un workspace separato.

## Cosa non è coperto da Vega

Vega non prova in modo dedicato:

- PDF;
- PPTX;
- HTML;
- TXT;
- Markdown come fonte documentale;
- XLSM/VBA;
- external link workbook;
- copertura multipla dello stesso parser;
- replay AI congelato;
- temporalità complessa;
- orphan GEXF intenzionali;
- partial-success controllato.

Questi scenari sono più adatti ai laboratori estesi Aurora/Orione.
