# Institution product validation

Validated locally on 28 October 2026, using an isolated PostgreSQL copy plus synthetic QA records. Hosted institution data was not modified.

| Check | Result |
| --- | --- |
| Backend API, recovery, pilot workflows and integrity suite | 164 tests passed |
| Frontend routing, learning, password, student-login, binary API and renewal tests | 31 tests passed |
| ESLint and production Vite build | Passed |
| PostgreSQL migration from an empty database | Passed |
| Upgrade, downgrade and second upgrade | Passed |
| Downgrade refuses email-less pupil accounts | Passed; records preserved |
| PostgreSQL identity uniqueness and nullable pupil emails | Passed |
| Alembic model/schema comparison on preview copy | No new upgrade operations detected |
| Reminder CLI dry run | Passed; no email sent |
| Signed institution export and reviewed atomic merge | Passed |
| Streamed full PostgreSQL backup and separate-database recovery | Passed; record counts and migration head matched |
| Recovered sessions and pending access links | Revoked; running source administrator session unchanged |
| Audit action filter, observed IP and request details | Passed |
| Viewport-height sidebar, collapse and mobile navigation | Passed |
| Refresh rotation, replay rejection, revocation and absolute expiry | Passed |
| Concurrent renewal in two browser tabs | Passed; one rotation |
| Teacher register/assessment and student assignment draft recovery | Passed in browser |
| Expired session reauthentication preserves open attendance work | Passed in browser |
| CSV preview/import, credential download and first-password change | Passed in browser |
| XLSX parsing, formula rejection and full-batch rollback | Passed in HTTP tests |
| Calendar periods, activation, closure and class promotion | Passed in browser |
| Stale academic saves/plans and historical teacher delegation | Rejected in HTTP tests |

Browser tests used the running React frontend, FastAPI API, PostgreSQL and Redis, with actual sign-in requests. They covered email/student-ID pupil login, all staff roles, hidden marks and feedback before release, teacher release, cross-subject class reports, institution terminology, institution search, ID-only account creation, forced first-password change, assignment draft/final submission and teacher review, automatic freezing, payment-driven recovery, the support email and mobile navigation.

Staff and pupil login pages were checked at 320×480, 390×844, 768×600 and 1440×900 with no page overflow. Mobile dashboard charts were visually inspected after replacing scaled SVG labels with readable responsive text and bars. Charts include accessible text values and a data-table alternative.

Known scope boundaries and deployment requirements are in [Institution product operations](INSTITUTION_PRODUCT.md). Automated checks are specific evidence, not a claim of a complete curriculum implementation, load-test certification or an independent security audit. Live email delivery and the optional production reminder schedule were not activated.

Backup/restore behavior and server configuration are in [Platform operations](PLATFORM_OPERATIONS.md). Full recovery was tested against a disposable local database. An unused empty recovery destination is configured for the local preview; no production connection was switched.
