# Generated route reference

Generated from source with `python scripts/update_reference.py`. This inventory records declared routes; it does not prove authorization or deployed availability. See CODE_MAP.md for services and tests.

## Browser routes

| Browser URL | Component | Source |
| --- | --- | --- |
| `/` | LoginPage | [LoginPage.jsx](../frontend/src/pages/auth/LoginPage.jsx) |
| `/sign-in` | LoginPage | [LoginPage.jsx](../frontend/src/pages/auth/LoginPage.jsx) |
| `/login` | LoginPage | [LoginPage.jsx](../frontend/src/pages/auth/LoginPage.jsx) |
| `/forgot-password` | ForgotPasswordPage | [ForgotPasswordPage.jsx](../frontend/src/pages/auth/ForgotPasswordPage.jsx) |
| `/reset-password` | ResetPasswordPage | [ResetPasswordPage.jsx](../frontend/src/pages/auth/ResetPasswordPage.jsx) |
| `/invite/:token` | InvitePage | [InvitePage.jsx](../frontend/src/pages/invite/InvitePage.jsx) |
| `/student/login` | StudentLoginPage | [StudentLoginPage.jsx](../frontend/src/pages/student/StudentLoginPage.jsx) |
| `/student/forgot-password` | StudentForgotPasswordPage | [StudentForgotPasswordPage.jsx](../frontend/src/pages/student/StudentForgotPasswordPage.jsx) |
| `/student/reset-password` | StudentResetPasswordPage | [StudentResetPasswordPage.jsx](../frontend/src/pages/student/StudentResetPasswordPage.jsx) |
| `/student/change-password` | ChangePasswordPage | [ChangePasswordPage.jsx](../frontend/src/pages/auth/ChangePasswordPage.jsx) |
| `/teacher/change-password` | ChangePasswordPage | [ChangePasswordPage.jsx](../frontend/src/pages/auth/ChangePasswordPage.jsx) |
| `/change-password` | ChangePasswordPage | [ChangePasswordPage.jsx](../frontend/src/pages/auth/ChangePasswordPage.jsx) |
| `/institution` | InstitutionLayout | [InstitutionLayout.jsx](../frontend/src/pages/institution/InstitutionLayout.jsx) |
| `/institution/dashboard` | InstitutionDashboardPage | [InstitutionDashboardPage.jsx](../frontend/src/pages/institution/InstitutionDashboardPage.jsx) |
| `/institution/reports` | AcademicDocumentsPage | [AcademicDocumentsPage.jsx](../frontend/src/pages/AcademicDocumentsPage.jsx) |
| `/institution/invitations` | InstitutionInvitationsPage | [InstitutionInvitationsPage.jsx](../frontend/src/pages/institution/InstitutionInvitationsPage.jsx) |
| `/institution/teachers` | InstitutionTeachersPage | [InstitutionTeachersPage.jsx](../frontend/src/pages/institution/InstitutionTeachersPage.jsx) |
| `/institution/teachers/:teacherId` | InstitutionTeacherDetailPage | [InstitutionTeacherDetailPage.jsx](../frontend/src/pages/institution/InstitutionTeacherDetailPage.jsx) |
| `/institution/classes` | InstitutionClassesPage | [InstitutionClassesPage.jsx](../frontend/src/pages/institution/InstitutionClassesPage.jsx) |
| `/institution/progression` | InstitutionProgressionPage | [StudentProgressionPage.jsx](../frontend/src/pages/institution/StudentProgressionPage.jsx) |
| `/institution/academic-years` | AcademicYearsPage | [AcademicYearsPage.jsx](../frontend/src/pages/institution/AcademicYearsPage.jsx) |
| `/institution/academic-structure` | AcademicStructurePage | [AcademicStructurePage.jsx](../frontend/src/pages/institution/AcademicStructurePage.jsx) |
| `/institution/course-enrollment` | CourseRegistrationsPage | [CourseRegistrationsPage.jsx](../frontend/src/pages/institution/CourseRegistrationsPage.jsx) |
| `/institution/student-imports` | StudentImportPage | [StudentImportPage.jsx](../frontend/src/pages/institution/StudentImportPage.jsx) |
| `/institution/classes/:classId` | ClassStudentsPage | [ClassStudentsPage.jsx](../frontend/src/pages/teacher/ClassStudentsPage.jsx) |
| `/institution/students` | AdminUsersPage | [AdminPages.jsx](../frontend/src/pages/AdminPages.jsx) |
| `/institution/users` | AdminUsersPage | [AdminPages.jsx](../frontend/src/pages/AdminPages.jsx) |
| `/institution/attendance` | TeacherAttendancePage | [TeacherAttendancePage.jsx](../frontend/src/pages/teacher/TeacherAttendancePage.jsx) |
| `/institution/coursework` | TeacherCourseworkPage | [TeacherCourseworkPage.jsx](../frontend/src/pages/teacher/TeacherCourseworkPage.jsx) |
| `/institution/materials` | TeacherMaterialsPage | [TeacherMaterialsPage.jsx](../frontend/src/pages/teacher/TeacherMaterialsPage.jsx) |
| `/institution/scores` | TeacherScoresPage | [TeacherScoresPage.jsx](../frontend/src/pages/teacher/TeacherScoresPage.jsx) |
| `/institution/audit-logs` | AdminAuditPage | [AdminPages.jsx](../frontend/src/pages/AdminPages.jsx) |
| `/institution/settings` | InstitutionSettingsPage | [AdminPages.jsx](../frontend/src/pages/AdminPages.jsx) |
| `/institution/account` | AdminAccountPage | [AdminPages.jsx](../frontend/src/pages/AdminPages.jsx) |
| `/teacher` | TeacherLayout | [TeacherLayout.jsx](../frontend/src/pages/teacher/TeacherLayout.jsx) |
| `/teacher/dashboard` | TeacherDashboardPage | [TeacherDashboardPage.jsx](../frontend/src/pages/teacher/TeacherDashboardPage.jsx) |
| `/teacher/reports` | AcademicDocumentsPage | [AcademicDocumentsPage.jsx](../frontend/src/pages/AcademicDocumentsPage.jsx) |
| `/teacher/profile` | TeacherProfilePage | [TeacherProfilePage.jsx](../frontend/src/pages/teacher/TeacherProfilePage.jsx) |
| `/teacher/classes` | TeacherClassesPage | [TeacherClassesPage.jsx](../frontend/src/pages/teacher/TeacherClassesPage.jsx) |
| `/teacher/classes/:classId` | ClassStudentsPage | [ClassStudentsPage.jsx](../frontend/src/pages/teacher/ClassStudentsPage.jsx) |
| `/teacher/attendance` | TeacherAttendancePage | [TeacherAttendancePage.jsx](../frontend/src/pages/teacher/TeacherAttendancePage.jsx) |
| `/teacher/coursework` | TeacherCourseworkPage | [TeacherCourseworkPage.jsx](../frontend/src/pages/teacher/TeacherCourseworkPage.jsx) |
| `/teacher/materials` | TeacherMaterialsPage | [TeacherMaterialsPage.jsx](../frontend/src/pages/teacher/TeacherMaterialsPage.jsx) |
| `/teacher/scores` | TeacherScoresPage | [TeacherScoresPage.jsx](../frontend/src/pages/teacher/TeacherScoresPage.jsx) |
| `/student` | StudentLayout | [StudentLayout.jsx](../frontend/src/pages/student/StudentLayout.jsx) |
| `/student/dashboard` | StudentDashboardPage | [StudentDashboardPage.jsx](../frontend/src/pages/student/StudentDashboardPage.jsx) |
| `/student/reports` | AcademicDocumentsPage | [AcademicDocumentsPage.jsx](../frontend/src/pages/AcademicDocumentsPage.jsx) |
| `/student/subjects` | StudentSubjectsPage | [StudentSubjectsPage.jsx](../frontend/src/pages/student/StudentSubjectsPage.jsx) |
| `/student/subjects/:subjectId` | StudentSubjectPage | [StudentSubjectsPage.jsx](../frontend/src/pages/student/StudentSubjectsPage.jsx) |
| `/student/attendance` | StudentAttendancePage | [StudentAttendancePage.jsx](../frontend/src/pages/student/StudentAttendancePage.jsx) |
| `/student/assignments` | StudentCourseworkPage | [StudentCourseworkPage.jsx](../frontend/src/pages/student/StudentCourseworkPage.jsx) |
| `/student/assignments/:assignmentId` | StudentAssignmentPage | [StudentAssignmentPage.jsx](../frontend/src/pages/student/StudentAssignmentPage.jsx) |
| `/student/grades` | StudentCourseworkPage | [StudentCourseworkPage.jsx](../frontend/src/pages/student/StudentCourseworkPage.jsx) |
| `/student/profile` | StudentProfilePage | [StudentProfilePage.jsx](../frontend/src/pages/student/StudentProfilePage.jsx) |
| `/student/progression` | StudentProgressionPage | [StudentProgressionPage.jsx](../frontend/src/pages/student/StudentProgressionPage.jsx) |
| `/student/academic-record` | AcademicRecordPage | [AcademicRecordPage.jsx](../frontend/src/pages/student/AcademicRecordPage.jsx) |
| `/teacher/login` | TeacherLoginPage | [TeacherLoginPage.jsx](../frontend/src/pages/teacher/TeacherLoginPage.jsx) |
| `/teacher/forgot-password` | TeacherForgotPasswordPage | [TeacherForgotPasswordPage.jsx](../frontend/src/pages/teacher/TeacherForgotPasswordPage.jsx) |
| `/teacher/reset-password` | TeacherResetPasswordPage | [TeacherResetPasswordPage.jsx](../frontend/src/pages/teacher/TeacherResetPasswordPage.jsx) |
| `/platform` | PlatformLayout | [PlatformLayout.jsx](../frontend/src/pages/platform/PlatformLayout.jsx) |
| `/platform/dashboard` | PlatformDashboardPage | [PlatformDashboardPage.jsx](../frontend/src/pages/platform/PlatformDashboardPage.jsx) |
| `/platform/institutions` | PlatformInstitutionsPage | [PlatformInstitutionsPage.jsx](../frontend/src/pages/platform/PlatformInstitutionsPage.jsx) |
| `/platform/institutions/:institutionId` | PlatformInstitutionDetailPage | [PlatformInstitutionDetailPage.jsx](../frontend/src/pages/platform/PlatformInstitutionDetailPage.jsx) |
| `/platform/billing` | PlatformBillingPage | [PlatformBillingPage.jsx](../frontend/src/pages/platform/PlatformBillingPage.jsx) |
| `/platform/backup` | PlatformBackupPage | [PlatformBackupPage.jsx](../frontend/src/pages/platform/PlatformBackupPage.jsx) |
| `/platform/restore` | PlatformRestorePage | [PlatformRestorePage.jsx](../frontend/src/pages/platform/PlatformRestorePage.jsx) |
| `/platform/users` | AdminUsersPage | [AdminPages.jsx](../frontend/src/pages/AdminPages.jsx) |
| `/platform/usage` | PlatformUsagePage | [AdminPages.jsx](../frontend/src/pages/AdminPages.jsx) |
| `/platform/revenue` | Navigate | [App.jsx](../frontend/src/App.jsx) |
| `/platform/audit-logs` | AdminAuditPage | [AdminPages.jsx](../frontend/src/pages/AdminPages.jsx) |
| `/platform/settings` | AdminAccountPage | [AdminPages.jsx](../frontend/src/pages/AdminPages.jsx) |
| `*` | NotFoundPage | [App.jsx](../frontend/src/App.jsx) |

