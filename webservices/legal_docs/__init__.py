DOCS_INDEX = 'docs_index'
DOCS_SEARCH = 'docs_search'

from .advisory_opinions import load_advisory_opinions
from .current_murs import load_current_murs

from .load_legal_docs import (
    delete_advisory_opinions_from_es,
    delete_murs_from_es,
    delete_murs_from_s3,
    index_regulations,
    index_statutes,
    load_archived_murs
)

from .index_management import (
    initialize_legal_docs,
    create_staging_index,
    restore_from_staging_index,
)

def load_all_legal_docs():
    index_statutes()
    index_regulations()
    load_advisory_opinions()
    load_current_murs()
    #load_archived_murs()

def reinitialize_all_legal_docs():
    initialize_legal_docs()
    load_all_legal_docs()

def refresh_legal_docs_zero_downtime():
    create_staging_index()
    load_all_legal_docs()
    restore_from_staging_index()
