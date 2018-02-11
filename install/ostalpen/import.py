import subprocess
import time

import psycopg2.extras

"""
To do:
- create a field and save old id
- keep insert timestamp
- track user_id
- add case study type
"""

start = time.time()
db_pass = open('../../instance/password.txt').read().splitlines()[0]

# make a fresh database
subprocess.call('dropdb openatlas_dpp', shell=True)
subprocess.call('createdb openatlas_dpp -O openatlas', shell=True)
subprocess.call('psql openatlas_dpp < ../../instance/dpp_origin.sql', shell=True)


def connect(database_name):
    try:
        connection_ = psycopg2.connect(database=database_name, user='openatlas', password=db_pass)
        connection_.autocommit = True
        return connection_
    except Exception as e:  # pragma: no cover
        print(database_name + " connection error.")
        raise Exception(e)


connection_dpp = connect('openatlas_dpp')
connection_ostalpen = connect('ostalpen')
cursor_dpp = connection_dpp.cursor(cursor_factory=psycopg2.extras.NamedTupleCursor)
cursor_ostalpen = connection_ostalpen.cursor(cursor_factory=psycopg2.extras.NamedTupleCursor)


def insert_entity(entity_):
    sql = """
        INSERT INTO model.entity (name, description, class_code, system_type)
        VALUES (%(name)s, %(description)s, %(class_code)s, %(system_type)s) RETURNING id"""
    cursor_dpp.execute(sql, {
        'name': entity_['name'],
        'description': entity_['description'],
        'class_code': entity_['class_code'],
        'system_type': entity_['system_type']})
    entity['id'] = cursor_dpp.fetchone()[0]


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
        end_time_abs, start_time_text, end_time_text
    FROM openatlas.tbl_entities e
    JOIN openatlas.tbl_classes c ON e.classes_uid = c.tbl_classes_uid;"""
cursor_ostalpen.execute(sql_)

for row in cursor_ostalpen.fetchall():
    entities.append({
        'system_type': None,
        'old_id': row.uid,
        'name': row.entity_name_uri,
        'description': row.entity_description,
        'class_code': row.cidoc_class_nr})

for entity in entities:
    if not entity['name']:
        continue
    if entity['class_code'] == 'E021':
        entity['class_code'] = 'E21'
        insert_entity(entity)
        count['E21 Person'] += 1
    elif entity['class_code'] == 'E033':
        entity['class_code'] = 'E33'
        entity['system_type'] = 'source content'
        insert_entity(entity)
        count['E33 Document'] += 1
    elif entity['class_code'] == 'E074':
        entity['class_code'] = 'E74'
        insert_entity(entity)
        count['E74 Group'] += 1
    elif entity['class_code'] == 'E008':
        entity['class_code'] = 'E8'
        insert_entity(entity)
        count['E8 Acquisition'] += 1
    else:
        missing_classes[entity['class_code']] = entity['class_code']

for name, count in count.items():
    print('New ' + name + ': ' + str(count))

print('Missing classes:' + ', '.join(missing_classes))
connection_dpp.close()
connection_ostalpen.close()
print('Execution time: ' + str(int(time.time() - start)) + ' seconds')
