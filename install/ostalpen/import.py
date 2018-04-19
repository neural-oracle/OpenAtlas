import os
import subprocess
import sys
import time

import psycopg2.extras

sys.path.append(os.path.dirname(os.path.realpath(__file__)))


"""
To do:

Places:
 - geom
 - links to sources
 - other links
 - feature, su, ...
 - dates,
 - types

After gis implementation:
- split case studies

"""


class Entity:
    system_type = None


def connect(database_name):
    db_pass = open('instance/password.txt').read().splitlines()[0]
    connection = psycopg2.connect(database=database_name, user='openatlas', password=db_pass)
    connection.autocommit = True
    return connection


def reset_database():
    subprocess.call('dropdb openatlas_dpp', shell=True)
    subprocess.call('createdb openatlas_dpp -O openatlas', shell=True)
    subprocess.call('psql openatlas_dpp < instance/dpp_origin.sql', shell=True)


start = time.time()
ostalpen_user_id = 38
ostalpen_type_id = 11821
reset_database()
connection_dpp = connect('openatlas_dpp')
connection_ostalpen = connect('ostalpen')
cursor_dpp = connection_dpp.cursor(cursor_factory=psycopg2.extras.NamedTupleCursor)
cursor_ostalpen = connection_ostalpen.cursor(cursor_factory=psycopg2.extras.NamedTupleCursor)


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


def insert_entity(entity, with_case_study=False):
    sql = """
        INSERT INTO model.entity (name, description, class_code, system_type, ostalpen_id, created)
        VALUES (%(name)s, %(description)s, %(class_code)s, %(system_type)s, %(ostalpen_id)s,
            %(created)s)
        RETURNING id"""
    description = entity.description
    dates_comment = None
    if e.class_code == 'E33':
        if e.start_time_text:
            dates_comment = e.start_time_text
        if e.start_time_abs:
            dates_comment += ' ' + str(e.start_time_abs)
        if description and dates_comment:
            description = dates_comment + ': ' + description
        elif dates_comment:
            description = dates_comment

    cursor_dpp.execute(sql, {
        'name': entity.name,
        'ostalpen_id': entity.ostalpen_id,
        'description': description,
        'class_code': entity.class_code,
        'created': entity.created,
        'system_type': entity.system_type})
    entity.id = cursor_dpp.fetchone()[0]
    sql = """
        INSERT INTO web.user_log (user_id, action, entity_id, created)
        VALUES (%(ostalpen_user_id)s, 'insert', %(entity_id)s, %(created)s);"""
    cursor_dpp.execute(sql, {
        'ostalpen_user_id': ostalpen_user_id, 'entity_id': entity.id, 'created': entity.created})
    if with_case_study:
        sql = """
            INSERT INTO model.link (property_code, domain_id, range_id)
            VALUES (%(property_code)s, %(domain_id)s, %(range_id)s);"""
        cursor_dpp.execute(sql, {
            'property_code': 'P2', 'domain_id': entity.id, 'range_id': ostalpen_type_id})
    return entity.id


# Add comment to ostalpen_id
sql_ = """
    ALTER TABLE model.entity ADD COLUMN ostalpen_id integer;
    COMMENT ON COLUMN model.entity.ostalpen_id IS 'uid of former Ostalpen table tbl_entities';"""
cursor_dpp.execute(sql_)

# Set counters
new_entities = {}
missing_classes = {}
count = {
    'E21 person': 0,
    'E18 place': 0,
    'E33 source': 0,
    'E33 translation': 0,
    'E33 original text': 0,
    'E74 group': 0,
    'E8 acquisition': 0,
    'link': 0}

# Get DPP types
types = {}
cursor_dpp.execute("SELECT id, name FROM model.entity WHERE class_code = 'E55';")
for row in cursor_dpp.fetchall():
    if row.name in types:
        print('Warning - double type entry for: ' + row.name)
    types[row.name] = row.id

