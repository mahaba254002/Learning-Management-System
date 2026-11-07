# Parent messages

Roadmap phase 8. Institution admins send results, fee balance reminders, announcements and emergency notices to parents and guardians by SMS through Africa's Talking. Guardians with an email address also get a free email copy. Migration: `r0b1c2d3e4f5` (after `q9a0b1c2d3e4`).

## Rules

- **Everything is reviewed.** A message is a draft until an institution administrator opens *Check and send*, reads the examples and answers their **secret question**. Nothing is sent automatically, emergencies included.
- **Secret question.** Each admin sets a question and answer under Parent messages, confirming with their account password. The answer is stored only as a one-way hash (Argon2, like passwords), never in code or readable form. Capital letters and extra spaces don't matter. Five wrong answers lock sending for 30 minutes. A forgotten answer is cleared by the platform administrator (Platform → SMS usage → Clear), which is audited. The admin then sets a new one. Sending and setting the question are refused while a platform admin is working in the institution's workspace.
- **The platform pays for SMS.** Each school has a monthly allowance in SMS parts (about 160 characters per part in the normal alphabet, 70 with emoji or other symbols). It starts at zero. Sending is refused if a message needs more parts than are left this month (Nairobi calendar month). Failed SMS don't count against the allowance. Platform → **SMS usage** shows each school's parts, sent, failed, emails and the provider's cost per month, for pricing.
- **Who receives it.** Active students only. By default only each student's main contact; *Send to every guardian* includes all linked guardians. A guardian with several children gets one copy of a notice that is the same for each child, and one per child when the text names the child.

## Message types

| Type | Audience | Placeholders |
| --- | --- | --- |
| Results | A class and a term, as the term result or one exam by name. Uses the class marksheet. Students without marks are left out. | `{student}` `{first_name}` `{admission}` `{class}` `{results}` `{mean}` `{grade}` `{position}` `{exam}` `{term}` `{school}` |
| Fee balance reminder | A term, the statuses to remind (not paid, partly paid) and optionally a class | `{student}` `{first_name}` `{admission}` `{class}` `{balance}` `{status}` `{term}` `{school}` |
| Announcement / Emergency | The whole school, one class or chosen students | `{student}` `{first_name}` `{admission}` `{class}` `{school}` |

`{results}` reads like *Mathematics 78 A, English 64 B. Mean 71 B+, position 3 of 40*. Long results can take several SMS parts; the preview shows the count.

## Sending and delivery

After *Send*, deliveries go into an outbox and are sent straight away: SMS with the same text are batched (up to 100 numbers per request), and emails go one by one. Each delivery is shown as queued, sent, delivered or failed, with the provider's reason. Failed deliveries can be retried, which again needs the secret answer. A message is never sent twice.

Anything interrupted (for example a provider outage or a restart) is picked up by `python send_messages.py`, which the hourly job in `deploy/render-billing.yaml` now runs after the subscription notices.

## Setup (platform)

Set on the API service (and on the hourly job):

| Setting | Value |
| --- | --- |
| AT_USERNAME / AT_API_KEY | From the Africa's Talking account. Use `sandbox` as the username with the sandbox key to test |
| AT_ENVIRONMENT | `sandbox` or `production` |
| AT_SENDER_ID | Optional registered sender name (for example the platform's name). Empty uses the shared short code. Registration with the networks takes a few weeks |
| AT_CALLBACK_SECRET | Random value of at least 32 characters |

In the Africa's Talking dashboard, set the SMS delivery report URL to `https://<api>/api/messaging/at/<AT_CALLBACK_SECRET>/delivery`. The secret is part of the address, so it appears in access logs; change it if logs leak. Email copies use the existing Resend settings.

Then give each school an allowance under Platform → SMS usage.