## API endpoints

Includes literal APIRouter prefixes. Function links identify the handler; dependency checks determine permissions. Dynamic/nonliteral declarations, if any, require manual review.

| Method | Endpoint | Handler | Source |
| --- | --- | --- | --- |
| GET | `/api/academic-documents/options` | `options` | [academic_documents.py](../backend/app/api/routes/academic_documents.py) |
| GET | `/api/academic-documents/preview` | `preview` | [academic_documents.py](../backend/app/api/routes/academic_documents.py) |
| POST | `/api/academic-documents` | `issue` | [academic_documents.py](../backend/app/api/routes/academic_documents.py) |
| GET | `/api/academic-documents` | `listing` | [academic_documents.py](../backend/app/api/routes/academic_documents.py) |
| GET | `/api/academic-documents/{document_id}` | `detail` | [academic_documents.py](../backend/app/api/routes/academic_documents.py) |
| POST | `/api/academic-documents/{document_id}/revoke` | `revoke` | [academic_documents.py](../backend/app/api/routes/academic_documents.py) |
| GET | `/api/institution/academic-years` | `years` | [academic_years.py](../backend/app/api/routes/academic_years.py) |
| POST | `/api/institution/academic-years` | `create` | [academic_years.py](../backend/app/api/routes/academic_years.py) |
| POST | `/api/institution/academic-years/{year_id}/periods` | `period` | [academic_years.py](../backend/app/api/routes/academic_years.py) |
| POST | `/api/institution/academic-years/{year_id}/transition` | `transition` | [academic_years.py](../backend/app/api/routes/academic_years.py) |
| POST | `/api/institution/academic-years/{year_id}/promotion/preview` | `preview_promotion` | [academic_years.py](../backend/app/api/routes/academic_years.py) |
| POST | `/api/institution/academic-years/{year_id}/promotion/commit` | `promote` | [academic_years.py](../backend/app/api/routes/academic_years.py) |
| GET | `/api/institution/settings` | `get_settings` | [administration.py](../backend/app/api/routes/administration.py) |
| PUT | `/api/institution/settings` | `save_settings` | [administration.py](../backend/app/api/routes/administration.py) |
| GET | `/api/institution/overview` | `overview` | [administration.py](../backend/app/api/routes/administration.py) |
| GET | `/api/institution/users` | `institution_users` | [administration.py](../backend/app/api/routes/administration.py) |
| GET | `/api/platform/users` | `platform_users` | [administration.py](../backend/app/api/routes/administration.py) |
| PUT | `/api/institution/users/{user_id}/status` | `institution_user_status` | [administration.py](../backend/app/api/routes/administration.py) |
| PUT | `/api/platform/users/{user_id}/status` | `platform_user_status` | [administration.py](../backend/app/api/routes/administration.py) |
| PUT | `/api/platform/institutions/{institution_id}/status` | `institution_status` | [administration.py](../backend/app/api/routes/administration.py) |
| GET | `/api/institution/audit-logs` | `institution_audit` | [administration.py](../backend/app/api/routes/administration.py) |
| GET | `/api/platform/audit-logs` | `platform_audit` | [administration.py](../backend/app/api/routes/administration.py) |
| GET | `/api/platform/usage` | `usage` | [administration.py](../backend/app/api/routes/administration.py) |
| POST | `/api/auth/login` | `login` | [auth.py](../backend/app/api/routes/auth.py) |
| POST | `/api/auth/teacher/login` | `teacher_login` | [auth.py](../backend/app/api/routes/auth.py) |
| POST | `/api/auth/student/login` | `student_login` | [auth.py](../backend/app/api/routes/auth.py) |
| POST | `/api/auth/refresh` | `refresh` | [auth.py](../backend/app/api/routes/auth.py) |
| POST | `/api/auth/logout` | `logout` | [auth.py](../backend/app/api/routes/auth.py) |
| POST | `/api/auth/change-password` | `change_password` | [auth.py](../backend/app/api/routes/auth.py) |
| POST | `/api/auth/forgot-password` | `forgot_password` | [auth.py](../backend/app/api/routes/auth.py) |
| POST | `/api/auth/teacher/forgot-password` | `teacher_forgot_password` | [auth.py](../backend/app/api/routes/auth.py) |
| POST | `/api/auth/student/forgot-password` | `student_forgot_password` | [auth.py](../backend/app/api/routes/auth.py) |
| POST | `/api/auth/reset-password` | `reset_password` | [auth.py](../backend/app/api/routes/auth.py) |
| POST | `/api/auth/teacher/reset-password` | `teacher_reset_password` | [auth.py](../backend/app/api/routes/auth.py) |
| POST | `/api/auth/student/reset-password` | `student_reset_password` | [auth.py](../backend/app/api/routes/auth.py) |
| GET | `/api/platform/backups/capabilities` | `capabilities` | [backups.py](../backend/app/api/routes/backups.py) |
| POST | `/api/platform/backups/institution` | `institution_backup` | [backups.py](../backend/app/api/routes/backups.py) |
| POST | `/api/platform/backups/platform` | `platform_backup` | [backups.py](../backend/app/api/routes/backups.py) |
| POST | `/api/platform/backups/restore/preview` | `restore_preview` | [backups.py](../backend/app/api/routes/backups.py) |
| POST | `/api/platform/backups/restore/authorize` | `authorize_restore` | [backups.py](../backend/app/api/routes/backups.py) |
| POST | `/api/platform/backups/restore/execute` | `restore_execute` | [backups.py](../backend/app/api/routes/backups.py) |
| POST | `/api/contact/enquiries` | `send_product_enquiry` | [contact.py](../backend/app/api/routes/contact.py) |
| GET | `/api/platform/academic-templates` | `templates` | [curriculum.py](../backend/app/api/routes/curriculum.py) |
| GET | `/api/platform/institutions/{institution_id}/academic-configuration` | `platform_configuration` | [curriculum.py](../backend/app/api/routes/curriculum.py) |
| PUT | `/api/platform/institutions/{institution_id}/academic-configuration` | `configure` | [curriculum.py](../backend/app/api/routes/curriculum.py) |
| GET | `/api/institution/academic-configuration` | `configuration` | [curriculum.py](../backend/app/api/routes/curriculum.py) |
| GET | `/api/institution/academic-structure` | `structure` | [curriculum.py](../backend/app/api/routes/curriculum.py) |
| POST | `/api/institution/academic-structure/{kind}` | `create_structure` | [curriculum.py](../backend/app/api/routes/curriculum.py) |
| PUT | `/api/institution/academic-structure/{kind}/{record_id}` | `edit_structure` | [curriculum.py](../backend/app/api/routes/curriculum.py) |
| GET | `/api/teaching/subjects/{subject_id}/students` | `subject_roster` | [curriculum.py](../backend/app/api/routes/curriculum.py) |
| GET | `/api/institution/subjects/{subject_id}/registrations` | `registrations` | [curriculum.py](../backend/app/api/routes/curriculum.py) |
| PUT | `/api/institution/subjects/{subject_id}/registrations` | `register` | [curriculum.py](../backend/app/api/routes/curriculum.py) |
| PUT | `/api/institution/subjects/{subject_id}/completion` | `complete` | [curriculum.py](../backend/app/api/routes/curriculum.py) |
| GET | `/api/student/academic-record` | `academic_record` | [curriculum.py](../backend/app/api/routes/curriculum.py) |
| GET | `/api/dashboard` | `dashboard` | [dashboards.py](../backend/app/api/routes/dashboards.py) |
| GET | `/api/drafts/{kind}/{resource}` | `get_draft` | [drafts.py](../backend/app/api/routes/drafts.py) |
| PUT | `/api/drafts/{kind}/{resource}` | `save_draft` | [drafts.py](../backend/app/api/routes/drafts.py) |
| GET | `/api/teaching/subjects/{subject_id}/final-grades` | `preview` | [final_grades.py](../backend/app/api/routes/final_grades.py) |
| PUT | `/api/institution/subjects/{subject_id}/final-grades` | `approve` | [final_grades.py](../backend/app/api/routes/final_grades.py) |
| GET | `/api/platform/institutions/{institution_id}/grading-offerings` | `offerings` | [grading_policy.py](../backend/app/api/routes/grading_policy.py) |
| PUT | `/api/platform/institutions/{institution_id}/grading-offerings/{subject_id}` | `apply` | [grading_policy.py](../backend/app/api/routes/grading_policy.py) |
| GET | `/api/institution/teachers` | `list_teachers` | [invitations.py](../backend/app/api/routes/invitations.py) |
| GET | `/api/institution/teachers/{teacher_id}` | `get_teacher` | [invitations.py](../backend/app/api/routes/invitations.py) |
| POST | `/api/institution/invitations/teachers` | `send_teacher_invitation` | [invitations.py](../backend/app/api/routes/invitations.py) |
| GET | `/api/institution/invitations` | `list_invitations` | [invitations.py](../backend/app/api/routes/invitations.py) |
| POST | `/api/institution/invitations/{invitation_id}/approve` | `approve_invitation` | [invitations.py](../backend/app/api/routes/invitations.py) |
| POST | `/api/institution/invitations/{invitation_id}/reject` | `reject_invitation` | [invitations.py](../backend/app/api/routes/invitations.py) |
| GET | `/api/invitations/{token}` | `view_invitation` | [invitations.py](../backend/app/api/routes/invitations.py) |
| POST | `/api/invitations/{token}/submit` | `submit_invitation` | [invitations.py](../backend/app/api/routes/invitations.py) |
| GET | `/api/student/profile` | `profile` | [learning.py](../backend/app/api/routes/learning.py) |
| GET | `/api/student/subjects` | `subjects` | [learning.py](../backend/app/api/routes/learning.py) |
| GET | `/api/student/attendance` | `attendance` | [learning.py](../backend/app/api/routes/learning.py) |
| GET | `/api/student/subjects/{subject_id}/materials` | `materials` | [learning.py](../backend/app/api/routes/learning.py) |
| GET | `/api/student/assignments` | `assignments` | [learning.py](../backend/app/api/routes/learning.py) |
| PUT | `/api/student/assignments/{work_id}/submission` | `save_submission` | [learning.py](../backend/app/api/routes/learning.py) |
| GET | `/api/teaching/subjects/{subject_id}/materials` | `teacher_materials` | [learning.py](../backend/app/api/routes/learning.py) |
| POST | `/api/teaching/subjects/{subject_id}/materials` | `create_material` | [learning.py](../backend/app/api/routes/learning.py) |
| PUT | `/api/teaching/materials/{material_id}` | `update_material` | [learning.py](../backend/app/api/routes/learning.py) |
| GET | `/api/teaching/coursework/{work_id}/submissions` | `review_submissions` | [learning.py](../backend/app/api/routes/learning.py) |
| GET | `/api/student/final-grades` | `final_results` | [learning.py](../backend/app/api/routes/learning.py) |
| POST | `/api/platform/institutions/request-create` | `request_create_institution` | [platform.py](../backend/app/api/routes/platform.py) |
| POST | `/api/platform/institutions/confirm-create` | `confirm_create_institution` | [platform.py](../backend/app/api/routes/platform.py) |
| POST | `/api/platform/institutions/{institution_id}/request-archive` | `request_archive_institution` | [platform.py](../backend/app/api/routes/platform.py) |
| POST | `/api/platform/institutions/confirm-archive` | `confirm_archive_institution` | [platform.py](../backend/app/api/routes/platform.py) |
| GET | `/api/platform/institutions` | `list_institutions` | [platform.py](../backend/app/api/routes/platform.py) |
| POST | `/api/platform/institutions/{institution_id}/admins` | `create_institution_admin` | [platform.py](../backend/app/api/routes/platform.py) |
| GET | `/api/platform/stats` | `get_platform_stats` | [platform.py](../backend/app/api/routes/platform.py) |
| GET | `/api/teaching/overview` | `teaching_overview` | [product.py](../backend/app/api/routes/product.py) |
| GET | `/api/platform/institution-directory` | `institution_directory` | [product.py](../backend/app/api/routes/product.py) |
| GET | `/api/platform/subscription-summary` | `subscription_summary` | [product.py](../backend/app/api/routes/product.py) |
| GET | `/api/institution/learning-settings` | `read_learning_settings` | [product.py](../backend/app/api/routes/product.py) |
| PUT | `/api/institution/learning-settings` | `save_learning_settings` | [product.py](../backend/app/api/routes/product.py) |
| PUT | `/api/institution/students/{user_id}/login` | `student_access` | [product.py](../backend/app/api/routes/product.py) |
| POST | `/api/institution/students/{user_id}/reset-password` | `reset_student_password` | [product.py](../backend/app/api/routes/product.py) |
| GET | `/api/teaching/classes/{class_id}/report` | `class_report` | [product.py](../backend/app/api/routes/product.py) |
| GET | `/api/institution/subscription` | `institution_subscription` | [product.py](../backend/app/api/routes/product.py) |
| GET | `/api/platform/institutions/{institution_id}/detail` | `institution_detail` | [product.py](../backend/app/api/routes/product.py) |
| PUT | `/api/platform/institutions/{institution_id}/subscription` | `configure_subscription` | [product.py](../backend/app/api/routes/product.py) |
| POST | `/api/platform/institutions/{institution_id}/payments` | `record_payment` | [product.py](../backend/app/api/routes/product.py) |
| GET | `/api/platform/institutions/{institution_id}/prerequisites` | `prerequisites` | [progression.py](../backend/app/api/routes/progression.py) |
| PUT | `/api/platform/institutions/{institution_id}/prerequisites/{course_id}` | `set_prerequisites` | [progression.py](../backend/app/api/routes/progression.py) |
| POST | `/api/institution/progression/preview` | `preview` | [progression.py](../backend/app/api/routes/progression.py) |
| POST | `/api/institution/progression/approve` | `approve` | [progression.py](../backend/app/api/routes/progression.py) |
| GET | `/api/institution/progression/history` | `history` | [progression.py](../backend/app/api/routes/progression.py) |
| GET | `/api/student/progression` | `student_history` | [progression.py](../backend/app/api/routes/progression.py) |
| POST | `/api/institution/student-imports/parse` | `parse_file` | [student_imports.py](../backend/app/api/routes/student_imports.py) |
| POST | `/api/institution/student-imports/preview` | `preview` | [student_imports.py](../backend/app/api/routes/student_imports.py) |
| POST | `/api/institution/student-imports/commit` | `execute` | [student_imports.py](../backend/app/api/routes/student_imports.py) |
| GET | `/api/teacher/profile` | `profile` | [teaching.py](../backend/app/api/routes/teaching.py) |
| GET | `/api/teaching/classes` | `classes` | [teaching.py](../backend/app/api/routes/teaching.py) |
| POST | `/api/teaching/classes` | `create_class` | [teaching.py](../backend/app/api/routes/teaching.py) |
| PUT | `/api/teaching/classes/{class_id}` | `update_class` | [teaching.py](../backend/app/api/routes/teaching.py) |
| GET | `/api/teaching/subjects` | `subjects` | [teaching.py](../backend/app/api/routes/teaching.py) |
| POST | `/api/teaching/classes/{class_id}/subjects` | `create_subject` | [teaching.py](../backend/app/api/routes/teaching.py) |
| PUT | `/api/teaching/subjects/{subject_id}` | `update_subject` | [teaching.py](../backend/app/api/routes/teaching.py) |
| GET | `/api/teaching/classes/{class_id}/students` | `roster` | [teaching.py](../backend/app/api/routes/teaching.py) |
| POST | `/api/teaching/classes/{class_id}/students` | `create_student` | [teaching.py](../backend/app/api/routes/teaching.py) |
| POST | `/api/teaching/classes/{class_id}/enrollments` | `enroll` | [teaching.py](../backend/app/api/routes/teaching.py) |
| PUT | `/api/teaching/classes/{class_id}/students/{student_id}` | `edit_student` | [teaching.py](../backend/app/api/routes/teaching.py) |
| DELETE | `/api/teaching/classes/{class_id}/enrollments/{student_id}` | `remove_enrollment` | [teaching.py](../backend/app/api/routes/teaching.py) |
| GET | `/api/teaching/classes/{class_id}/attendance` | `attendance` | [teaching.py](../backend/app/api/routes/teaching.py) |
| PUT | `/api/teaching/classes/{class_id}/attendance` | `save_attendance` | [teaching.py](../backend/app/api/routes/teaching.py) |
| GET | `/api/teaching/subjects/{subject_id}/coursework` | `coursework` | [teaching.py](../backend/app/api/routes/teaching.py) |
| POST | `/api/teaching/subjects/{subject_id}/coursework` | `create_coursework` | [teaching.py](../backend/app/api/routes/teaching.py) |
| PUT | `/api/teaching/coursework/{coursework_id}` | `edit_coursework` | [teaching.py](../backend/app/api/routes/teaching.py) |
| GET | `/api/teaching/coursework/{coursework_id}/scores` | `scores` | [teaching.py](../backend/app/api/routes/teaching.py) |
| PUT | `/api/teaching/coursework/{coursework_id}/results-release` | `release_results` | [teaching.py](../backend/app/api/routes/teaching.py) |
| PUT | `/api/teaching/coursework/{coursework_id}/scores` | `save_scores` | [teaching.py](../backend/app/api/routes/teaching.py) |
| GET | `/api/student/coursework` | `student_coursework` | [teaching.py](../backend/app/api/routes/teaching.py) |
| GET | `/api/teaching/subjects/{subject_id}/periods` | `assessment_periods` | [teaching.py](../backend/app/api/routes/teaching.py) |
| POST | `/api/workspace-access/start` | `start_workspace` | [workspace_access.py](../backend/app/api/routes/workspace_access.py) |
| POST | `/api/workspace-access/stop` | `stop_workspace` | [workspace_access.py](../backend/app/api/routes/workspace_access.py) |

