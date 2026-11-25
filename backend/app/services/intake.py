from datetime import UTC, datetime
from uuid import UUID

from sqlalchemy import Engine, select
from sqlalchemy.orm import Session

from app.core.config import Settings
from app.db.complaint_models import AnalysisStatus, Category, Complaint, Priority
from app.db.intelligence_models import Analysis, CategoryDepartmentMapping
from app.db.models import Department, User
from app.services import duplicates
from app.services.gemini import PROMPT_VERSION, GeminiClient, GeminiFailure, without_identifiers


def process(engine: Engine, settings: Settings, complaint_id: UUID, gemini: GeminiClient | None) -> None:
    with Session(engine, expire_on_commit=False) as db:
        complaint = db.get(Complaint, complaint_id, with_for_update=True)
        if complaint is None:
            return
        duplicates.detect(db, complaint, settings)
        if gemini is None or complaint.ai_analysis_status != AnalysisStatus.PENDING:
            db.commit()
            return

        analysis = Analysis(
            complaint_id=complaint_id, provider="gemini", model_name=gemini.model, prompt_version=PROMPT_VERSION,
            status=AnalysisStatus.PROCESSING, started_at=datetime.now(UTC),
        )
        db.add(analysis)
        complaint.ai_analysis_status = AnalysisStatus.PROCESSING
        categories = {item.code: item for item in db.scalars(select(Category).where(Category.is_active))}
        departments = {item.code: item for item in db.scalars(
            select(Department).where(Department.organization_id == complaint.organization_id, Department.is_active)
        )}
        citizen_name = db.scalar(select(User.full_name).where(User.id == complaint.citizen_id)) or ""
        hint = next((code for code, item in categories.items() if item.id == complaint.category_id), None)
        db.commit()

        result = None
        failure = None
        try:
            if not categories:
                raise GeminiFailure("NO_ACTIVE_CATEGORIES")
            result = gemini.analyze(
                without_identifiers(complaint.title, citizen_name),
                without_identifiers(complaint.description, citizen_name),
                hint, sorted(categories), sorted(departments),
            )
        except GeminiFailure as error:
            failure = error.code

        status = AnalysisStatus.FAILED if result is None else AnalysisStatus.SUCCEEDED
        if result is not None:
            category = categories[result.category]
            mapping = (
                db.get(CategoryDepartmentMapping, (complaint.organization_id, category.id))
                if complaint.organization_id is not None else None
            )
            suggested = departments.get(result.recommended_department_code or "")
            fallback_id = mapping.department_id if mapping is not None else category.default_department_id
            if suggested is None:
                suggested = next((item for item in departments.values() if item.id == fallback_id), None)
            analysis.suggested_category_id = category.id
            analysis.suggested_department_id = suggested.id if suggested is not None else None
            analysis.suggested_priority = result.priority
            analysis.summary = without_identifiers(result.summary, citizen_name)[:1000]
            analysis.priority_reason = without_identifiers(result.priority_reason, citizen_name)[:1000]
            analysis.confidence = result.confidence
            analysis.needs_human_review = (
                result.needs_human_review or result.priority == Priority.CRITICAL
                or result.confidence < 0.7 or suggested is None or category.code == "OTHER"
            )
            analysis.safety_flags = [without_identifiers(flag, citizen_name)[:100] for flag in result.safety_flags]
        analysis.status = complaint.ai_analysis_status = status
        analysis.sanitized_error_code = failure
        analysis.completed_at = datetime.now(UTC)
        db.commit()
