# AI Package Content AIPKG_000002

Use only the evidence blocks below.

## Evidence CHK_000001

- source_id: SRC_000002
- source_revision_id: REV_000002
- source_path: corpus/active/documenti/manuale_operativo_vega_2026.docx
- source_type: unknown
- authority_level: unknown
- evidence_kind: chunk
- chunk_id: CHK_000001
- sequence: 1
- text_hash: 0949d9eb61c9f5ae95cdfecadc7b7c74d7240d94ed42e515ff8c968dccd29a73
- truncated: false

```text
## Vega Ricambi - Manuale operativo 2026

Questo documento fittizio descrive le regole minime usate nel laboratorio DSL Manager.

### Regole correnti

Una richiesta P1 deve essere presa in carico entro 30 minuti.

La chiusura e consentita soltanto dopo lo stato CONSEGNATA.

Una prenotazione riduce la disponibilita dell'articolo.

Le regole correnti decorrono dal 2026-09-01.

### Punti da non dedurre automaticamente

Il manuale non stabilisce chi approva le eccezioni di scorta e non documenta alcun sistema esterno di acquisto. Questi aspetti devono restare incerti.

| Priorita   | Presa in carico   | Nota              |
|------------|-------------------|-------------------|
| P1         | 30 minuti         | urgenza operativa |
| P2         | 4 ore             | ordinaria         |
```

## Evidence CHK_000002

- source_id: SRC_000003
- source_revision_id: REV_000003
- source_path: corpus/active/documenti/matrice_priorita_vega_2026.xlsx
- source_type: unknown
- authority_level: unknown
- evidence_kind: chunk
- chunk_id: CHK_000002
- sequence: 1
- text_hash: 7e53ea44f13e014023ce250ee74d83a87849feea11c4546b9828296cf78ae193
- truncated: false

```text
| Priorità   |   Tempo presa in carico (ore) | Descrizione                                               | Esempio                                      |
|------------|-------------------------------|-----------------------------------------------------------|----------------------------------------------|
| P1         |                             1 | Blocco totale o rischio operativo critico                 | Ricambio urgente: linea ferma                |
| P2         |                             4 | Impatto elevato ma attività ancora parzialmente possibile | Ricambio necessario entro la giornata        |
| P3         |                            24 | Impatto moderato, workaround disponibile                  | Richiesta standard con urgenza contenuta     |
| P4         |                            72 | Bassa priorità o richiesta programmabile                  | Scorta preventiva / manutenzione pianificata |
```

## Evidence FRAG_000029

- source_id: SRC_000006
- source_revision_id: REV_000006
- source_path: corpus/active/plsql/logica_vega.sql
- source_type: database_code
- authority_level: runtime_code
- evidence_kind: fragment
- fragment_id: FRAG_000029
- fragment_type: sql_statement
- path_or_selector: procedure:PRC_PRENOTA_ARTICOLO/statement:1
- sequence: 3
- text_hash: 7b9b0f098670b9856f549b2582c5fe3842a5ee8c6a29afddf6ef8363bdd9a407
- truncated: false

```text
UPDATE RICHIESTA_RICAMBIO
       SET STATO = 'PRENOTATA'
     WHERE ID_RICHIESTA = P_ID_RICHIESTA;
```

## Evidence FRAG_000030

- source_id: SRC_000006
- source_revision_id: REV_000006
- source_path: corpus/active/plsql/logica_vega.sql
- source_type: database_code
- authority_level: runtime_code
- evidence_kind: fragment
- fragment_id: FRAG_000030
- fragment_type: sql_statement
- path_or_selector: procedure:PRC_PRENOTA_ARTICOLO/statement:2
- sequence: 4
- text_hash: 95b301327e0e09103bff7abc3ad6e6e5c483b9d20e280a1a6aa981e04205a48c
- truncated: false

```text
UPDATE ARTICOLO
       SET QTA_DISPONIBILE = QTA_DISPONIBILE - 1
     WHERE ID_ARTICOLO = (
        SELECT ID_ARTICOLO
          FROM RICHIESTA_RICAMBIO
         WHERE ID_RICHIESTA = P_ID_RICHIESTA
     );
```

