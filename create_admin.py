from src.backend.core.database import MainSessionLocal, init_main_db
from src.backend.models.user import User, UserRole
from src.backend.services.auth import AuthService
from dotenv import load_dotenv
import os
load_dotenv()

init_main_db()
db = MainSessionLocal()

user = AuthService.create_user(
    db, 
    username=os.getenv("ADMIN_USERNAME"), 
    password=os.getenv("ADMIN_PASSWORD"), 
    role=UserRole.ADMIN
)
print(f"Created admin user: {user.username}")