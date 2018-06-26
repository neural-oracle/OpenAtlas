-- SQL to filter demo data from DPP

-- To do:
-- delete other users

BEGIN;

-- Disable triggers, otherwise script takes forever and/or run into errors
ALTER TABLE model.entity DISABLE TRIGGER on_delete_entity;
ALTER TABLE model.link_property DISABLE TRIGGER on_delete_link_property;

-- Delete data from other case studies
DELETE FROM model.entity WHERE id NOT IN
    (SELECT e.id
    FROM model.entity e
    JOIN model.link l ON
        e.id = l.domain_id
        AND l.property_code = 'P2'
        AND l.range_id = (SELECT id FROM model.entity WHERE name = 'Ethnonym of the Vlachs'))

AND class_code IN ('E33', 'E6', 'E7', 'E8', 'E12', 'E21', 'E74', 'E40', 'E31', 'E18', 'E53', 'E84') AND (system_type IS NULL OR system_type NOT IN ('source translation'));

-- Delete orphans manually because triggers are disabled
DELETE FROM model.entity WHERE id IN (
   SELECT e.id FROM model.entity e
        LEFT JOIN model.link l1 on e.id = l1.domain_id
        LEFT JOIN model.link l2 on e.id = l2.range_id
        LEFT JOIN model.link_property lp2 on e.id = lp2.range_id
        WHERE
            l1.domain_id IS NULL
            AND l2.range_id IS NULL
            AND lp2.range_id IS NULL
            AND e.class_code IN ('E61', 'E41', 'E53', 'E82'));

-- Re-enable triggers
ALTER TABLE model.entity ENABLE TRIGGER on_delete_entity;
ALTER TABLE model.link_property ENABLE TRIGGER on_delete_link_property;

COMMIT;
