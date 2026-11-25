from argparse import ArgumentParser
from getpass import getpass

from pydantic import ValidationError
from sqlalchemy.orm import Session

from app.core.config import Settings
from app.db.models import Role
from app.db.session import create_database_engine
from app.schemas.auth import AccountInput
from app.services.auth import EmailInUse, add_user


def main() -> None:
    parser = ArgumentParser(description="Create a platform administrator in the configured database.")
    parser.add_argument("--email", required=True)
    parser.add_argument("--name", required=True)
    args = parser.parse_args()
    password = getpass("Administrator password (12–128 characters): ")
    if password != getpass("Confirm password: "):
        parser.error("Passwords differ.")
    try:
        account = AccountInput(full_name=args.name, email=args.email, password=password)
    except ValidationError:
        parser.error("Provide a valid email, name, and password length.")

    engine = create_database_engine(Settings())
    try:
        with Session(engine) as db:
            add_user(db, account.full_name, account.email, account.password, Role.ADMIN)
            db.commit()
    except EmailInUse:
        parser.error("An account already uses this email.")
    finally:
        engine.dispose()
    print("Administrator created.")


if __name__ == "__main__":
    main()
