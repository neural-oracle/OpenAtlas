ALTER TABLE model.entity DISABLE TRIGGER on_delete_entity;
ALTER TABLE model.link_property DISABLE TRIGGER on_delete_link_property;

DELETE FROM model.entity WHERE id IN (
    SELECT entity_id FROM web.user_log
        WHERE action = 'insert'
        AND class_code IN ('E33', 'E6', 'E7', 'E8', 'E12', 'E21', 'E40', 'E74', 'E18', 'E31', 'E84')
        AND user_id NOT IN (21, 16));

ALTER TABLE model.entity ENABLE TRIGGER on_delete_entity;
ALTER TABLE model.link_property ENABLE TRIGGER on_delete_link_property;
