# Created by Alexander Watzinger and others. Please see README.md for licensing information
import ast
import time

from flask import g
from flask_babel import lazy_gettext as _
from wtforms import HiddenField, FloatField
from wtforms.validators import Optional
from wtforms.widgets import HiddenInput

from openatlas import app
from openatlas.forms.date import DateForm
from openatlas.models.entity import EntityMapper
from openatlas.models.node import NodeMapper
from openatlas.util.util import get_base_table_data, pager, truncate_string, uc_first


def build_form(form, form_name, entity=None, request_origin=None, entity2=None):
    # Todo: write comment, reflect that entity can be a link
    # Add custom fields
    custom_list = []

    def add_value_type_fields(subs):
        for sub_id in subs:
            sub = g.nodes[sub_id]
            setattr(form, 'value_list-' + str(sub.id), FloatField(sub.name, [Optional()]))
            add_value_type_fields(sub.subs)

    for id_, node in NodeMapper.get_nodes_for_form(form_name).items():
        custom_list.append(id_)
        setattr(form, str(id_), TreeMultiField(str(id_)) if node.multiple else TreeField(str(id_)))
        if node.value_type:
            add_value_type_fields(node.subs)

    form_instance = form(obj=entity)

    # Delete custom fields except the ones specified for the form
    delete_list = []  # Can't delete fields in the loop so creating a list for later deletion
    for field in form_instance:
        if isinstance(field, (TreeField, TreeMultiField)) and int(field.id) not in custom_list:
            delete_list.append(field.id)
    for item in delete_list:
        delattr(form_instance, item)

    # Set field data if available and only if it's a GET request
    if entity and request_origin and request_origin.method == 'GET':
        if isinstance(form_instance, DateForm):
            form_instance.populate_dates(entity)
        nodes = entity.nodes
        if entity2:
            nodes.update(entity2.nodes)
        if hasattr(form, 'opened'):
            form_instance.opened.data = time.time()
        node_data = {}
        for node, node_value in nodes.items():
            root = g.nodes[node.root[-1]] if node.root else node
            if root.id not in node_data:
                node_data[root.id] = []
            node_data[root.id].append(node.id)
            if root.value_type:
                getattr(form_instance, 'value_list-' + str(node.id)).data = node_value
        for root_id, nodes in node_data.items():
            if hasattr(form_instance, str(root_id)):
                getattr(form_instance, str(root_id)).data = nodes
    return form_instance


def build_node_form(form, node, request_origin=None):
    if not request_origin:
        root = node
        node = None
    else:
        root = g.nodes[node.root[-1]]
    setattr(form, str(root.id), TreeField(str(root.id)))
    form_instance = form(obj=node)
    if not root.directional:
        del form_instance.name_inverse

    # Delete custom fields except the one specified for the form
    delete_list = []  # Can't delete fields in the loop so creating a list for later deletion
    for field in form_instance:
        if isinstance(field, TreeField) and int(field.id) != root.id:
            delete_list.append(field.id)
    for item in delete_list:
        delattr(form_instance, item)

    # Set field data if available and only if it's a GET request
    if node and request_origin and request_origin.method == 'GET':
        name_parts = node.name.split(' (')
        form_instance.name.data = name_parts[0]
        if root.directional and len(name_parts) > 1:
            form_instance.name_inverse.data = name_parts[1][:-1]  # remove the ")" from 2nd part
        form_instance.description.data = node.description
        if root:  # Set super if exists and is not same as root
            super_ = g.nodes[node.root[0]]
            getattr(form_instance, str(root.id)).data = super_.id if super_.id != root.id else None
    return form_instance


