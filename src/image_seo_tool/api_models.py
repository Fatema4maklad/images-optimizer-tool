"""Response models shared by local and hosted HTTP adapters."""

from pydantic import BaseModel


class ErrorResponse(BaseModel):
    detail: str


class ImageSummary(BaseModel):
    filename: str
    alt_text: str
    original_bytes: int
    output_bytes: int
    original_size: tuple[int, int]
    output_size: tuple[int, int]
    reduction_percent: float


class HealthResponse(BaseModel):
    status: str
