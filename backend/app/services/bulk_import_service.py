import csv
import io
import logging
import tempfile
import zipfile
from datetime import datetime
from pathlib import Path
from typing import List, Tuple
from uuid import UUID

import httpx
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.config import settings
from app.core.security import hash_password
from app.models.face_embedding import FaceEmbedding
from app.models.user import User
from app.schemas.bulk_import import BulkImportResponse, BulkUserResult, BulkUserRow

logger = logging.getLogger(__name__)


class BulkImportService:
    def __init__(self, db: AsyncSession):
        self.db = db

    async def process_zip_upload(
        self,
        org_id: UUID,
        zip_content: bytes,
        skip_existing: bool = True
    ) -> BulkImportResponse:
        results: List[BulkUserResult] = []

        with tempfile.TemporaryDirectory() as temp_dir:
            temp_path = Path(temp_dir)

            try:
                with zipfile.ZipFile(io.BytesIO(zip_content)) as zf:
                    zf.extractall(temp_path)
            except zipfile.BadZipFile:
                return BulkImportResponse(
                    total_rows=0,
                    successful=0,
                    failed=1,
                    skipped=0,
                    results=[BulkUserResult(
                        folder_name="",
                        name="",
                        status="error",
                        error="Invalid ZIP file"
                    )]
                )

            csv_path = self._find_csv(temp_path)
            if not csv_path:
                return BulkImportResponse(
                    total_rows=0,
                    successful=0,
                    failed=1,
                    skipped=0,
                    results=[BulkUserResult(
                        folder_name="",
                        name="",
                        status="error",
                        error="No users.csv found in ZIP"
                    )]
                )

            try:
                rows = self._parse_csv(csv_path)
            except Exception as e:
                return BulkImportResponse(
                    total_rows=0,
                    successful=0,
                    failed=1,
                    skipped=0,
                    results=[BulkUserResult(
                        folder_name="",
                        name="",
                        status="error",
                        error=f"CSV parsing error: {str(e)}"
                    )]
                )

            faces_dir = self._find_faces_dir(temp_path)

            for row in rows:
                result = await self._process_single_user(
                    org_id, row, faces_dir, skip_existing
                )
                results.append(result)

        return BulkImportResponse(
            total_rows=len(results),
            successful=sum(1 for r in results if r.status == "success"),
            failed=sum(1 for r in results if r.status == "error"),
            skipped=sum(1 for r in results if r.status == "skipped"),
            results=results
        )

    def _find_csv(self, base_path: Path) -> Path | None:
        for csv_name in ["users.csv", "data.csv", "import.csv"]:
            csv_path = base_path / csv_name
            if csv_path.exists():
                return csv_path
            for sub in base_path.iterdir():
                if sub.is_dir():
                    csv_path = sub / csv_name
                    if csv_path.exists():
                        return csv_path
        return None

    def _find_faces_dir(self, base_path: Path) -> Path | None:
        for dir_name in ["faces", "images", "photos"]:
            faces_path = base_path / dir_name
            if faces_path.exists() and faces_path.is_dir():
                return faces_path
            for sub in base_path.iterdir():
                if sub.is_dir():
                    faces_path = sub / dir_name
                    if faces_path.exists() and faces_path.is_dir():
                        return faces_path
        return base_path

    def _parse_csv(self, csv_path: Path) -> List[BulkUserRow]:
        rows: List[BulkUserRow] = []
        with open(csv_path, "r", encoding="utf-8-sig") as f:
            reader = csv.DictReader(f)
            for idx, row in enumerate(reader):
                folder_name = row.get("folder_name", "").strip()
                if not folder_name:
                    folder_name = row.get("external_id", "").strip() or str(idx + 1)

                name = row.get("name", "").strip()
                if not name:
                    continue

                rows.append(BulkUserRow(
                    folder_name=folder_name,
                    name=name,
                    email=row.get("email", "").strip() or None,
                    external_id=row.get("external_id", "").strip() or None,
                    department=row.get("department", "").strip() or None,
                    role=row.get("role", "member").strip() or "member"
                ))
        return rows

    async def _user_exists(self, org_id: UUID, row: BulkUserRow) -> bool:
        if row.email:
            result = await self.db.execute(
                select(User).where(
                    User.org_id == org_id,
                    User.email == row.email
                )
            )
            if result.scalar_one_or_none():
                return True

        if row.external_id:
            result = await self.db.execute(
                select(User).where(
                    User.org_id == org_id,
                    User.external_id == row.external_id
                )
            )
            if result.scalar_one_or_none():
                return True

        return False

    async def _process_single_user(
        self,
        org_id: UUID,
        row: BulkUserRow,
        faces_dir: Path | None,
        skip_existing: bool
    ) -> BulkUserResult:
        try:
            if skip_existing and await self._user_exists(org_id, row):
                return BulkUserResult(
                    folder_name=row.folder_name,
                    name=row.name,
                    status="skipped",
                    error="User already exists"
                )

            user = User(
                org_id=org_id,
                name=row.name,
                email=row.email,
                external_id=row.external_id,
                department=row.department,
                role=row.role,
                is_active=True
            )
            self.db.add(user)
            await self.db.flush()

            images_processed = 0
            embeddings_created = 0

            if faces_dir:
                folder_path = faces_dir / row.folder_name
                if folder_path.exists() and folder_path.is_dir():
                    images_processed, embeddings_created = await self._process_user_faces(
                        user.id, folder_path
                    )
                    if embeddings_created > 0:
                        user.enrolled_at = datetime.utcnow()

            await self.db.commit()

            return BulkUserResult(
                folder_name=row.folder_name,
                name=row.name,
                status="success",
                user_id=str(user.id),
                images_processed=images_processed,
                embeddings_created=embeddings_created
            )

        except Exception as e:
            await self.db.rollback()
            logger.exception(f"Error processing user {row.name}")
            return BulkUserResult(
                folder_name=row.folder_name,
                name=row.name,
                status="error",
                error=str(e)
            )

    async def _process_user_faces(
        self,
        user_id: UUID,
        folder_path: Path
    ) -> Tuple[int, int]:
        image_extensions = {".jpg", ".jpeg", ".png", ".webp"}
        images = [
            f for f in folder_path.iterdir()
            if f.is_file() and f.suffix.lower() in image_extensions
        ][:5]

        embeddings_created = 0

        async with httpx.AsyncClient(timeout=30.0) as client:
            for idx, img_path in enumerate(images):
                try:
                    image_bytes = img_path.read_bytes()
                    content_type = "image/jpeg"
                    if img_path.suffix.lower() == ".png":
                        content_type = "image/png"

                    response = await client.post(
                        f"{settings.FACE_SERVICE_URL}/api/v1/embed",
                        files={"image": (img_path.name, image_bytes, content_type)},
                    )

                    if response.status_code == 200:
                        result = response.json()
                        embedding = result.get("embedding")
                        quality = result.get("quality_score")

                        if embedding:
                            face_emb = FaceEmbedding(
                                user_id=user_id,
                                embedding=embedding,
                                quality_score=quality,
                                is_primary=(embeddings_created == 0),
                            )
                            self.db.add(face_emb)
                            embeddings_created += 1
                except Exception as e:
                    logger.warning(f"Failed to process image {img_path}: {e}")
                    continue

        return len(images), embeddings_created
