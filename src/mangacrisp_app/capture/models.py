from __future__ import annotations

from dataclasses import asdict, dataclass, field
from typing import Any


@dataclass(frozen=True)
class CaptureWarning:
    code: str
    message: str

    @classmethod
    def from_dict(cls, value: dict[str, Any]) -> CaptureWarning:
        return cls(code=str(value["code"]), message=str(value["message"]))


@dataclass(frozen=True)
class CapturePage:
    position: int
    file: str
    sha256: str
    perceptual_hash: str
    width: int
    height: int
    warnings: tuple[CaptureWarning, ...] = ()

    def to_dict(self) -> dict[str, Any]:
        value = asdict(self)
        value["warnings"] = [asdict(warning) for warning in self.warnings]
        return value

    @classmethod
    def from_dict(cls, value: dict[str, Any]) -> CapturePage:
        return cls(
            position=int(value["position"]),
            file=str(value["file"]),
            sha256=str(value["sha256"]),
            perceptual_hash=str(value.get("perceptual_hash", "")),
            width=int(value["width"]),
            height=int(value["height"]),
            warnings=tuple(CaptureWarning.from_dict(item) for item in value.get("warnings", [])),
        )


@dataclass
class CaptureSessionManifest:
    schema_version: int
    session_name: str
    created_at: str
    capture_mode: str = "fixed_region"
    pixel_size: dict[str, int] | None = None
    pages: list[CapturePage] = field(default_factory=list)
    output: dict[str, str] | None = None

    def to_dict(self) -> dict[str, Any]:
        return {
            "schema_version": self.schema_version,
            "session_name": self.session_name,
            "created_at": self.created_at,
            "capture_mode": self.capture_mode,
            "pixel_size": self.pixel_size,
            "pages": [page.to_dict() for page in self.pages],
            "output": self.output,
        }

    @classmethod
    def from_dict(cls, value: dict[str, Any]) -> CaptureSessionManifest:
        schema_version = int(value.get("schema_version", 0))
        if schema_version != 1:
            raise ValueError(f"unsupported capture manifest schema: {schema_version}")
        return cls(
            schema_version=schema_version,
            session_name=str(value["session_name"]),
            created_at=str(value["created_at"]),
            capture_mode=str(value.get("capture_mode", "fixed_region")),
            pixel_size=value.get("pixel_size"),
            pages=[CapturePage.from_dict(page) for page in value.get("pages", [])],
            output=value.get("output"),
        )