## Evidence FRAG_000001

- source_id: SRC_000001
- source_revision_id: REV_000001
- source_path: corpus/active/database/schema_vega.sql
- source_type: ddl
- authority_level: technical_structure
- evidence_kind: fragment
- fragment_id: FRAG_000001
- fragment_type: ddl_table
- path_or_selector: table:ARTICOLO
- sequence: 1
- text_hash: 81814eecd7c72c942ccd925fdc72efe7480319e6d5c846a278ef853b71aee32c
- truncated: false

```text
CREATE TABLE ARTICOLO (
    ID_ARTICOLO NUMBER PRIMARY KEY,
    CODICE VARCHAR2(30) NOT NULL,
    DESCRIZIONE VARCHAR2(200) NOT NULL,
    QTA_DISPONIBILE NUMBER NOT NULL
);
```

## Evidence FRAG_000002

- source_id: SRC_000001
- source_revision_id: REV_000001
- source_path: corpus/active/database/schema_vega.sql
- source_type: ddl
- authority_level: technical_structure
- evidence_kind: fragment
- fragment_id: FRAG_000002
- fragment_type: ddl_column
- path_or_selector: table:ARTICOLO/column:ID_ARTICOLO
- sequence: 2
- text_hash: 755a643188bd7ac8866b488fbcdfcb4f4acff3fe5f000c1137b34d1fd06ad33f
- truncated: false

```text
ID_ARTICOLO NUMBER PRIMARY KEY
```

## Evidence FRAG_000003

- source_id: SRC_000001
- source_revision_id: REV_000001
- source_path: corpus/active/database/schema_vega.sql
- source_type: ddl
- authority_level: technical_structure
- evidence_kind: fragment
- fragment_id: FRAG_000003
- fragment_type: ddl_column
- path_or_selector: table:ARTICOLO/column:CODICE
- sequence: 3
- text_hash: ff21e9f7f4f7456274bb3b5561150d2ef3ebe237f3cadac96882941473ab8358
- truncated: false

```text
CODICE VARCHAR2(30) NOT NULL
```

## Evidence FRAG_000004

- source_id: SRC_000001
- source_revision_id: REV_000001
- source_path: corpus/active/database/schema_vega.sql
- source_type: ddl
- authority_level: technical_structure
- evidence_kind: fragment
- fragment_id: FRAG_000004
- fragment_type: ddl_column
- path_or_selector: table:ARTICOLO/column:DESCRIZIONE
- sequence: 4
- text_hash: 54408614f47c988f08688bebef83ac1c4acd2b6f2ba977b17508f2d948aff71c
- truncated: false

```text
DESCRIZIONE VARCHAR2(200) NOT NULL
```

## Evidence FRAG_000005

- source_id: SRC_000001
- source_revision_id: REV_000001
- source_path: corpus/active/database/schema_vega.sql
- source_type: ddl
- authority_level: technical_structure
- evidence_kind: fragment
- fragment_id: FRAG_000005
- fragment_type: ddl_column
- path_or_selector: table:ARTICOLO/column:QTA_DISPONIBILE
- sequence: 5
- text_hash: 41c2bdfa1ccdf33d863297fdada4705a2b0ec43d4d2a95f7f9250a43e958b69c
- truncated: false

```text
QTA_DISPONIBILE NUMBER NOT NULL
```

## Evidence FRAG_000006

- source_id: SRC_000001
- source_revision_id: REV_000001
- source_path: corpus/active/database/schema_vega.sql
- source_type: ddl
- authority_level: technical_structure
- evidence_kind: fragment
- fragment_id: FRAG_000006
- fragment_type: ddl_constraint
- path_or_selector: table:ARTICOLO/primary_key:ID_ARTICOLO
- sequence: 6
- text_hash: 755a643188bd7ac8866b488fbcdfcb4f4acff3fe5f000c1137b34d1fd06ad33f
- truncated: false

```text
ID_ARTICOLO NUMBER PRIMARY KEY
```

