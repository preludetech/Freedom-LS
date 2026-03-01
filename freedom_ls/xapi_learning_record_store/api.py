from datetime import datetime

from ninja import Router, Schema
from pydantic import ConfigDict

from django.contrib.sites.models import Site
from django.contrib.sites.shortcuts import get_current_site

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
    if not isinstance(site, Site):
        return {"status": "ERROR", "message": "Could not determine site"}
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
