"""Workflow management endpoints."""
import logging

from fastapi import APIRouter, Depends, HTTPException, Request, status
from pydantic import BaseModel
from sqlalchemy.orm import Session

from src.backend.api.v1.dependencies import get_current_user
from src.backend.core.config import settings
from src.backend.core.database import get_main_db
from src.backend.models.workflow import Workflow
from src.backend.models.workflow_field_mapping import WorkflowFieldMapping
from src.backend.models.user import User
from src.backend.models.lead import Lead
from src.backend.services.database import database_service
from src.backend.services.bitrix24 import Bitrix24Service
from src.backend.utils.bitrix24_url import extract_domain_from_webhook_url

logger = logging.getLogger(__name__)

router = APIRouter()


class CreateWorkflowRequest(BaseModel):
    """Create workflow request model."""

    name: str
    bitrix24_webhook_url: str  # Full URL: https://domain.bitrix24.ru/rest/1/token


class WorkflowResponse(BaseModel):
    """Workflow response model."""

    id: int
    name: str
    bitrix24_webhook_url: str
    user_id: int
    created_at: str

    class Config:
        from_attributes = True


@router.get("", response_model=list[WorkflowResponse])
async def list_workflows(
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_main_db),
):
    """List workflows for current user (admin sees all, regular users see their own and accessible workflows)."""
    if current_user.role == "admin":
        workflows = db.query(Workflow).all()
    else:
        # Get workflows created by user and workflows user has access to
        created_workflows = db.query(Workflow).filter(Workflow.user_id == current_user.id).all()
        accessible_workflows = current_user.accessible_workflows.all()
        
        # Combine and deduplicate
        workflow_ids = {w.id for w in created_workflows} | {w.id for w in accessible_workflows}
        workflows = db.query(Workflow).filter(Workflow.id.in_(workflow_ids)).all()

    return [
        WorkflowResponse(
            id=workflow.id,
            name=workflow.name,
            bitrix24_webhook_url=workflow.bitrix24_webhook_url,
            user_id=workflow.user_id,
            created_at=workflow.created_at.isoformat(),
        )
        for workflow in workflows
    ]


@router.post("", response_model=WorkflowResponse, status_code=status.HTTP_201_CREATED)
async def create_workflow(
    request: CreateWorkflowRequest,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_main_db),
):
    """Create a new workflow."""
    # Extract domain from webhook URL
    try:
        domain = extract_domain_from_webhook_url(request.bitrix24_webhook_url)
    except Exception as e:
        logger.warning(f"Failed to extract domain from webhook URL: {e}")
        domain = None
    
    workflow = Workflow(
        name=request.name,
        bitrix24_webhook_url=request.bitrix24_webhook_url,
        user_id=current_user.id,
        bitrix24_domain=domain,
    )
    db.add(workflow)
    db.commit()
    db.refresh(workflow)

    # Initialize workflow database
    database_service.init_workflow_db(workflow.id)

    return WorkflowResponse(
        id=workflow.id,
        name=workflow.name,
        bitrix24_webhook_url=workflow.bitrix24_webhook_url,
        user_id=workflow.user_id,
        created_at=workflow.created_at.isoformat(),
    )


@router.get("/{workflow_id}", response_model=WorkflowResponse)
async def get_workflow(
    workflow_id: int,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_main_db),
):
    """Get workflow by ID."""
    workflow = db.query(Workflow).filter(Workflow.id == workflow_id).first()
    if not workflow:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Workflow not found",
        )

    # Check access: user can access workflow if they created it, have access to it, or are admin
    has_access = (
        current_user.role == "admin"
        or workflow.user_id == current_user.id
        or workflow in current_user.accessible_workflows
    )
    
    if not has_access:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Access denied",
        )

    return WorkflowResponse(
        id=workflow.id,
        name=workflow.name,
        bitrix24_webhook_url=workflow.bitrix24_webhook_url,
        user_id=workflow.user_id,
        created_at=workflow.created_at.isoformat(),
    )