## Evidence FRAG_000007

- source_id: SRC_000001
- source_revision_id: REV_000001
- source_path: corpus/active/database/schema_vega.sql
- source_type: ddl
- authority_level: technical_structure
- evidence_kind: fragment
- fragment_id: FRAG_000007
- fragment_type: ddl_table
- path_or_selector: table:RICHIESTA_RICAMBIO
- sequence: 7
- text_hash: 1b50aa570dc39497b9f6df21e54e52c114df628b6a831ff596cfc47e01d14009
- truncated: false

```text
CREATE TABLE RICHIESTA_RICAMBIO (
    ID_RICHIESTA NUMBER PRIMARY KEY,
    ID_ARTICOLO NUMBER NOT NULL,
    PRIORITA VARCHAR2(10) NOT NULL,
    STATO VARCHAR2(20) NOT NULL,
    QTA_RICHIESTA NUMBER NOT NULL,
    CONSTRAINT FK_RICHIESTA_ARTICOLO
        FOREIGN KEY (ID_ARTICOLO) REFERENCES ARTICOLO(ID_ARTICOLO)
);
```

## Evidence FRAG_000008

- source_id: SRC_000001
- source_revision_id: REV_000001
- source_path: corpus/active/database/schema_vega.sql
- source_type: ddl
- authority_level: technical_structure
- evidence_kind: fragment
- fragment_id: FRAG_000008
- fragment_type: ddl_column
- path_or_selector: table:RICHIESTA_RICAMBIO/column:ID_RICHIESTA
- sequence: 8
- text_hash: e9561d78493965c0ca8e3734346134f74f18d5898f7e3cf06e532b439c5bd379
- truncated: false

```text
ID_RICHIESTA NUMBER PRIMARY KEY
```

## Evidence FRAG_000009

- source_id: SRC_000001
- source_revision_id: REV_000001
- source_path: corpus/active/database/schema_vega.sql
- source_type: ddl
- authority_level: technical_structure
- evidence_kind: fragment
- fragment_id: FRAG_000009
- fragment_type: ddl_column
- path_or_selector: table:RICHIESTA_RICAMBIO/column:ID_ARTICOLO
- sequence: 9
- text_hash: 1129cf5143216dc0ddcc47ba2141f2d99feeb2e83e3e6ba88cc8b3dee75a46bf
- truncated: false

```text
ID_ARTICOLO NUMBER NOT NULL
```

## Evidence FRAG_000010

- source_id: SRC_000001
- source_revision_id: REV_000001
- source_path: corpus/active/database/schema_vega.sql
- source_type: ddl
- authority_level: technical_structure
- evidence_kind: fragment
- fragment_id: FRAG_000010
- fragment_type: ddl_column
- path_or_selector: table:RICHIESTA_RICAMBIO/column:PRIORITA
- sequence: 10
- text_hash: 39408a007f2e2904aea74caba73c8197a8027a0c98df3c7d43a4cb2e14c03635
- truncated: false

```text
PRIORITA VARCHAR2(10) NOT NULL
```

## Evidence FRAG_000011

- source_id: SRC_000001
- source_revision_id: REV_000001
- source_path: corpus/active/database/schema_vega.sql
- source_type: ddl
- authority_level: technical_structure
- evidence_kind: fragment
- fragment_id: FRAG_000011
- fragment_type: ddl_column
- path_or_selector: table:RICHIESTA_RICAMBIO/column:STATO
- sequence: 11
- text_hash: 376fdb67145cff0fa70bad2132e131958107b4cfe4de20b9cb5b47925e2b779a
- truncated: false

```text
STATO VARCHAR2(20) NOT NULL
```

## Evidence FRAG_000012

- source_id: SRC_000001
- source_revision_id: REV_000001
- source_path: corpus/active/database/schema_vega.sql
- source_type: ddl
- authority_level: technical_structure
- evidence_kind: fragment
- fragment_id: FRAG_000012
- fragment_type: ddl_column
- path_or_selector: table:RICHIESTA_RICAMBIO/column:QTA_RICHIESTA
- sequence: 12
- text_hash: 4b29bd88e0a90dddc9e129072457f4347b8f21410bf7afab262dcdd2bbba7b71
- truncated: false

