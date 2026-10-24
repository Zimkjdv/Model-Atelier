"""Explicit per-application paths and engine access used by route installers."""

from dataclasses import dataclass, field
from contextlib import closing
from pathlib import Path
import sqlite3
from typing import Callable, ClassVar

import httpx
from backend.schemas import Settings, ModelTarget, ModelMetadata, DraftInput
from backend.diagnostics import Recorder, EngineClient
from backend.deployment_profile import Profile


@dataclass
class AppContext:
    ROOT: Path
    DATA: Path
    DB: Path
    engine_client_factory: Callable | None
    gpu_info: Callable
    deployment: Profile = field(default_factory=Profile)
    default_engine_url: str = 'http://127.0.0.1:8188'
    engine: Callable | None = field(default=None, init=False)
    current_catalog: Callable | None = field(default=None, init=False)
    local_environment_state: object = field(default=None, init=False)
    diagnostics: Recorder = field(default_factory=Recorder, init=False)
    # Immutable request types; specialized installers add their derived types.
    Settings: ClassVar[type] = Settings
    ModelTarget: ClassVar[type] = ModelTarget
    ModelMetadata: ClassVar[type] = ModelMetadata
    DraftInput: ClassVar[type] = DraftInput

    def initialize(self):
        self.DATA.mkdir(parents=True, exist_ok=True)
        self.DB.parent.mkdir(parents=True, exist_ok=True)
        with closing(sqlite3.connect(self.DB)) as database, database:
            database.execute(
                'CREATE TABLE IF NOT EXISTS settings (key TEXT PRIMARY KEY, value TEXT NOT NULL)'
            )

    def engine_url(self):
        with closing(sqlite3.connect(self.DB)) as database:
            row = database.execute("SELECT value FROM settings WHERE key='comfy_url'").fetchone()
        return row[0] if row else self.default_engine_url

    def http_client(self, **options):
        factory = self.engine_client_factory or httpx.AsyncClient
        return EngineClient(factory(**options))