@router.delete("/{workflow_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_workflow(
    workflow_id: int,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_main_db),
):
    """Delete workflow."""
    workflow = db.query(Workflow).filter(Workflow.id == workflow_id).first()
    if not workflow:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Workflow not found",
        )

    # Check access: user can access workflow if they created it, have access to it, or are admin
    has_access = (
        current_user.role == "admin"
        or workflow.user_id == current_user.id
        or workflow in current_user.accessible_workflows
    )
    
    if not has_access:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Access denied",
        )

    # Delete workflow database
    database_service.delete_workflow_db(workflow_id)

    db.delete(workflow)
    db.commit()


# Settings endpoints
class WorkflowSettingsResponse(BaseModel):
    """Workflow settings response model."""

    entity_type: str
    deal_category_id: int | None
    deal_stage_id: str | None
    lead_status_id: str | None
    bitrix24_webhook_url: str
    app_token: str | None
    webhook_endpoint_url: str  # Full URL for Bitrix24 to send events to
    api_token: str | None  # API token for public endpoint
    public_api_url: str | None  # Full URL for public API endpoint


class UpdateWorkflowSettingsRequest(BaseModel):
    """Update workflow settings request model."""

    entity_type: str
    deal_category_id: int | None = None
    deal_stage_id: str | None = None
    lead_status_id: str | None = None
    bitrix24_webhook_url: str | None = None
    app_token: str | None = None


class FunnelResponse(BaseModel):
    """Funnel response model."""

    id: int
    name: str


class StatusResponse(BaseModel):
    """Status response model."""

    id: str
    name: str


@router.get("/{workflow_id}/settings", response_model=WorkflowSettingsResponse)
async def get_workflow_settings(
    workflow_id: int,
    request: Request,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_main_db),
):
    """Get workflow settings."""
    workflow = db.query(Workflow).filter(Workflow.id == workflow_id).first()
    if not workflow:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Workflow not found",
        )

    # Check access: user can access workflow if they created it, have access to it, or are admin
    has_access = (
        current_user.role == "admin"
        or workflow.user_id == current_user.id
        or workflow in current_user.accessible_workflows
    )
    
    if not has_access:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Access denied",
        )

    # Build webhook endpoint URL
    base_url = str(request.base_url).rstrip("/")
    # Force HTTPS for webhook endpoint URL
    if base_url.startswith("http://"):
        base_url = base_url.replace("http://", "https://", 1)
    webhook_endpoint_url = f"{base_url}/api/v1/webhook"
    
    # Build public API URL if token exists (use same base_url as webhook for consistency)
    public_api_url = None
    if workflow.api_token:
        public_api_url = f"{base_url}/api/public/workflows/{workflow.api_token}/leads"

    return WorkflowSettingsResponse(
        entity_type=workflow.entity_type or "lead",
        deal_category_id=workflow.deal_category_id,
        deal_stage_id=workflow.deal_stage_id,
        lead_status_id=workflow.lead_status_id or "NEW",
        bitrix24_webhook_url=workflow.bitrix24_webhook_url,
        app_token=workflow.app_token,
        webhook_endpoint_url=webhook_endpoint_url,
        api_token=workflow.api_token,
        public_api_url=public_api_url,
    )