```text
QTA_RICHIESTA NUMBER NOT NULL
```

## Evidence FRAG_000013

- source_id: SRC_000001
- source_revision_id: REV_000001
- source_path: corpus/active/database/schema_vega.sql
- source_type: ddl
- authority_level: technical_structure
- evidence_kind: fragment
- fragment_id: FRAG_000013
- fragment_type: ddl_constraint
- path_or_selector: table:RICHIESTA_RICAMBIO/primary_key:ID_RICHIESTA
- sequence: 13
- text_hash: e9561d78493965c0ca8e3734346134f74f18d5898f7e3cf06e532b439c5bd379
- truncated: false

```text
ID_RICHIESTA NUMBER PRIMARY KEY
```

## Evidence FRAG_000014

- source_id: SRC_000001
- source_revision_id: REV_000001
- source_path: corpus/active/database/schema_vega.sql
- source_type: ddl
- authority_level: technical_structure
- evidence_kind: fragment
- fragment_id: FRAG_000014
- fragment_type: ddl_constraint
- path_or_selector: table:RICHIESTA_RICAMBIO/foreign_key:ID_ARTICOLO->ARTICOLO.ID_ARTICOLO
- sequence: 14
- text_hash: 7919c511af69b27e4ed1173265fd8171c08123d01101051ee8dd542fb8416fed
- truncated: false

```text
CONSTRAINT FK_RICHIESTA_ARTICOLO
        FOREIGN KEY (ID_ARTICOLO) REFERENCES ARTICOLO(ID_ARTICOLO)
```

## Evidence FRAG_000015

- source_id: SRC_000003
- source_revision_id: REV_000003
- source_path: corpus/active/documenti/matrice_priorita_vega_2026.xlsx
- source_type: unknown
- authority_level: unknown
- evidence_kind: fragment
- fragment_id: FRAG_000015
- fragment_type: excel_region
- path_or_selector: xl/worksheets/sheet1.xml#A1:D5
- sequence: 1
- text_hash: 6471cb5fe36d722903ec7a908204528e9bad36ba3533a32428302a32c7d640ec
- truncated: false

```text
{"cells":[{"cached_value":null,"column":1,"coordinate":"A1","formula":null,"row":1,"style_id":8,"type":"string","value":"Priorità"},{"cached_value":null,"column":2,"coordinate":"B1","formula":null,"row":1,"style_id":8,"type":"string","value":"Tempo presa in carico (ore)"},{"cached_value":null,"column":3,"coordinate":"C1","formula":null,"row":1,"style_id":8,"type":"string","value":"Descrizione"},{"cached_value":null,"column":4,"coordinate":"D1","formula":null,"row":1,"style_id":8,"type":"string","value":"Esempio"},{"cached_value":null,"column":1,"coordinate":"A2","formula":null,"row":2,"style_id":9,"type":"string","value":"P1"},{"cached_value":null,"column":2,"coordinate":"B2","formula":null,"row":2,"style_id":9,"type":"number","value":"1"},{"cached_value":null,"column":3,"coordinate":"C2","formula":null,"row":2,"style_id":9,"type":"string","value":"Blocco totale o rischio operativo critico"},{"cached_value":null,"column":4,"coordinate":"D2","formula":null,"row":2,"style_id":9,"type":"string","value":"Ricambio urgente: linea ferma"},{"cached_value":null,"column":1,"coordinate":"A3","formula":null,"row":3,"style_id":9,"type":"string","value":"P2"},{"cached_value":null,"column":2,"coordinate":"B3","formula":null,"row":3,"style_id":9,"type":"number","value":"4"},{"cached_value":null,"column":3,"coordinate":"C3","formula":null,"row":3,"style_id":9,"type":"string","value":"Impatto elevato ma attività ancora parzialmente possibile"},{"cached_value":null,"column":4,"coordinate":"D3","formula":null,"row":3,"style_id":9,"type":"string","value":"Ricambio necessario entro la giornata"},{"cached_value":null,"column":1,"coordinate":"A4","formula":null,"row":4,"style_id":9,"type":"string","value":"P3"},{"cached_value":null,"column":2,"coordinate":"B4","formula":null,"row":4,"style_id":9,"type":"number","value":"24"},{"cached_value":null,"column":3,"coordinate":"C4","formula":null,"row":4,"style_id":9,"type":"string","value":"Impatto moderato, workaround disponibile"},{"cached_value":null,"column":4,"coordinate":"D4","formula":null,"row":4,"style_id":9,"type":"string","value":"Richiesta standard con urgenza contenuta"},{"cached_value":null,"column":1,"coordinate":"A5","formula":null,"row":5,"style_id":9,"type":"string","value":"P4"},{"cached_value":null,"column":2,"coordinate":"B5","formula":null,"row":5,"style_id":9,"type":"number","value":"72"},{"cached_value":null,"column":3,"coordinate":"C5","formula":null,"row":5,"style_id":9,"type":"string","value":"Bassa priorità o richiesta programmabile"},{"cached_value":null,"column":4,"coordinate":"D5","formula":null,"row":5,"style_id":9,"type":"string","value":"Scorta preventiva / manutenzione pianificata"}],"detector":{"id":"connected_non_empty_cells","version":"1"},"end_cell":"D5","locator":{"part_name":"xl/worksheets/sheet1.xml","range":"A1:D5"},"region_hash":"20aada49828c65a87d0bf8b42c319b780ed4b87f57b299507572f9797efcf4fe","region_kind":"connected_cells","sheet":{"index":0,"name":"Priorita"},"start_cell":"A1"}
```

