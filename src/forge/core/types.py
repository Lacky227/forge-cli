"""Shared enumerations for project definitions."""

from enum import StrEnum


class ProjectType(StrEnum):
    REST_API = "rest-api"
    CLI = "cli"
    WORKER = "worker"


class Language(StrEnum):
    PYTHON = "python"


class ArchitectureStyle(StrEnum):
    SIMPLE = "simple"
    MODULAR_MONOLITH = "modular-monolith"
    CLEAN = "clean"


class SqlDatabase(StrEnum):
    """SQL engine choices — independent of NoSQL selection."""

    POSTGRESQL = "postgresql"
    SQLITE = "sqlite"


class NoSqlDatabase(StrEnum):
    """NoSQL / infrastructure client choices — independent of SQL selection."""

    MONGODB = "mongodb"
    REDIS = "redis"
