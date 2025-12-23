"""Database migration script for updating workflows table schema."""
import sqlite3
from pathlib import Path

from src.backend.core.config import settings
from src.backend.utils.bitrix24_url import extract_domain_from_webhook_url


def migrate_workflow_settings():
    """Migrate workflows table to add settings fields."""
    db_path = Path(settings.MAIN_DB_URL.replace("sqlite:///", ""))
    
    if not db_path.exists():
        print(f"Database file {db_path} does not exist. Skipping migration.")
        return
    
    conn = sqlite3.connect(str(db_path))
    cursor = conn.cursor()
    
    try:
        # Check if columns already exist
        cursor.execute("PRAGMA table_info(workflows)")
        columns = [row[1] for row in cursor.fetchall()]
        
        columns_to_add = []
        if "entity_type" not in columns:
            columns_to_add.append(("entity_type", "VARCHAR NOT NULL DEFAULT 'lead'"))
        if "deal_category_id" not in columns:
            columns_to_add.append(("deal_category_id", "INTEGER"))
        if "deal_stage_id" not in columns:
            columns_to_add.append(("deal_stage_id", "VARCHAR"))
        if "lead_status_id" not in columns:
            columns_to_add.append(("lead_status_id", "VARCHAR DEFAULT 'NEW'"))
        
        if not columns_to_add:
            print("Migration already applied. Settings columns exist.")
            return
        
        print("Migrating workflows table to add settings fields...")
        
        # Add new columns
        for column_name, column_def in columns_to_add:
            cursor.execute(f"ALTER TABLE workflows ADD COLUMN {column_name} {column_def}")
        
        # Update existing workflows to have default values
        cursor.execute("""
            UPDATE workflows 
            SET entity_type = 'lead', lead_status_id = 'NEW'
            WHERE entity_type IS NULL OR entity_type = ''
        """)
        
        conn.commit()
        print(f"Migration completed. Added {len(columns_to_add)} columns.")
        
    except Exception as e:
        conn.rollback()
        print(f"Migration failed: {e}")
        raise
    finally:
        conn.close()


def migrate_workflows_table():
    """Migrate workflows table to use bitrix24_webhook_url instead of separate fields."""
    db_path = Path(settings.MAIN_DB_URL.replace("sqlite:///", ""))
    
    if not db_path.exists():
        print(f"Database file {db_path} does not exist. Skipping migration.")
        return
    
    conn = sqlite3.connect(str(db_path))
    cursor = conn.cursor()
    
    try:
        # Check if new column already exists
        cursor.execute("PRAGMA table_info(workflows)")
        columns = [row[1] for row in cursor.fetchall()]
        
        if "bitrix24_webhook_url" in columns:
            print("Migration already applied. bitrix24_webhook_url column exists.")
            return
        
        # Check if old columns exist
        has_old_columns = "bitrix24_portal_url" in columns and "bitrix24_webhook_token" in columns
        
        if has_old_columns:
            print("Migrating workflows table...")
            
            # Create new table with updated schema
            cursor.execute("""
                CREATE TABLE workflows_new (
                    id INTEGER PRIMARY KEY,
                    name VARCHAR NOT NULL,
                    bitrix24_webhook_url VARCHAR NOT NULL,
                    user_id INTEGER NOT NULL,
                    created_at DATETIME NOT NULL,
                    FOREIGN KEY(user_id) REFERENCES users(id)
                )
            """)
            
            # Migrate data: combine portal_url and token into webhook_url
            cursor.execute("""
                SELECT id, name, bitrix24_portal_url, bitrix24_webhook_token, user_id, created_at
                FROM workflows
            """)
            workflows = cursor.fetchall()
            
            for workflow in workflows:
                workflow_id, name, portal_url, token, user_id, created_at = workflow
                # Construct webhook URL: portal_url/rest/1/token/
                portal_url_clean = portal_url.rstrip("/")
                webhook_url = f"{portal_url_clean}/rest/1/{token}/"
                
                cursor.execute("""
                    INSERT INTO workflows_new (id, name, bitrix24_webhook_url, user_id, created_at)
                    VALUES (?, ?, ?, ?, ?)
                """, (workflow_id, name, webhook_url, user_id, created_at))
            
            # Drop old table and rename new one
            cursor.execute("DROP TABLE workflows")
            cursor.execute("ALTER TABLE workflows_new RENAME TO workflows")
            
            # Recreate indexes
            cursor.execute("CREATE INDEX ix_workflows_name ON workflows(name)")
            cursor.execute("CREATE INDEX ix_workflows_user_id ON workflows(user_id)")
            
            conn.commit()
            print(f"Migration completed. Migrated {len(workflows)} workflows.")
        else:
            # Old columns don't exist - check if table exists at all
            cursor.execute("SELECT name FROM sqlite_master WHERE type='table' AND name='workflows'")
            table_exists = cursor.fetchone() is not None
            
            if table_exists:
                # Table exists but without old columns - this shouldn't happen, but handle it
                print("Table exists but old columns are missing. Recreating table...")
                cursor.execute("DROP TABLE workflows")
                # Table will be recreated by init_main_db() with correct schema
                conn.commit()
                print("Migration completed. Table will be recreated with correct schema.")
            else:
                # Table doesn't exist - will be created by init_main_db() with correct schema
                print("Table doesn't exist. Will be created with correct schema by init_main_db().")
                conn.commit()
            
    except Exception as e:
        conn.rollback()
        print(f"Migration failed: {e}")
        raise
    finally:
        conn.close()