# Get ostalpen entities
sql_ = """
    SELECT
        uid, entity_name_uri, cidoc_class_nr, entity_type, entity_description, start_time_abs,
        end_time_abs, start_time_text, end_time_text, timestamp_creation, entity_id
    FROM openatlas.tbl_entities e
    JOIN openatlas.tbl_classes c ON e.classes_uid = c.tbl_classes_uid;"""
cursor_ostalpen.execute(sql_)
entities = []
for row in cursor_ostalpen.fetchall():
    e = Entity()
    e.created = row.timestamp_creation
    e.id_name = row.entity_id
    e.ostalpen_id = row.uid
    e.name = row.entity_name_uri
    e.description = row.entity_description
    e.class_code = row.cidoc_class_nr
    e.start_time_text = row.start_time_text
    e.start_time_abs = row.start_time_abs
    entities.append(e)

# Insert entities in DPP
for e in entities:
    if not e.name:
        continue
    if e.class_code == 'E021':  # Person
        e.class_code = 'E21'
        insert_entity(e, with_case_study=True)
        count['E21 person'] += 1
    elif e.class_code == 'E033':  # Linguistic Object (Source)
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
        insert_entity(e, with_case_study=True if e.system_type == 'source content' else False)
    elif e.class_code == 'E074':  # Group
        e.class_code = 'E74'
        insert_entity(e, with_case_study=True)
        count['E74 group'] += 1
    elif e.class_code == 'E008':  # Acquisition
        e.class_code = 'E8'
        insert_entity(e, with_case_study=True)
        count['E8 acquisition'] += 1
    elif e.class_code in ['E18', 'E53']:
        continue # place will be added later
    else:
        missing_classes[e.class_code] = e.class_code
        continue
    new_entities[e.ostalpen_id] = e

# Insert places

sql_ = """
    SELECT
        uid, entity_name_uri, entity_type, entity_description, start_time_abs,
        end_time_abs, start_time_text, end_time_text, timestamp_creation, name_path
    FROM openatlas.sites;"""
cursor_ostalpen.execute(sql_)
places = []
for row in cursor_ostalpen.fetchall():
    e = Entity()
    e.created = row.timestamp_creation
    e.ostalpen_id = row.uid
    e.name = row.entity_name_uri
    e.description = row.entity_description
    e.start_time_text = row.start_time_text
    e.start_time_abs = row.start_time_abs
    places.append(e)

for e in places:
    if not e.name:
        continue
    # split place, features ...
    e.class_code = 'E18'
    e.system_type = 'place'
    object_id = insert_entity(e, with_case_study=True)
    e.system_type = 'place location'
    e.class_code = 'E53'
    e.name = 'Location of ' + e.name
    location_id = insert_entity(e)
    link('P53', object_id, location_id)


    """
    SELECT ST_AsText(
    
      ST_Transform(
        ST_GeomFromText('POINT(646274.7681 5429433.0725)',32633),4326)
      
    
    ) AS whatever FROM openatlas.sites WHERE srid_epsg = 32633;"""



    count['E18 place'] += 1


# Get links in DPP
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
            link('P2', domain.id, types['Original text'])
            count['link'] += 2
        elif domain.id_name.startswith('tbl_2_quelle_uebersetzung'):
            link('P73', range_.id, domain.id, row.links_annotation)
            link('P2', domain.id, types['Translation'])
            count['link'] += 2
        else:
            print('Error missing translation type, id: ' + str(domain.id) + ', ' + domain.id_name)
    elif row.links_cidoc_number_direction == 4:  # documents
        # Todo: remove when all entites
        if row.links_entity_uid_to not in new_entities or \
                row.links_entity_uid_from not in new_entities:
                    continue
        count['link'] += 1
        domain = new_entities[row.links_entity_uid_to]
        range_ = new_entities[row.links_entity_uid_from]
        link('P67', domain.id, range_.id ,row.links_annotation)

for name, count in count.items():
    print(name + ': ' + str(count))

print('Missing classes:' + ', '.join(missing_classes))
connection_dpp.close()
connection_ostalpen.close()
print('Execution time: ' + str(int(time.time() - start)) + ' seconds')
