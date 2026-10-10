from sqlalchemy import create_engine, event, select
from sqlalchemy.ext.declarative import declarative_base
from sqlalchemy.orm import Session, sessionmaker, with_loader_criteria
from backend.app.config import settings

engine = create_engine(
    settings.DATABASE_URL,
    connect_args={"check_same_thread": False} if "sqlite" in settings.DATABASE_URL else {}
)

# Enable foreign key support for SQLite
if "sqlite" in settings.DATABASE_URL:
    @event.listens_for(engine, "connect")
    def set_sqlite_pragma(dbapi_connection, connection_record):
        cursor = dbapi_connection.cursor()
        cursor.execute("PRAGMA foreign_keys=ON")
        cursor.close()

SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)

Base = declarative_base()


def _tenant_mappers():
    # Import lazily so every model is registered before evaluating policies.
    from backend.app import models  # noqa: F401
    # A tenant reference does not itself imply tenant ownership: subscriptions
    # and platform audit events are managed by the platform.
    return tuple(mapper for mapper in Base.registry.mappers
                 if "tenant_id" in mapper.local_table.c
                 and mapper.local_table.name not in {"subscriptions", "platform_audit_events",
                                                     "saas_invoices", "saas_payments"})


@event.listens_for(Session, "do_orm_execute")
def scope_tenant_queries(state):
    scope = state.session.info.get("tenant_scope")
    if scope not in ("tenant", "platform"):
        return
    tenant_id = state.session.info.get("tenant_id")
    if scope == "tenant" and tenant_id is None:
        raise RuntimeError("Tenant-scoped session has no tenant ID")
    if state.is_select:
        state.statement = state.statement.options(*(
            with_loader_criteria(
                mapper.class_, mapper.class_.tenant_id == tenant_id if scope == "tenant" else False,
                include_aliases=True,
            ) for mapper in _tenant_mappers()
        ))
    elif state.is_update or state.is_delete:
        table = state.statement.table
        if "tenant_id" in table.c:
            state.statement = state.statement.where(
                table.c.tenant_id == tenant_id if scope == "tenant" else False
            )


@event.listens_for(Session, "before_flush")
def enforce_tenant_writes(session, flush_context, instances):
    scope = session.info.get("tenant_scope")
    if scope not in ("tenant", "platform"):
        return
    tenant_id = session.info.get("tenant_id")
    tenant_tables = {mapper.local_table.name for mapper in _tenant_mappers()}
    for obj in tuple(session.new) + tuple(session.dirty) + tuple(session.deleted):
        if obj.__table__.name not in tenant_tables:
            continue
        if scope == "platform":
            from backend.app.models.user import User
            if isinstance(obj, User) and obj not in session.new and obj not in session.deleted and obj.tenant_id is None:
                continue
            raise PermissionError("Platform identity cannot modify school records")
        if obj in session.new and obj.tenant_id is None:
            obj.tenant_id = tenant_id
        if obj.tenant_id != tenant_id:
            raise PermissionError("Cross-tenant write denied")
        if obj in session.deleted:
            continue
        table = obj.__table__
        for foreign_key in table.foreign_keys:
            if foreign_key.parent.name == "tenant_id" or foreign_key.column.table.name not in tenant_tables:
                continue
            value = getattr(obj, foreign_key.parent.name)
            if value is None:
                continue
            target = foreign_key.column.table
            owner = session.connection().execute(
                select(target.c.tenant_id).where(foreign_key.column == value)
            ).scalar_one_or_none()
            if owner is not None and owner != tenant_id:
                raise PermissionError("Cross-tenant relationship denied")

def get_db():
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()

def init_db():
    # Import all models to ensure they are registered with Base.metadata
    from backend.app import models
    Base.metadata.create_all(bind=engine)