def migrate_workflow_app_token():
    """Migrate workflows table to add app_token and bitrix24_domain fields."""
    db_path = Path(settings.MAIN_DB_URL.replace("sqlite:///", ""))
    
    if not db_path.exists():
        print(f"Database file {db_path} does not exist. Skipping migration.")
        return
    
    conn = sqlite3.connect(str(db_path))
    cursor = conn.cursor()
    
    try:
        # Check if columns already exist
        cursor.execute("PRAGMA table_info(workflows)")
        columns = [row[1] for row in cursor.fetchall()]
        
        columns_to_add = []
        if "app_token" not in columns:
            columns_to_add.append(("app_token", "VARCHAR"))
        if "bitrix24_domain" not in columns:
            columns_to_add.append(("bitrix24_domain", "VARCHAR"))
        
        if not columns_to_add:
            print("Migration already applied. app_token and bitrix24_domain columns exist.")
            return
        
        print("Migrating workflows table to add app_token and bitrix24_domain fields...")
        
        # Add new columns
        for column_name, column_def in columns_to_add:
            cursor.execute(f"ALTER TABLE workflows ADD COLUMN {column_name} {column_def}")
        
        # Extract and update bitrix24_domain from existing webhook URLs
        cursor.execute("SELECT id, bitrix24_webhook_url FROM workflows WHERE bitrix24_webhook_url IS NOT NULL")
        workflows = cursor.fetchall()
        
        updated_count = 0
        for workflow_id, webhook_url in workflows:
            try:
                domain = extract_domain_from_webhook_url(webhook_url)
                cursor.execute(
                    "UPDATE workflows SET bitrix24_domain = ? WHERE id = ?",
                    (domain, workflow_id)
                )
                updated_count += 1
            except Exception as e:
                print(f"Warning: Failed to extract domain from webhook URL for workflow {workflow_id}: {e}")
        
        # Create index on bitrix24_domain for faster lookups
        try:
            cursor.execute("CREATE INDEX IF NOT EXISTS ix_workflows_bitrix24_domain ON workflows(bitrix24_domain)")
        except Exception as e:
            print(f"Warning: Failed to create index on bitrix24_domain: {e}")
        
        conn.commit()
        print(f"Migration completed. Added {len(columns_to_add)} columns. Updated {updated_count} workflows with domain.")
        
    except Exception as e:
        conn.rollback()
        print(f"Migration failed: {e}")
        raise
    finally:
        conn.close()


