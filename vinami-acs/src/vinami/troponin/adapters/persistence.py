"""SQLAlchemy mappings and repository for troponin orders, results, and timelines."""

from __future__ import annotations

from datetime import datetime
from uuid import UUID, uuid4

from sqlalchemy import Float, ForeignKey, String, UniqueConstraint
from sqlalchemy.orm import Mapped, Session, mapped_column

from vinami.shared.persistence import Base, JSONDocument, UTCDateTime, UUIDType
from vinami.troponin.domain.model import (
    TroponinAssay,
    TroponinMeasurement,
    TroponinQualityFlag,
    TroponinTimeline,
)


class TroponinTimelineRecord(Base):
    """One troponin evidence timeline per clinical case."""

    __tablename__ = "troponin_timelines"
    __table_args__ = (UniqueConstraint("case_id", name="uq_troponin_timeline_case"),)

    id: Mapped[UUID] = mapped_column(UUIDType, primary_key=True)
    case_id: Mapped[UUID] = mapped_column(
        ForeignKey("clinical_cases.id", ondelete="CASCADE"), nullable=False
    )


class LabOrderRecord(Base):
    """Laboratory order reference captured before sample collection."""

    __tablename__ = "lab_orders"
    __table_args__ = (UniqueConstraint("order_reference", name="uq_lab_order_reference"),)

    id: Mapped[UUID] = mapped_column(UUIDType, primary_key=True, default=uuid4)
    timeline_id: Mapped[UUID] = mapped_column(
        ForeignKey("troponin_timelines.id", ondelete="CASCADE"), index=True
    )
    case_id: Mapped[UUID] = mapped_column(
        ForeignKey("clinical_cases.id", ondelete="CASCADE"), index=True
    )
    order_reference: Mapped[str] = mapped_column(String(160), nullable=False)
    ordered_at: Mapped[datetime] = mapped_column(UTCDateTime(), nullable=False)
    collected_at: Mapped[datetime | None] = mapped_column(UTCDateTime(), nullable=True)


class LabResultRecord(Base):
    """Quantitative troponin laboratory result with explicit assay and unit."""

    __tablename__ = "lab_results"

    id: Mapped[UUID] = mapped_column(UUIDType, primary_key=True)
    order_id: Mapped[UUID] = mapped_column(
        ForeignKey("lab_orders.id", ondelete="CASCADE"), nullable=False, index=True
    )
    timeline_id: Mapped[UUID] = mapped_column(
        ForeignKey("troponin_timelines.id", ondelete="CASCADE"), nullable=False
    )
    assay_name: Mapped[str] = mapped_column(String(200), nullable=False)
    assay_manufacturer: Mapped[str] = mapped_column(String(200), nullable=False)
    analyzer: Mapped[str] = mapped_column(String(200), nullable=False)
    unit: Mapped[str] = mapped_column(String(50), nullable=False)
    reference_limit: Mapped[float] = mapped_column(Float, nullable=False)
    reference_metadata: Mapped[dict[str, object]] = mapped_column(
        JSONDocument, nullable=False, default=dict
    )
    value: Mapped[float] = mapped_column(Float, nullable=False)
    collected_at: Mapped[datetime] = mapped_column(UTCDateTime(), nullable=False, index=True)
    resulted_at: Mapped[datetime] = mapped_column(UTCDateTime(), nullable=False)
    ingested_at: Mapped[datetime | None] = mapped_column(UTCDateTime(), nullable=True)
    source_system: Mapped[str] = mapped_column(String(200), nullable=False)
    source_record_id: Mapped[str | None] = mapped_column(String(300), nullable=True)
    quality_flags: Mapped[dict[str, object]] = mapped_column(
        JSONDocument, nullable=False, default=dict
    )
    renal_function_context: Mapped[str | None] = mapped_column(String(2000), nullable=True)


def _quality_flags_from_document(document: dict[str, object]) -> tuple[TroponinQualityFlag, ...]:
    values = document.get("values")
    if not isinstance(values, list):
        return ()
    return tuple(TroponinQualityFlag(value) for value in values if isinstance(value, str))


