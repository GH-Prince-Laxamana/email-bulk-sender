from __future__ import annotations

from fastapi import APIRouter, Depends
from fastapi.responses import JSONResponse
from pydantic import BaseModel, ConfigDict, Field

from app.api.dependencies import get_campaign_service
from app.services.campaigns import CampaignError, CampaignService

router = APIRouter(prefix="/api/campaigns", tags=["campaigns"])


class CampaignResponse(BaseModel):
    id: int
    name: str
    subject: str
    body_html: str
    variables: list[str]
    state: str
    locked: bool
    halt_reason: str | None
    counts: dict[str, int]


class CreateCampaignRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")

    name: str = Field(min_length=1)
    subject: str = ""
    body_html: str = ""
    variables: list[str] = Field(default_factory=list)


class UpdateCampaignRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")

    name: str = Field(min_length=1)
    subject: str
    body_html: str
    variables: list[str] = Field(default_factory=list)


class DuplicateCampaignRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")

    new_name: str = Field(min_length=1)
    carry_recipients: bool = False


def _error(exc: CampaignError) -> JSONResponse:
    if exc.code == "campaign_not_found":
        status_code = 404
    elif exc.code in {"campaign_locked", "campaign_running"}:
        status_code = 409
    else:
        status_code = 400

    return JSONResponse(
        {
            "error": {
                "code": exc.code,
                "message": exc.message,
            }
        },
        status_code=status_code,
    )


@router.get("", response_model=list[CampaignResponse])
def list_campaigns(
    service: CampaignService = Depends(get_campaign_service),
) -> list[dict]:
    return service.list()


@router.post("", response_model=CampaignResponse, status_code=201)
def create_campaign(
    payload: CreateCampaignRequest,
    service: CampaignService = Depends(get_campaign_service),
) -> dict:
    try:
        return service.create(
            name=payload.name,
            subject=payload.subject,
            body_html=payload.body_html,
            variables=payload.variables,
        )
    except CampaignError as exc:
        return _error(exc)


@router.delete("/{campaign_id}", status_code=204)
def delete_campaign(
    campaign_id: int,
    service: CampaignService = Depends(get_campaign_service),
) -> None:
    try:
        service.delete(campaign_id)
    except CampaignError as exc:
        return _error(exc)


@router.get("/{campaign_id}", response_model=CampaignResponse)
def get_campaign(
    campaign_id: int,
    service: CampaignService = Depends(get_campaign_service),
) -> dict:
    try:
        return service.get(campaign_id)
    except CampaignError as exc:
        return _error(exc)


@router.patch("/{campaign_id}", response_model=CampaignResponse)
def update_campaign(
    campaign_id: int,
    payload: UpdateCampaignRequest,
    service: CampaignService = Depends(get_campaign_service),
) -> dict:
    try:
        return service.update(
            campaign_id,
            name=payload.name,
            subject=payload.subject,
            body_html=payload.body_html,
            variables=payload.variables,
        )
    except CampaignError as exc:
        return _error(exc)


@router.post(
    "/{campaign_id}/duplicate",
    response_model=CampaignResponse,
    status_code=201,
)
def duplicate_campaign(
    campaign_id: int,
    payload: DuplicateCampaignRequest,
    service: CampaignService = Depends(get_campaign_service),
) -> dict:
    try:
        return service.duplicate(
            campaign_id,
            new_name=payload.new_name,
            carry_recipients=payload.carry_recipients,
        )
    except CampaignError as exc:
        return _error(exc)
