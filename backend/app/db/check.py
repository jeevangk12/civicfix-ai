from sqlalchemy import text

from app.core.config import Settings
from app.db.session import create_database_engine


def main() -> None:
    engine = create_database_engine(Settings())
    try:
        with engine.connect() as connection:
            result = connection.execute(text("SELECT 1")).scalar_one()
            if result != 1:
                raise RuntimeError(f"Expected SELECT 1 to return 1, got {result!r}")
            print(result)
    finally:
        engine.dispose()


if __name__ == "__main__":
    main()
