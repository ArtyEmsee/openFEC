"""
A RESTful web service supporting fulltext and field-specific searches on FEC
candidate data.

SEE DOCUMENTATION FOLDER
"""
import os
import re
import sys
import http
import logging

import yaml
import smore.apispec
from flask import abort
from flask import request
from flask import jsonify
from flask import url_for
from flask import render_template
from flask import Flask
from flask import Blueprint

from flask.ext import restful
import flask.ext.restful.representations.json
import sqlalchemy as sa

from webservices import args
from webservices import docs
from webservices import spec
from webservices import schemas
from webservices.common import models
from webservices.common.models import db
from webservices.resources.candidates import CandidateList, CandidateSearch, CandidateView, CandidateHistoryView
from webservices.resources.totals import TotalsView
from webservices.resources.reports import ReportsView
from webservices.resources.committees import CommitteeList, CommitteeView, CommitteeHistoryView

from .json_encoding import TolerantJSONEncoder

speedlogger = logging.getLogger('speed')
speedlogger.setLevel(logging.CRITICAL)
speedlogger.addHandler(logging.FileHandler(('rest_speed.log')))

flask.ext.restful.representations.json.settings["cls"] = TolerantJSONEncoder


def sqla_conn_string():
    sqla_conn_string = os.getenv('SQLA_CONN')
    if not sqla_conn_string:
        print("Environment variable SQLA_CONN is empty; running against " + "local `cfdm_test`")
        sqla_conn_string = 'postgresql://:@/cfdm_test'
    print(sqla_conn_string)
    return sqla_conn_string


app = Flask(__name__)
app.debug = True
app.config['SQLALCHEMY_DATABASE_URI'] = sqla_conn_string()
db.init_app(app)

v1 = Blueprint('v1', __name__, url_prefix='/v1')
api = restful.Api(v1)

app.register_blueprint(v1)

# api.data.gov
trusted_proxies = ('54.208.160.112', '54.208.160.151')
FEC_API_WHITELIST_IPS = os.getenv('FEC_API_WHITELIST_IPS', False)


@app.before_request
def limit_remote_addr():
    falses = (False, 'False', 'false', 'f')
    if FEC_API_WHITELIST_IPS not in falses:
        try:
            *_, api_data_route, cf_route = request.access_route
        except ValueError:  # Not enough routes
            abort(403)
        else:
            if api_data_route not in trusted_proxies:
                abort(403)


@app.after_request
def after_request(response):
    response.headers.add('Access-Control-Allow-Origin', '*')
    response.headers.add('Access-Control-Allow-Methods', 'GET')
    response.headers.add('Access-Control-Max-Age', '3000')
    return response


resource_filter_map = {
    'candidate': models.NameSearch.cand_id,
    'committee': models.NameSearch.cmte_id,
}

@spec.doc(
    tags=['search'],
    description=docs.NAME_SEARCH,
)
class NameSearch(restful.Resource):
    """
    A quick name search (candidate or committee) optimized for response time
    for typeahead
    """

    @args.register_kwargs(args.names)
    @schemas.marshal_with(schemas.NameSearchListSchema())
    def get(self, **kwargs):
        vector = ' & '.join(kwargs['q'].split())
        vector = sa.func.concat(vector, ':*')

        query = models.NameSearch.query.filter(
            models.NameSearch.name_vec.match(vector)
        )

        if kwargs['type']:
            column = resource_filter_map[kwargs['type']]
            query = query.filter(column != None)  # noqa

        query = query.order_by(
            sa.desc(sa.func.ts_rank_cd(models.NameSearch.name_vec, sa.func.to_tsquery(vector)))
        )

        query = query.limit(20)

        return {'results': query.all()}


class Help(restful.Resource):
    def get(self):
        result = {'doc': sys.modules[__name__].__doc__,
                  'endpoints': {}}
        return result


