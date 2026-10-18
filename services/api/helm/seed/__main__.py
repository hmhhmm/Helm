from helm.db import SessionLocal, reset_db
from helm.seed import seed_database

if __name__ == "__main__":
    reset_db()
    with SessionLocal() as s:
        print(seed_database(s))
        s.commit()
