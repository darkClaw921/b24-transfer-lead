"""Lead management endpoints."""
import csv
import io
import json
from typing import Any

from fastapi import APIRouter, Depends, File, Form, HTTPException, Response, UploadFile, status
from pydantic import BaseModel, ConfigDict
from sqlalchemy.orm import Session

from src.backend.api.v1.dependencies import get_current_user
from src.backend.core.database import get_main_db
from src.backend.models.lead import Lead
from src.backend.models.lead_field import LeadField
from src.backend.models.workflow import Workflow
from src.backend.models.workflow_field_mapping import WorkflowFieldMapping
from src.backend.models.user import User
from src.backend.services.database import database_service
from src.backend.services.bitrix24 import Bitrix24Service
from src.backend.utils.csv_parser import parse_csv_leads

router = APIRouter()


class CreateLeadRequest(BaseModel):
    """Create lead request model."""

    phone: str
    name: str
    # Additional fields can be passed as dict[str, Any]
    # They will be mapped using WorkflowFieldMapping
    
    model_config = ConfigDict(extra='allow')


class LeadFieldResponse(BaseModel):
    """Lead field response model."""

    field_name: str
    field_value: str

    class Config:
        from_attributes = True


class LeadResponse(BaseModel):
    """Lead response model."""

    id: int
    phone: str
    name: str
    status: str | None
    bitrix24_lead_id: str | None
    assigned_by_name: str | None  # Имя и фамилия ответственного
    status_semantic_id: str | None  # Семантический ID статуса (S/F)
    created_at: str
    updated_at: str
    fields: list[LeadFieldResponse] = []  # Additional fields

    class Config:
        from_attributes = True


@router.get("/{workflow_id}/leads", response_model=list[LeadResponse])
async def list_leads(
    workflow_id: int,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_main_db),
):
    """List leads for a workflow."""
    # Verify workflow access
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
    leads = workflow_db.query(Lead).all()

    result = []
    for lead in leads:
        # Get additional fields for this lead
        lead_fields = workflow_db.query(LeadField).filter(LeadField.lead_id == lead.id).all()
        fields = [
            LeadFieldResponse(field_name=lf.field_name, field_value=lf.field_value)
            for lf in lead_fields
        ]
        
        result.append(
            LeadResponse(
                id=lead.id,
                phone=lead.phone,
                name=lead.name,
                status=lead.status,
                bitrix24_lead_id=lead.bitrix24_lead_id,
                assigned_by_name=lead.assigned_by_name,
                status_semantic_id=lead.status_semantic_id,
                created_at=lead.created_at.isoformat(),
                updated_at=lead.updated_at.isoformat(),
                fields=fields,
            )
        )
    
    workflow_db.close()
    return result


@router.post("/{workflow_id}/leads", response_model=LeadResponse, status_code=status.HTTP_201_CREATED)
async def create_lead(
    workflow_id: int,
    request: CreateLeadRequest,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_main_db),
):
    """Create a new lead."""
    # Verify workflow access
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

    # Get field mappings for this workflow
    mappings = db.query(WorkflowFieldMapping).filter(
        WorkflowFieldMapping.workflow_id == workflow_id,
        WorkflowFieldMapping.entity_type == workflow.entity_type,
    ).all()
    
    # Create mapping dict: field_name -> bitrix24_field_id
    field_mapping = {mapping.field_name: mapping.bitrix24_field_id for mapping in mappings}
    
    # Extract additional fields from request (exclude name and phone)
    request_dict = request.model_dump()
    extra_fields_data = {k: v for k, v in request_dict.items() if k not in ["name", "phone"]}
    
    # Prepare extra fields for Bitrix24 (only mapped fields)
    bitrix24_extra_fields: dict[str, Any] = {}
    lead_fields_to_save: list[tuple[str, str]] = []
    
    for field_name, field_value in extra_fields_data.items():
        if field_name in field_mapping:
            bitrix24_field_id = field_mapping[field_name]
            bitrix24_extra_fields[bitrix24_field_id] = field_value
            lead_fields_to_save.append((field_name, str(field_value)))

    # Create lead in workflow database
    workflow_db = next(database_service.get_workflow_session(workflow_id))
    lead = Lead(phone=request.phone, name=request.name, status="NEW")
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
                request.name, request.phone, category_id, stage_id, extra_fields=bitrix24_extra_fields
            )
        else:
            # Create lead (default)
            status_id = workflow.lead_status_id if workflow.lead_status_id else "NEW"
            bitrix_entity_id = await bitrix_service.create_lead(
                request.name, request.phone, status_id, extra_fields=bitrix24_extra_fields
            )
        
        lead.bitrix24_lead_id = str(bitrix_entity_id)
        workflow_db.commit()
    except Exception as e:
        # Log error but don't fail the request
        print(f"Error creating {entity_type} in Bitrix24: {e}")
    
    # Get additional fields for response
    lead_fields_query = workflow_db.query(LeadField).filter(LeadField.lead_id == lead.id).all()
    fields = [
        LeadFieldResponse(field_name=lf.field_name, field_value=lf.field_value)
        for lf in lead_fields_query
    ]
    
    # Save attribute values before closing session
    lead_id = lead.id
    lead_phone = lead.phone
    lead_name = lead.name
    lead_status = lead.status
    lead_bitrix_id = lead.bitrix24_lead_id
    lead_assigned_by_name = lead.assigned_by_name
    lead_status_semantic_id = lead.status_semantic_id
    lead_created_at = lead.created_at.isoformat()
    lead_updated_at = lead.updated_at.isoformat()
    
    workflow_db.close()

    return LeadResponse(
        id=lead_id,
        phone=lead_phone,
        name=lead_name,
        status=lead_status,
        bitrix24_lead_id=lead_bitrix_id,
        assigned_by_name=lead_assigned_by_name,
        status_semantic_id=lead_status_semantic_id,
        created_at=lead_created_at,
        updated_at=lead_updated_at,
        fields=fields,
    )


