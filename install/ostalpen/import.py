import os
import subprocess
import sys
import time
import copy

import psycopg2.extras

sys.path.append(os.path.dirname(os.path.realpath(__file__)))


"""
To do:

- split case studies?

Places:

- check links to from missing (Stefan mail)
- dates (Stefan tries to clean up ostalpen dates)
- types (Alex)

- links to sources
- other links
 
- types

Clean up:
- if subunit has same gis as above delete gis of subunit
- links between subunits have sometimes description texts which are not visible in new system (e.g. postion of find)

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

# Add subunit types
sql = """
INSERT INTO entity (class_code, name, description) VALUES ('E55', 'Bibliography', 'Categories for bibliographical entries as used for example in BibTeX, e.g. Book, Inbook, Article etc.');
INSERT INTO entity (class_code, name) VALUES ('E55', 'Inbook'), ('E55', 'Article'), ('E55', 'Book');
INSERT INTO link (property_code, range_id, domain_id) VALUES
('P127', (SELECT id FROM entity WHERE name='Bibliography'), (SELECT id FROM entity WHERE name='Inbook')),
('P127', (SELECT id FROM entity WHERE name='Bibliography'), (SELECT id FROM entity WHERE name='Article')),
('P127', (SELECT id FROM entity WHERE name='Bibliography'), (SELECT id FROM entity WHERE name='Book'));"""



# Set counters
new_entities = {}
missing_classes = {}
count = {
    'Gis point': 0,
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
types_double = {}
cursor_dpp.execute("SELECT id, name FROM model.entity WHERE class_code = 'E55';")
for row in cursor_dpp.fetchall():
    if row.name in types:
        types_double[row.name] = row.id
    types[row.name] = row.id

# Get Ostalpen types
ostalpen_types = {}
ostalpen_types_double = {}
cursor_ostalpen.execute("SELECT uid, entity_name_uri FROM openatlas.tbl_entities WHERE classes_uid = 13;")
for row in cursor_ostalpen.fetchall():
    if row.entity_name_uri in ostalpen_types:
        ostalpen_types_double[row.uid] = row.entity_name_uri
    ostalpen_types[row.uid] = row.entity_name_uri

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
    elif e.class_code in ['E018', 'E053']:
        continue # place will be added later in script
    else:
        missing_classes[e.class_code] = e.class_code
        continue
    new_entities[e.ostalpen_id] = e

# Insert places
sql_ = """
    SELECT
        uid, entity_name_uri, entity_type, entity_description, start_time_abs, srid_epsg,
        end_time_abs, start_time_text, end_time_text, timestamp_creation, name_path,
        x_lon_easting, y_lat_northing
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
    e.srid_epsg = row.srid_epsg
    e.x = row.x_lon_easting
    e.y = row.y_lat_northing
    places.append(e)

for e in places:
    if not e.name:
        continue
    e.class_code = 'E18'
    e.system_type = 'place'
    object_id = insert_entity(e, with_case_study=True)
    new_entities[e.ostalpen_id] = e
    p = copy.copy(e)
    p.system_type = 'place location'
    p.class_code = 'E53'
    p.name = 'Location of ' + e.name
    location_id = insert_entity(p)
    link('P53', object_id, location_id)
    if e.srid_epsg == 32633 and e.x and e.y:
        sql = """
        INSERT INTO gis.point (name, entity_id, type, created, geom)
        VALUES ('', %(entity_id)s, 'centerpoint', %(created)s,(
            SELECT ST_SetSRID(ST_Transform(ST_GeomFromText('POINT({x} {y})',32633),4326),4326)
        ))""".format(x=e.x, y=e.y)
        cursor_dpp.execute(sql, {'entity_id': location_id, 'created': e.created})
        count['Gis point'] += 1
    count['E18 place'] += 1


# Insert features
sql_ = """
    SELECT
        uid, entity_name_uri, entity_type, entity_description, start_time_abs, srid_epsg,
        end_time_abs, start_time_text, end_time_text, timestamp_creation, name_path,
        x_lon_easting, y_lat_northing
    FROM openatlas.features;"""
cursor_ostalpen.execute(sql_)
features = []
for row in cursor_ostalpen.fetchall():
    e = Entity()
    e.created = row.timestamp_creation
    e.ostalpen_id = row.uid
    e.name = row.entity_name_uri
    e.description = row.entity_description
    e.start_time_text = row.start_time_text
    e.start_time_abs = row.start_time_abs
    e.srid_epsg = row.srid_epsg
    e.x = row.x_lon_easting
    e.y = row.y_lat_northing
    features.append(e)

for e in features:
    if not e.name:
        continue
    e.class_code = 'E18'
    e.system_type = 'feature'
    object_id = insert_entity(e, with_case_study=True)
    new_entities[e.ostalpen_id] = e
    p = copy.copy(e)
    p.system_type = 'place location'
    p.class_code = 'E53'
    p.name = 'Location of ' + p.name
    location_id = insert_entity(p)
    link('P53', object_id, location_id)
    if e.srid_epsg and e.x and e.y:
        sql = """
        INSERT INTO gis.point (name, entity_id, type, created, geom)
        VALUES ('', %(entity_id)s, 'centerpoint', %(created)s,(
            SELECT ST_SetSRID(ST_Transform(ST_GeomFromText('POINT({x} {y})',32633),4326),4326)
        ))""".format(x=e.x, y=e.y)
        cursor_dpp.execute(sql, {'entity_id': location_id, 'created': e.created})
        count['Gis point'] += 1
    count['E18 place'] += 1

# Insert stratigraphic units
sql_ = """
    SELECT
        uid, entity_name_uri, entity_type, entity_description, start_time_abs, srid_epsg,
        end_time_abs, start_time_text, end_time_text, timestamp_creation, name_path,
        x_lon_easting, y_lat_northing
    FROM openatlas.stratigraphical_units;"""
