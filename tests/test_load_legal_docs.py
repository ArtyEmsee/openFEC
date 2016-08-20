from mock import patch, MagicMock
import unittest
from webservices.load_legal_docs import *
from zipfile import ZipFile

class ElasticSearchMock:
    def __init__(self, dictToIndex):
        self.dictToIndex = dictToIndex
    def search():
        pass

    def index(self, index, doc_type, doc, id):
        assert self.dictToIndex == doc

    def delete_index(self, index):
        assert index == 'docs'

    def create_index(self, index, mappings):
        assert index == 'docs'
        assert mappings

def get_es_with_doc(doc):
    def get_es():
        return ElasticSearchMock(doc)
    return get_es

def mock_xml(xml):
    def request_zip(url, stream=False):
        with open('test_xml.xml', 'w') as f:
            f.write(xml)

        with ZipFile('xml_test.zip', 'w') as z:
            z.write('test_xml.xml')

        return open('xml_test.zip', 'rb')

    return request_zip

class Engine:
    def __init__(self, legal_loaded):
        self.legal_loaded = legal_loaded

    def __iter__(self):
        return self.result.__iter__()

    def __next__(self):
        return self.result.__next__()

    def fetchone(self):
        return self.result[0]

    def fetchall(self):
        return self.result

    def connect(self):
        return self

    def execution_options(self, stream_results):
        return self

    def execute(self, sql):
        if sql == 'select document_id from document':
            self.result = [(1,), (2,)]
        if 'fileimage' in sql:
            return [(1, 'ABC'.encode('utf8'))]
        if 'EXISTS' in sql:
            self.result = [(self.legal_loaded,)]
        if 'count' in sql:
            self.result = [(5,)]
        if 'DOCUMENT_ID' in sql:
            self.result = [(123, 'textAB', 'description123', 'category123', 'id123',
                           'name4U', 'summaryABC', 'tags123', 'no123', 'date123')]
        return self


class Db:
    def __init__(self, legal_loaded=True):
        self.engine = Engine(legal_loaded)

def get_credential_mock(var, default):
    return 'https://eregs.api.com/'

class RequestResult:
    def __init__(self, result):
        self.result = result

    def json(self):
        return self.result

def mock_get_regulations(url):
    if url.endswith('regulation'):
        return RequestResult({'versions': [{'version': 'versionA',
                             'regulation': 'reg104'}]})
    if url.endswith('reg104/versionA'):
        return RequestResult({'children': [{'children': [{'label': ['104', '1'],
                               'title': 'Section 104.1 Title',
                               'text': 'sectionContentA',
                               'children': [{'text': 'sectionContentB',
                               'children': []}]}]}]})

class obj:
    def __init__(self, key):
        self.key = key

    def delete(self):
        pass

class S3Objects:
    def __init__(self, objects):
        self.objects = objects

    def filter(self, Prefix):
        return self.objects

class BucketMock:
    def __init__(self, existing_pdfs):
        self.objects = S3Objects(existing_pdfs)

    def put_object(self, Key, Body, ContentType, ACL):
        assert Key == 'legal/aos/1.pdf'

def get_bucket_mock(existing_pdfs):
    def get_bucket():
        return BucketMock(existing_pdfs)
    return get_bucket