@router.put("/{workflow_id}/settings", response_model=WorkflowSettingsResponse)
async def update_workflow_settings(
    workflow_id: int,
    request: UpdateWorkflowSettingsRequest,
    http_request: Request,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_main_db),
):
    """Update workflow settings."""
    workflow = db.query(Workflow).filter(Workflow.id == workflow_id).first()
    if not workflow:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Workflow not found",
        )

    # Check access: user can access workflow if they created it, have access to it, or are admin
    has_access = (
        current_user.role == "admin"
        or workflow.user_id == current_user.id
        or workflow in current_user.accessible_workflows
    )
    
    if not has_access:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Access denied",
        )

    # Validate entity_type
    if request.entity_type not in ["lead", "deal"]:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="entity_type must be 'lead' or 'deal'",
        )

    # Update settings
    workflow.entity_type = request.entity_type
    workflow.deal_category_id = request.deal_category_id
    workflow.deal_stage_id = request.deal_stage_id
    workflow.lead_status_id = request.lead_status_id

    # Update webhook URL if provided
    if request.bitrix24_webhook_url is not None:
        workflow.bitrix24_webhook_url = request.bitrix24_webhook_url
        # Automatically extract and update domain
        try:
            domain = extract_domain_from_webhook_url(request.bitrix24_webhook_url)
            workflow.bitrix24_domain = domain
        except Exception as e:
            logger.warning(f"Failed to extract domain from webhook URL: {e}")

    # Update app token if provided
    if request.app_token is not None:
        workflow.app_token = request.app_token if request.app_token else None

    db.commit()
    db.refresh(workflow)

    # Build webhook endpoint URL
    base_url = str(http_request.base_url).rstrip("/")
    # Force HTTPS for webhook endpoint URL
    if base_url.startswith("http://"):
        base_url = base_url.replace("http://", "https://", 1)
    webhook_endpoint_url = f"{base_url}/api/v1/webhook"
    
    # Build public API URL if token exists (use same base_url as webhook for consistency)
    public_api_url = None
    if workflow.api_token:
        public_api_url = f"{base_url}/api/public/workflows/{workflow.api_token}/leads"

    return WorkflowSettingsResponse(
        entity_type=workflow.entity_type,
        deal_category_id=workflow.deal_category_id,
        deal_stage_id=workflow.deal_stage_id,
        lead_status_id=workflow.lead_status_id,
        bitrix24_webhook_url=workflow.bitrix24_webhook_url,
        app_token=workflow.app_token,
        webhook_endpoint_url=webhook_endpoint_url,
        api_token=workflow.api_token,
        public_api_url=public_api_url,
    )


@router.get("/{workflow_id}/settings/funnels", response_model=list[FunnelResponse])
async def get_workflow_funnels(
    workflow_id: int,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_main_db),
):
    """Get list of deal funnels from Bitrix24."""
    workflow = db.query(Workflow).filter(Workflow.id == workflow_id).first()
    if not workflow:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Workflow not found",
        )

    # Check access: user can access workflow if they created it, have access to it, or are admin
    has_access = (
        current_user.role == "admin"
        or workflow.user_id == current_user.id
        or workflow in current_user.accessible_workflows
    )
    
    if not has_access:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Access denied",
        )

    try:
        bitrix_service = Bitrix24Service(workflow.bitrix24_webhook_url)
        funnels = await bitrix_service.get_deal_categories()
        logger.info(f"Service returned {len(funnels)} funnels: {funnels}")
        
        if not funnels:
            logger.warning(f"No funnels found for workflow {workflow_id}. Check Bitrix24 webhook permissions.")
        
        result = [FunnelResponse(id=funnel["id"], name=funnel["name"]) for funnel in funnels]
        logger.info(f"Returning {len(result)} funnels to client")
        return result
    except Exception as e:
        logger.error(f"Error fetching funnels: {e}", exc_info=True)
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to fetch funnels: {str(e)}",
        )


@router.get("/{workflow_id}/settings/stages", response_model=list[StatusResponse])
async def get_workflow_stages(
    workflow_id: int,
    category_id: int = 0,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_main_db),
):
    """Get list of deal stages for a funnel from Bitrix24."""
    workflow = db.query(Workflow).filter(Workflow.id == workflow_id).first()
    if not workflow:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Workflow not found",
        )

    # Check access: user can access workflow if they created it, have access to it, or are admin
    has_access = (
        current_user.role == "admin"
        or workflow.user_id == current_user.id
        or workflow in current_user.accessible_workflows
    )
    
    if not has_access:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Access denied",
        )

    try:
        bitrix_service = Bitrix24Service(workflow.bitrix24_webhook_url)
        stages = await bitrix_service.get_deal_stages(category_id)
        return [StatusResponse(id=stage["id"], name=stage["name"]) for stage in stages]
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to fetch stages: {str(e)}",
        )


