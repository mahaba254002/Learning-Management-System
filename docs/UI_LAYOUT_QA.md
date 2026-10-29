# Login and workspace form layout review — 29 October 2026

## Changes and reference files

- `frontend/src/pages/auth/SkynetLogin.css` replaces overlapping viewport rules with one responsive layout. The information panel is narrower than the sign-in form; restrained typography, solid surfaces and consistent controls replace the large gradient/pill treatment. The mobile menu remains on the right. The statement under Welcome Back and the separate student login remain available.
- `frontend/src/components/common/Modal.jsx` renders dialogs through a portal into `document.body`, outside the dashboard's scrolling/clipping containers. The background is inert while open. Focus is trapped and restored, Escape closes the dialog, and changing form values no longer re-runs initial focus merely because the close callback changed identity.
- `frontend/src/components/common/Modal.css` keeps the dialog header visible and gives the body its own bounded scroll area. Wide setup dialogs use up to 980px and switch to one column on narrow screens.
- `frontend/src/styles/workspace-forms.css` provides consistent field sizing, spacing, helper text, wrapping and responsive academic-configuration grids. It is imported by `styles/global.css`; its workspace/modal scope intentionally outranks the older page-specific form defaults.
- `CreateInstitutionModal.jsx` places institution/contact details before academic configuration. `AcademicConfigurationEditor.jsx` groups terminology, progression and final grading into expandable sections. Short select labels have readable structure descriptions instead of truncated arrow chains. `TeachingUI.jsx` connects descriptions to controls using `aria-describedby`.
- `InstitutionTeacherDetailPage.jsx` uses a grid minimum bounded by the available width. `styles/tokens.css` uses the same Inter/system type family for workspace headings and body content.

## Verification

Frontend lint, production build and 39 existing frontend tests passed. No backend schema, authentication contract, academic data or billing setting changed.

Visual interaction checks ran against the local frontend with a read-only layout fixture. Academic templates came from the actual backend template functions; institution class/subject/calendar/teacher responses were read-only snapshots of the presentation institution. These fixtures exercise layout, not production authorization. No form was submitted to create an institution or send email during visual QA.

| Screen / interaction | Result |
| --- | --- |
| Staff login at 1366×768 and 1280×720 | Wider form than information panel; full page fits the viewport; no horizontal overflow |
| Staff login at 390×844 and 360×640 | Fits the viewport, including required-field validation at 360×640; hamburger on the right |
| Student login at 390×844 | Email/student-ID field and all actions fit; no extra student/pupil heading |
| Phone education navigation | Opens the enquiry dialog; dialog remains within the viewport and has no horizontal overflow |
| University setup, including enabled numeric grading | Scrollable long form; bottom verification action reachable; dialog header/close button remain visible |
| Setup dialog at 390×844 | One-column fields, no horizontal overflow, dialog bounded to 12px viewport margins |
| Dialog keyboard navigation | Tab from final action wraps to Close; Escape closes; focus returns to Create institution; background inert state restored |
| Class and subject forms at 1280×720 and 390×844 | No overflowing field containers or horizontal page overflow |

When diagnosing future clipping, first inspect the nearest `.modal-body`, `.teaching-panel`, `.academic-config-grid` and `.form-field`. Long documents should scroll vertically; avoid imposing fixed form heights or hiding overflowing inputs. Tables have their own horizontal scroll containers. A highly zoomed page or many validation messages may need vertical scrolling so content stays readable rather than being cropped.
