from flask import url_for

from openatlas import app
from openatlas.models.entity import EntityMapper
from openatlas.models.link import LinkMapper
from openatlas.models.node import NodeMapper
from openatlas.test_base import TestBaseCase


class PlaceTest(TestBaseCase):

    def test_place(self):
        with app.app_context():
            self.login()
            rv = self.app.get(url_for('place_insert'))
            assert b'+ Place' in rv.data
            data = {'name': 'Asgard', 'alias-0': 'Valhöll'}
            with app.test_request_context():
                app.preprocess_request()
                reference_id = EntityMapper.insert('E84', 'Ancient Books', 'information carrier').id
                place_node = NodeMapper.get_hierarchy_by_name('Place')
                source_id = EntityMapper.insert('E33', 'Tha source').id
            rv = self.app.post(url_for('place_insert', origin_id=reference_id), data=data,
                               follow_redirects=True)
            assert b'Asgard' in rv.data
            gis_points = """[{"type":"Feature", "geometry":{"type":"Point", "coordinates":[9,17]},
                    "properties":{"name":"Valhalla","description":"","shapeType":"centerpoint"}}]"""
            data['gis_points'] = gis_points
            gis_polygons = """[{"geometry":{
                "coordinates":[[[9.75307425847859,17.8111792731339],
                [9.75315472474904,17.8110005175436],[9.75333711496205,17.8110873417098],
                [9.75307425847859,17.8111792731339]]],"type":"Polygon"},
                "properties":{"count":4,"description":"","id":8,"name":"",
                "objectDescription":"","objectId":185,"shapeType":"Shape",
                "siteType":"Settlement","title":""},"type":"Feature"}]"""
            data['gis_polygons'] = gis_polygons
            data[place_node.id] = place_node.subs
            data['continue_'] = 'yes'
            rv = self.app.post(
                url_for('place_insert', origin_id=source_id), data=data, follow_redirects=True)
            assert b'Tha source' in rv.data
            with app.test_request_context():
                app.preprocess_request()
                places = EntityMapper.get_by_codes('place')
                place_id = places[0].id
                second_place_id = places[1].id
                location = LinkMapper.get_linked_entity(second_place_id, 'P53')
                actor_id = EntityMapper.insert('E21', 'Milla Jovovich').id
                LinkMapper.insert(actor_id, 'P74', location.id)
            assert b'Tha source' in rv.data
            rv = self.app.get(url_for('place_index'))
            assert b'Asgard' in rv.data
            rv = self.app.get(url_for('place_update', id_=place_id))
            assert b'Valhalla' in rv.data
            data['continue_'] = ''
            data['alias-1'] = 'Val-hall'
            rv = self.app.post(
                url_for('place_update', id_=place_id), data=data, follow_redirects=True)
            assert b'Val-hall' in rv.data
            with app.test_request_context():
                app.preprocess_request()
                event = EntityMapper.insert('E8', 'Valhalla rising')
                event.link('P7', location)
                event.link('P24', location)
            rv = self.app.get(
                url_for(
                    'place_view', id_=second_place_id, unlink_id=place_id), follow_redirects=True)
            assert b'Link removed' in rv.data and b'Milla Jovovich' in rv.data

            # Subunits
            with app.app_context():
                self.app.get(url_for('place_insert', origin_id=place_id))
                name = "It's not a bug, it's a feature!"
                rv = self.app.post(url_for('place_insert', origin_id=place_id), data={'name': name})
                feat_id = rv.location.split('/')[-1]
                self.app.get(url_for('place_insert', origin_id=feat_id))
                self.app.get(url_for('place_update', id_=feat_id))
                self.app.post(url_for('place_update', id_=feat_id), data={'name': name})
                name = "I'm a stratigraphic unit"
                rv = self.app.post(url_for('place_insert', origin_id=feat_id), data={'name': name})
                strat_id = rv.location.split('/')[-1]
                self.app.get(url_for('place_insert', origin_id=strat_id))
                self.app.get(url_for('place_update', id_=strat_id))
                self.app.post(url_for('place_update', id_=strat_id), data={'name': name})
                name = "You never find me"
                rv = self.app.post(url_for('place_insert', origin_id=strat_id), data={'name': name})
                find_id = rv.location.split('/')[-1]
                self.app.get(url_for('place_update', id_=find_id))
                self.app.post(url_for('place_update', id_=find_id), data={'name': name})
            rv = self.app.get(url_for('place_view', id_=feat_id))
            assert b'not a bug' in rv.data
            rv = self.app.get(url_for('place_view', id_=strat_id))
            assert b'a stratigraphic unit' in rv.data
            rv = self.app.get(url_for('place_view', id_=find_id))
            assert b'You never' in rv.data
            rv = self.app.get(url_for('place_delete', id_=place_id), follow_redirects=True)
            assert b'not possible if subunits' in rv.data
            rv = self.app.get(url_for('place_delete', id_=find_id), follow_redirects=True)
            assert b'The entry has been deleted.' in rv.data
