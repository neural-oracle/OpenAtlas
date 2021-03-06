# Created by Alexander Watzinger and others. Please see README.md for licensing information
from collections import OrderedDict

from flask import g
from flask_login import current_user
from werkzeug.exceptions import abort

from openatlas import app, debug_model, logger
from openatlas.models.date import DateMapper
from openatlas.models.link import LinkMapper
from openatlas.util.util import get_view_name, uc_first


class Entity:
    def __init__(self, row):
        if not row:
            logger.log('error', 'model', 'invalid id')
            abort(418)
        self.id = row.id
        self.nodes = dict()
        if hasattr(row, 'types') and row.types:
            for node in row.types:
                if not node['f1']:
                    continue
                self.nodes[g.nodes[node['f1']]] = node['f2']
        self.name = row.name
        self.root = None
        self.description = row.description if row.description else ''
        self.system_type = row.system_type
        self.created = row.created
        self.modified = row.modified
        self.first = int(row.first) if hasattr(row, 'first') and row.first else None
        self.last = int(row.last) if hasattr(row, 'last') and row.last else None
        self.class_ = g.classes[row.class_code]
        self.dates = {}

    def get_linked_entity(self, code, inverse=False):
        return LinkMapper.get_linked_entity(self, code, inverse)

    def get_linked_entities(self, code, inverse=False):
        return LinkMapper.get_linked_entities(self, code, inverse)

    def link(self, code, range_, description=None):
        return LinkMapper.insert(self, code, range_, description)

    def get_links(self, code, inverse=False):
        return LinkMapper.get_links(self, code, inverse)

    def delete(self):
        EntityMapper.delete(self.id)

    def delete_links(self, codes):
        LinkMapper.delete_by_codes(self, codes)

    def update(self):
        EntityMapper.update(self)

    def save_dates(self, form):
        DateMapper.save_dates(self, form)

    def save_nodes(self, form):
        from openatlas.models.node import NodeMapper
        NodeMapper.save_entity_nodes(self, form)

    def set_dates(self):
        self.dates = DateMapper.get_dates(self)

    def print_base_type(self):
        from openatlas.models.node import NodeMapper
        view_name = get_view_name(self)
        if not view_name or view_name == 'actor':  # actors have no base type
            return ''
        root_name = view_name.title()
        if view_name == 'reference':
            root_name = self.system_type.title()
        elif view_name == 'file':
            root_name = 'License'
        elif view_name == 'place':
            root_name = uc_first(self.system_type)
            if self.system_type == 'stratigraphic unit':
                root_name = 'Stratigraphic Unit'
        root_id = NodeMapper.get_hierarchy_by_name(root_name).id
        for node in self.nodes:
            if node.root and node.root[-1] == root_id:
                return node.name
        return ''

    def get_name_directed(self, inverse=False):
        """ Returns name part of a directed type e.g. Actor Actor Relation: Parent of (Child of)"""
        from openatlas.util.util import sanitize
        name_parts = self.name.split(' (')
        if inverse and len(name_parts) > 1:  # pragma: no cover
            return sanitize(name_parts[1], 'node')
        return name_parts[0]