## Test modules

Run from backend: `python -m pytest tests/<module>.py -q`. See the maintenance handbook for isolated database constraints.

- [test_academic_documents.py](../backend/tests/test_academic_documents.py)
- [test_administration.py](../backend/tests/test_administration.py)
- [test_backups.py](../backend/tests/test_backups.py)
- [test_contact.py](../backend/tests/test_contact.py)
- [test_curriculum.py](../backend/tests/test_curriculum.py)
- [test_grading_rules.py](../backend/tests/test_grading_rules.py)
- [test_institution_product.py](../backend/tests/test_institution_product.py)
- [test_learning.py](../backend/tests/test_learning.py)
- [test_login.py](../backend/tests/test_login.py)
- [test_pilot.py](../backend/tests/test_pilot.py)
- [test_progression.py](../backend/tests/test_progression.py)
- [test_seed_demo.py](../backend/tests/test_seed_demo.py)
- [test_teaching.py](../backend/tests/test_teaching.py)
- [test_workspace_access.py](../backend/tests/test_workspace_access.py)

## Database model map

Columns below are declared on each class; inherited tenant IDs, UUIDs and timestamps are defined in backend/app/db/base.py. Read each model for constraints, indexes and types. Changes also need an Alembic migration.

| Table | Model | Declared fields | Source |
| --- | --- | --- | --- |
| `academic_classes` | `AcademicClass` | `name`, `academic_year`, `supervisor_id`, `programme_id`, `level_id` | [academic.py](../backend/app/models/academic.py) |
| `teaching_subjects` | `Subject` | `grading_policy`, `class_id`, `name`, `teacher_id`, `catalogue_id`, `period_id`, `registration_mode` | [academic.py](../backend/app/models/academic.py) |
| `students` | `Student` | `user_id`, `admission_number`, `phone` | [academic.py](../backend/app/models/academic.py) |
| `class_enrollments` | `Enrollment` | `class_id`, `student_id`, `active` | [academic.py](../backend/app/models/academic.py) |
| `coursework` | `Coursework` | `period_id`, `subject_id`, `title`, `instructions`, `kind`, `due_at`, `max_score`, `published`, `grades_released`, `assessment_mode`, `rubric_labels`, `grading_bands`, `allow_late_submissions` | [academic.py](../backend/app/models/academic.py) |
| `student_scores` | `Score` | `coursework_id`, `student_id`, `score`, `competency_label`, `feedback` | [academic.py](../backend/app/models/academic.py) |
| `student_attendance` | `Attendance` | `class_id`, `subject_id`, `scope_key`, `day`, `student_id`, `status`, `note` | [academic.py](../backend/app/models/academic.py) |
| `academic_documents` | `AcademicDocument` | `student_id`, `class_id`, `kind`, `status`, `reference`, `source_digest`, `snapshot`, `issued_by_name`, `revoked_at`, `revocation_reason` | [academic_document.py](../backend/app/models/academic_document.py) |
| `audit_events` | `AuditEvent` | `institution_id`, `actor_id`, `action`, `target_id`, `detail`, `ip_address`, `request_method`, `request_path` | [audit.py](../backend/app/models/audit.py) |
| `academic_departments` | `Department` | `code`, `name` | [curriculum.py](../backend/app/models/curriculum.py) |
| `academic_programmes` | `Programme` | `department_id`, `code`, `name`, `award` | [curriculum.py](../backend/app/models/curriculum.py) |
| `academic_levels` | `StudyLevel` | `programme_id`, `code`, `name`, `position` | [curriculum.py](../backend/app/models/curriculum.py) |
| `academic_catalogue` | `CatalogueUnit` | `programme_id`, `level_id`, `code`, `name`, `credits` | [curriculum.py](../backend/app/models/curriculum.py) |
| `course_registrations` | `CourseRegistration` | `subject_id`, `student_id`, `active` | [curriculum.py](../backend/app/models/curriculum.py) |
| `course_completions` | `CourseCompletion` | `subject_id`, `student_id`, `outcome`, `credits`, `released` | [curriculum.py](../backend/app/models/curriculum.py) |
| `email_failures` | `EmailFailure` | `recipient`, `subject`, `email_type`, `error_message`, `context`, `resolved` | [email_failure.py](../backend/app/models/email_failure.py) |
| `final_grades` | `FinalGrade` | `subject_id`, `student_id`, `scope`, `source_digest`, `result`, `released` | [final_grade.py](../backend/app/models/final_grade.py) |
| `institutions` | `Institution` | `name`, `learning_settings`, `academic_configuration`, `code`, `type`, `country`, `address`, `official_email`, `phone`, `website`, `status`, `archived_at`, `archived_by` | [institution.py](../backend/app/models/institution.py) |
| `invitations` | `Invitation` | `invited_role`, `email`, `invite_token`, `status`, `submitted_data`, `invited_by`, `reviewed_by`, `reviewed_at`, `created_user_id`, `expires_at` | [invitation.py](../backend/app/models/invitation.py) |
| `course_materials` | `CourseMaterial` | `subject_id`, `title`, `body`, `link_url`, `published` | [learning.py](../backend/app/models/learning.py) |
| `assignment_submissions` | `Submission` | `coursework_id`, `student_id`, `answer`, `link_url`, `status`, `submitted_at`, `is_late`, `version` | [learning.py](../backend/app/models/learning.py) |
| `auth_sessions` | `AuthSession` | `user_id`, `refresh_digest`, `expires_at`, `remember_me`, `revoked` | [pilot.py](../backend/app/models/pilot.py) |
| `academic_years` | `AcademicYear` | `name`, `start_date`, `end_date`, `status` | [pilot.py](../backend/app/models/pilot.py) |
| `academic_periods` | `AcademicPeriod` | `year_id`, `name`, `start_date`, `end_date` | [pilot.py](../backend/app/models/pilot.py) |
| `work_drafts` | `WorkDraft` | `actor_id`, `user_id`, `kind`, `resource`, `data`, `version` | [pilot.py](../backend/app/models/pilot.py) |
| `course_prerequisites` | `Prerequisite` | `course_id`, `required_id`, `minimum_percentage` | [progression.py](../backend/app/models/progression.py) |
| `progression_decisions` | `ProgressionDecision` | `source_class_id`, `target_class_id`, `student_id`, `decision`, `snapshot` | [progression.py](../backend/app/models/progression.py) |
| `institution_subscriptions` | `Subscription` | `monthly_fee`, `next_due_date`, `grace_days`, `enforcement_enabled`, `manually_frozen`, `support_email` | [subscription.py](../backend/app/models/subscription.py) |
| `subscription_payments` | `SubscriptionPayment` | `amount`, `reference`, `paid_on`, `previous_due_date`, `next_due_date`, `recorded_by` | [subscription.py](../backend/app/models/subscription.py) |
| `billing_notices` | `BillingNotice` | `notice_key`, `sent_at` | [subscription.py](../backend/app/models/subscription.py) |
| `teachers` | `Teacher` | `user_id`, `gender`, `date_of_birth`, `phone`, `qualification`, `specialization`, `employment_type`, `status`, `invited_from` | [teacher.py](../backend/app/models/teacher.py) |
| `users` | `User` | `institution_id`, `username`, `first_name`, `last_name`, `email`, `student_login_method`, `student_login_id`, `password_hash`, `role`, `status`, `must_change_password`, `password_changed_at` | [user.py](../backend/app/models/user.py) |
| `verification_codes` | `VerificationCode` | `user_id`, `purpose`, `code_hash`, `payload`, `expires_at`, `consumed_at`, `attempt_count` | [verification_code.py](../backend/app/models/verification_code.py) |

