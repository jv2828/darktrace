"""Demo seed script for DARKTRACE.

Usage:
  python -m app.scripts.seed_demo

Creates:
  1. Demo investigator user (from DEMO_USERNAME, DEMO_EMAIL, DEMO_PASSWORD)
  2. Demo investigation: "Demo: Alpha marketplaces"
  3. Attaches the Alpha synthetic benchmark sample dataset to the investigation.

SAFETY:
  - Strictly refuses to run when APP_ENV=production.
  - Idempotent: safe to run multiple times.
  - Never prints the password.
"""

import os
import sys
from dotenv import load_dotenv

from sqlalchemy import select

from app.core.config import ROOT_DIR, settings
from app.core.security import hash_password, validate_password_policy
from app.db.session import SessionLocal
from app.models.investigation import Investigation, InvestigationStatus
from app.models.user import User, UserRole
from app.services.ingestion_service import load_sample_to_investigation

# Load root .env file if present
load_dotenv(ROOT_DIR / ".env")


def seed_demo_data() -> None:
    """Bootstrap demo investigator, demo investigation, and Alpha dataset."""
    if settings.APP_ENV.lower() == "production":
        print("ERROR: seed_demo is disabled in production environments (APP_ENV=production).")
        sys.exit(1)

    demo_username = os.environ.get("DEMO_USERNAME", "analyst").strip()
    demo_email = os.environ.get("DEMO_EMAIL", "analyst@darktrace.org").strip()
    demo_password = os.environ.get("DEMO_PASSWORD", "").strip()

    if not demo_password:
        print("ERROR: DEMO_PASSWORD environment variable is required to seed the demo user.")
        print("Please export DEMO_PASSWORD (e.g. DEMO_PASSWORD=DemoPassword123!) and re-run.")
        sys.exit(1)

    is_compliant, policy_err = validate_password_policy(
        demo_password, username=demo_username, email=demo_email
    )
    if not is_compliant:
        print(f"ERROR: DEMO_PASSWORD failed password policy: {policy_err}")
        sys.exit(1)

    db = SessionLocal()
    try:
        # 1. Get or create demo investigator
        user_stmt = select(User).where(
            (User.username == demo_username) | (User.email == demo_email)
        )
        user = db.execute(user_stmt).scalar_one_or_none()

        if not user:
            user = User(
                username=demo_username,
                email=demo_email,
                full_name="Demo Threat Intelligence Analyst",
                role=UserRole.INVESTIGATOR,
                is_active=True,
                password_hash=hash_password(demo_password),
            )
            db.add(user)
            db.commit()
            db.refresh(user)
            print(f"[+] Provisioned demo investigator: '{user.username}' (role: {user.role.value})")
        else:
            print(f"[*] Found existing demo user: '{user.username}' (id: {user.id})")

        # 2. Get or create demo investigation
        inv_title = "Demo: Alpha marketplaces"
        inv_stmt = select(Investigation).where(
            Investigation.title == inv_title,
            Investigation.created_by == user.id,
        )
        investigation = db.execute(inv_stmt).scalar_one_or_none()

        if not investigation:
            investigation = Investigation(
                title=inv_title,
                description="Demonstration case workspace seeded with the Alpha synthetic intelligence dataset.",
                status=InvestigationStatus.DRAFT,
                created_by=user.id,
            )
            db.add(investigation)
            db.commit()
            db.refresh(investigation)
            print(f"[+] Created demo investigation: '{investigation.title}' (id: {investigation.id})")
        else:
            print(f"[*] Found existing demo investigation: '{investigation.title}' (id: {investigation.id})")

        # 3. Load Alpha sample dataset and attach to investigation
        load_result = load_sample_to_investigation(
            db=db,
            user=user,
            investigation_id=investigation.id,
            sample_key="alpha",
        )
        print(f"[+] Alpha dataset attached to investigation {investigation.id}:")
        print(f"    Dataset ID:   {load_result['dataset_id']}")
        print(f"    Posts loaded: {load_result['imported']}")
        print(f"    New actors:   {load_result['new_actors']}")
        print(f"    New markets:  {load_result['new_marketplaces']}")
        print("\nDemo seeding completed successfully.")

    except Exception as exc:
        db.rollback()
        print(f"ERROR: Failed to seed demo data: {exc}")
        sys.exit(1)
    finally:
        db.close()


if __name__ == "__main__":
    seed_demo_data()