## Evidence FRAG_000016

- source_id: SRC_000004
- source_revision_id: REV_000004
- source_path: corpus/active/forms/frm_richiesta.xml
- source_type: xml_form
- authority_level: technical_structure
- evidence_kind: fragment
- fragment_id: FRAG_000016
- fragment_type: xml_form
- path_or_selector: /form[@name='FRM_RICHIESTA']
- sequence: 1
- text_hash: 86fafaace02463b63adc0f48e8e2aecee26e77a2c29e9982ce9be8d2c03cc939
- truncated: false

```text
<form name="FRM_RICHIESTA" title="Richiesta ricambio">
  <block name="RICHIESTA_RICAMBIO" table="RICHIESTA_RICAMBIO">
    <item name="ID_RICHIESTA" column="ID_RICHIESTA" datatype="NUMBER" required="true"/>
    <item name="ID_ARTICOLO" column="ID_ARTICOLO" datatype="NUMBER" required="true"/>
    <item name="PRIORITA" column="PRIORITA" datatype="VARCHAR2" required="true"/>
    <item name="STATO" column="STATO" datatype="VARCHAR2" required="true"/>
  </block>
  <button name="BTN_PRENOTA" label="Prenota" operation="PRC_PRENOTA_ARTICOLO"/>
</form>
```

## Evidence FRAG_000017

- source_id: SRC_000004
- source_revision_id: REV_000004
- source_path: corpus/active/forms/frm_richiesta.xml
- source_type: xml_form
- authority_level: technical_structure
- evidence_kind: fragment
- fragment_id: FRAG_000017
- fragment_type: xml_field
- path_or_selector: /form[@name='FRM_RICHIESTA']/block[@name='RICHIESTA_RICAMBIO']/item[@name='ID_RICHIESTA']
- sequence: 2
- text_hash: 535b1a301387fde6d2ef65f98b30341a6e8b538d18337a6e584d4233bc2efa5b
- truncated: false

```text
<item name="ID_RICHIESTA" column="ID_RICHIESTA" datatype="NUMBER" required="true"/>
```

## Evidence FRAG_000018

