-- Orione Assistenza - schema legacy dimostrativo, interamente fittizio.
CREATE TABLE tecnico (
    tecnico_id NUMBER(10) NOT NULL,
    codice VARCHAR2(20) NOT NULL,
    nome_operativo VARCHAR2(80) NOT NULL,
    attivo NUMBER(1) DEFAULT 1 NOT NULL,
    CONSTRAINT pk_tecnico PRIMARY KEY (tecnico_id),
    CONSTRAINT uq_tecnico_codice UNIQUE (codice)
);

CREATE TABLE asset (
    asset_id NUMBER(10) NOT NULL,
    codice_asset VARCHAR2(30) NOT NULL,
    categoria VARCHAR2(40) NOT NULL,
    criticita VARCHAR2(10) NOT NULL,
    CONSTRAINT pk_asset PRIMARY KEY (asset_id),
    CONSTRAINT uq_asset_codice UNIQUE (codice_asset)
);

CREATE TABLE intervento (
    intervento_id NUMBER(10) NOT NULL,
    asset_id NUMBER(10) NOT NULL,
    priorita VARCHAR2(4) NOT NULL,
    stato VARCHAR2(20) NOT NULL,
    aperto_il TIMESTAMP WITH TIME ZONE NOT NULL,
    chiuso_il TIMESTAMP WITH TIME ZONE,
    CONSTRAINT pk_intervento PRIMARY KEY (intervento_id),
    CONSTRAINT fk_intervento_asset FOREIGN KEY (asset_id) REFERENCES asset (asset_id)
);

CREATE TABLE assegnazione (
    assegnazione_id NUMBER(10) NOT NULL,
    intervento_id NUMBER(10) NOT NULL,
    tecnico_id NUMBER(10) NOT NULL,
    assegnato_il TIMESTAMP WITH TIME ZONE NOT NULL,
    CONSTRAINT pk_assegnazione PRIMARY KEY (assegnazione_id),
    CONSTRAINT fk_assegnazione_intervento FOREIGN KEY (intervento_id)
        REFERENCES intervento (intervento_id),
    CONSTRAINT fk_assegnazione_tecnico FOREIGN KEY (tecnico_id)
        REFERENCES tecnico (tecnico_id),
    CONSTRAINT uq_assegnazione_intervento UNIQUE (intervento_id)
);

CREATE TABLE checklist_chiusura (
    voce_id NUMBER(10) NOT NULL,
    intervento_id NUMBER(10) NOT NULL,
    descrizione VARCHAR2(200) NOT NULL,
    obbligatoria NUMBER(1) DEFAULT 1 NOT NULL,
    completata NUMBER(1) DEFAULT 0 NOT NULL,
    CONSTRAINT pk_checklist_chiusura PRIMARY KEY (voce_id),
    CONSTRAINT fk_checklist_intervento FOREIGN KEY (intervento_id)
        REFERENCES intervento (intervento_id)
);

CREATE TABLE regola_sla (
    regola_sla_id NUMBER(10) NOT NULL,
    priorita VARCHAR2(4) NOT NULL,
    ore_risoluzione NUMBER(5,2) NOT NULL,
    valida_dal DATE NOT NULL,
    valida_al DATE,
    CONSTRAINT pk_regola_sla PRIMARY KEY (regola_sla_id)
);

CREATE INDEX ix_intervento_stato_priorita ON intervento (stato, priorita);
CREATE INDEX ix_checklist_intervento ON checklist_chiusura (intervento_id);

CREATE VIEW vw_interventi_aperti AS
SELECT i.intervento_id, i.asset_id, i.priorita, i.aperto_il
FROM intervento i
WHERE i.stato <> 'CHIUSO';
