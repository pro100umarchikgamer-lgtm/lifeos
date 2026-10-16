CREATE OR REPLACE FUNCTION control_audit_append_only() RETURNS trigger LANGUAGE plpgsql AS $$
BEGIN
    RAISE EXCEPTION 'control_audit is append-only';
END;
$$;
CREATE TRIGGER control_audit_no_update_delete BEFORE UPDATE OR DELETE ON control_audit
FOR EACH ROW EXECUTE FUNCTION control_audit_append_only();
