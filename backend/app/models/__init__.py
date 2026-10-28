from app.models.institution import Institution  # noqa: F401
from app.models.user import User  # noqa: F401
from app.models.verification_code import VerificationCode  # noqa: F401
from app.models.invitation import Invitation  # noqa: F401
from app.models.teacher import Teacher  # noqa: F401
from app.models.email_failure import EmailFailure  # noqa: F401
from app.models.academic import AcademicClass, Subject, Student, Enrollment, Coursework, Score, Attendance  # noqa: F401
from app.models.learning import CourseMaterial, Submission  # noqa: F401
from app.models.audit import AuditEvent
from app.models.subscription import Subscription, SubscriptionPayment, BillingNotice
from app.models.pilot import AuthSession, AcademicYear, AcademicPeriod, WorkDraft
from app.models.curriculum import Department, Programme, StudyLevel, CatalogueUnit, CourseRegistration, CourseCompletion

from app.models.academic_document import AcademicDocument

from app.models.final_grade import FinalGrade

from app.models.progression import Prerequisite,ProgressionDecision
