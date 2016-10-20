from flask_apispec import doc

from webservices import args
from webservices import docs
from webservices import utils
from webservices import schemas
from webservices.common import models
from webservices.common.views import ApiResource


@doc(
    tags=['financial'],
    description=docs.ENTITY_RECEIPTS_TOTLAS,
)
class EntityReceiptsTotalsView(ApiResource):

    model = models.EntityReceiptsTotals
    schema = schemas.EntityReceiptsTotalsSchema
    page_schema = schemas.EntityReceiptsTotalsPageSchema

    filter_match_fields = [
        ('cycle', model.cycle),
    ]

    @property
    def args(self):
        return utils.extend(
            args.paging,
            args.large_aggregates,
        )

    @property
    def index_column(self):
        return self.model.idx


@doc(
    tags=['financial'],
    description=docs.ENTITY_DISBURSEMENTS_TOTLAS,
)
class EntityDisbursementsTotalsView(ApiResource):

    model = models.EntityDisbursementsTotals
    schema = schemas.EntityDisbursementsTotalsSchema
    page_schema = schemas.EntityDisbursementsTotalsPageSchema

    filter_match_fields = [
        ('cycle', model.cycle),
    ]

    @property
    def args(self):
        return utils.extend(
            args.paging,
            args.large_aggregates,
        )

    @property
    def index_column(self):
        return self.model.idx