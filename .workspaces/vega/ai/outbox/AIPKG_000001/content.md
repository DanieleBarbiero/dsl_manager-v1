# AI Package Content AIPKG_000001

Use only the evidence blocks below.

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
