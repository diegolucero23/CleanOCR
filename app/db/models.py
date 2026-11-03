import time
from datetime import timezone
from sqlalchemy import Column, String, Integer, BigInteger, Float, Text, Boolean, DateTime, ForeignKey, func
from sqlalchemy.orm import relationship
from app.db.database import Base


def _utc_iso(value):
    """ISO-8601 with an explicit offset. SQLite returns created_at naive (UTC);
    without an offset, browsers would parse it as local time."""
    if value is None:
        return None
    if value.tzinfo is None:
        value = value.replace(tzinfo=timezone.utc)
    return value.isoformat()


class JobModel(Base):
    __tablename__ = "jobs"

    id = Column(String(36), primary_key=True, index=True)
    status = Column(String(20), nullable=False, index=True, default="queued")
    file_hash = Column(String(64), nullable=True, index=True)
    original_filename = Column(String(255), nullable=False)
    file_size = Column(BigInteger, nullable=False)
    total_pages = Column(Integer, nullable=True)
    processed_pages = Column(Integer, nullable=False, default=0)
    model_name = Column(String(64), nullable=False, default="gemini-3.1-flash-lite")
    layout_type = Column(String(32), nullable=True)
    upload_time = Column(Float, nullable=False, default=time.time)
    end_time = Column(Float, nullable=True)
    duration_seconds = Column(Float, nullable=True)
    complexity = Column(Float, nullable=True)
    error_message = Column(Text, nullable=True)
    created_at = Column(DateTime(timezone=True), server_default=func.now(), index=True)
    updated_at = Column(DateTime(timezone=True), server_default=func.now(), onupdate=func.now())

    # 1-to-1 Relationships with Cascade Deletion
    # Renamed to citation_metadata to avoid collision with DeclarativeBase.metadata
    citation_metadata = relationship(
        "JobMetadataModel",
        back_populates="job",
        uselist=False,
        cascade="all, delete-orphan",
        lazy="joined",
    )
    result = relationship(
        "JobResultModel",
        back_populates="job",
        uselist=False,
        cascade="all, delete-orphan",
        lazy="joined",
    )

    def to_summary_dict(self):
        """Serialize job summary envelope for GET /jobs list."""
        meta_dict = None
        if self.citation_metadata:
            meta_dict = {
                "title": self.citation_metadata.title,
                "volume": self.citation_metadata.volume,
                "issue": self.citation_metadata.issue,
                "publication_date": self.citation_metadata.publication_date,
            }
        return {
            "job_id": self.id,
            "status": self.status,
            "original_filename": self.original_filename,
            "file_size": self.file_size,
            "total_pages": self.total_pages,
            "processed_pages": self.processed_pages,
            "model_name": self.model_name,
            "layout_type": self.layout_type,
            "upload_time": self.upload_time,
            "end_time": self.end_time,
            "duration_seconds": self.duration_seconds,
            "complexity": self.complexity,
            "error_message": self.error_message,
            "metadata": meta_dict,
            "created_at": _utc_iso(self.created_at),
        }

    def to_detail_dict(self):
        """Serialize full job detail envelope for GET /jobs/{job_id}."""
        data = self.to_summary_dict()
        if self.result:
            data["result"] = {
                "markdown_text": self.result.markdown_text,
                "total_words": self.result.total_words,
                "confidence_score": self.result.confidence_score,
                "statistics": self.result.statistics_json,
            }
        else:
            data["result"] = None
        return data


class JobMetadataModel(Base):
    __tablename__ = "job_metadata"

    id = Column(Integer, primary_key=True, autoincrement=True)
    job_id = Column(
        String(36),
        ForeignKey("jobs.id", ondelete="CASCADE"),
        unique=True,
        nullable=False,
        index=True,
    )
    title = Column(String(255), nullable=True)
    volume = Column(String(50), nullable=True)
    issue = Column(String(50), nullable=True)
    publication_date = Column(String(50), nullable=True)
    skip_metadata = Column(Boolean, default=False)

    job = relationship("JobModel", back_populates="citation_metadata")


class JobResultModel(Base):
    __tablename__ = "job_results"

    id = Column(Integer, primary_key=True, autoincrement=True)
    job_id = Column(
        String(36),
        ForeignKey("jobs.id", ondelete="CASCADE"),
        unique=True,
        nullable=False,
        index=True,
    )
    markdown_text = Column(Text, nullable=True)
    total_words = Column(Integer, default=0)
    confidence_score = Column(Float, nullable=True)
    statistics_json = Column(Text, nullable=True)

    job = relationship("JobModel", back_populates="result")
