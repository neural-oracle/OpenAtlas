# Created 2017 by Alexander Watzinger and others. Please see README.md for licensing information
import datetime
import random
import string

import bcrypt
from flask import g, session
from flask_babel import lazy_gettext as _
from flask_login import UserMixin

import openatlas


class User(UserMixin):
    def __init__(self, row=None, bookmarks=None):
        self.id = None
        self.username = None
        self.email = None
        if not row:
            return
        self.id = row.id
        self.active = True if row.active == 1 else False
        self.username = row.username
        self.password = row.password
        self.login_last_success = row.login_last_success
        self.login_last_failure = row.login_last_failure
        self.login_failed_count = row.login_failed_count
        self.real_name = row.real_name
        self.email = row.email
        self.description = row.info
        self.settings = UserMapper.get_settings(row.id)
        self.bookmarks = bookmarks
        self.password_reset_code = row.password_reset_code
        self.password_reset_date = row.password_reset_date
        self.unsubscribe_code = row.unsubscribe_code
        self.group = row.group_name
        self.created = row.created
        self.modified = row.modified

    def update(self):
        UserMapper.update(self)
        return

    def update_settings(self):
        UserMapper.update_settings(self)
        return

    def login_attempts_exceeded(self):
        failed_login_tries = int(session['settings']['failed_login_tries'])
        if not self.login_last_failure or self.login_failed_count < failed_login_tries:
            return False
        last_failure_date = self.login_last_failure
        forget_minutes = int(session['settings']['failed_login_forget_minutes'])
        last_failure_date += datetime.timedelta(minutes=forget_minutes)
        if last_failure_date > datetime.datetime.now():
            return True
        return False  # pragma no cover - because not waiting in tests for forget_minutes to pass


