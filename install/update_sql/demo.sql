SET session_replication_role = replica;

DELETE FROM model.entity WHERE id IN (
    SELECT entity_id FROM web.user_log
        WHERE action = 'insert'
        AND class_code IN ('E33', 'E6', 'E7', 'E8', 'E12', 'E21', 'E40', 'E74', 'E18', 'E31', 'E84')
        AND user_id NOT IN (21, 16));

SET session_replication_role = DEFAULT;
