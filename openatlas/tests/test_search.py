# Copyright 2017 by Alexander Watzinger and others. Please see README.md for licensing information
from flask import url_for

from openatlas import app, EntityMapper
from openatlas.test_base import TestBaseCase


class SearchTest(TestBaseCase):

    def test_search(self):
        self.login()
        EntityMapper.insert('E21', 'Waldo')
        with app.app_context():
            rv = self.app.post(url_for('index_search'), data={'terminus': 'wal'})
            assert b'Waldo' in rv.data
            data = {'term': 'do', 'classes': 'actor'}
            rv = self.app.post(url_for('index_search'), data=data)
            assert b'Waldo' in rv.data