class SQLAlchemyTroponinTimelineRepository:
    """Timeline repository that maps orders and results to explicit relational rows."""

    def __init__(self, session: Session) -> None:
        """Bind repository work to the active session."""
        self._session = session

    def add(self, timeline: TroponinTimeline) -> None:
        """Insert a timeline and all currently known order/result facts."""
        if self._session.get(TroponinTimelineRecord, timeline.id) is not None:
            raise ValueError(f"troponin timeline {timeline.id} already exists")
        self._session.add(TroponinTimelineRecord(id=timeline.id, case_id=timeline.case_id))
        self._sync(timeline)

    def get_by_case_id(self, case_id: UUID) -> TroponinTimeline | None:
        """Rehydrate one timeline with its orders, collections, and results."""
        timeline_record = (
            self._session.query(TroponinTimelineRecord).filter_by(case_id=case_id).one_or_none()
        )
        if timeline_record is None:
            return None
        timeline = TroponinTimeline.create(case_id=case_id, timeline_id=timeline_record.id)
        orders = self._session.query(LabOrderRecord).filter_by(timeline_id=timeline_record.id).all()
        for order in orders:
            timeline.ordered_references.add(order.order_reference)
            timeline.ordered_at_by_reference[order.order_reference] = order.ordered_at
            if order.collected_at is not None:
                timeline.collected_references.add(order.order_reference)
                timeline.collected_at_by_reference[order.order_reference] = order.collected_at
        results = (
            self._session.query(LabResultRecord)
            .filter_by(timeline_id=timeline_record.id)
            .order_by(LabResultRecord.collected_at)
            .all()
        )
        timeline.measurements = [
            TroponinMeasurement(
                id=result.id,
                value=result.value,
                assay=TroponinAssay(
                    result.assay_name,
                    result.unit,
                    manufacturer=result.assay_manufacturer,
                    analyzer=result.analyzer,
                    reference_limit=result.reference_limit,
                ),
                collected_at=result.collected_at,
                resulted_at=result.resulted_at,
                order_reference=next(
                    order.order_reference for order in orders if order.id == result.order_id
                ),
                quality_flags=_quality_flags_from_document(result.quality_flags),
                renal_function_context=result.renal_function_context,
                source_system=result.source_system,
                source_record_id=result.source_record_id,
                ingested_at=result.ingested_at,
                reference_metadata=tuple(
                    sorted(
                        (str(key), str(value)) for key, value in result.reference_metadata.items()
                    )
                ),
            )
            for result in results
        ]
        return timeline

    def save(self, timeline: TroponinTimeline) -> None:
        """Persist timeline facts that have not yet been recorded."""
        if self._session.get(TroponinTimelineRecord, timeline.id) is None:
            raise ValueError(f"troponin timeline {timeline.id} does not exist")
        self._sync(timeline)

    def _sync(self, timeline: TroponinTimeline) -> None:
        existing_orders = {
            item.order_reference: item
            for item in self._session.query(LabOrderRecord).filter_by(timeline_id=timeline.id)
        }
        for reference in timeline.ordered_references:
            order = existing_orders.get(reference)
            if order is None:
                order = LabOrderRecord(
                    timeline_id=timeline.id,
                    case_id=timeline.case_id,
                    order_reference=reference,
                    ordered_at=timeline.ordered_at_by_reference[reference],
                )
                self._session.add(order)
                existing_orders[reference] = order
            if reference in timeline.collected_references and order.collected_at is None:
                order.collected_at = timeline.collected_at_by_reference[reference]
        self._session.flush()
        existing_result_ids = {
            item.id
            for item in self._session.query(LabResultRecord).filter_by(timeline_id=timeline.id)
        }
        for measurement in timeline.measurements:
            if measurement.id not in existing_result_ids:
                self._session.add(
                    LabResultRecord(
                        id=measurement.id,
                        order_id=existing_orders[measurement.order_reference].id,
                        timeline_id=timeline.id,
                        assay_name=measurement.assay.name,
                        assay_manufacturer=measurement.assay.manufacturer,
                        analyzer=measurement.assay.analyzer,
                        unit=measurement.assay.unit,
                        reference_limit=measurement.assay.reference_limit,
                        reference_metadata=dict(measurement.reference_metadata),
                        value=measurement.value,
                        collected_at=measurement.collected_at,
                        resulted_at=measurement.resulted_at,
                        ingested_at=measurement.ingested_at,
                        source_system=measurement.source_system,
                        source_record_id=measurement.source_record_id,
                        quality_flags={
                            "values": [flag.value for flag in measurement.quality_flags]
                        },
                        renal_function_context=measurement.renal_function_context,
                    )
                )
