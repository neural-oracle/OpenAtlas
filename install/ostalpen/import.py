import subprocess
import time

import psycopg2.extras

"""
To do:
- user_id, will be Ostalpen user id
- add type case study - eastern alps

After gis implementation:
- split case studies
"""

start = time.time()
db_pass = open('../../instance/password.txt').read().splitlines()[0]

# make a fresh database
subprocess.call('dropdb openatlas_dpp', shell=True)
subprocess.call('createdb openatlas_dpp -O openatlas', shell=True)
subprocess.call('psql openatlas_dpp < ../../instance/dpp_origin.sql', shell=True)


def connect(database_name):
    connection = psycopg2.connect(database=database_name, user='openatlas', password=db_pass)
    connection.autocommit = True
    return connection


connection_dpp = connect('openatlas_dpp')
connection_ostalpen = connect('ostalpen')
cursor_dpp = connection_dpp.cursor(cursor_factory=psycopg2.extras.NamedTupleCursor)
cursor_ostalpen = connection_ostalpen.cursor(cursor_factory=psycopg2.extras.NamedTupleCursor)


class Entity:
    system_type = None


def insert_entity(entity):
    sql = """
        INSERT INTO model.entity (name, description, class_code, system_type, ostalpen_id, created)
        VALUES (%(name)s, %(description)s, %(class_code)s, %(system_type)s, %(ostalpen_id)s,
            %(created)s)
        RETURNING id"""
    cursor_dpp.execute(sql, {
        'name': entity.name,
        'ostalpen_id': entity.ostalpen_id,
        'description': entity.description,
        'class_code': entity.class_code,
        'created': entity.created,
        'system_type': entity.system_type})
    entity.id = cursor_dpp.fetchone()[0]


sql = """
    ALTER TABLE model.entity ADD COLUMN ostalpen_id integer;
    COMMENT ON COLUMN model.entity.ostalpen_id IS 'uid of former Ostalpen table tbl_entities';"""

cursor_dpp.execute(sql)

entities = []
missing_classes = {}
count = {
    'E21 Person': 0,
    'E33 Document': 0,
    'E74 Group': 0,
    'E8 Acquisition': 0,
    'Link': 0}
sql_ = """
    SELECT
        uid, entity_name_uri, cidoc_class_nr, entity_type, entity_description, start_time_abs,
        end_time_abs, start_time_text, end_time_text, timestamp_creation
    FROM openatlas.tbl_entities e
    JOIN openatlas.tbl_classes c ON e.classes_uid = c.tbl_classes_uid;"""
cursor_ostalpen.execute(sql_)

for row in cursor_ostalpen.fetchall():
    e = Entity()
    e.created = row.timestamp_creation
    e.ostalpen_id = row.uid
    e.name = row.entity_name_uri
    e.description = row.entity_description
    e.class_code = row.cidoc_class_nr
    entities.append(e)

for e in entities:
    if not e.name:
        continue
    if e.class_code == 'E021':
        e.class_code = 'E21'
        insert_entity(e)
        count['E21 Person'] += 1
    elif e.class_code == 'E033':
        e.class_code = 'E33'
        e.system_type = 'source content'
        insert_entity(e)
        count['E33 Document'] += 1
    elif e.class_code == 'E074':
        e.class_code = 'E74'
        insert_entity(e)
        count['E74 Group'] += 1
    elif e.class_code == 'E008':
        e.class_code = 'E8'
        insert_entity(e)
        count['E8 Acquisition'] += 1
    else:
        missing_classes[e.class_code] = e.class_code

for name, count in count.items():
    print('New ' + name + ': ' + str(count))

print('Missing classes:' + ', '.join(missing_classes))
connection_dpp.close()
connection_ostalpen.close()
print('Execution time: ' + str(int(time.time() - start)) + ' seconds')