def migrate_workflow_api_token():
    """Migrate workflows table to add api_token field."""
    db_path = Path(settings.MAIN_DB_URL.replace("sqlite:///", ""))
    
    if not db_path.exists():
        print(f"Database file {db_path} does not exist. Skipping migration.")
        return
    
    conn = sqlite3.connect(str(db_path))
    cursor = conn.cursor()
    
    try:
        # Check if column already exists
        cursor.execute("PRAGMA table_info(workflows)")
        columns = [row[1] for row in cursor.fetchall()]
        
        if "api_token" in columns:
            print("Migration already applied. api_token column exists.")
            return
        
        print("Migrating workflows table to add api_token field...")
        
        # Add api_token column
        cursor.execute("ALTER TABLE workflows ADD COLUMN api_token VARCHAR")
        
        # Create unique index on api_token
        try:
            cursor.execute("CREATE UNIQUE INDEX IF NOT EXISTS ix_workflows_api_token ON workflows(api_token)")
        except Exception as e:
            print(f"Warning: Failed to create index on api_token: {e}")
        
        conn.commit()
        print("Migration completed. Added api_token column.")
        
    except Exception as e:
        conn.rollback()
        print(f"Migration failed: {e}")
        raise
    finally:
        conn.close()


def migrate_workflow_field_mapping():
    """Create workflow_field_mappings table in main database."""
    db_path = Path(settings.MAIN_DB_URL.replace("sqlite:///", ""))
    
    if not db_path.exists():
        print(f"Database file {db_path} does not exist. Skipping migration.")
        return
    
    conn = sqlite3.connect(str(db_path))
    cursor = conn.cursor()
    
    try:
        # Check if table already exists
        cursor.execute("SELECT name FROM sqlite_master WHERE type='table' AND name='workflow_field_mappings'")
        table_exists = cursor.fetchone() is not None
        
        if not table_exists:
            print("Creating workflow_field_mappings table...")
            
            # Create table
            cursor.execute("""
                CREATE TABLE workflow_field_mappings (
                    id INTEGER PRIMARY KEY,
                    workflow_id INTEGER NOT NULL,
                    field_name VARCHAR NOT NULL,
                    display_name VARCHAR NOT NULL,
                    bitrix24_field_id VARCHAR NOT NULL,
                    bitrix24_field_name VARCHAR NOT NULL,
                    entity_type VARCHAR NOT NULL,
                    created_at DATETIME NOT NULL,
                    FOREIGN KEY(workflow_id) REFERENCES workflows(id)
                )
            """)
            
            # Create indexes
            cursor.execute("CREATE INDEX ix_workflow_field_mappings_workflow_id ON workflow_field_mappings(workflow_id)")
            
            conn.commit()
            print("Migration completed. Created workflow_field_mappings table.")
        else:
            # Table exists, check if display_name column exists
            cursor.execute("PRAGMA table_info(workflow_field_mappings)")
            columns = [row[1] for row in cursor.fetchall()]
            
            if "display_name" not in columns:
                print("Adding display_name column to workflow_field_mappings table...")
                cursor.execute("ALTER TABLE workflow_field_mappings ADD COLUMN display_name VARCHAR NOT NULL DEFAULT ''")
                
                # Update existing rows: use bitrix24_field_name as display_name if display_name is empty
                cursor.execute("""
                    UPDATE workflow_field_mappings 
                    SET display_name = bitrix24_field_name 
                    WHERE display_name = '' OR display_name IS NULL
                """)
                
                conn.commit()
                print("Migration completed. Added display_name column.")
            else:
                print("Migration already applied. workflow_field_mappings table and display_name column exist.")
            
            # Check if update_on_event column exists
            if "update_on_event" not in columns:
                print("Adding update_on_event column to workflow_field_mappings table...")
                cursor.execute("ALTER TABLE workflow_field_mappings ADD COLUMN update_on_event BOOLEAN NOT NULL DEFAULT 0")
                conn.commit()
                print("Migration completed. Added update_on_event column.")
            else:
                print("Migration already applied. update_on_event column exists.")
        
    except Exception as e:
        conn.rollback()
        print(f"Migration failed: {e}")
        raise
    finally:
        conn.close()