## Migration source inventory

Inspect revision/down_revision inside each file and use Alembic history for execution order. Filename order alone does not establish ancestry. Downgrades may deliberately refuse to discard populated history.

- [3d189991fe53_create_institutions_and_users_tables.py](../backend/alembic/versions/3d189991fe53_create_institutions_and_users_tables.py)
- [5934dac1f22c_make_email_required_and_unique_on_users.py](../backend/alembic/versions/5934dac1f22c_make_email_required_and_unique_on_users.py)
- [a0c44aa007dd_add_invitations_table.py](../backend/alembic/versions/a0c44aa007dd_add_invitations_table.py)
- [a3c4d5e6f7b8_add_student_learning.py](../backend/alembic/versions/a3c4d5e6f7b8_add_student_learning.py)
- [b4d5e6f7a8c9_add_admin_audit.py](../backend/alembic/versions/b4d5e6f7a8c9_add_admin_audit.py)
- [b60a722a1c84_add_archived_status_and_archive_audit_.py](../backend/alembic/versions/b60a722a1c84_add_archived_status_and_archive_audit_.py)
- [c2f3071cddcb_add_verification_codes_table.py](../backend/alembic/versions/c2f3071cddcb_add_verification_codes_table.py)
- [c5e6f7a8b9d0_institution_product.py](../backend/alembic/versions/c5e6f7a8b9d0_institution_product.py)
- [ca5b2e8f6fde_add_email_failures_table.py](../backend/alembic/versions/ca5b2e8f6fde_add_email_failures_table.py)
- [d6f7a8b9c0e1_audit_request_details.py](../backend/alembic/versions/d6f7a8b9c0e1_audit_request_details.py)
- [d75fe944c53f_add_password_reset_verification_purpose.py](../backend/alembic/versions/d75fe944c53f_add_password_reset_verification_purpose.py)
- [e1a2b3c4d5f6_add_password_changed_at_to_users.py](../backend/alembic/versions/e1a2b3c4d5f6_add_password_changed_at_to_users.py)
- [e7a8b9c0d1f2_pilot_workflows.py](../backend/alembic/versions/e7a8b9c0d1f2_pilot_workflows.py)
- [f2b3c4d5e6a7_add_teaching_workspace.py](../backend/alembic/versions/f2b3c4d5e6a7_add_teaching_workspace.py)
- [f8b9c0d1e2a3_configurable_academic_structure.py](../backend/alembic/versions/f8b9c0d1e2a3_configurable_academic_structure.py)
- [ff3955f0f5c2_add_teachers_table.py](../backend/alembic/versions/ff3955f0f5c2_add_teachers_table.py)
- [g9c0d1e2f3b4_grading_policy_snapshots.py](../backend/alembic/versions/g9c0d1e2f3b4_grading_policy_snapshots.py)
- [h0d1e2f3a4b5_academic_documents.py](../backend/alembic/versions/h0d1e2f3a4b5_academic_documents.py)
- [i1e2f3a4b5c6_final_grades.py](../backend/alembic/versions/i1e2f3a4b5c6_final_grades.py)
- [j2f3a4b5c6d7_progression.py](../backend/alembic/versions/j2f3a4b5c6d7_progression.py)
