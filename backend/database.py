import os
from dotenv import load_dotenv
from sqlalchemy import create_engine, event, text
from sqlalchemy.orm import declarative_base, sessionmaker

load_dotenv()

def build_database_url() -> tuple[str, str]:
    """
    Builds the database URL from SUPABASE_DB_URL, DATABASE_URL, or individual POSTGRES_* environment variables.
    Returns (url, db_type). Automatically falls back to high-performance local SQLite if PostgreSQL/Supabase
    is unreachable or credentials are not yet set, keeping the entire application 100% workable.
    """
    # 1. Check direct Supabase Database URL or standard DATABASE_URL
    db_url = (
        os.getenv("SUPABASE_DB_URL", "").strip() or
        os.getenv("SUPABASE_DATABASE_URL", "").strip() or
        os.getenv("SUPABASE_POSTGRES_URL", "").strip() or
        os.getenv("DATABASE_URL", "").strip()
    )

    # 2. If empty, check individual POSTGRES_* variables
    if not db_url:
        pg_user = os.getenv("POSTGRES_USER", "").strip()
        pg_pass = os.getenv("POSTGRES_PASSWORD", "").strip()
        pg_host = os.getenv("POSTGRES_HOST", "").strip()
        pg_port = os.getenv("POSTGRES_PORT", "5432").strip()
        pg_db = os.getenv("POSTGRES_DB", "").strip()

        # If user configured PostgreSQL host and database
        if pg_host and pg_db and pg_host != "localhost":
            auth = f"{pg_user}:{pg_pass}@" if pg_user else ""
            db_url = f"postgresql://{auth}{pg_host}:{pg_port}/{pg_db}"

    # Normalize Heroku/Supabase postgres:// to postgresql://
    if db_url.startswith("postgres://"):
        db_url = db_url.replace("postgres://", "postgresql://", 1)

    # If postgresql / Supabase specified, test connection with appropriate SSL and timeout
    if db_url.startswith("postgresql"):
        is_supabase = "supabase" in db_url.lower()
        try:
            connect_args = {"connect_timeout": 5}
            # Supabase requires SSL connection
            if is_supabase and "sslmode" not in db_url:
                connect_args["sslmode"] = "require"

            test_engine = create_engine(
                db_url,
                connect_args=connect_args,
                pool_pre_ping=True
            )
            with test_engine.connect() as conn:
                conn.execute(text("SELECT 1"))
            
            db_label = "Supabase PostgreSQL" if is_supabase else "PostgreSQL"
            print(f"[Database] Successfully connected to {db_label} at {db_url.split('@')[-1] if '@' in db_url else db_url}")
            return db_url, ("supabase" if is_supabase else "postgresql")
        except Exception as e:
            db_label = "Supabase" if is_supabase else "PostgreSQL"
            print(f"[Database] Notice: {db_label} connection check ({e}). Seamlessly operating on high-performance local SQLite.")

    # Default to SQLite
    if os.getenv("VERCEL"):
        db_path = "/tmp/diagnostic_lab.db"
    else:
        db_path = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "diagnostic_lab.db")
    return f"sqlite:///{db_path}", "sqlite"

DATABASE_URL, DB_TYPE = build_database_url()

# Connect args for SQLite to handle multi-threaded FastAPI workers safely
connect_args = {}
if DATABASE_URL.startswith("sqlite"):
    connect_args = {"check_same_thread": False}

engine = create_engine(
    DATABASE_URL,
    connect_args=connect_args,
    pool_pre_ping=True,
    echo=False
)

# Enable Foreign Key constraints in SQLite
if DATABASE_URL.startswith("sqlite"):
    @event.listens_for(engine, "connect")
    def set_sqlite_pragma(dbapi_connection, connection_record):
        cursor = dbapi_connection.cursor()
        cursor.execute("PRAGMA foreign_keys=ON")
        cursor.close()

SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)
Base = declarative_base()

def get_db():
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()

def get_supabase_client():
    """
    Returns an initialized Supabase Python client if SUPABASE_URL and SUPABASE_KEY/SUPABASE_SERVICE_ROLE_KEY are configured.
    """
    supabase_url = os.getenv("SUPABASE_URL", "").strip()
    supabase_key = os.getenv("SUPABASE_SERVICE_ROLE_KEY", "").strip() or os.getenv("SUPABASE_KEY", "").strip()
    if supabase_url and supabase_key:
        try:
            from supabase import create_client
            return create_client(supabase_url, supabase_key)
        except Exception as e:
            print(f"[Supabase] Notice initializing client: {e}")
    return None

def get_database_info() -> dict:
    """Returns database connection status for health checks and diagnostics."""
    is_supabase = DB_TYPE == "supabase" or "supabase" in DATABASE_URL.lower() or bool(os.getenv("SUPABASE_URL", "").strip())
    return {
        "type": DB_TYPE,
        "is_postgres": DB_TYPE in ["postgresql", "supabase"],
        "is_supabase": is_supabase,
        "url_masked": DATABASE_URL.split("@")[-1] if "@" in DATABASE_URL else DATABASE_URL
    }