@router.post("/{workflow_id}/leads/upload", response_model=list[LeadResponse], status_code=status.HTTP_201_CREATED)
async def upload_leads_csv(
    workflow_id: int,
    file: UploadFile = File(...),
    column_mapping: str | None = Form(None),
    limit: str | None = Form(None),
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_main_db),
):
    """Upload leads from CSV file.
    
    Args:
        workflow_id: ID of the workflow
        file: CSV file to upload
        column_mapping: Optional JSON string mapping CSV column names to field names
                        (e.g., '{"Email": "email", "Company": "company"}')
        limit: Optional limit on number of rows to process (if None, processes all rows)
    """
    # Verify workflow access
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

    # Parse column mapping if provided
    column_mapping_dict: dict[str, str] | None = None
    if column_mapping:
        try:
            column_mapping_dict = json.loads(column_mapping)
        except json.JSONDecodeError:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Invalid column_mapping JSON format",
            )

    # Parse limit if provided
    limit_int: int | None = None
    if limit:
        try:
            limit_int = int(limit)
            if limit_int < 1:
                raise HTTPException(
                    status_code=status.HTTP_400_BAD_REQUEST,
                    detail="limit must be a positive integer",
                )
        except ValueError:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Invalid limit format",
            )

    # Parse CSV
    content = await file.read()
    leads_data = parse_csv_leads(content.decode("utf-8"), column_mapping=column_mapping_dict)
    
    # Apply limit if specified
    if limit_int is not None:
        leads_data = leads_data[:limit_int]

    # Get field mappings for this workflow
    mappings = db.query(WorkflowFieldMapping).filter(
        WorkflowFieldMapping.workflow_id == workflow_id,
        WorkflowFieldMapping.entity_type == workflow.entity_type,
    ).all()
    
    # Create mapping dict: field_name -> bitrix24_field_id
    field_mapping = {mapping.field_name: mapping.bitrix24_field_id for mapping in mappings}

    # Create leads
    workflow_db = next(database_service.get_workflow_session(workflow_id))
    bitrix_service = Bitrix24Service(workflow.bitrix24_webhook_url)
    created_leads = []
    entity_type = workflow.entity_type or "lead"

    for lead_data in leads_data:
        # Extract base fields and additional fields
        phone = lead_data.get("phone", "")
        name = lead_data.get("name", "")
        extra_fields_data = {k: v for k, v in lead_data.items() if k not in ["name", "phone"]}
        
        # Prepare extra fields for Bitrix24 (only mapped fields)
        bitrix24_extra_fields: dict[str, Any] = {}
        lead_fields_to_save: list[tuple[str, str]] = []
        
        for field_name, field_value in extra_fields_data.items():
            if field_name in field_mapping:
                bitrix24_field_id = field_mapping[field_name]
                bitrix24_extra_fields[bitrix24_field_id] = field_value
                lead_fields_to_save.append((field_name, str(field_value)))
        
        lead = Lead(phone=phone, name=name, status="NEW")
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
            if entity_type == "deal":
                # Create deal
                category_id = workflow.deal_category_id if workflow.deal_category_id is not None else 0
                stage_id = workflow.deal_stage_id if workflow.deal_stage_id else "NEW"
                bitrix_entity_id = await bitrix_service.create_deal(
                    name, phone, category_id, stage_id, extra_fields=bitrix24_extra_fields
                )
            else:
                # Create lead (default)
                status_id = workflow.lead_status_id if workflow.lead_status_id else "NEW"
                bitrix_entity_id = await bitrix_service.create_lead(
                    name, phone, status_id, extra_fields=bitrix24_extra_fields
                )
            
            lead.bitrix24_lead_id = str(bitrix_entity_id)
            workflow_db.commit()
        except Exception as e:
            print(f"Error creating {entity_type} in Bitrix24: {e}")

        created_leads.append(lead)

    result = []
    for lead in created_leads:
        # Get additional fields for this lead
        lead_fields = workflow_db.query(LeadField).filter(LeadField.lead_id == lead.id).all()
        fields = [
            LeadFieldResponse(field_name=lf.field_name, field_value=lf.field_value)
            for lf in lead_fields
        ]
        
        result.append(
            LeadResponse(
                id=lead.id,
                phone=lead.phone,
                name=lead.name,
                status=lead.status,
                bitrix24_lead_id=lead.bitrix24_lead_id,
                assigned_by_name=lead.assigned_by_name,
                status_semantic_id=lead.status_semantic_id,
                created_at=lead.created_at.isoformat(),
                updated_at=lead.updated_at.isoformat(),
                fields=fields,
            )
        )
    
    workflow_db.close()
    return result


