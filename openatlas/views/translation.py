# Created by Alexander Watzinger and others. Please see README.md for licensing information
from flask import flash, g, render_template, request, url_for
from flask_babel import lazy_gettext as _
from flask_wtf import Form
from werkzeug.utils import redirect
from wtforms import HiddenField, StringField, SubmitField, TextAreaField
from wtforms.validators import DataRequired

from openatlas import app, logger
from openatlas.forms.forms import build_form
from openatlas.models.entity import EntityMapper
from openatlas.util.util import get_entity_data, required_group


class TranslationForm(Form):
    name = StringField(_('name'), [DataRequired()])
    description = TextAreaField(_('content'))
    save = SubmitField(_('insert'))
    insert_and_continue = SubmitField(_('insert and continue'))
    continue_ = HiddenField()


@app.route('/source/translation/insert/<int:source_id>', methods=['POST', 'GET'])
@required_group('editor')
def translation_insert(source_id):
    source = EntityMapper.get_by_id(source_id)
    form = build_form(TranslationForm, 'Source translation')
    if form.validate_on_submit():
        translation = save(form, source=source)
        flash(_('entity created'), 'info')
        if form.continue_.data == 'yes':
            return redirect(url_for('translation_insert', source_id=source.id))
        return redirect(url_for('translation_view', id_=translation.id))
    return render_template('translation/insert.html', source=source, form=form)


@app.route('/source/translation/view/<int:id_>')
@required_group('readonly')
def translation_view(id_):
    translation = EntityMapper.get_by_id(id_)
    source = translation.get_linked_entity('P73', True)
    return render_template(
        'translation/view.html',
        source=source,
        translation=translation,
        tables={'info': get_entity_data(translation)})


@app.route('/source/translation/delete/<int:id_>/<int:source_id>')
@required_group('editor')
def translation_delete(id_, source_id):
    g.cursor.execute('BEGIN')
    try:
        EntityMapper.delete(id_)
        g.cursor.execute('COMMIT')
        flash(_('entity deleted'), 'info')
    except Exception as e:  # pragma: no cover
        g.cursor.execute('ROLLBACK')
        logger.log('error', 'database', 'transaction failed', e)
        flash(_('error transaction'), 'error')
    return redirect(url_for('source_view', id_=source_id))


@app.route('/source/translation/update/<int:id_>', methods=['POST', 'GET'])
@required_group('editor')
def translation_update(id_):
    translation = EntityMapper.get_by_id(id_)
    source = translation.get_linked_entity('P73', True)
    form = build_form(TranslationForm, 'Source translation', translation, request)
    if form.validate_on_submit():
        save(form, translation)
        flash(_('info update'), 'info')
        return redirect(url_for('translation_view', id_=translation.id))
    return render_template(
        'translation/update.html',
        translation=translation,
        source=source,
        form=form)


def save(form, entity=None, source=None):
    g.cursor.execute('BEGIN')
    try:
        if entity:
            logger.log_user(entity.id, 'update')
        else:
            entity = EntityMapper.insert('E33', form.name.data, 'source translation')
            source.link('P73', entity)
            logger.log_user(entity.id, 'insert')
        entity.name = form.name.data
        entity.description = form.description.data
        entity.update()
        entity.save_nodes(form)
        g.cursor.execute('COMMIT')
    except Exception as e:  # pragma: no cover
        g.cursor.execute('ROLLBACK')
        logger.log('error', 'database', 'transaction failed', e)
        flash(_('error transaction'), 'error')
    return entity
