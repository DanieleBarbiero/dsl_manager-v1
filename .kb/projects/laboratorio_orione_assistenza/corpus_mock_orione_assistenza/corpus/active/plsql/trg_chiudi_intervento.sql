-- Il trigger registra la chiusura; la regola di checklist resta da interpretare.
CREATE OR REPLACE TRIGGER trg_chiudi_intervento
BEFORE UPDATE ON intervento
FOR EACH ROW
BEGIN
    IF :NEW.stato = 'CHIUSO' AND :OLD.stato <> 'CHIUSO' THEN
        :NEW.chiuso_il := SYSTIMESTAMP;
        UPDATE checklist_chiusura
           SET completata = completata
         WHERE intervento_id = :NEW.intervento_id;
    END IF;
END trg_chiudi_intervento;
/
