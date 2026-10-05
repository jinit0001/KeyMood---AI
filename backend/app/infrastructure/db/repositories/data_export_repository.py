from sqlalchemy.orm import Session

from app.domain.profile.entities import DataExportRequest
from app.infrastructure.db.models.data_export_request import DataExportRequestModel


class SqlDataExportRepository:
    """Implements domain.profile.ports.DataExportRepository."""

    def __init__(self, session: Session):
        self._session = session

    def add(self, request: DataExportRequest) -> None:
        row = DataExportRequestModel(
            id=request.id,
            user_id=request.user_id,
            status=request.status,
            download_url=request.download_url,
            expires_at=request.expires_at,
            completed_at=request.completed_at,
        )
        self._session.add(row)
        self._session.flush()
