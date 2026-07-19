import logging
from sqlalchemy.orm import Session
from app.database.session import SessionLocal
from app.repositories.user import user_repo
from app.schemas.user import UserCreate

logger = logging.getLogger(__name__)


def seed_db(db: Session) -> None:
    """Seed the database with initial data (e.g., admin user)."""
    admin_email = "admin@example.com"
    admin_user = user_repo.get_by_email(db, email=admin_email)
    
    if not admin_user:
        logger.info(f"Seeding database with default admin user: {admin_email}")
        user_in = UserCreate(
            email=admin_email,
            password="adminpassword",
            full_name="Admin User",
            is_superuser=True,
            is_active=True,
        )
        user_repo.create(db, obj_in=user_in)
        logger.info("Admin user created successfully.")
    else:
        logger.info("Admin user already exists. Skipping seeding.")


def main() -> None:
    logging.basicConfig(level=logging.INFO)
    db = SessionLocal()
    try:
        seed_db(db)
    finally:
        db.close()


if __name__ == "__main__":
    main()
