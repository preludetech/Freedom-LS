from datetime import datetime

from django.contrib.sites.shortcuts import get_current_site
from ninja import Router, Schema
from pydantic import ConfigDict

# router = Router(tags=["xapi"]) # TODO, what are tags for?
router = Router()

# TODO: Authentication


class ExperienceRecordSchemaIn(Schema):
    model_config = ConfigDict(extra="forbid")

    # pass
    timestamp: datetime
    # record_id # uuid


class TODOSchema(Schema):
    pass


@router.get("/hello")
def hello(request):
    """Check if the service is working and all is well"""
    site = get_current_site(request)
    return {
        "status": "OK",
        "site": {
            "id": site.id,
            "domain": site.domain,
            "name": site.name,
        },
    }


@router.post("/")
def create_experience_record(
    request, data: ExperienceRecordSchemaIn, response: TODOSchema
):
    return "todo"
