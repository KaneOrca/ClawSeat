from __future__ import annotations

from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from enum import Enum
from typing import Any


class SessionState(Enum):
    AUTH_NEEDED = "auth_needed"
    ONBOARDING = "onboarding"
    RUNNING = "running"
    READY = "ready"
    DEGRADED = "degraded"
    DEAD = "dead"


@dataclass(slots=True)
class SeatPlan:
    seat_id: str
    project: str
    role: str
    tool: str
    workspace_path: str
    contract_content: dict[str, Any]
    session_binding_spec: dict[str, Any]
    metadata: dict[str, Any] = field(default_factory=dict)


@dataclass(slots=True)
class SessionHandle:
    seat_id: str
    project: str
    tool: str
    runtime_id: str
    locator: dict[str, Any] = field(default_factory=dict)
    workspace_path: str = ""
    session_path: str = ""


@dataclass(slots=True)
class ResumeResult:
    resumed: bool
    state: SessionState
    detail: str = ""


@dataclass(slots=True)
class RecoverResult:
    recovered: bool
    resumed: bool
    restarted: bool
    state: SessionState
    detail: str = ""


@dataclass(slots=True)
class SendResult:
    delivered: bool
    transport: str
    detail: str = ""


@dataclass(slots=True)
class AuthConfig:
    seat_id: str
    project: str
    auth_mode: str
    provider: str
    identity: str
    secret_file: str = ""
    runtime_dir: str = ""
    locator: dict[str, Any] = field(default_factory=dict)


class HarnessAdapter(ABC):
    @abstractmethod
    def materialize(self, plan: SeatPlan) -> SessionHandle:
        raise NotImplementedError

    @abstractmethod
    def start_session(self, seat_id: str, project: str, plan: SeatPlan) -> SessionHandle:
        raise NotImplementedError

    @abstractmethod
    def stop_session(self, handle: SessionHandle) -> None:
        raise NotImplementedError

    @abstractmethod
    def destroy_session(self, handle: SessionHandle) -> None:
        raise NotImplementedError

    @abstractmethod
    def resume_session(self, handle: SessionHandle) -> ResumeResult:
        raise NotImplementedError

    @abstractmethod
    def recover_session(self, handle: SessionHandle) -> RecoverResult:
        raise NotImplementedError

    @abstractmethod
    def send_message(self, handle: SessionHandle, text: str) -> SendResult:
        raise NotImplementedError

    @abstractmethod
    def get_output(self, handle: SessionHandle, lines: int = 50) -> str:
        raise NotImplementedError

    @abstractmethod
    def probe_state(self, handle: SessionHandle) -> SessionState:
        raise NotImplementedError

    @abstractmethod
    def list_sessions(self, project: str) -> list[SessionHandle]:
        raise NotImplementedError

    @abstractmethod
    def get_auth_config(self, seat_id: str, project: str) -> AuthConfig:
        raise NotImplementedError
