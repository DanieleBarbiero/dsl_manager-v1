# Limitazioni intenzionali del corpus

## Oracle Forms

I file XML simulano una semplice esportazione leggibile di form Oracle. Non sono file binari `.fmb`.

Il parser v1 di `dsl-manager` riconosce un elemento radice `<form>` con figli `<field>` e `<button>`. Per questo motivo le fixture sono volutamente semplici.

## SQL e PL/SQL

Il DDL usa tipi Oracle come `NUMBER` e `VARCHAR2`, ma mantiene i vincoli dentro `CREATE TABLE`, forma gestita dal parser minimale. Gli indici Oracle sono volutamente omessi perché il parser DDL v1 non gestisce ancora in modo affidabile `CREATE INDEX`.

Il parser del codice database non è un parser PL/SQL generale. Le procedure e i trigger usano il sottoinsieme coperto dalla v1: `CREATE PROCEDURE`, `CREATE TRIGGER`, `UPDATE` e `CALL`.

## Documenti

Markdown, testo, HTML e DOCX sono fonti normalizzabili. Il foglio XLSX è incluso per mostrare un formato utile ma non supportato dal batch v1: deve risultare `skipped`, non va forzato nel parser sbagliato.

## Dati

Non sono presenti dati personali reali. Gli identificativi nei log sono fittizi.
