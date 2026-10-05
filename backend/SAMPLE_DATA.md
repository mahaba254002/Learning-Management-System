# Sample learning dataset

The generator creates realistic, fictional records for Acacia Secondary School, Harbour Academy, Ridgeway Training Institute and Lakeview College. Contact addresses use the reserved `example.test` domain. It does not send email.

The base dataset includes 49 accounts, 8 teacher profiles, 36 student profiles and enrollments, 4 classes, 12 subjects, 36 resources, 72 assessments, 156 submissions, 168 scores, 1,200 attendance records, 10 invitations and 4 administrative audit entries. It includes published and draft resources, open and closed assessments, late-work policies, withdrawn enrollment and different institution statuses.

See the root README for safe local setup. `scripts/seed_demo.py` retains its original filename and deterministic UUID namespace to preserve relationships across reruns. The visible records use natural names. Normal runs insert missing records while preserving existing edits and passwords; `--rename-existing` explicitly updates generator-owned display fields.

The default run rolls back. `--apply` commits to the explicitly selected host. `--password` privately prompts for an initial sample password. Use a development database. Generated account directories, production repair scripts and passwords are private operational material and are not part of the public project.

Sample data demonstrates workflows; it is not evidence of real institutional adoption or measured learning outcomes.
