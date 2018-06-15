BEGIN;
SET session_replication_role = replica;
DELETE FROM model.entity WHERE id NOT IN
    (SELECT e.id
    FROM model.entity e
    JOIN model.link l ON
        e.id = l.domain_id
        AND l.property_code = 'P2'
        AND l.range_id = (SELECT id FROM model.entity WHERE name = 'Ethnonym of the Vlachs'))

AND class_code IN ('E33', 'E6', 'E7', 'E8', 'E12', 'E21', 'E74', 'E40', 'E31', 'E18', 'E53', 'E84') AND (system_type IS NULL OR system_type NOT IN ('source translation'));
SET session_replication_role = DEFAULT;
COMMIT;
