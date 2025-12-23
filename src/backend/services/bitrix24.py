"""Bitrix24 REST API service."""
import logging
from typing import Any

from fast_bitrix24 import BitrixAsync

from src.backend.utils.cache import lead_statuses_cache
from src.backend.utils.phone import format_phone_variants, normalize_phone

logger = logging.getLogger(__name__)


class Bitrix24Service:
    """Service for interacting with Bitrix24 REST API using fast-bitrix24."""

    def __init__(self, webhook_url: str):
        """Initialize Bitrix24 service.

        Args:
            webhook_url: Full Bitrix24 webhook URL (e.g., https://domain.bitrix24.ru/rest/1/token/)
        """
        # Ensure webhook URL ends with / for proper API calls
        self.webhook_url = webhook_url.rstrip("/") + "/"

    def _get_client(self) -> BitrixAsync:
        """Get Bitrix24 async client instance.

        Returns:
            BitrixAsync client instance
        """
        return BitrixAsync(self.webhook_url, respect_velocity_policy=True)

    async def add_contact_to_lead(self, lead_id: int, contact_id: int) -> bool:
        """Add contact to lead in Bitrix24.

        Args:
            lead_id: Lead ID
            contact_id: Contact ID

        Returns:
            True if successful
        """
        client = self._get_client()
        # Update lead with contact ID
        await client.call(
            "crm.lead.update",
            {
                "id": lead_id,
                "fields": {"CONTACT_ID": contact_id},
            },
        )
        logger.info(f"Added contact {contact_id} to lead {lead_id}")
        return True

    async def _get_user_field_info(self, field_id: str, entity_type: str = "CRM_LEAD") -> str | None:
        """Get user field title from Bitrix24 using crm.userfield.get.
        
        Args:
            field_id: User field ID (e.g., "UF_CRM_1763470519")
            entity_type: Entity type (CRM_LEAD, CRM_DEAL, etc.)
            
        Returns:
            Field title or None if not found
        """
        if not field_id.startswith("UF_CRM_"):
            return None
            
        client = self._get_client()
        try:
            # Используем crm.userfield.get для получения информации о пользовательском поле
            # Формат: {"id": field_id} - entityId определяется автоматически по полю
            result = await client.call("crm.userfield.get", {"id": field_id})
            
            if isinstance(result, dict):
                # Проверяем различные варианты названия
                # В Bitrix24 пользовательские поля имеют поле "LIST_LABEL" или "TITLE"
                title = (
                    result.get("LIST_LABEL") or
                    result.get("TITLE") or
                    result.get("title") or
                    result.get("listLabel") or
                    result.get("formLabel") or
                    result.get("label") or
                    result.get("name")
                )
                if title:
                    return title
        except Exception as e:
            logger.warning(f"Failed to get user field info for {field_id}: {e}")
        
        return None

    async def get_lead_fields(self) -> list[dict[str, Any]]:
        """Get list of lead fields from Bitrix24.

        Returns:
            List of fields with id, name, and type
        """
        client = self._get_client()
        # Use get_all() as recommended by fast-bitrix24 for .fields methods
        try:
            result = await client.get_all("crm.lead.fields", {})
        except Exception as e:
            logger.error(f"Failed to get lead fields: {e}")
            raise
        
        fields = []
        # get_all() returns a dict with field_id as key and field_info as value
        if isinstance(result, dict):
            for field_id, field_info in result.items():
                if isinstance(field_info, dict):
                    # Для пользовательских полей (UF_CRM_*) приоритет: listLabel -> formLabel -> title
                    # Для обычных полей: title -> name -> field_id
                    if field_id.startswith("UF_CRM_"):
                        # Пользовательские поля имеют listLabel и formLabel с человекочитаемыми названиями
                        field_name = (
                            field_info.get("listLabel") or
                            field_info.get("formLabel") or
                            field_info.get("filterLabel") or
                            field_info.get("title") or
                            field_id
                        )
                    else:
                        # Обычные поля используют title
                        field_name = (
                            field_info.get("title") or
                            field_info.get("name") or
                            field_id
                        )
                    
                    fields.append({
                        "id": field_id,
                        "name": field_name,
                        "type": field_info.get("type", "string"),
                    })
        
        logger.info(f"Retrieved {len(fields)} lead fields from Bitrix24")
        return fields

    async def get_deal_fields(self) -> list[dict[str, Any]]:
        """Get list of deal fields from Bitrix24.

        Returns:
            List of fields with id, name, and type
        """
        client = self._get_client()
        # Use get_all() as recommended by fast-bitrix24 for .fields methods
        try:
            result = await client.get_all("crm.deal.fields", {})
        except Exception as e:
            logger.error(f"Failed to get deal fields: {e}")
            raise
        
        fields = []
        # get_all() returns a dict with field_id as key and field_info as value
        if isinstance(result, dict):
            for field_id, field_info in result.items():
                if isinstance(field_info, dict):
                    # Для пользовательских полей (UF_CRM_*) приоритет: listLabel -> formLabel -> filterLabel -> title
                    # Для обычных полей: title -> name -> field_id
                    if field_id.startswith("UF_CRM_"):
                        # Пользовательские поля имеют listLabel и formLabel с человекочитаемыми названиями
                        # title для них равен ID, поэтому не используем его первым
                        field_name = (
                            field_info.get("listLabel") or
                            field_info.get("formLabel") or
                            field_info.get("filterLabel") or
                            field_info.get("title") or
                            field_id
                        )
                    else:
                        # Обычные поля используют title
                        field_name = (
                            field_info.get("title") or
                            field_info.get("name") or
                            field_id
                        )
                    
                    fields.append({
                        "id": field_id,
                        "name": field_name,
                        "type": field_info.get("type", "string"),
                    })
        
        logger.info(f"Retrieved {len(fields)} deal fields from Bitrix24")
        return fields

    async def create_lead(
        self,
        name: str,
        phone: str,
        status_id: str = "NEW",
        extra_fields: dict[str, Any] | None = None,
    ) -> int:
        """Create a lead in Bitrix24 with contact search/creation.

        Args:
            name: Lead name
            phone: Lead phone number
            status_id: Lead status ID (default: 'NEW')
            extra_fields: Additional fields to set in Bitrix24 (field_id -> value mapping)

        Returns:
            Created lead ID
        """
        # Search for existing contact by phone
        contact_id = await self.find_contact_by_phone(phone)
        
        # Create contact if not found
        if contact_id is None:
            contact_id = await self.create_contact(name, phone)

        normalized_phone = normalize_phone(phone)
        fields = {
            "TITLE": name,
            "NAME": name,
            "STATUS_ID": status_id,
            "PHONE": [{"VALUE": normalized_phone, "VALUE_TYPE": "WORK"}],
            "CONTACT_ID": contact_id,  # Link contact to lead
        }
        
        # Add extra fields if provided
        if extra_fields:
            fields.update(extra_fields)

        client = self._get_client()
        result = await client.call("crm.lead.add", {"fields": fields})
        lead_id = int(result) if isinstance(result, (int, str)) else result.get("id", result)
        logger.info(f"Created lead in Bitrix24 with ID: {lead_id}, linked to contact {contact_id}")
        return lead_id

    async def get_lead(self, lead_id: int) -> dict[str, Any]:
        """Get lead data from Bitrix24.

        Args:
            lead_id: Bitrix24 lead ID

        Returns:
            Lead data dictionary
        """
        client = self._get_client()
        result = await client.call("crm.lead.get", {"id": lead_id})
        if isinstance(result, dict):
            if result.get("order0000000000") is not None:
                return result.get("order0000000000")
            else:
                return result
        return None

    async def get_deal(self, deal_id: int) -> dict[str, Any]:
        """Get deal data from Bitrix24.

        Args:
            deal_id: Bitrix24 deal ID

        Returns:
            Deal data dictionary
        """
        client = self._get_client()
        result = await client.call("crm.deal.get", {"id": deal_id})
        if isinstance(result, dict):
            if result.get("order0000000000") is not None:
                return result.get("order0000000000")
            else:
                return result
        return None

    async def get_user(self, user_id: int) -> dict[str, Any] | None:
        """Get user data from Bitrix24.

        Args:
            user_id: Bitrix24 user ID

        Returns:
            User data dictionary with NAME and LAST_NAME fields, or None if not found
        """
        client = self._get_client()
        try:
            result = await client.call("user.get", {"id": user_id})
            if isinstance(result, dict):
                # Handle nested structure if present
                if result.get("order0000000000") is not None:
                    return result.get("order0000000000")
                else:
                    return result
            return None
        except Exception as e:
            logger.warning(f"Failed to get user {user_id} from Bitrix24: {e}")
            return None

    async def update_lead_status(self, lead_id: int, status_id: str) -> bool:
        """Update lead status in Bitrix24.

        Args:
            lead_id: Bitrix24 lead ID
            status_id: New status ID

        Returns:
            True if successful
        """
        fields = {"STATUS_ID": status_id}
        client = self._get_client()
        await client.call("crm.lead.update", {"id": lead_id, "fields": fields})
        logger.info(f"Updated lead {lead_id} status to {status_id}")
        return True

    async def get_deal_categories(self) -> list[dict[str, Any]]:
        """Get list of deal funnels (categories) from Bitrix24.

        Returns:
            List of funnels with id and name
        """
        client = self._get_client()
        
        # Try get_all() first - it may extract categories automatically
        try:
            result = await client.get_all("crm.category.list", {"entityTypeId": 2})
            logger.info(f"get_all() result (type: {type(result)}): {result}")
            
            # get_all() might return the categories list directly or nested structure
            if isinstance(result, list):
                categories = result
            elif isinstance(result, dict):
                # Check if get_all() extracted categories
                if "categories" in result:
                    categories = result["categories"]
                elif "result" in result:
                    nested = result["result"]
                    if isinstance(nested, dict) and "categories" in nested:
                        categories = nested["categories"]
                    elif isinstance(nested, list):
                        categories = nested
                    else:
                        categories = []
                else:
                    categories = []
            else:
                categories = []
        except Exception as e:
            logger.warning(f"get_all() failed: {e}, trying call()")
            # Fallback to call() if get_all() fails
            result = await client.call("crm.category.list", {"entityTypeId": 2})
            logger.info(f"call() result (type: {type(result)}): {result}")
            
            # Extract from standard Bitrix24 response: {"result": {"categories": [...], "total": N}}
            categories = []
            if isinstance(result, dict):
                if "result" in result:
                    nested_result = result["result"]
                    if isinstance(nested_result, dict) and "categories" in nested_result:
                        categories = nested_result["categories"]
                    elif isinstance(nested_result, list):
                        categories = nested_result
                elif "categories" in result:
                    categories = result["categories"]
            elif isinstance(result, list):
                categories = result
        
        logger.info(f"Extracted {len(categories)} categories: {categories}")
        
        # Extract id and name from categories
        funnels = []
        for cat in categories:
            if isinstance(cat, dict):
                cat_id = cat.get("id")
                cat_name = cat.get("name", "")
                if cat_id is not None:
                    funnels.append({"id": int(cat_id), "name": str(cat_name)})
        
        logger.info(f"Retrieved {len(funnels)} deal categories: {funnels}")
        return funnels

    async def get_lead_statuses(self) -> list[dict[str, Any]]:
        """Get list of lead statuses from Bitrix24.
        
        Использует кэширование на 1 день для уменьшения количества запросов к Bitrix24.
        Кэш привязан к webhook_url, так как разные порталы могут иметь разные статусы.

        Returns:
            List of statuses with STATUS_ID and NAME
        """
        # Используем webhook_url как ключ кэша
        cache_key = f"lead_statuses:{self.webhook_url}"
        
        # Проверяем кэш
        cached_statuses = lead_statuses_cache.get(cache_key)
        if cached_statuses is not None:
            logger.debug(f"Returning cached lead statuses for {self.webhook_url}")
            return cached_statuses
        
        # Если в кэше нет, делаем запрос к Bitrix24
        client = self._get_client()
        # Use get_all() for .list methods as recommended by fast-bitrix24
        result = await client.get_all("crm.status.list", {"filter": {"ENTITY_ID": "STATUS"}})
        
        # get_all() returns a list directly
        statuses = []
        if isinstance(result, list):
            statuses = [
                {"id": status.get("STATUS_ID"), "name": status.get("NAME", "")}
                for status in result
            ]
        
        # Сохраняем в кэш на 1 день
        if statuses:
            lead_statuses_cache.set(cache_key, statuses)
            logger.info(f"Cached {len(statuses)} lead statuses for {self.webhook_url}")
        
        return statuses

    async def get_deal_stages(self, category_id: int = 0) -> list[dict[str, Any]]:
        """Get list of deal stages for a specific funnel.

        Args:
            category_id: Funnel ID (0 for default funnel)

        Returns:
            List of stages with STATUS_ID and NAME
        """
        client = self._get_client()
        
        # For default funnel (category_id=0), use DEAL_STAGE
        # For custom funnels, use DEAL_STAGE_{category_id}
        entity_id = "DEAL_STAGE" if category_id == 0 else f"DEAL_STAGE_{category_id}"
        
        # Use get_all() for .list methods as recommended by fast-bitrix24
        result = await client.get_all("crm.status.list", {"filter": {"ENTITY_ID": entity_id}})
        
        # get_all() returns a list directly
        if isinstance(result, list):
            return [
                {"id": stage.get("STATUS_ID"), "name": stage.get("NAME", "")}
                for stage in result
            ]
        return []

    async def find_contact_by_phone(self, phone: str) -> int | None:
        """Find contact by phone number in Bitrix24.
        
        First normalizes the phone number, then generates all format variants,
        and searches using batch requests for all variants simultaneously.
        
        Args:
            phone: Phone number in any format
            
        Returns:
            Contact ID if found, None otherwise
        """
        import asyncio
        
        client = self._get_client()
        
        # Step 1: Normalize the phone number first
        normalized_search_phone = normalize_phone(phone)
        
        # Step 2: Generate all format variants from normalized phone
        phone_variants = format_phone_variants(normalized_search_phone)
        
        logger.info(f"Searching contact by phone: {phone} (normalized: {normalized_search_phone})")
        logger.debug(f"Phone variants to search: {phone_variants}")
        
        # Step 3: Create batch requests for all variants
        async def search_variant(variant: str) -> list[dict]:
            """Search for a single phone variant."""
            try:
                result = await client.get_all(
                    "crm.contact.list",
                    {
                        "filter": {"PHONE": variant},
                        "select": ["ID", "NAME", "LAST_NAME", "PHONE"],
                    },
                )
                return result if result else []
            except Exception as e:
                logger.debug(f"Search failed for variant '{variant}': {e}")
                return []
        
        # Execute all searches in parallel using asyncio.gather
        logger.info(f"Executing batch search for {len(phone_variants)} phone variants...")
        search_results = await asyncio.gather(*[search_variant(variant) for variant in phone_variants])
        
        # Process all results
        all_found_contacts = []
        for variant, results in zip(phone_variants, search_results):
            logger.info(f"Search for '{variant}' returned {len(results)} contacts")
            if results:
                all_found_contacts.extend(results)
        
        # Remove duplicates by contact ID
        seen_ids = set()
        unique_contacts = []
        for contact in all_found_contacts:
            contact_id = contact.get("ID")
            if contact_id and contact_id not in seen_ids:
                seen_ids.add(contact_id)
                unique_contacts.append(contact)
        
        logger.info(f"Found {len(unique_contacts)} unique contacts to verify")
        
        # Verify that contacts actually have the matching phone number
        for contact in unique_contacts:
            contact_id = contact.get("ID")
            contact_phones = contact.get("PHONE", [])
            
            logger.debug(f"Checking contact {contact_id} with phones: {contact_phones}")
            
            # Check if any phone in contact matches our normalized search phone
            for contact_phone in contact_phones:
                if isinstance(contact_phone, dict):
                    phone_value = contact_phone.get("VALUE", "")
                else:
                    phone_value = str(contact_phone)
                
                # Normalize both for comparison
                normalized_contact_phone = normalize_phone(phone_value)
                
                logger.debug(f"Comparing: search={normalized_search_phone}, contact={normalized_contact_phone} (from '{phone_value}')")
                
                if normalized_contact_phone == normalized_search_phone:
                    logger.info(f"✓ Found matching contact {contact_id} by phone {phone} (normalized: {normalized_search_phone})")
                    return int(contact_id)
        
        # If batch search didn't work, try local filtering as fallback
        logger.info("Batch search didn't find matching contact, trying local filtering approach...")
        try:
            # Get contacts and filter locally
            all_contacts = await client.get_all(
                "crm.contact.list",
                {
                    "select": ["ID", "NAME", "LAST_NAME", "PHONE"],
                },
            )
            
            logger.info(f"Fetched {len(all_contacts) if all_contacts else 0} contacts for local filtering")
            
            if all_contacts:
                # Filter contacts locally by comparing normalized phone numbers
                checked_count = 0
                for contact in all_contacts:
                    contact_id = contact.get("ID")
                    contact_phones = contact.get("PHONE", [])
                    
                    if not contact_phones:
                        continue
                    
                    checked_count += 1
                    if checked_count <= 10:  # Log first 10 contacts for debugging
                        logger.debug(f"Checking contact {contact_id} with phones: {contact_phones}")
                    
                    # Check if any phone in contact matches our search phone
                    for contact_phone in contact_phones:
                        if isinstance(contact_phone, dict):
                            phone_value = contact_phone.get("VALUE", "")
                        else:
                            phone_value = str(contact_phone)
                        
                        # Normalize both for comparison
                        normalized_contact_phone = normalize_phone(phone_value)
                        
                        if normalized_contact_phone == normalized_search_phone:
                            logger.info(f"✓ Found matching contact {contact_id} by phone {phone} (local filtering, checked {checked_count} contacts)")
                            return int(contact_id)
                
                logger.info(f"Checked {checked_count} contacts locally, no match found")
        except Exception as e:
            logger.warning(f"Local filtering approach failed: {e}")
        
        logger.info(f"✗ Contact not found by phone: {phone} (normalized: {normalized_search_phone})")
        return None

    async def create_contact(self, name: str, phone: str) -> int:
        """Create a contact in Bitrix24.

        Args:
            name: Contact name
            phone: Contact phone number

        Returns:
            Created contact ID
        """
        normalized_phone = normalize_phone(phone)
        # Add + prefix for Bitrix24 storage format
        phone_for_bitrix = f"+{normalized_phone}" if not normalized_phone.startswith("+") else normalized_phone
        
        # Split name into first and last name if possible
        name_parts = name.strip().split(maxsplit=1)
        first_name = name_parts[0] if name_parts else name
        last_name = name_parts[1] if len(name_parts) > 1 else ""

        fields = {
            "NAME": first_name,
            "LAST_NAME": last_name,
            "PHONE": [{"VALUE": phone_for_bitrix, "VALUE_TYPE": "WORK"}],
        }

        client = self._get_client()
        result = await client.call("crm.contact.add", {"fields": fields})
        contact_id = int(result) if isinstance(result, (int, str)) else result.get("id", result)
        logger.info(f"Created contact in Bitrix24 with ID: {contact_id}")
        return contact_id

    async def add_contact_to_deal(self, deal_id: int, contact_id: int) -> bool:
        """Add contact to deal in Bitrix24.

        Args:
            deal_id: Deal ID
            contact_id: Contact ID

        Returns:
            True if successful
        """
        client = self._get_client()
        await client.call(
            "crm.deal.contact.add",
            {
                "id": deal_id,
                "fields": {"CONTACT_ID": contact_id, "IS_PRIMARY": "Y"},
            },
        )
        logger.info(f"Added contact {contact_id} to deal {deal_id}")
        return True

    async def create_deal(
        self,
        name: str,
        phone: str,
        category_id: int = 0,
        stage_id: str = "NEW",
        extra_fields: dict[str, Any] | None = None,
    ) -> int:
        """Create a deal in Bitrix24 with contact search/creation.

        Args:
            name: Deal name
            phone: Contact phone number
            category_id: Funnel ID (default: 0 for default funnel)
            stage_id: Stage ID (default: 'NEW')
            extra_fields: Additional fields to set in Bitrix24 (field_id -> value mapping)

        Returns:
            Created deal ID
        """
        # Search for existing contact by phone
        contact_id = await self.find_contact_by_phone(phone)
        
        # Create contact if not found
        if contact_id is None:
            contact_id = await self.create_contact(name, phone)

        # Create deal
        fields = {
            "TITLE": name,
            "CATEGORY_ID": category_id,
            "STAGE_ID": stage_id,
        }
        
        # Add extra fields if provided
        if extra_fields:
            fields.update(extra_fields)

        client = self._get_client()
        result = await client.call("crm.deal.add", {"fields": fields})
        deal_id = int(result) if isinstance(result, (int, str)) else result.get("id", result)
        logger.info(f"Created deal in Bitrix24 with ID: {deal_id}")
        
        # Add contact to deal
        await self.add_contact_to_deal(deal_id, contact_id)
        
        return deal_id

