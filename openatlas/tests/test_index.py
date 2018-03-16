from flask import url_for

from openatlas import app
from openatlas.test_base import TestBaseCase


class IndexTests(TestBaseCase):

    def test_index(self):
        with app.app_context():
            rv = self.app.get('/')
            assert b'Overview' in rv.data
            rv = self.app.get('/some_missing_site')
            assert b'404' in rv.data
            rv = self.app.get(url_for('index_changelog'))
            assert b'2.0.0' in rv.data
            rv = self.app.get(url_for('index_contact'))
            assert b'Contact' in rv.data
            rv = self.app.get(url_for('index_credits'))
            assert b'Stefan Eichert' in rv.data
            self.app.get(url_for('set_locale', language='en'))
            rv = self.app.get(url_for('login'))
            assert b'Password' in rv.data
            rv = self.app.post(url_for('login'), data={'username': 'Never', 'password': 'wrong'})
            assert b'No user with this name found' in rv.data
            rv = self.app.post(url_for('login'), data={'username': 'Alice', 'password': 'wrong'})
            assert b'Wrong Password' in rv.data
            rv = self.app.post(url_for('login'), data={'username': 'inactive', 'password': 'test'})
            assert b'This user is not activated' in rv.data
            for i in range(4):
                rv = self.app.post(url_for('login'), data={'username': 'inactive', 'password': '?'})
            assert b'Too many login attempts' in rv.data
            self.login()
            rv = self.app.get('/')
            assert b'0' in rv.data
            rv = self.app.get(url_for('index_feedback'))
            assert b'Thank you' in rv.data

            # test reset password, unsubscribe
            rv = self.app.get(url_for('reset_password'))
            assert b'Forgot your password?' in rv.data
            rv = self.app.get(url_for('reset_confirm', code='1234'))
            assert b'404' in rv.data
            rv = self.app.get(url_for('index_unsubscribe', code='1234'))
            assert b'invalid' in rv.data

            # test redirection to overview if trying to login again
            rv = self.app.get(url_for('login'), follow_redirects=True)
            assert b'first' in rv.data
            rv = self.app.get(url_for('set_locale', language='de'), follow_redirects=True)
            assert b'Quelle' in rv.data
            rv = self.app.get(url_for('logout'), follow_redirects=True)
            assert b'Password' in rv.data
            rv = self.app.get('/404')
            assert b'not found' in rv.data

            # raise an id not found error
            self.login()
            rv = self.app.get('/actor/view/666', follow_redirects=True)
            assert b'teapot' in rv.data