def migrate_lead_assigned_by_and_semantic():
    """Migrate all workflow databases to add assigned_by_name and status_semantic_id fields to leads table."""
    workflows_dir = Path(settings.WORKFLOWS_DIR)
    
    if not workflows_dir.exists():
        print(f"Workflows directory {workflows_dir} does not exist. Skipping migration.")
        return
    
    print("Migrating workflow databases to add assigned_by_name and status_semantic_id fields...")
    
    migrated_count = 0
    skipped_count = 0
    
    # Iterate through all workflow directories
    for workflow_dir in workflows_dir.iterdir():
        if not workflow_dir.is_dir():
            continue
        
        db_path = workflow_dir / "database.db"
        if not db_path.exists():
            skipped_count += 1
            continue
        
        try:
            conn = sqlite3.connect(str(db_path))
            cursor = conn.cursor()
            
            # Check if table exists
            cursor.execute("SELECT name FROM sqlite_master WHERE type='table' AND name='leads'")
            if not cursor.fetchone():
                conn.close()
                skipped_count += 1
                continue
            
            # Check if columns already exist
            cursor.execute("PRAGMA table_info(leads)")
            columns = [row[1] for row in cursor.fetchall()]
            
            columns_to_add = []
            if "assigned_by_name" not in columns:
                columns_to_add.append(("assigned_by_name", "VARCHAR"))
            if "status_semantic_id" not in columns:
                columns_to_add.append(("status_semantic_id", "VARCHAR"))
            
            if not columns_to_add:
                conn.close()
                skipped_count += 1
                continue
            
            # Add new columns
            for column_name, column_def in columns_to_add:
                cursor.execute(f"ALTER TABLE leads ADD COLUMN {column_name} {column_def}")
            
            conn.commit()
            conn.close()
            migrated_count += 1
            print(f"Migrated workflow database: {workflow_dir.name}")
            
        except Exception as e:
            print(f"Warning: Failed to migrate workflow database {workflow_dir.name}: {e}")
            try:
                conn.close()
            except:
                pass
    
    print(f"Migration completed. Migrated {migrated_count} databases, skipped {skipped_count}.")


def migrate_user_workflow_access():
    """Create user_workflow_access table for many-to-many relationship between users and workflows."""
    db_path = Path(settings.MAIN_DB_URL.replace("sqlite:///", ""))
    
    if not db_path.exists():
        print(f"Database file {db_path} does not exist. Skipping migration.")
        return
    
    conn = sqlite3.connect(str(db_path))
    cursor = conn.cursor()
    
    try:
        # Check if table already exists
        cursor.execute("SELECT name FROM sqlite_master WHERE type='table' AND name='user_workflow_access'")
        table_exists = cursor.fetchone() is not None
        
        if not table_exists:
            print("Creating user_workflow_access table...")
            
            # Create table
            cursor.execute("""
                CREATE TABLE user_workflow_access (
                    user_id INTEGER NOT NULL,
                    workflow_id INTEGER NOT NULL,
                    PRIMARY KEY (user_id, workflow_id),
                    FOREIGN KEY(user_id) REFERENCES users(id),
                    FOREIGN KEY(workflow_id) REFERENCES workflows(id)
                )
            """)
            
            # Create indexes
            cursor.execute("CREATE INDEX IF NOT EXISTS ix_user_workflow_access_user_id ON user_workflow_access(user_id)")
            cursor.execute("CREATE INDEX IF NOT EXISTS ix_user_workflow_access_workflow_id ON user_workflow_access(workflow_id)")
            
            conn.commit()
            print("Migration completed. Created user_workflow_access table.")
        else:
            print("Migration already applied. user_workflow_access table exists.")
        
    except Exception as e:
        conn.rollback()
        print(f"Migration failed: {e}")
        raise
    finally:
        conn.close()


if __name__ == "__main__":
    migrate_workflows_table()
    migrate_workflow_settings()
    migrate_workflow_app_token()
    migrate_workflow_api_token()
    migrate_workflow_field_mapping()
    migrate_lead_assigned_by_and_semantic()
    migrate_user_workflow_access()