- source_id: SRC_000004
- source_revision_id: REV_000004
- source_path: corpus/active/forms/frm_richiesta.xml
- source_type: xml_form
- authority_level: technical_structure
- evidence_kind: fragment
- fragment_id: FRAG_000018
- fragment_type: xml_field
- path_or_selector: /form[@name='FRM_RICHIESTA']/block[@name='RICHIESTA_RICAMBIO']/item[@name='ID_ARTICOLO']
- sequence: 3
- text_hash: 7be0e2ec8a6ee27e512e4129408fba4d834f6d28c80e1f179b111af789c474bd
- truncated: false

```text
<item name="ID_ARTICOLO" column="ID_ARTICOLO" datatype="NUMBER" required="true"/>
```

## Evidence FRAG_000019

- source_id: SRC_000004
- source_revision_id: REV_000004
- source_path: corpus/active/forms/frm_richiesta.xml
- source_type: xml_form
- authority_level: technical_structure
- evidence_kind: fragment
- fragment_id: FRAG_000019
- fragment_type: xml_field
- path_or_selector: /form[@name='FRM_RICHIESTA']/block[@name='RICHIESTA_RICAMBIO']/item[@name='PRIORITA']
- sequence: 4
- text_hash: 94f92d5b5bbf4a0324b08661435ec82449d05845297baaf75c94e128bad810b4
- truncated: false

```text
<item name="PRIORITA" column="PRIORITA" datatype="VARCHAR2" required="true"/>
```

## Evidence FRAG_000020

- source_id: SRC_000004
- source_revision_id: REV_000004
- source_path: corpus/active/forms/frm_richiesta.xml
- source_type: xml_form
- authority_level: technical_structure
- evidence_kind: fragment
- fragment_id: FRAG_000020
- fragment_type: xml_field
- path_or_selector: /form[@name='FRM_RICHIESTA']/block[@name='RICHIESTA_RICAMBIO']/item[@name='STATO']
- sequence: 5
- text_hash: 1cb57413e00229dbaed9efac40c499f110ce595ded5df3d7986858c239d14d15
- truncated: false

```text
<item name="STATO" column="STATO" datatype="VARCHAR2" required="true"/>
```

## Evidence FRAG_000021

- source_id: SRC_000004
- source_revision_id: REV_000004
- source_path: corpus/active/forms/frm_richiesta.xml
- source_type: xml_form
- authority_level: technical_structure
- evidence_kind: fragment
- fragment_id: FRAG_000021
- fragment_type: xml_button
- path_or_selector: /form[@name='FRM_RICHIESTA']/button[@name='BTN_PRENOTA']
- sequence: 6
- text_hash: 1dcc617ccb1924f00242af5f7e693dc286e73c0fe5da5d005db6b911214386cc
- truncated: false

```text
<button name="BTN_PRENOTA" label="Prenota" operation="PRC_PRENOTA_ARTICOLO"/>
```

## Evidence FRAG_000022

- source_id: SRC_000005
- source_revision_id: REV_000005
- source_path: corpus/active/logs/vega_2026.log
- source_type: log
- authority_level: runtime_observation
- evidence_kind: fragment
- fragment_id: FRAG_000022
- fragment_type: log_event
- path_or_selector: log/line:1
- sequence: 1
- text_hash: e99a55d81603ef0096e0b40d29897605aa02cbdf9acfddd039044846fcc07a0a
- truncated: false

```text
2026-09-01 08:00:00 INFO scanner Start richiesta=RV-1001 priorita=P1
```

## Evidence FRAG_000023

- source_id: SRC_000005
- source_revision_id: REV_000005
- source_path: corpus/active/logs/vega_2026.log
- source_type: log
- authority_level: runtime_observation
- evidence_kind: fragment
- fragment_id: FRAG_000023
- fragment_type: log_event
- path_or_selector: log/line:2
- sequence: 2
- text_hash: fed9868a4d1cf2c01e8e66040afaf0b6d3e6eb46517f4355d8560694d77ee155
- truncated: false

```text
2026-09-01 08:00:01 INFO scanner Processed richiesta=RV-1001 articolo=RIC-774 quantita=2
```

## Evidence FRAG_000024