class TreeSelect(HiddenInput):

    def __call__(self, field, **kwargs):
        from openatlas.models.node import NodeMapper
        selection = ''
        selected_ids = []
        if field.data:
            field.data = field.data[0] if isinstance(field.data, list) else field.data
            selection = g.nodes[int(field.data)].name
            selected_ids.append(g.nodes[int(field.data)].id)
        try:
            hierarchy_id = int(field.id)
        except ValueError:
            hierarchy_id = NodeMapper.get_hierarchy_by_name(uc_first(field.id)).id
        root = g.nodes[hierarchy_id]
        html = """
            <input id="{name}-button" name="{name}-button" type="text"
                class="table-select {required}" onfocus="this.blur()"
                readonly="readonly" value="{selection}" placeholder="{change_label}" />
            <a id="{name}-clear" {clear_style} class="button"
                onclick="clearSelect('{name}');">{clear_label}</a>
            <div id="{name}-overlay" class="overlay">
                <div id="{name}-dialog" class="overlay-container">
                    <input class="tree-filter" id="{name}-tree-search" placeholder="Filter" />
                    <div id="{name}-tree"></div>
                </div>
            </div>
            <script>
                $(document).ready(function () {{
                    createOverlay("{name}","{title}",false,);
                    $("#{name}-tree").jstree({{
                        "core" : {{"check_callback" : true, 'data':[{tree_data}]}},
                        "search": {{"case_insensitive": true, "show_only_matches": true}},
                        "plugins" : ["search"],
                    }});
                    $("#{name}-tree").on("select_node.jstree", function (e, data) {{
                        selectFromTree("{name}", data.node.id, data.node.text);
                    }});
                    $("#{name}-tree-search").keyup(function() {{
                        $("#{name}-tree").jstree("search", $(this).val());
                    }});
                }});
            </script>""".format(
            name=field.id,
            title=root.name,
            change_label=uc_first(_('change')),
            clear_label=uc_first(_('clear')),
            selection=selection,
            tree_data=NodeMapper.get_tree_data(hierarchy_id, selected_ids),
            clear_style='' if selection else ' style="display: none;" ',
            required=' required' if field.flags.required else '')
        return super(TreeSelect, self).__call__(field, **kwargs) + html


class TreeField(HiddenField):
    widget = TreeSelect()


class TreeMultiSelect(HiddenInput):

    def __call__(self, field, **kwargs):
        selection = ''
        selected_ids = []
        root = g.nodes[int(field.id)]
        if field.data:
            if isinstance(field.data, str):
                field.data = ast.literal_eval(field.data)
            for entity_id in field.data:
                entity = g.nodes[entity_id]
                selected_ids.append(entity.id)
        html = """
            <span id="{name}-button" class="button">{change_label}</span>
            <div id="{name}-selection" style="text-align:left;">{selection}</div>
            <div id="{name}-overlay" class="overlay">
               <div id="{name}-dialog" class="overlay-container">
                   <input class="tree-filter" id="{name}-tree-search" placeholder="Filter" />
                   <div id="{name}-tree"></div>
               </div>
            </div>
            <script>
                createOverlay("{name}", "{title}", true, "tree");
                $("#{name}-tree").jstree({{
                    "core" : {{ "check_callback" : true, 'data':[{tree_data}] }},
                    "search": {{"case_insensitive": true, "show_only_matches": true}},
                    "plugins": ["search", "checkbox"],
                    "checkbox": {{"three_state": false}}
                }});
                $("#{name}-tree-search").keyup(function(){{
                    $("#{name}-tree").jstree("search", $(this).val());
                }});
            </script>""".format(
            name=field.id,
            title=root.name,
            selection=selection,
            change_label=uc_first(_('change')),
            tree_data=NodeMapper.get_tree_data(int(field.id), selected_ids))
        return super(TreeMultiSelect, self).__call__(field, **kwargs) + html


class TreeMultiField(HiddenField):
    widget = TreeMultiSelect()