@router.get("/{workflow_id}/leads/export")
async def export_leads_csv(
    workflow_id: int,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_main_db),
):
    """Export leads to CSV file."""
    # Verify workflow access
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
    leads = workflow_db.query(Lead).all()

    # Get field mappings for column headers
    mappings = db.query(WorkflowFieldMapping).filter(
        WorkflowFieldMapping.workflow_id == workflow_id,
        WorkflowFieldMapping.entity_type == workflow.entity_type,
    ).all()
    
    # Create mapping dict: field_name -> display_name
    field_display_names = {}
    for mapping in mappings:
        display_name = mapping.display_name.strip() if mapping.display_name else mapping.bitrix24_field_name
        field_display_names[mapping.field_name] = display_name

    # Get status map for display
    status_map: dict[str, str] = {}
    try:
        bitrix_service = Bitrix24Service(workflow.bitrix24_webhook_url)
        entity_type = workflow.entity_type or "lead"
        
        if entity_type == "deal":
            category_id = workflow.deal_category_id if workflow.deal_category_id is not None else 0
            statuses = await bitrix_service.get_deal_stages(category_id)
        else:
            statuses = await bitrix_service.get_lead_statuses()
        
        for status in statuses:
            status_map[status["id"]] = status["name"]
    except Exception as e:
        print(f"Error loading status map: {e}")

    # Get all unique field names from leads
    all_field_names = set()
    for lead in leads:
        lead_fields = workflow_db.query(LeadField).filter(LeadField.lead_id == lead.id).all()
        for field in lead_fields:
            all_field_names.add(field.field_name)

    # Build CSV headers
    headers = ["Имя", "Телефон", "Статус", "Ответственный", "Bitrix24 ID", "Создан"]
    # Add additional fields in order from mappings
    for mapping in mappings:
        if mapping.field_name in all_field_names:
            display_name = mapping.display_name.strip() if mapping.display_name else mapping.bitrix24_field_name
            headers.append(display_name)

    # Create CSV content
    output = io.StringIO()
    writer = csv.writer(output, delimiter=',', quoting=csv.QUOTE_MINIMAL)
    
    # Write headers
    writer.writerow(headers)
    
    # Write data rows
    for lead in leads:
        # Get status display name
        status_display = status_map.get(lead.status, lead.status) if lead.status else "NEW"
        
        # Get additional fields
        lead_fields = workflow_db.query(LeadField).filter(LeadField.lead_id == lead.id).all()
        field_dict = {field.field_name: field.field_value for field in lead_fields}
        
        # Build row
        row = [
            lead.name,
            lead.phone,
            status_display,
            lead.assigned_by_name or "",
            lead.bitrix24_lead_id or "",
            lead.created_at.strftime("%Y-%m-%d %H:%M:%S") if lead.created_at else "",
        ]
        
        # Add additional fields in order from mappings
        for mapping in mappings:
            if mapping.field_name in all_field_names:
                row.append(field_dict.get(mapping.field_name, ""))
        
        writer.writerow(row)
    
    workflow_db.close()
    
    # Return CSV file
    csv_content = output.getvalue()
    output.close()
    
    return Response(
        content=csv_content,
        media_type="text/csv",
        headers={
            "Content-Disposition": f'attachment; filename="leads_workflow_{workflow_id}.csv"'
        }
    )