@router.get("/{workflow_id}/settings/lead-statuses", response_model=list[StatusResponse])
async def get_workflow_lead_statuses(
    workflow_id: int,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_main_db),
):
    """Get list of lead statuses from Bitrix24."""
    workflow = db.query(Workflow).filter(Workflow.id == workflow_id).first()
    if not workflow:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Workflow not found",
        )

    # Check access: user can access workflow if they created it, have access to it, or are admin
    has_access = (
        current_user.role == "admin"
        or workflow.user_id == current_user.id
        or workflow in current_user.accessible_workflows
    )
    
    if not has_access:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Access denied",
        )

    try:
        bitrix_service = Bitrix24Service(workflow.bitrix24_webhook_url)
        statuses = await bitrix_service.get_lead_statuses()
        return [StatusResponse(id=status["id"], name=status["name"]) for status in statuses]
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to fetch lead statuses: {str(e)}",
        )


# Field mapping endpoints (admin only)
class FieldResponse(BaseModel):
    """Field response model."""

    id: str
    name: str
    type: str


class CreateFieldMappingRequest(BaseModel):
    """Create field mapping request model."""

    field_name: str  # Field name in our system
    display_name: str  # Human-readable name for display in UI
    bitrix24_field_id: str  # Field ID in Bitrix24
    entity_type: str  # "lead" or "deal"
    update_on_event: bool = False  # Update this field when receiving webhook event from Bitrix24


class UpdateFieldMappingRequest(BaseModel):
    """Update field mapping request model."""

    field_name: str | None = None
    display_name: str | None = None
    bitrix24_field_id: str | None = None
    entity_type: str | None = None
    update_on_event: bool | None = None  # Update this field when receiving webhook event from Bitrix24


class FieldMappingResponse(BaseModel):
    """Field mapping response model."""

    id: int
    workflow_id: int
    field_name: str
    display_name: str
    bitrix24_field_id: str
    bitrix24_field_name: str
    entity_type: str
    update_on_event: bool
    created_at: str

    class Config:
        from_attributes = True


@router.get("/{workflow_id}/fields", response_model=list[FieldResponse])
async def get_workflow_fields(
    workflow_id: int,
    entity_type: str = "lead",
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_main_db),
):
    """Get list of available fields from Bitrix24 for field mapping (admin only)."""
    if current_user.role != "admin":
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Admin access required",
        )

    workflow = db.query(Workflow).filter(Workflow.id == workflow_id).first()
    if not workflow:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Workflow not found",
        )

    # Validate entity_type
    if entity_type not in ["lead", "deal"]:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="entity_type must be 'lead' or 'deal'",
        )

    try:
        bitrix_service = Bitrix24Service(workflow.bitrix24_webhook_url)
        if entity_type == "deal":
            fields = await bitrix_service.get_deal_fields()
        else:
            fields = await bitrix_service.get_lead_fields()
        
        return [FieldResponse(id=field["id"], name=field["name"], type=field["type"]) for field in fields]
    except Exception as e:
        logger.error(f"Error fetching fields: {e}", exc_info=True)
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to fetch fields: {str(e)}",
        )


