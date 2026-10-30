"""Central configuration. Every value comes from environment variables."""
import os

from dotenv import load_dotenv

load_dotenv()


class Config:
    SECRET_KEY = os.getenv("SECRET_KEY", "dev-secret")
    FLASK_ENV = os.getenv("FLASK_ENV", "development")
    MONGODB_URI = os.getenv("MONGODB_URI", "")
    MONGODB_DB = os.getenv("MONGODB_DB", "handoff")
    GEMINI_API_KEY = os.getenv("GEMINI_API_KEY", "")
    GEMINI_MODEL = os.getenv("GEMINI_MODEL", "gemini-2.5-flash")
    AI_TIMEOUT_SECONDS = int(os.getenv("AI_TIMEOUT_SECONDS", "30"))
    AI_MAX_ATTEMPTS = int(os.getenv("AI_MAX_ATTEMPTS", "2"))
    LOG_LEVEL = os.getenv("LOG_LEVEL", "INFO")
    LOG_DIR = os.getenv("LOG_DIR", "logs")
    SEED_ON_STARTUP = os.getenv("SEED_ON_STARTUP", "true").lower() == "true"
    MAX_UPLOAD_MB = int(os.getenv("MAX_UPLOAD_MB", "5"))
    MAX_CONTENT_LENGTH = MAX_UPLOAD_MB * 1024 * 1024
    APP_VERSION = "1.0.0"
