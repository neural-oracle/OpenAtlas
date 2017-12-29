-- delete orphaned data which breaks application
DELETE FROM model.entity WHERE id in (1043);

-- delete BC dates until issue is solved
DELETE FROM model.entity WHERE value_timestamp < '0001-01-01';
