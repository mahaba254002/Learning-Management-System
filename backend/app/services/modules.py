"""Institution capabilities, independent of account roles and academic policy."""
from pydantic import model_validator
from fastapi import HTTPException
from app.schemas.academic import Input


class InstitutionModules(Input):
    staff_directory: bool = True
    course_allocation: bool = True
    staff_attendance: bool = True
    student_records: bool = True
    student_attendance: bool = True
    student_portal: bool = True
    learning_materials: bool = True
    coursework: bool = True
    assessments: bool = True
    academic_reports: bool = True
    progression: bool = True

    @model_validator(mode='after')
    def dependencies(self):
        for feature, required in DEPENDENCIES.items():
            if getattr(self, feature):
                for parent in required:
                    if not getattr(self, parent):
                        raise ValueError(f'{feature} requires {parent}')
        return self


DEPENDENCIES = {
    'course_allocation': ['staff_directory'],
    'staff_attendance': ['staff_directory'],
    'student_records': ['course_allocation'],
    'student_attendance': ['student_records'],
    'student_portal': ['student_records'],
    'learning_materials': ['course_allocation'],
    'coursework': ['student_records'],
    'assessments': ['coursework'],
    'academic_reports': ['assessments'],
    'progression': ['student_records'],
}


def module_presets():
    full = InstitutionModules().model_dump()
    management = {key: key in {'staff_directory', 'course_allocation', 'staff_attendance'} for key in full}
    records = {**management, 'student_records': True, 'student_attendance': True}
    return {'MANAGEMENT': management, 'MANAGEMENT_WITH_STUDENTS': records, 'FULL': full}


def institution_modules(institution):
    # Empty settings mean full access for institutions created before modules existed.
    return InstitutionModules.model_validate(institution.module_settings or {}).model_dump()


def require_enabled(institution, *features):
    enabled = institution_modules(institution)
    for feature in features:
        if not enabled[feature]:
            raise HTTPException(403, f'{feature.replace("_", " ").capitalize()} is not enabled for this institution.')


def path_modules(path):
    """Classify authenticated routes; shared configuration and security stay available."""
    parts = path.strip('/').split('/')
    required = []
    if path.startswith('/api/student/'):
        required.append('student_portal')
    if 'management' in parts:
        if 'attendance' in parts: required.append('staff_attendance')
        elif 'allocations' in parts: required.append('course_allocation')
        else: required.append('staff_directory')
    if 'academic-structure' in parts or 'academic-years' in parts:
        required.append('course_allocation')
    if 'teacher' in parts or 'teachers' in parts or 'invitations' in parts:
        required.append('staff_directory')
    if 'staff-allocations' in parts: required.append('course_allocation')
    if 'teaching' in parts:
        required.append('course_allocation')
    if any(key in parts for key in ('students', 'enrollments', 'registrations', 'student-imports')):
        required.append('student_records')
    if 'attendance' in parts and 'management' not in parts:
        required.append('student_attendance')
    if 'materials' in parts: required.append('learning_materials')
    if any(key in parts for key in ('coursework', 'assignments', 'submissions')):
        required.append('coursework')
    if any(key in parts for key in ('scores', 'results-release', 'final-grades', 'completion', 'academic-record')):
        required.append('assessments')
    if 'academic-documents' in parts or 'report' in parts:
        required.append('academic_reports')
    if 'progression' in parts or 'promotion' in parts:
        required.append('progression')
    # Draft endpoints must follow the same restrictions as their live resources.
    if 'work-drafts' in parts or 'drafts' in parts:
        if 'submission' in parts: required.extend(['student_portal', 'coursework'])
        if 'assessment' in parts: required.append('coursework')
        if 'marks' in parts or 'scores' in parts: required.append('assessments')
    return set(required)


def check_module_access(db, institution_id, role, path):
    if institution_id is None or path.startswith('/api/platform/'):
        return
    from app.models.institution import Institution
    from app.models.user import UserRole
    institution = db.get(Institution, institution_id)
    required = path_modules(path)
    security_paths = {'/api/me', '/api/auth/logout', '/api/auth/change-password',
                      '/api/institution/modules', '/api/institution/subscription',
                      '/api/workspace-access/stop'}
    if role == UserRole.STUDENT and path not in security_paths:
        required.add('student_portal')
    if role in {UserRole.TEACHER, UserRole.STAFF} and path not in security_paths:
        required.add('staff_directory')
    require_enabled(institution, *required)


def dashboard_link_enabled(href, modules):
    sections = href.split('?')[0].strip('/').split('/')
    key = sections[1] if len(sections) > 1 else ''
    feature = {
        'staff': 'staff_directory', 'departments': 'staff_directory', 'teachers': 'staff_directory',
        'allocations': 'course_allocation', 'staff-attendance': 'staff_attendance',
        'classes': 'student_records', 'students': 'student_records', 'student-imports': 'student_records',
        'course-enrollment': 'student_records', 'academic-years': 'course_allocation', 'academic-structure': 'course_allocation',
        'attendance': 'student_attendance', 'materials': 'learning_materials', 'assignments': 'coursework',
        'coursework': 'coursework', 'scores': 'assessments', 'grades': 'assessments',
        'reports': 'academic_reports', 'academic-record': 'assessments', 'progression': 'progression',
    }.get(key)
    return feature is None or modules[feature]