api.add_resource(Help, '/')
api.add_resource(CandidateList, '/candidates')
api.add_resource(CandidateSearch, '/candidates/search')
api.add_resource(
    CandidateView,
    '/candidate/<string:candidate_id>',
    '/committee/<string:committee_id>/candidates',
)
api.add_resource(
    CandidateHistoryView,
    '/candidate/<string:candidate_id>/history/<int:cycle>',
    '/candidate/<string:candidate_id>/history',
)
api.add_resource(CommitteeList, '/committees')
api.add_resource(
    CommitteeView,
    '/committee/<string:committee_id>',
    '/candidate/<string:candidate_id>/committees',
)
api.add_resource(
    CommitteeHistoryView,
    '/committee/<string:committee_id>/history/<int:cycle>',
    '/committee/<string:committee_id>/history',
)
api.add_resource(TotalsView, '/committee/<string:committee_id>/totals')
api.add_resource(ReportsView, '/committee/<string:committee_id>/reports', '/reports/<string:committee_type>')
api.add_resource(NameSearch, '/names')


RE_URL = re.compile(r'<(?:[^:<>]+:)?([^<>]+)>')
def extract_path(path):
    '''
    Transform a Flask/Werkzeug URL pattern in a Swagger one.
    '''
    return RE_URL.sub(r'{\1}', path)


def resolve(key, docs, default=None):
    for doc in docs:
        value = doc.get(key)
        if value:
            return value
    return default


def register_resource(resource, blueprint=None):
    key = resource.__name__.lower()
    if blueprint:
        key = '{0}.{1}'.format(blueprint, key)
    rules = app.url_map._rules_by_endpoint[key]
    resource_doc = getattr(resource, '__apidoc__', {})
    operations = {}
    for rule in rules:
        path = extract_path(rule.rule)
        path_params = [
            each for each in resource_doc.get('path_params', [])
            if each['name'] in rule.arguments
        ]
        for method in [method.lower() for method in resource.methods or []]:
            view = getattr(resource, method)
            method_doc = getattr(view, '__apidoc__', {})
            docs = [method_doc, resource_doc]
            operations[method] = {
                'tags': resolve('tags', docs, []),
                'responses': resolve('responses', docs, {}),
                'description': resolve('description', docs, None),
                'parameters': resolve('parameters', docs, []) + path_params,
            }
        spec.spec.add_path(path=path, operations=operations, view=view)


register_resource(NameSearch, blueprint='v1')
register_resource(CandidateView, blueprint='v1')
register_resource(CandidateList, blueprint='v1')
register_resource(CandidateSearch, blueprint='v1')
register_resource(CommitteeView, blueprint='v1')
register_resource(CommitteeList, blueprint='v1')
register_resource(ReportsView, blueprint='v1')
register_resource(TotalsView, blueprint='v1')

renderers = {
    'application/json': lambda data: jsonify(data),
    'application/json;charset=utf-8': lambda data: jsonify(data),
    'application/yaml': lambda data: yaml.dump(data, default_flow_style=False),
}

yaml.add_representer(
    smore.apispec.Path,
    lambda dumper, data: dumper.represent_dict(data),
)

# Adapted from https://github.com/noirbizarre/flask-restplus
here, _ = os.path.split(__file__)
docs = Blueprint(
    'docs',
    __name__,
    static_folder=os.path.join(here, os.pardir, 'node_modules', 'swagger-ui'),
    static_url_path='/docs/static',
)


@docs.route('/swagger')
def api_spec():
    render_type = request.accept_mimetypes.best_match(renderers.keys())
    if not render_type:
        abort(http.client.NOT_ACCEPTABLE)
    rendered = renderers[render_type](spec.spec.to_dict())
    return rendered, http.client.OK, {'Content-Type': render_type}


@docs.add_app_template_global
def swagger_static(filename):
    return url_for('docs.static', filename='dist/{0}'.format(filename))


@docs.route('/swagger/ui')
def api_ui():
    return render_template('swagger-ui.html', specs_url=url_for('docs.api_spec'))


app.register_blueprint(docs)
