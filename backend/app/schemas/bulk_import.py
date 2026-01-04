from typing import List, Optional

from pydantic import BaseModel, Field


class BulkUserRow(BaseModel):
    folder_name: str
    name: str
    email: Optional[str] = None
    external_id: Optional[str] = None
    department: Optional[str] = None
    role: str = Field(default="member", pattern="^(admin|manager|member)$")


class BulkUserResult(BaseModel):
    folder_name: str
    name: str
    status: str
    user_id: Optional[str] = None
    error: Optional[str] = None
    images_processed: int = 0
    embeddings_created: int = 0


class BulkImportResponse(BaseModel):
    total_rows: int
    successful: int
    failed: int
    skipped: int
    results: List[BulkUserResult]