class IndexStatutesTest(unittest.TestCase):
    @patch('webservices.load_legal_docs.requests.get', mock_xml('<test></test>'))
    def test_get_xml_tree_from_url(self):
        etree = get_xml_tree_from_url('anything.com')
        assert etree.getroot().tag == 'test'

    @patch('webservices.utils.get_elasticsearch_connection',
            get_es_with_doc({'name': 'title',
            'chapter': '1', 'title': '26', 'no': '123',
            'text': '   title  content ', 'doc_id': '/us/usc/t26/s123',
            'url': 'https://www.gpo.gov/fdsys/pkg/USCODE-2014-title26/' +
            'pdf/USCODE-2014-title26-subtitleH-chap1-sec123.pdf'}))
    @patch('webservices.load_legal_docs.requests.get', mock_xml(
            """<?xml version="1.0" encoding="UTF-8"?>
            <uscDoc xmlns="http://xml.house.gov/schemas/uslm/1.0">
            <subtitle identifier="/us/usc/t26/stH">
            <chapter identifier="/us/usc/t26/stH/ch1">
            <section identifier="/us/usc/t26/s123">
            <heading>title</heading>
            <subsection>content</subsection>
            </section></chapter></subtitle></uscDoc>
            """))
    def test_title_26(self):
        get_title_26_statutes()

    @patch('webservices.utils.get_elasticsearch_connection',
            get_es_with_doc({'subchapter': 'I',
            'doc_id': '/us/usc/t52/s123', 'chapter': '1',
            'text': '   title  content ',
            'url': 'https://www.gpo.gov/fdsys/pkg/USCODE-2014-title52/pdf/' +
                'USCODE-2014-title52-subtitleIII-chap1-subchapI-sec123.pdf',
            'title': '52', 'name': 'title', 'no': '123'}))
    @patch('webservices.load_legal_docs.requests.get', mock_xml(
            """<?xml version="1.0" encoding="UTF-8"?>
            <uscDoc xmlns="http://xml.house.gov/schemas/uslm/1.0">
            <subtitle identifier="/us/usc/t52/stIII">
            <subchapter identifier="/us/usc/t52/stIII/ch1/schI">
            <section identifier="/us/usc/t52/s123">
            <heading>title</heading>
            <subsection>content</subsection>
            </section></subchapter></subtitle></uscDoc>
            """))
    def test_title_52(self):
        get_title_52_statutes()

    @patch('webservices.load_legal_docs.get_title_52_statutes', lambda: '')
    @patch('webservices.load_legal_docs.get_title_26_statutes', lambda: '')
    def test_index_statutes(self):
        index_statutes()

class IndexRegulationsTest(unittest.TestCase):
    @patch('webservices.load_legal_docs.env.get_credential', get_credential_mock)
    @patch('webservices.load_legal_docs.requests.get', mock_get_regulations)
    @patch('webservices.utils.get_elasticsearch_connection',
            get_es_with_doc({'text': 'sectionContentA sectionContentB',
            'no': '104.1', 'name': 'Title',
            'url': '/regulations/104-1/versionA#104-1',
            'doc_id': '104_1'}))
    def test_index_regulations(self):
        index_regulations()

    @patch('webservices.load_legal_docs.env.get_credential', lambda e, d: '')
    def test_no_env_variable(self):
        index_regulations()

class IndexAdvisoryOpinionsTest(unittest.TestCase):
    @patch('webservices.load_legal_docs.db', Db())
    @patch('webservices.utils.get_elasticsearch_connection',
            side_effect=get_es_with_doc({'category': 'category123',
            'summary': 'summaryABC', 'no': 'no123', 'date': 'date123',
            'tags': 'tags123', 'name': 'name4U', 'text': 'textAB',
            'description': 'description123',
            'url': 'https://None.s3.amazonaws.com/legal/aos/123.pdf',
            'doc_id': 123, 'id': 'id123'}))
    def test_advisory_opinion_load(self, es_mock):
        index_advisory_opinions()

    @patch('webservices.load_legal_docs.db', Db(False))
    def test_no_legal_loaded(self):
        index_advisory_opinions()

class LoadAdvisoryOpinionsIntoS3Test(unittest.TestCase):
    @patch('webservices.load_legal_docs.db', Db())
    @patch('webservices.load_legal_docs.get_bucket',
     get_bucket_mock([obj('legal/aos/2.pdf')]))
    def test_load_advisory_opinions_into_s3(self):
        load_advisory_opinions_into_s3()

    @patch('webservices.load_legal_docs.db', Db())
    @patch('webservices.load_legal_docs.get_bucket',
     get_bucket_mock([obj('legal/aos/1.pdf'), obj('legal/aos/2.pdf')]))
    def test_load_advisory_opinions_into_s3_already_loaded(self):
        load_advisory_opinions_into_s3()

    @patch('webservices.load_legal_docs.get_bucket',
     get_bucket_mock([obj('legal/aos/2.pdf')]))
    def test_delete_advisory_opinions_from_s3(self):
        delete_advisory_opinions_from_s3()

class RemoveLegalDocsTest(unittest.TestCase):
    @patch('webservices.utils.get_elasticsearch_connection',
    get_es_with_doc({}))
    def test_remove_legal_docs(self):
        remove_legal_docs()
