"""Create the first platform owner after migrations.

Requires PLATFORM_ADMIN_USERNAME, PLATFORM_ADMIN_EMAIL, PLATFORM_ADMIN_NAME,
and PLATFORM_ADMIN_PASSWORD in the environment. Never run with demo credentials.
"""

import os

from backend.app.database import SessionLocal
from backend.app.models.user import User
from backend.app.utils.security import get_password_hash


def main():
    names = ("PLATFORM_ADMIN_USERNAME", "PLATFORM_ADMIN_EMAIL", "PLATFORM_ADMIN_NAME", "PLATFORM_ADMIN_PASSWORD")
    values = {name: os.environ.get(name, "").strip() for name in names}
    if any(not values[name] for name in names):
        raise SystemExit("Set PLATFORM_ADMIN_USERNAME, PLATFORM_ADMIN_EMAIL, PLATFORM_ADMIN_NAME, and PLATFORM_ADMIN_PASSWORD")
    if len(values["PLATFORM_ADMIN_PASSWORD"]) < 16:
        raise SystemExit("Platform admin password must be at least 16 characters")
    with SessionLocal() as db:
        if db.query(User).filter(User.tenant_id.is_(None), User.role == "PLATFORM_SUPER_ADMIN").first():
            raise SystemExit("A platform owner already exists; use the platform account recovery procedure")
        db.add(User(username=values["PLATFORM_ADMIN_USERNAME"], email=values["PLATFORM_ADMIN_EMAIL"],
                    full_name=values["PLATFORM_ADMIN_NAME"],
                    hashed_password=get_password_hash(values["PLATFORM_ADMIN_PASSWORD"]),
                    role="PLATFORM_SUPER_ADMIN", is_active=True))
        db.commit()
    print("Platform owner created")


if __name__ == "__main__":
    main()