- source_id: SRC_000005
- source_revision_id: REV_000005
- source_path: corpus/active/logs/vega_2026.log
- source_type: log
- authority_level: runtime_observation
- evidence_kind: fragment
- fragment_id: FRAG_000024
- fragment_type: log_event
- path_or_selector: log/line:3
- sequence: 3
- text_hash: 9d7e11da6e3107c94b164ae8e356f5f8a3670e846e02eaf1638c958d248cab9b
- truncated: false

```text
2026-09-01 08:00:02 WARNING magazzino missing richiesta=RV-1002 articolo=RIC-118 priorita=P2
```

## Evidence FRAG_000025

- source_id: SRC_000005
- source_revision_id: REV_000005
- source_path: corpus/active/logs/vega_2026.log
- source_type: log
- authority_level: runtime_observation
- evidence_kind: fragment
- fragment_id: FRAG_000025
- fragment_type: log_event
- path_or_selector: log/line:4
- sequence: 4
- text_hash: acd1e678d7805f389cf046eb355bbf7cd3b7f6da9865b71befb949a9519100ec
- truncated: false

```text
2026-09-01 08:00:03 INFO magazzino Processed richiesta=RV-1002 articolo=RIC-118 disponibilita=parziale
```

## Evidence FRAG_000026

- source_id: SRC_000005
- source_revision_id: REV_000005
- source_path: corpus/active/logs/vega_2026.log
- source_type: log
- authority_level: runtime_observation
- evidence_kind: fragment
- fragment_id: FRAG_000026
- fragment_type: log_event
- path_or_selector: log/line:5
- sequence: 5
- text_hash: 490e3fda21b0f91e9a6a41b26bdcc717f9eb16a8911a5d31a8bc7ea48a81caf9
- truncated: false

```text
2026-09-01 08:00:04 INFO scanner End richiesta=RV-1001 esito=inoltrata
```

## Evidence FRAG_000027

- source_id: SRC_000006
- source_revision_id: REV_000006
- source_path: corpus/active/plsql/logica_vega.sql
- source_type: database_code
- authority_level: runtime_code
- evidence_kind: fragment
- fragment_id: FRAG_000027
- fragment_type: sql_trigger
- path_or_selector: trigger:TRG_CHIUDI_RICHIESTA
- sequence: 1
- text_hash: a67b70ca50a81990b777a3f93d6dfa9078c18981f6666a1b6c71edba6ecfba0d
- truncated: false

```text
CREATE TRIGGER TRG_CHIUDI_RICHIESTA
BEFORE UPDATE OF STATO ON RICHIESTA_RICAMBIO
FOR EACH ROW
BEGIN
    IF :NEW.STATO = 'CHIUSA' AND :OLD.STATO <> 'CONSEGNATA' THEN
        RAISE_APPLICATION_ERROR(-20001, 'La richiesta deve essere consegnata prima della chiusura');
    END IF;
END;
```

## Evidence FRAG_000028

- source_id: SRC_000006
- source_revision_id: REV_000006
- source_path: corpus/active/plsql/logica_vega.sql
- source_type: database_code
- authority_level: runtime_code
- evidence_kind: fragment
- fragment_id: FRAG_000028
- fragment_type: sql_procedure
- path_or_selector: procedure:PRC_PRENOTA_ARTICOLO
- sequence: 2
- text_hash: 583946ddd210a10a6cf4fdc51ba5d57eeb676f7a170cf848858e677e0261f736
- truncated: false

```text
CREATE PROCEDURE PRC_PRENOTA_ARTICOLO (
    P_ID_RICHIESTA IN NUMBER
) AS
BEGIN
    UPDATE RICHIESTA_RICAMBIO
       SET STATO = 'PRENOTATA'
     WHERE ID_RICHIESTA = P_ID_RICHIESTA;

    UPDATE ARTICOLO
       SET QTA_DISPONIBILE = QTA_DISPONIBILE - 1
     WHERE ID_ARTICOLO = (
        SELECT ID_ARTICOLO
          FROM RICHIESTA_RICAMBIO
         WHERE ID_RICHIESTA = P_ID_RICHIESTA
     );
END;
```