class TableSelect(HiddenInput):

    def __call__(self, field, **kwargs):
        selection = ''
        class_ = field.id
        if class_ in ['residence', 'appears_first', 'appears_last']:
            class_ = 'place'
        header = app.config['TABLE_HEADERS'][class_]
        table = {'id': field.id, 'header': header, 'data': []}
        if class_ == 'place':
            entities = EntityMapper.get_by_system_type('place')
        elif class_ == 'reference':
            entities = EntityMapper.get_by_system_type('bibliography') + \
                       EntityMapper.get_by_system_type('edition')
        elif class_ == 'file':
            entities = EntityMapper.get_by_system_type('file')
        else:
            entities = EntityMapper.get_by_codes(class_)
        for entity in entities:
            # Todo: don't show self e.g. at source
            if field.data and entity.id == int(field.data):
                selection = entity.name
            data = get_base_table_data(entity)
            data[0] = """<a onclick="selectFromTable(this,'{name}', {entity_id})">{entity_name}</a>
                        """.format(
                        name=field.id,
                        entity_id=entity.id,
                        entity_name=truncate_string(entity.name, span=False))
            table['data'].append(data)
        html = """
            <input id="{name}-button" name="{name}-button" class="table-select {required}"
                type="text" placeholder="{change_label}" onfocus="this.blur()" readonly="readonly"
                value="{selection}">
            <a id="{name}-clear" class="button" {clear_style}
                onclick="clearSelect('{name}');">{clear_label}</a>
            <div id="{name}-overlay" class="overlay">
            <div id="{name}-dialog" class="overlay-container">{pager}</div></div>
            <script>$(document).ready(function () {{createOverlay("{name}", "{title}");}});</script>
            """.format(
                name=field.id,
                title=_(field.id.replace('_', ' ')),
                change_label=uc_first(_('change')),
                clear_label=uc_first(_('clear')),
                pager=pager(table),
                selection=selection,
                clear_style='' if selection else ' style="display: none;" ',
                required=' required' if field.flags.required else '')
        return super(TableSelect, self).__call__(field, **kwargs) + html


class TableField(HiddenField):
    widget = TableSelect()


class TableMultiSelect(HiddenInput):
    """ Table with checkboxes used in forms."""

    def __call__(self, field, **kwargs):
        if field.data and isinstance(field.data, str):
            field.data = ast.literal_eval(field.data)
        selection = ''
        class_ = field.id
        if class_ in ['donor', 'recipient']:
            class_ = 'actor'
        if class_ in ['given_place']:
            class_ = 'place'
        table = {
            'id': field.id,
            'header': app.config['TABLE_HEADERS'][class_],
            'data': []}
        # Make checkbox column sortable and show selected on top
        table['headers'] = 'headers: { ' + str(len(table['header'])) + ': { sorter: "checkbox" } }'
        table['sort'] = 'sortList: [[' + str(len(table['header'])) + ',0],[0,0]]'
        if class_ == 'place':
            entities = EntityMapper.get_by_system_type('place')
        else:
            entities = EntityMapper.get_by_codes(class_)
        for entity in entities:
            selection += entity.name + '<br/>' if field.data and entity.id in field.data else ''
            data = get_base_table_data(entity)
            data[0] = truncate_string(entity.name)  # replace entity link with entity name
            html = """<input type="checkbox" id="{id}" {checked} value="{name}"
                class="multi-table-select">""".format(
                    id=str(entity.id),
                    name=entity.name,
                    checked='checked = "checked"' if field.data and entity.id in field.data else '')
            data.append(html)
            table['data'].append(data)
        html = """
            <span id="{name}-button" class="button">{change_label}</span><br />
            <div id="{name}-selection" class="selection" style="text-align:left;">{selection}</div>
            <div id="{name}-overlay" class="overlay">
            <div id="{name}-dialog" class="overlay-container">{pager}</div></div>
            <script>
                $(document).ready(function () {{createOverlay("{name}", "{title}", true);}});
            </script>""".format(
                name=field.id,
                change_label=uc_first(_('change')),
                title=_(field.id.replace('_', ' ')),
                selection=selection,
                pager=pager(table))
        return super(TableMultiSelect, self).__call__(field, **kwargs) + html


class TableMultiField(HiddenField):
    widget = TableMultiSelect()
