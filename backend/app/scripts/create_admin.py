"""CLI bootstrap script to create the first administrative user in DARKTRACE.

Usage:
  # Interactive mode:
  python -m app.scripts.create_admin

  # Non-interactive / scripted mode:
  python -m app.scripts.create_admin --email admin@darktrace.local --username admin --full-name "Chief Admin" --password "ChangeMe123!"
"""

import argparse
import getpass
import sys
from email_validator import EmailNotValidError, validate_email
from sqlalchemy import func, select

from app.core.security import hash_password, validate_password_policy
from app.db.session import SessionLocal
from app.models.user import User, UserRole


def parse_arguments() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Bootstrap or create an administrator account in DARKTRACE."
    )
    parser.add_argument("--email", help="Administrator email address")
    parser.add_argument("--username", help="Administrator username")
    parser.add_argument("--full-name", help="Administrator full name")
    parser.add_argument("--password", help="Administrator password (insecure via history; prefer interactive prompt)")
    return parser.parse_args()


def main() -> None:
    args = parse_arguments()
    print("=" * 60)
    print(" DARKTRACE Administrator Provisioning")
    print("=" * 60)

    # 1. Collect Email
    email = (args.email or "").strip()
    if not email:
        try:
            email = input("Enter admin email: ").strip()
        except (KeyboardInterrupt, EOFError):
            print("\nAborted.")
            sys.exit(1)

    try:
        valid_email_info = validate_email(email, check_deliverability=False)
        email = valid_email_info.normalized
    except EmailNotValidError as exc:
        print(f"Error: Invalid email format ({exc}).")
        sys.exit(1)

    # 2. Collect Username
    username = (args.username or "").strip()
    if not username:
        try:
            username = input("Enter admin username: ").strip()
        except (KeyboardInterrupt, EOFError):
            print("\nAborted.")
            sys.exit(1)

    if len(username) < 3:
        print("Error: Username must be at least 3 characters long.")
        sys.exit(1)

    # 3. Collect Full Name
    full_name = (args.full_name or "").strip()
    if not full_name:
        try:
            full_name = input("Enter admin full name: ").strip()
        except (KeyboardInterrupt, EOFError):
            print("\nAborted.")
            sys.exit(1)

    if not full_name:
        print("Error: Full name is required.")
        sys.exit(1)

    # 4. Collect Password
    password = args.password
    if not password:
        try:
            password = getpass.getpass("Enter password (min 10 chars, letters & digits): ")
            confirm = getpass.getpass("Confirm password: ")
        except (KeyboardInterrupt, EOFError):
            print("\nAborted.")
            sys.exit(1)

        if password != confirm:
            print("Error: Passwords do not match.")
            sys.exit(1)

    # 5. Enforce Password Policy
    is_compliant, policy_err = validate_password_policy(password, username=username, email=email)
    if not is_compliant:
        print(f"Error: Password policy violation - {policy_err}")
        sys.exit(1)

    # 6. Database Verification & Creation
    db = SessionLocal()
    try:
        norm_email = email.lower()
        norm_username = username.lower()

        stmt = select(User).where(
            (func.lower(User.email) == norm_email) | (func.lower(User.username) == norm_username)
        )
        existing = db.execute(stmt).scalar_one_or_none()

        if existing:
            if existing.email.lower() == norm_email:
                print(f"Error: An account with email '{email}' already exists.")
            else:
                print(f"Error: An account with username '{username}' already exists.")
            sys.exit(1)

        hashed = hash_password(password)
        admin = User(
            email=email,
            username=username,
            full_name=full_name,
            role=UserRole.ADMIN,
            is_active=True,
            password_hash=hashed,
        )
        db.add(admin)
        db.commit()
        db.refresh(admin)

        print(f"\n[+] Administrator successfully provisioned!")
        print(f"    ID:       {admin.id}")
        print(f"    Username: {admin.username}")
        print(f"    Email:    {admin.email}")
        print(f"    Role:     {admin.role.value}")
        print("=" * 60)

    except Exception as exc:
        db.rollback()
        print(f"Database error while provisioning administrator: {exc}")
        sys.exit(1)
    finally:
        db.close()


if __name__ == "__main__":
    main()
