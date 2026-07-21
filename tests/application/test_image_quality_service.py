from document_intake.application.services.image_quality import QualityAssessmentError
from document_intake.domain.enums import QualityAssessmentErrorCode


def test_quality_assessment_error_is_safe() -> None:
    error = QualityAssessmentError(QualityAssessmentErrorCode.DECODE_FAILED)
    assert type(error) is QualityAssessmentError
    assert error.code is QualityAssessmentErrorCode.DECODE_FAILED
    assert str(error) == "DECODE_FAILED"
    assert repr(error) == "QualityAssessmentError(code=DECODE_FAILED)"
    assert error.__cause__ is None
