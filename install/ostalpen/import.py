import subprocess
import time

import psycopg2.extras

"""
To do:

- remove hardcoded ids for types eg: 37 with type id from "Original text"
- add type case study - eastern alps
- add source links to actors, places, ... (add documented in)
- check if sources have dates

After gis implementation:
- split case studies

At the end:
- compare links created with links existing
"""

start = time.time()
db_pass = open('instance/password.txt').read().splitlines()[0]

ostalpen_user_id = 38
ostalpen_type_id = 11821

# make a fresh database
subprocess.call('dropdb openatlas_dpp', shell=True)
subprocess.call('createdb openatlas_dpp -O openatlas', shell=True)
subprocess.call('psql openatlas_dpp < instance/dpp_origin.sql', shell=True)


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


def link(property_code, domain_id, range_id, description=None):
    sql = """
        INSERT INTO model.link (property_code, domain_id, range_id, description)
        VALUES (
            %(property_code)s,
            %(domain_id)s,
            %(range_id)s,
            %(description)s)
        RETURNING id;"""
    cursor_dpp.execute(sql, {
        'property_code': property_code,
        'domain_id': domain_id,
        'range_id': range_id,
        'description': description})
    count['link'] += 1
    return cursor_dpp.fetchone()[0]


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
        INSERT INTO web.user_log (user_id, action, entity_id, created)
        VALUES (38, 'insert', %(entity_id)s, %(created)s);"""
    cursor_dpp.execute(sql, {'entity_id': entity.id, 'created': entity.created})


sql_ = """
    ALTER TABLE model.entity ADD COLUMN ostalpen_id integer;
    COMMENT ON COLUMN model.entity.ostalpen_id IS 'uid of former Ostalpen table tbl_entities';"""

cursor_dpp.execute(sql_)

entities = []
new_entities = {}
missing_classes = {}
count = {
    'E21 person': 0,
    'E33 source': 0,
    'E33 translation': 0,
    'E33 original text': 0,
    'E74 group': 0,
    'E8 acquisition': 0,
    'link': 0}
sql_ = """
    SELECT
        uid, entity_name_uri, cidoc_class_nr, entity_type, entity_description, start_time_abs,
        end_time_abs, start_time_text, end_time_text, timestamp_creation, entity_id
    FROM openatlas.tbl_entities e
    JOIN openatlas.tbl_classes c ON e.classes_uid = c.tbl_classes_uid;"""
cursor_ostalpen.execute(sql_)

for row in cursor_ostalpen.fetchall():
    e = Entity()
    e.created = row.timestamp_creation
    e.id_name = row.entity_id
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
        count['E21 person'] += 1
    elif e.class_code == 'E033':
        if e.id_name.startswith('tbl_2_quelle_original'):
            e.system_type = 'source translation'
            count['E33 translation'] += 1
        elif e.id_name.startswith('tbl_2_quelle_uebersetzung'):
            e.system_type = 'source translation'
            count['E33 original text'] += 1
        else:
            e.system_type = 'source content'
            count['E33 source'] += 1
        e.class_code = 'E33'
        insert_entity(e)

    elif e.class_code == 'E074':
        e.class_code = 'E74'
        insert_entity(e)
        count['E74 group'] += 1
    elif e.class_code == 'E008':
        e.class_code = 'E8'
        insert_entity(e)
        count['E8 acquisition'] += 1
    else:
        missing_classes[e.class_code] = e.class_code
        continue
    new_entities[e.ostalpen_id] = e

sql_ = """
    SELECT links_uid, links_entity_uid_from, links_cidoc_number_direction, links_entity_uid_to,
        links_annotation, links_creator, links_timestamp_start, links_timestamp_end,
        links_timestamp_creation, links_timespan
    FROM openatlas.tbl_links;"""

cursor_ostalpen.execute(sql_)

for row in cursor_ostalpen.fetchall():
    if row.links_cidoc_number_direction == 33:  # has translation
        domain = new_entities[row.links_entity_uid_from]
        range_ = new_entities[row.links_entity_uid_to]
        if domain.id_name.startswith('tbl_2_quelle_original'):
            link('P73', range_.id, domain.id, row.links_annotation)
            link('P2', domain.id, 37)
            count['link'] += 2
        elif domain.id_name.startswith('tbl_2_quelle_uebersetzung'):
            link('P73', range_.id, domain.id, row.links_annotation)
            link('P2', domain.id, 38)
            count['link'] += 2
        else:
            print('Error missing translation type, id: ' + str(domain.id) + ', ' + domain.id_name)

for name, count in count.items():
    print(name + ': ' + str(count))

print('Missing classes:' + ', '.join(missing_classes))
connection_dpp.close()
connection_ostalpen.close()
print('Execution time: ' + str(int(time.time() - start)) + ' seconds')