class EntityMapper:
    sql = """
        SELECT
            e.id, e.class_code, e.name, e.description, e.created, e.modified,
            e.value_integer, e.system_type,
            array_to_json(array_agg((t.range_id, t.description))) as types,
            min(date_part('year', d1.value_timestamp)) AS first,
            max(date_part('year', d2.value_timestamp)) AS last

        FROM model.entity e
        LEFT JOIN model.link t ON e.id = t.domain_id AND t.property_code IN ('P2', 'P89')

        LEFT JOIN model.link dl1 ON e.id = dl1.domain_id
            AND dl1.property_code IN ('OA1', 'OA3', 'OA5')
        LEFT JOIN model.entity d1 ON dl1.range_id = d1.id

        LEFT JOIN model.link dl2 ON e.id = dl2.domain_id
            AND dl2.property_code IN ('OA2', 'OA4', 'OA6')
        LEFT JOIN model.entity d2 ON dl2.range_id = d2.id"""

    sql_orphan = """
        SELECT e.id FROM model.entity e
        LEFT JOIN model.link l1 on e.id = l1.domain_id
        LEFT JOIN model.link l2 on e.id = l2.range_id
        LEFT JOIN model.link_property lp2 on e.id = lp2.range_id
        WHERE
            l1.domain_id IS NULL
            AND l2.range_id IS NULL
            AND lp2.range_id IS NULL
            AND e.class_code != 'E55'"""

    @staticmethod
    def update(entity):
        from openatlas.util.util import sanitize
        sql = """
            UPDATE model.entity SET (name, description) = (%(name)s, %(description)s)
            WHERE id = %(id)s;"""
        g.cursor.execute(sql, {
            'id': entity.id,
            'name': entity.name,
            'description': sanitize(entity.description, 'description')})

    @staticmethod
    def get_by_system_type(system_type):
        sql = EntityMapper.sql
        sql += ' WHERE e.system_type = %(system_type)s GROUP BY e.id ORDER BY e.name;'
        g.cursor.execute(sql, {'system_type': system_type})
        entities = []
        for row in g.cursor.fetchall():
            entities.append(Entity(row))
        return entities

    @staticmethod
    def insert(code, name, system_type=None, description=None, date=None):
        if not name and not date:  # pragma: no cover
            logger.log('error', 'database', 'Insert entity without name and date')
            return  # Something went wrong so don't insert
        sql = """
            INSERT INTO model.entity (name, system_type, class_code, description, value_timestamp)
            VALUES (%(name)s, %(system_type)s, %(code)s, %(description)s, %(value_timestamp)s)
            RETURNING id;"""
        params = {
            'name': str(date) if date else name.strip(),
            'code': code,
            'system_type': system_type.strip() if system_type else None,
            'description': description.strip() if description else None,
            'value_timestamp':  DateMapper.datetime64_to_timestamp(date) if date else None}
        g.cursor.execute(sql, params)
        return EntityMapper.get_by_id(g.cursor.fetchone()[0])

    @staticmethod
    def get_by_id(entity_id, ignore_not_found=False):
        sql = EntityMapper.sql + ' WHERE e.id = %(id)s GROUP BY e.id ORDER BY e.name;'
        g.cursor.execute(sql, {'id': entity_id})
        debug_model['by id'] += 1
        if g.cursor.rowcount < 1 and ignore_not_found:
            return None  # pragma: no cover, only used where expected to avoid a 418 e.g. at logs
        return Entity(g.cursor.fetchone())

    @staticmethod
    def get_by_ids(entity_ids):
        if not entity_ids:
            return []
        sql = EntityMapper.sql + ' WHERE e.id IN %(ids)s GROUP BY e.id ORDER BY e.name;'
        g.cursor.execute(sql, {'ids': tuple(entity_ids)})
        debug_model['by id'] += 1
        entities = []
        for row in g.cursor.fetchall():
            entities.append(Entity(row))
        return entities

    @staticmethod
    def get_by_codes(class_name):
        if class_name == 'source':
            sql = EntityMapper.sql + """
                WHERE e.class_code IN %(codes)s AND e.system_type = 'source content'
                GROUP BY e.id ORDER BY e.name;"""
        elif class_name == 'reference':
            sql = EntityMapper.sql + """
                WHERE e.class_code IN %(codes)s AND e.system_type != 'file'
                GROUP BY e.id ORDER BY e.name;"""
        else:
            sql = EntityMapper.sql + """
                WHERE e.class_code IN %(codes)s GROUP BY e.id ORDER BY e.name;"""
        g.cursor.execute(sql, {'codes': tuple(app.config['CLASS_CODES'][class_name])})
        debug_model['by codes'] += 1
        entities = []
        for row in g.cursor.fetchall():
            entities.append(Entity(row))
        return entities

    @staticmethod
    def delete(entity):
        """ Triggers function model.delete_entity_related() for deleting related entities"""
        entity_id = entity if isinstance(entity, int) else entity.id
        sql = "DELETE FROM model.entity WHERE id = %(entity_id)s;"
        g.cursor.execute(sql, {'entity_id': entity_id})

    @staticmethod
    def get_overview_counts():
        sql = """
            SELECT
            SUM(CASE WHEN
                class_code = 'E33' AND system_type = 'source content' THEN 1 END) AS source,
            SUM(CASE WHEN class_code IN ('E6', 'E7', 'E8', 'E12') THEN 1 END) AS event,
            SUM(CASE WHEN class_code IN ('E21', 'E74', 'E40') THEN 1 END) AS actor,
            SUM(CASE WHEN class_code = 'E18' THEN 1 END) AS place,
            SUM(CASE WHEN class_code IN ('E31', 'E84') THEN 1 END) AS reference
            FROM model.entity;"""
        g.cursor.execute(sql)
        row = g.cursor.fetchone()
        counts = OrderedDict()
        for idx, col in enumerate(g.cursor.description):
            counts[col[0]] = row[idx]
        return counts

    @staticmethod
    def get_orphans():
        """ Returns entities without links. """
        entities = []
        g.cursor.execute(EntityMapper.sql_orphan)
        debug_model['div sql'] += 1
        for row in g.cursor.fetchall():
            entities.append(EntityMapper.get_by_id(row.id))
        return entities

    @staticmethod
    def get_latest(limit):
        """ Returns the newest created entities"""
        codes = []
        for class_codes in app.config['CLASS_CODES'].values():
            codes += class_codes
        sql = EntityMapper.sql + """
                WHERE e.class_code IN %(codes)s
                GROUP BY e.id
                ORDER BY e.created DESC LIMIT %(limit)s;"""
        g.cursor.execute(sql, {'codes': tuple(codes), 'limit': limit})
        debug_model['div sql'] += 1
        entities = []
        for row in g.cursor.fetchall():
            entities.append(Entity(row))
        return entities

    @staticmethod
    def delete_orphans(parameter):
        from openatlas.models.node import NodeMapper
        class_codes = tuple(app.config['CODE_CLASS'].keys())
        if parameter == 'orphans':
            class_codes = class_codes + ('E55',)
            sql_where = EntityMapper.sql_orphan + " AND e.class_code NOT IN %(class_codes)s"
        elif parameter == 'unlinked':
            sql_where = EntityMapper.sql_orphan + " AND e.class_code IN %(class_codes)s"
        elif parameter == 'types':
            count = 0
            for node in NodeMapper.get_orphans():
                EntityMapper.delete(node)
                count += 1
            return count
        else:
            return 0
        sql = "DELETE FROM model.entity WHERE id IN (" + sql_where + ");"
        g.cursor.execute(sql, {'class_codes': class_codes})
        return g.cursor.rowcount

    @staticmethod
    def search(term, codes, description=False, own=False):
        sql = EntityMapper.sql
        if own:
            sql += " LEFT JOIN web.user_log ul ON e.id = ul.entity_id "
        sql += " WHERE LOWER(e.name) LIKE LOWER(%(term)s)"
        sql += " OR lower(e.description) LIKE lower(%(term)s) AND " if description else " AND "
        sql += " ul.user_id = %(user_id)s AND " if own else ''
        sql += " e.class_code IN %(codes)s"
        sql += " GROUP BY e.id ORDER BY e.name"
        g.cursor.execute(sql, {
            'term': '%' + term + '%',
            'codes': tuple(codes),
            'user_id': current_user.id})
        debug_model['div sql'] += 1
        entities = []
        for row in g.cursor.fetchall():
            if row.class_code == 'E82':  # If found in actor alias
                entities.append(LinkMapper.get_linked_entity(row.id, 'P131', True))
            elif row.class_code == 'E41':  # If found in place alias
                entities.append(LinkMapper.get_linked_entity(row.id, 'P1', True))
            else:
                entities.append(Entity(row))
        return entities