@router.post("/{workflow_id}/fields/mapping", response_model=FieldMappingResponse, status_code=status.HTTP_201_CREATED)
async def create_field_mapping(
    workflow_id: int,
    request: CreateFieldMappingRequest,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_main_db),
):
    """Create field mapping (admin only)."""
    if current_user.role != "admin":
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Admin access required",
        )

    workflow = db.query(Workflow).filter(Workflow.id == workflow_id).first()
    if not workflow:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Workflow not found",
        )

    # Validate entity_type
    if request.entity_type not in ["lead", "deal"]:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="entity_type must be 'lead' or 'deal'",
        )

    # Get field name from Bitrix24
    try:
        bitrix_service = Bitrix24Service(workflow.bitrix24_webhook_url)
        if request.entity_type == "deal":
            fields = await bitrix_service.get_deal_fields()
        else:
            fields = await bitrix_service.get_lead_fields()
        
        field_info = next((f for f in fields if f["id"] == request.bitrix24_field_id), None)
        if not field_info:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail=f"Field {request.bitrix24_field_id} not found in Bitrix24",
            )
        
        bitrix24_field_name = field_info["name"]
    except Exception as e:
        logger.error(f"Error fetching field info: {e}", exc_info=True)
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to fetch field info: {str(e)}",
        )

    # Check if mapping already exists
    existing = db.query(WorkflowFieldMapping).filter(
        WorkflowFieldMapping.workflow_id == workflow_id,
        WorkflowFieldMapping.field_name == request.field_name,
        WorkflowFieldMapping.entity_type == request.entity_type,
    ).first()
    
    if existing:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Field mapping for '{request.field_name}' already exists",
        )

    # Create mapping
    # Если display_name не указан, используем bitrix24_field_name
    display_name = request.display_name.strip() if request.display_name else bitrix24_field_name
    
    mapping = WorkflowFieldMapping(
        workflow_id=workflow_id,
        field_name=request.field_name,
        display_name=display_name,
        bitrix24_field_id=request.bitrix24_field_id,
        bitrix24_field_name=bitrix24_field_name,
        entity_type=request.entity_type,
        update_on_event=request.update_on_event,
    )
    db.add(mapping)
    db.commit()
    db.refresh(mapping)

    return FieldMappingResponse(
        id=mapping.id,
        workflow_id=mapping.workflow_id,
        field_name=mapping.field_name,
        display_name=mapping.display_name,
        bitrix24_field_id=mapping.bitrix24_field_id,
        bitrix24_field_name=mapping.bitrix24_field_name,
        entity_type=mapping.entity_type,
        update_on_event=mapping.update_on_event,
        created_at=mapping.created_at.isoformat(),
    )


@router.get("/{workflow_id}/fields/mapping", response_model=list[FieldMappingResponse])
async def get_field_mappings(
    workflow_id: int,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_main_db),
):
    """Get list of field mappings for workflow."""
    workflow = db.query(Workflow).filter(Workflow.id == workflow_id).first()
    if not workflow:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Workflow not found",
        )

    # Check access: user can access workflow if they created it, have access to it, or are admin
    has_access = (
        current_user.role == "admin"
        or workflow.user_id == current_user.id
        or workflow in current_user.accessible_workflows
    )
    
    if not has_access:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Access denied",
        )

    mappings = db.query(WorkflowFieldMapping).filter(
        WorkflowFieldMapping.workflow_id == workflow_id
    ).all()

    return [
        FieldMappingResponse(
            id=mapping.id,
            workflow_id=mapping.workflow_id,
            field_name=mapping.field_name,
            display_name=mapping.display_name,
            bitrix24_field_id=mapping.bitrix24_field_id,
            bitrix24_field_name=mapping.bitrix24_field_name,
            entity_type=mapping.entity_type,
            update_on_event=mapping.update_on_event,
            created_at=mapping.created_at.isoformat(),
        )
        for mapping in mappings
    ]


