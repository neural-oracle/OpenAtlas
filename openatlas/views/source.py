# Copyright 2017 by Alexander Watzinger and others. Please see README.md for licensing information
from flask import render_template, url_for, flash, request
from flask_babel import lazy_gettext as _
from flask_wtf import Form
from werkzeug.utils import redirect
from wtforms import StringField, TextAreaField, HiddenField, SubmitField
from wtforms.validators import InputRequired

import openatlas
from openatlas import app
from openatlas.forms import build_form
from openatlas.models.entity import EntityMapper
from openatlas.models.link import LinkMapper
from openatlas.util.util import (link, truncate_string, required_group, append_node_data,
                                 build_table_form, build_remove_link, build_delete_link)


class SourceForm(Form):
    name = StringField(_('name'), validators=[InputRequired()])
    description = TextAreaField(_('content'))
    save = SubmitField(_('insert'))
    insert_and_continue = SubmitField(_('insert and continue'))
    continue_ = HiddenField()


@app.route('/source')
@required_group('readonly')
def source_index():
    table = {'name': 'source', 'header': ['name', 'type', 'info'], 'data': []}
    for source in EntityMapper.get_by_codes('source'):
        table['data'].append([
            link(source),
            source.print_base_type(),
            truncate_string(source.description)])
    return render_template('source/index.html', table=table)


@app.route('/source/insert', methods=['POST', 'GET'])
@required_group('editor')
def source_insert():
    form = build_form(SourceForm, 'Source')
    if form.validate_on_submit():
        source = save(form)
        flash(_('entity created'), 'info')
        if form.continue_.data == 'yes':
            return redirect(url_for('source_insert'))
        return redirect(url_for('source_view', id_=source.id))
    return render_template('source/insert.html', form=form)


@app.route('/source/view/<int:id_>/<int:unlink_id>')
@app.route('/source/view/<int:id_>')
@required_group('readonly')
def source_view(id_, unlink_id=None):
    source = EntityMapper.get_by_id(id_)
    if unlink_id:
        LinkMapper.delete_by_id(unlink_id)
    data = {'info': []}
    append_node_data(data['info'], source)
    tables = {'translation': {
        'name': 'translation',
        'header': ['translations', 'type', 'text'],
        'data': []}}
    for translation in source.get_linked_entities('P73'):
        tables['translation']['data'].append([
            link(translation),
            translation.nodes[0].name if translation.nodes else '',
            truncate_string(translation.description)])
    tables['actor'] = {
        'name': 'actor',
        'header': ['name', 'class', 'first', 'last', ''],
        'data': []}
    tables['place'] = {
        'name': 'place',
        'header': ['name', 'type', 'first', 'last', ''],
        'data': []}
    tables['event'] = {
        'name': 'event',
        'header': ['name', 'class', 'type', 'first', 'last', ''],
        'data': []}
    for link_ in source.get_links('P67'):
        name = app.config['CODE_CLASS'][link_.range.class_.code]
        entity = link_.range
        unlink_url = url_for('source_view', id_=source.id, unlink_id=link_.id) + '#tab-' + name
        if name == 'event':  # show class and base type in event
            tables[name]['data'].append([
                link(entity),
                entity.class_.name,
                entity.print_base_type(),
                format(entity.first),
                format(entity.last),
                build_remove_link(unlink_url, entity.name)])
        else:  # actor has no base type, place always the same class
            tables[name]['data'].append([
                link(entity),
                entity.class_.name if name == 'actor' else entity.print_base_type(),
                format(entity.first),
                format(entity.last),
                build_remove_link(unlink_url, entity.name)])
    return render_template(
        'source/view.html',
        source=source,
        data=data,
        tables=tables,
        delete_link=build_delete_link(url_for('source_delete', id_=source.id), source.name))


@app.route('/source/add/<int:id_>/<class_name>', methods=['POST', 'GET'])
@required_group('editor')
def source_add(id_, class_name):
    source = EntityMapper.get_by_id(id_)
    if request.method == 'POST':
        for value in request.form.getlist('values'):
            source.link('P67', int(value))
        return redirect(url_for('source_view', id_=source.id) + '#tab-' + class_name)
    form = build_table_form(class_name, source.get_linked_entities('P67'))
    return render_template('source/add.html', source=source, class_name=class_name, form=form)


@app.route('/source/delete/<int:id_>')
@required_group('editor')
def source_delete(id_):
    source = EntityMapper.get_by_id(id_)
    openatlas.get_cursor().execute('BEGIN')
    for translation in source.get_linked_entities('P73'):
        EntityMapper.delete(translation.id)
    EntityMapper.delete(source.id)
    openatlas.get_cursor().execute('COMMIT')
    flash(_('entity deleted'), 'info')
    return redirect(url_for('source_index'))


@app.route('/source/update/<int:id_>', methods=['POST', 'GET'])
@required_group('editor')
def source_update(id_):
    source = EntityMapper.get_by_id(id_)
    form = build_form(SourceForm, 'Source', source, request)
    if form.validate_on_submit():
        save(form, source)
        flash(_('info update'), 'info')
        return redirect(url_for('source_view', id_=id_))
    return render_template('source/update.html', form=form, source=source)


def save(form, entity=None):
    openatlas.get_cursor().execute('BEGIN')
    if not entity:
        entity = EntityMapper.insert('E33', form.name.data, 'source content')
    entity.name = form.name.data
    entity.description = form.description.data
    entity.update()
    entity.save_nodes(form)
    openatlas.get_cursor().execute('COMMIT')
    return entity