class UserMapper:
    sql = """
        SELECT u.id, u.username, u.password, u.active, u.real_name, u.info, u.created, u.modified,
            u.login_last_success, u.login_last_failure, u.login_failed_count, u.password_reset_code,
            u.password_reset_date, u.email, r.name as group_name, u.unsubscribe_code
        FROM web."user" u
        LEFT JOIN web.group r ON u.group_id = r.id """

    @staticmethod
    def get_all():
        g.cursor.execute(UserMapper.sql + ' ORDER BY username;')
        users = []
        for row in g.cursor.fetchall():
            users.append(User(row))
        openatlas.debug_model['user'] += 1
        return users

    @staticmethod
    def get_by_id(user_id, with_bookmarks=False):
        bookmarks = None
        if with_bookmarks:
            sql = 'SELECT entity_id FROM web.user_bookmarks WHERE user_id = %(user_id)s;'
            g.cursor.execute(sql, {'user_id': user_id})
            bookmarks = []
            for row in g.cursor.fetchall():
                bookmarks.append(row.entity_id)
        g.cursor.execute(UserMapper.sql + ' WHERE u.id = %(id)s;', {'id': user_id})
        return User(g.cursor.fetchone(), bookmarks) if g.cursor.rowcount == 1 else None

    @staticmethod
    def get_by_reset_code(code):
        sql = UserMapper.sql + ' WHERE u.password_reset_code = %(code)s;'
        g.cursor.execute(sql, {'code': code})
        return User(g.cursor.fetchone()) if g.cursor.rowcount == 1 else None

    @staticmethod
    def get_by_email(email):
        sql = UserMapper.sql + ' WHERE LOWER(u.email) = LOWER(%(email)s);'
        g.cursor.execute(sql, {'email': email})
        return User(g.cursor.fetchone()) if g.cursor.rowcount == 1 else None

    @staticmethod
    def get_by_username(username):
        sql = UserMapper.sql + ' WHERE LOWER(u.username) = LOWER(%(username)s);'
        g.cursor.execute(sql, {'username': username})
        return User(g.cursor.fetchone()) if g.cursor.rowcount == 1 else None

    @staticmethod
    def get_by_unsubscribe_code(code):
        g.cursor.execute(UserMapper.sql + ' WHERE u.unsubscribe_code = %(code)s;', {'code': code})
        return User(g.cursor.fetchone()) if g.cursor.rowcount == 1 else None

    @staticmethod
    def get_activities(limit, user_id, action):
        sql = """
            SELECT id, user_id, entity_id, created, action, 'ignore' AS ignore
            FROM web.user_log WHERE TRUE"""
        sql += ' AND user_id = %(user_id)s' if int(user_id) else ''
        sql += ' AND action = %(action)s' if action != 'all' else ''
        sql += ' ORDER BY created DESC'
        sql += ' LIMIT %(limit)s' if int(limit) else ''
        g.cursor.execute(sql, {'limit': limit, 'user_id': user_id, 'action': action})
        return g.cursor.fetchall()

    @staticmethod
    def get_created_entities_count(user_id):
        sql = "SELECT COUNT(*) FROM web.user_log WHERE user_id = %(user_id)s AND action = 'insert';"
        g.cursor.execute(sql, {'user_id': user_id})
        return g.cursor.fetchone()[0]

    @staticmethod
    def insert(form):
        sql = """
            INSERT INTO web.user (username, real_name, info, email, active, password, group_id)
            VALUES (%(username)s, %(real_name)s, %(info)s, %(email)s, %(active)s, %(password)s,
                (SELECT id FROM web.group WHERE name LIKE %(group_name)s))
            RETURNING id;"""
        password = form.password.data.encode('utf-8')
        g.cursor.execute(sql, {
            'username': form.username.data,
            'real_name': form.real_name.data,
            'info': form.description.data,
            'email': form.email.data,
            'active': form.active.data,
            'group_name': form.group.data,
            'password': bcrypt.hashpw(password, bcrypt.gensalt()).decode('utf-8')})
        return g.cursor.fetchone()[0]

    @staticmethod
    def update(user):
        sql = """
            UPDATE web.user SET (username, password, real_name, info, email, active,
                login_last_success, login_last_failure, login_failed_count, group_id,
                password_reset_code, password_reset_date, unsubscribe_code) =
            (%(username)s, %(password)s, %(real_name)s, %(info)s, %(email)s, %(active)s,
                %(login_last_success)s, %(login_last_failure)s, %(login_failed_count)s,
                (SELECT id FROM web.group WHERE name LIKE %(group_name)s),
                %(password_reset_code)s, %(password_reset_date)s, %(unsubscribe_code)s)
            WHERE id = %(id)s;"""
        g.cursor.execute(sql, {
            'id': user.id,
            'username': user.username,
            'real_name': user.real_name,
            'password': user.password,
            'info': user.description,
            'email': user.email,
            'active': user.active,
            'group_name': user.group,
            'login_last_success': user.login_last_success,
            'login_last_failure': user.login_last_failure,
            'login_failed_count': user.login_failed_count,
            'unsubscribe_code': user.unsubscribe_code,
            'password_reset_code': user.password_reset_code,
            'password_reset_date': user.password_reset_date})
        return

    @staticmethod
    def update_settings(user):
        for name, value in user.settings.items():
            if name == 'newsletter':
                value = 'True' if user.settings['newsletter'] else ''
            if name == 'show_email':
                value = 'True' if user.settings['show_email'] else ''
            sql = """
                INSERT INTO web.user_settings (user_id, "name", "value")
                VALUES (%(user_id)s, %(name)s, %(value)s)
                ON CONFLICT (user_id, name) DO UPDATE SET "value" = excluded.value;"""
            g.cursor.execute(sql, {'user_id': user.id, 'name': name, 'value': value})

    @staticmethod
    def delete(user_id):
        sql = 'DELETE FROM web."user" WHERE id = %(user_id)s;'
        g.cursor.execute(sql, {'user_id': user_id})

    @staticmethod
    def get_users():
        sql = 'SELECT id, username FROM web.user ORDER BY username;'
        g.cursor.execute(sql)
        users = []
        for row in g.cursor.fetchall():
            users.append((row.id, row.username))
        return users

    @staticmethod
    def toggle_bookmark(entity_id, user):
        sql = """
            INSERT INTO web.user_bookmarks (user_id, entity_id)
            VALUES (%(user_id)s, %(entity_id)s);"""
        label = _('bookmark remove')
        if int(entity_id) in user.bookmarks:
            sql = """
                DELETE FROM web.user_bookmarks
                WHERE user_id = %(user_id)s AND entity_id = %(entity_id)s;"""
            label = _('bookmark')
        g.cursor.execute(sql, {'user_id': user.id, 'entity_id': entity_id})
        return label

    @staticmethod
    def get_settings(user_id):
        sql = 'SELECT "name", value FROM web.user_settings WHERE user_id = %(user_id)s;'
        g.cursor.execute(sql, {'user_id': user_id})
        settings = {}
        for row in g.cursor.fetchall():
            settings[row.name] = row.value
        for item in ['newsletter', 'show_email']:
            settings[item] = True if item in settings and settings[item] == 'True' else False
        if 'theme' not in settings:
            settings['theme'] = 'default'
        if 'layout' not in settings:
            settings['layout'] = 'default'
        if 'language' not in settings:
            settings['language'] = ''
        if 'table_rows' in settings:
            settings['table_rows'] = int(settings['table_rows'])
        else:
            settings['table_rows'] = session['settings']['default_table_rows']
        return settings

    @staticmethod
    def generate_password(length=None):  # pragma no cover - because only used in mail functions
        length = length if length else session['settings']['random_password_length']
        # with python 3.6 following can be used instead:
        # ''.join(secrets.choice(string.ascii_uppercase + string.digits) for _ in range(length))
        password = ''.join(random.SystemRandom().choice(
            string.ascii_uppercase + string.digits) for _ in range(length))
        return password