@router.put("/{workflow_id}/fields/mapping/{mapping_id}", response_model=FieldMappingResponse)
async def update_field_mapping(
    workflow_id: int,
    mapping_id: int,
    request: UpdateFieldMappingRequest,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_main_db),
):
    """Update field mapping (admin only)."""
    if current_user.role != "admin":
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Admin access required",
        )

    workflow = db.query(Workflow).filter(Workflow.id == workflow_id).first()
    if not workflow:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Workflow not found",
        )

    mapping = db.query(WorkflowFieldMapping).filter(
        WorkflowFieldMapping.id == mapping_id,
        WorkflowFieldMapping.workflow_id == workflow_id,
    ).first()
    
    if not mapping:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Field mapping not found",
        )

    # Update fields if provided
    if request.field_name is not None:
        mapping.field_name = request.field_name
    if request.display_name is not None:
        # Если display_name пустой, используем bitrix24_field_name
        mapping.display_name = request.display_name.strip() if request.display_name.strip() else mapping.bitrix24_field_name
    if request.bitrix24_field_id is not None:
        # If bitrix24_field_id changes, update bitrix24_field_name too
        try:
            bitrix_service = Bitrix24Service(workflow.bitrix24_webhook_url)
            entity_type = request.entity_type or mapping.entity_type
            if entity_type == "deal":
                fields = await bitrix_service.get_deal_fields()
            else:
                fields = await bitrix_service.get_lead_fields()
            
            field_info = next((f for f in fields if f["id"] == request.bitrix24_field_id), None)
            if field_info:
                mapping.bitrix24_field_id = request.bitrix24_field_id
                mapping.bitrix24_field_name = field_info["name"]
                # Если display_name не был изменен вручную (равен старому bitrix24_field_name), обновляем его
                if mapping.display_name == mapping.bitrix24_field_name or not mapping.display_name:
                    mapping.display_name = field_info["name"]
        except Exception as e:
            logger.error(f"Error updating field info: {e}", exc_info=True)
            raise HTTPException(
                status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                detail=f"Failed to update field info: {str(e)}",
            )
    if request.entity_type is not None:
        if request.entity_type not in ["lead", "deal"]:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="entity_type must be 'lead' or 'deal'",
            )
        mapping.entity_type = request.entity_type
    if request.update_on_event is not None:
        mapping.update_on_event = request.update_on_event

    db.commit()
    db.refresh(mapping)

    return FieldMappingResponse(
        id=mapping.id,
        workflow_id=mapping.workflow_id,
        field_name=mapping.field_name,
        display_name=mapping.display_name,
        bitrix24_field_id=mapping.bitrix24_field_id,
        bitrix24_field_name=mapping.bitrix24_field_name,
        entity_type=mapping.entity_type,
        update_on_event=mapping.update_on_event,
        created_at=mapping.created_at.isoformat(),
    )


@router.delete("/{workflow_id}/fields/mapping/{mapping_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_field_mapping(
    workflow_id: int,
    mapping_id: int,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_main_db),
):
    """Delete field mapping (admin only)."""
    if current_user.role != "admin":
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Admin access required",
        )

    workflow = db.query(Workflow).filter(Workflow.id == workflow_id).first()
    if not workflow:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Workflow not found",
        )

    mapping = db.query(WorkflowFieldMapping).filter(
        WorkflowFieldMapping.id == mapping_id,
        WorkflowFieldMapping.workflow_id == workflow_id,
    ).first()
    
    if not mapping:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Field mapping not found",
        )

    db.delete(mapping)
    db.commit()


@router.post("/{workflow_id}/settings/generate-token", response_model=dict)
async def generate_api_token(
    workflow_id: int,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_main_db),
):
    """Generate or regenerate API token for public endpoint (admin only)."""
    if current_user.role != "admin":
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Admin access required",
        )

    workflow = db.query(Workflow).filter(Workflow.id == workflow_id).first()
    if not workflow:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Workflow not found",
        )

    import secrets
    new_token = secrets.token_urlsafe(32)
    workflow.api_token = new_token
    db.commit()
    db.refresh(workflow)

    return {"api_token": new_token}


class ConversionStatsResponse(BaseModel):
    """Conversion statistics response model."""

    total: int
    successful: int
    percentage: float


@router.get("/{workflow_id}/stats/conversion", response_model=ConversionStatsResponse)
async def get_conversion_stats(
    workflow_id: int,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_main_db),
):
    """Get conversion statistics for a workflow."""
    workflow = db.query(Workflow).filter(Workflow.id == workflow_id).first()
    if not workflow:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Workflow not found",
        )

    # Check access: user can access workflow if they created it, have access to it, or are admin
    has_access = (
        current_user.role == "admin"
        or workflow.user_id == current_user.id
        or workflow in current_user.accessible_workflows
    )
    
    if not has_access:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Access denied",
        )

    # Get leads from workflow database
    workflow_db = next(database_service.get_workflow_session(workflow_id))
    try:
        total_leads = workflow_db.query(Lead).count()
        successful_leads = workflow_db.query(Lead).filter(Lead.status_semantic_id == 'S').count()
        
        percentage = 0.0
        if total_leads > 0:
            percentage = round((successful_leads / total_leads) * 100, 2)
        
        return ConversionStatsResponse(
            total=total_leads,
            successful=successful_leads,
            percentage=percentage
        )
    finally:
        workflow_db.close()

