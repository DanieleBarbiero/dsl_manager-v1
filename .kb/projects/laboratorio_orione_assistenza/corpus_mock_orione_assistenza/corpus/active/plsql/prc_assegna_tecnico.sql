-- Assegnazione conservativa: il tecnico deve essere attivo e l'intervento aperto.
CREATE OR REPLACE PROCEDURE prc_assegna_tecnico (
    p_intervento_id IN NUMBER,
    p_tecnico_id IN NUMBER
) AS
    v_tecnico_attivo NUMBER;
BEGIN
    SELECT attivo
      INTO v_tecnico_attivo
      FROM tecnico
     WHERE tecnico_id = p_tecnico_id;

    INSERT INTO assegnazione (
        assegnazione_id, intervento_id, tecnico_id, assegnato_il
    ) VALUES (
        seq_assegnazione.NEXTVAL, p_intervento_id, p_tecnico_id, SYSTIMESTAMP
    );

    UPDATE intervento
       SET stato = 'ASSEGNATO'
     WHERE intervento_id = p_intervento_id
       AND stato = 'APERTO';
END prc_assegna_tecnico;
/
