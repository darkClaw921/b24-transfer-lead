"""Public API endpoints for creating leads without authentication."""
import logging
from typing import Any

from fastapi import APIRouter, Depends, HTTPException, Query, Request, status
from pydantic import BaseModel, ConfigDict
from sqlalchemy.orm import Session

from src.backend.core.database import get_main_db
from src.backend.models.lead import Lead
from src.backend.models.lead_field import LeadField
from src.backend.models.workflow import Workflow
from src.backend.models.workflow_field_mapping import WorkflowFieldMapping
from src.backend.services.database import database_service
from src.backend.services.bitrix24 import Bitrix24Service

logger = logging.getLogger(__name__)

router = APIRouter()


class CreateLeadPublicRequest(BaseModel):
    """Create lead public request model (supports partial fields)."""

    name: str
    phone: str
    # Additional fields can be passed as dict[str, Any]
    # They will be mapped using WorkflowFieldMapping
    
    model_config = ConfigDict(extra='allow')


class LeadPublicResponse(BaseModel):
    """Lead public response model."""

    id: int
    phone: str
    name: str
    status: str | None
    bitrix24_lead_id: str | None
    created_at: str


def get_workflow_by_token(token: str, db: Session) -> Workflow:
    """Get workflow by API token."""
    workflow = db.query(Workflow).filter(Workflow.api_token == token).first()
    if not workflow:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Invalid API token",
        )
    return workflow


@router.post("/workflows/{token}/leads", response_model=LeadPublicResponse, status_code=status.HTTP_201_CREATED)
@router.get("/workflows/{token}/leads", response_model=LeadPublicResponse, status_code=status.HTTP_201_CREATED)
async def create_lead_public(
    token: str,
    request: Request,
    db: Session = Depends(get_main_db),
    # Support query parameters as alternative to JSON body
    name: str | None = Query(None),
    phone: str | None = Query(None),
):
    """Create a lead through public API endpoint.
    
    Supports both POST and GET methods.
    Supports both JSON body (POST) and query parameters (GET/POST).
    Additional fields can be passed in JSON body or as query parameters.
    
    Note: GET requests are supported for convenience, but POST is recommended for production use.
    """
    # Get workflow by token
    workflow = get_workflow_by_token(token, db)
    
    # Get data from JSON body or query parameters
    if request.headers.get("content-type", "").startswith("application/json"):
        try:
            body_data = await request.json()
            lead_name = body_data.get("name") or name
            lead_phone = body_data.get("phone") or phone
            # Extract additional fields from body (exclude name and phone)
            extra_fields_data = {k: v for k, v in body_data.items() if k not in ["name", "phone"]}
        except Exception:
            # Fallback to query parameters if JSON parsing fails
            lead_name = name
            lead_phone = phone
            extra_fields_data = {}
    else:
        # Use query parameters
        lead_name = name
        lead_phone = phone
        # Extract additional fields from query parameters
        extra_fields_data = {}
        for key, value in request.query_params.items():
            if key not in ["name", "phone", "token"]:
                extra_fields_data[key] = value
    
    # Validate required fields
    if not lead_name or not lead_phone:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="name and phone are required",
        )
    
    # Get field mappings for this workflow
    mappings = db.query(WorkflowFieldMapping).filter(
        WorkflowFieldMapping.workflow_id == workflow.id,
        WorkflowFieldMapping.entity_type == workflow.entity_type,
    ).all()
    
    # Create mapping dict: field_name -> bitrix24_field_id
    field_mapping = {mapping.field_name: mapping.bitrix24_field_id for mapping in mappings}
    
    # Prepare extra fields for Bitrix24 (only mapped fields)
    bitrix24_extra_fields: dict[str, Any] = {}
    lead_fields_to_save: list[tuple[str, str]] = []
    
    for field_name, field_value in extra_fields_data.items():
        if field_name in field_mapping:
            bitrix24_field_id = field_mapping[field_name]
            bitrix24_extra_fields[bitrix24_field_id] = field_value
            lead_fields_to_save.append((field_name, str(field_value)))
    
    # Create lead in workflow database
    workflow_db = next(database_service.get_workflow_session(workflow.id))
    lead = Lead(phone=lead_phone, name=lead_name, status="NEW")
    workflow_db.add(lead)
    workflow_db.commit()
    workflow_db.refresh(lead)
    
    # Save additional fields
    for field_name, field_value in lead_fields_to_save:
        lead_field = LeadField(
            lead_id=lead.id,
            field_name=field_name,
            field_value=field_value,
        )
        workflow_db.add(lead_field)
    workflow_db.commit()
    
    # Create entity in Bitrix24 based on workflow settings
    try:
        bitrix_service = Bitrix24Service(workflow.bitrix24_webhook_url)
        entity_type = workflow.entity_type or "lead"
        
        if entity_type == "deal":
            # Create deal
            category_id = workflow.deal_category_id if workflow.deal_category_id is not None else 0
            stage_id = workflow.deal_stage_id if workflow.deal_stage_id else "NEW"
            bitrix_entity_id = await bitrix_service.create_deal(
                lead_name, lead_phone, category_id, stage_id, extra_fields=bitrix24_extra_fields
            )
        else:
            # Create lead (default)
            status_id = workflow.lead_status_id if workflow.lead_status_id else "NEW"
            bitrix_entity_id = await bitrix_service.create_lead(
                lead_name, lead_phone, status_id, extra_fields=bitrix24_extra_fields
            )
        
        lead.bitrix24_lead_id = str(bitrix_entity_id)
        workflow_db.commit()
    except Exception as e:
        # Log error but don't fail the request
        logger.error(f"Error creating {entity_type} in Bitrix24: {e}", exc_info=True)
    
    # Save attribute values before closing session
    lead_id = lead.id
    lead_phone = lead.phone
    lead_name = lead.name
    lead_status = lead.status
    lead_bitrix_id = lead.bitrix24_lead_id
    lead_created_at = lead.created_at.isoformat()
    
    workflow_db.close()
    
    return LeadPublicResponse(
        id=lead_id,
        phone=lead_phone,
        name=lead_name,
        status=lead_status,
        bitrix24_lead_id=lead_bitrix_id,
        created_at=lead_created_at,
    )