cursor_ostalpen.execute(sql_)
strati = []
for row in cursor_ostalpen.fetchall():
    e = Entity()
    e.created = row.timestamp_creation
    e.ostalpen_id = row.uid
    e.name = row.entity_name_uri
    e.description = row.entity_description
    e.start_time_text = row.start_time_text
    e.start_time_abs = row.start_time_abs
    e.srid_epsg = row.srid_epsg
    e.x = row.x_lon_easting
    e.y = row.y_lat_northing
    strati.append(e)

for e in strati:
    if not e.name:
        continue
    e.class_code = 'E18'
    e.system_type = 'stratigraphic_unit'
    object_id = insert_entity(e, with_case_study=True)
    new_entities[e.ostalpen_id] = e
    p = copy.copy(e)
    p.system_type = 'place location'
    p.class_code = 'E53'
    p.name = 'Location of ' + e.name
    location_id = insert_entity(e)
    link('P53', object_id, location_id)
    if e.srid_epsg and e.x and e.y:
        sql = """
        INSERT INTO gis.point (name, entity_id, type, created, geom)
        VALUES ('', %(entity_id)s, 'centerpoint', %(created)s,(
            SELECT ST_SetSRID(ST_Transform(ST_GeomFromText('POINT({x} {y})',32633),4326),4326)
        ))""".format(x=e.x, y=e.y)
        cursor_dpp.execute(sql, {'entity_id': location_id, 'created': e.created})
        count['Gis point'] += 1
    count['E18 place'] += 1


# Insert finds
sql_ = """
    SELECT
        uid, entity_name_uri, entity_type, entity_description, start_time_abs, srid_epsg,
        end_time_abs, start_time_text, end_time_text, timestamp_creation, name_path,
        x_lon_easting, y_lat_northing
    FROM openatlas.finds;"""
cursor_ostalpen.execute(sql_)
finds = []
for row in cursor_ostalpen.fetchall():
    e = Entity()
    e.created = row.timestamp_creation
    e.ostalpen_id = row.uid
    e.name = row.entity_name_uri
    e.description = row.entity_description
    e.start_time_text = row.start_time_text
    e.start_time_abs = row.start_time_abs
    e.srid_epsg = row.srid_epsg
    e.x = row.x_lon_easting
    e.y = row.y_lat_northing
    finds.append(e)

for e in finds:
    if not e.name:
        continue
    e.class_code = 'E22'
    e.system_type = 'find'
    object_id = insert_entity(e, with_case_study=True)
    new_entities[e.ostalpen_id] = e
    p = copy.copy(e)
    p.system_type = 'place location'
    p.class_code = 'E53'
    p.name = 'Location of ' + e.name
    location_id = insert_entity(p)
    link('P53', object_id, location_id)
    if e.srid_epsg and e.x and e.y:
        sql = """
        INSERT INTO gis.point (name, entity_id, type, created, geom)
        VALUES ('', %(entity_id)s, 'centerpoint', %(created)s,(
            SELECT ST_SetSRID(ST_Transform(ST_GeomFromText('POINT({x} {y})',32633),4326),4326)
        ))""".format(x=e.x, y=e.y)
        cursor_dpp.execute(sql, {'entity_id': location_id, 'created': e.created})
        count['Gis point'] += 1
    count['E18 place'] += 1


# Get links in DPP
missing_properties = set()
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
        # Todo: remove when all entities
        if row.links_entity_uid_to not in new_entities or \
                row.links_entity_uid_from not in new_entities:
                    # print('Missing source link for: ' + str(row.links_entity_uid_from))
                    continue
        domain = new_entities[row.links_entity_uid_to]
        range_ = new_entities[row.links_entity_uid_from]
        link('P67', domain.id, range_.id ,row.links_annotation)
        count['link'] += 1
    elif row.links_cidoc_number_direction == 11:  # subunits
        if row.links_entity_uid_to not in new_entities:
            # print('Missing subunit for a link (11, to) for: ' + str(row.links_entity_uid_to))
            continue
        if row.links_entity_uid_from not in new_entities:
            # print('Missing subunit for a link (11, from) for: ' + str(row.links_entity_uid_from))
            continue
        domain = new_entities[row.links_entity_uid_to]
        range_ = new_entities[row.links_entity_uid_from]
        link('P46', range_.id, domain.id, row.links_annotation)
    elif row.links_cidoc_number_direction == 1:  # types
        if row.links_entity_uid_to not in ostalpen_types:
            print('Invalid type link to : ' + str(row.links_entity_uid_to))
            continue
        type_name = ostalpen_types[row.links_entity_uid_to]
        if row.links_entity_uid_to in ostalpen_types_double:
            print('Double Ostalpen type: ' + type_name)
            continue
        if type_name in types_double:
            print('Use of DPP double type: ' + type_name)
            continue
        if type_name not in types:
            print('Missing DPP type: ' + type_name)
            continue
        if row.links_entity_uid_from not in new_entities:
            print('Missing entity for type with Ostalpen ID: ' + str(row.links_entity_uid_from))
            continue
        domain = new_entities[row.links_entity_uid_from]
        link('P2', domain.id, types[type_name])
        count['link'] += 1
    else:
        missing_properties.add(row.links_cidoc_number_direction)

for name, count in count.items():
    print(str(name) + ': ' + str(count))

print('Missing classes:' + ', '.join(missing_classes))
print('Missing property ids:')
print(missing_properties)
connection_dpp.close()
connection_ostalpen.close()
print('Execution time: ' + str(int(time.time() - start)) + ' seconds')
