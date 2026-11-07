"""Online quiz rules. The server owns every clock: answers after a time limit are refused,
expired questions move on by themselves and open attempts submit when time runs out."""
import random
from datetime import datetime, timedelta, timezone
from decimal import Decimal
from types import SimpleNamespace

from app.models.academic import Coursework, Score, Subject
from app.models.elearning import QuizAnswer, QuizAttempt, QuizExtraAttempt, QuizQuestion, QuizSettings

# Allowance for network delay when an answer arrives just after a question's time.
GRACE_SECONDS = 3


def utc(value):
    # SQLite drops timezone info in tests; production stores timestamptz.
    return value.replace(tzinfo=timezone.utc) if value is not None and value.tzinfo is None else value


def now():
    return datetime.now(timezone.utc)


def settings_for(db, work):
    row = db.query(QuizSettings).filter_by(institution_id=work.institution_id, coursework_id=work.id).first()
    if row is None:
        row = QuizSettings(institution_id=work.institution_id, coursework_id=work.id)
        db.add(row)
        db.flush()
    return row


def questions_for(db, work):
    return db.query(QuizQuestion).filter_by(institution_id=work.institution_id, coursework_id=work.id).order_by(QuizQuestion.position).all()


def is_sequential(settings, questions):
    """One question at a time, never going back, when asked for or when any question is timed."""
    return settings.no_going_back or any(q.time_limit_seconds for q in questions)


def attempts_allowed(db, work, settings, student_id):
    extra = db.query(QuizExtraAttempt).filter_by(institution_id=work.institution_id, coursework_id=work.id, student_id=student_id).count()
    return settings.attempts_allowed + extra


def closed(work, at=None):
    return work.due_at is not None and (at or now()) >= utc(work.due_at)


def make_plan(settings, questions):
    order = list(questions)
    if settings.shuffle_questions:
        random.SystemRandom().shuffle(order)
    plan = []
    for q in order:
        option_ids = [o['id'] for o in q.options]
        if settings.shuffle_options and q.kind != 'TRUE_FALSE':
            random.SystemRandom().shuffle(option_ids)
        plan.append({'q': str(q.id), 'o': option_ids})
    return plan


def start(db, work, settings, questions, student_id, number):
    at = now()
    ends = utc(work.due_at)
    if settings.time_limit_minutes:
        ends = min(ends, at + timedelta(minutes=settings.time_limit_minutes))
    attempt = QuizAttempt(institution_id=work.institution_id, coursework_id=work.id, student_id=student_id, number=number,
                          status='IN_PROGRESS', started_at=at, ends_at=ends, plan=make_plan(settings, questions),
                          sequential=is_sequential(settings, questions), current_index=0, current_started_at=at,
                          max_score=sum((q.points for q in questions), Decimal(0)))
    db.add(attempt)
    db.flush()
    return attempt


def question_deadline(attempt, question):
    """When the current question's own time runs out, capped by the attempt's end."""
    ends = utc(attempt.ends_at)
    if not attempt.sequential or not question.time_limit_seconds:
        return ends
    return min(ends, utc(attempt.current_started_at) + timedelta(seconds=question.time_limit_seconds))


def catch_up(db, attempt, by_id, at=None):
    """Move past questions whose time ran out and submit when the attempt's time is over.
    Returns True when the attempt is (now) submitted."""
    at = at or now()
    if attempt.status == 'SUBMITTED':
        return True
    if attempt.sequential:
        while attempt.current_index < len(attempt.plan):
            question = by_id[attempt.plan[attempt.current_index]['q']]
            deadline = question_deadline(attempt, question)
            if not question.time_limit_seconds or at < deadline + timedelta(seconds=GRACE_SECONDS):
                break
            # The next question's clock starts when this one ran out, even if nobody was watching.
            attempt.current_index += 1
            attempt.current_started_at = deadline
        if attempt.current_index >= len(attempt.plan):
            finish(db, attempt, by_id, auto=True, at=at)
            return True
    if at >= utc(attempt.ends_at) + timedelta(seconds=GRACE_SECONDS):
        finish(db, attempt, by_id, auto=True, at=at)
        return True
    return False


def answers_for(db, attempt):
    return {str(a.question_id): a for a in db.query(QuizAnswer).filter_by(institution_id=attempt.institution_id, attempt_id=attempt.id).all()}


def is_correct(question, selected):
    return sorted(selected) == sorted(question.correct)


def mark(attempt, by_id, answers):
    total = Decimal(0)
    for item in attempt.plan:
        question = by_id.get(item['q'])
        answer = answers.get(item['q'])
        if question is not None and answer is not None and is_correct(question, answer.selected):
            total += question.points
    return total


def finish(db, attempt, by_id, *, auto=False, at=None):
    at = at or now()
    # The answer that ends the quiz may not be written yet (sessions do not autoflush).
    db.flush()
    attempt.score = mark(attempt, by_id, answers_for(db, attempt))
    attempt.status = 'SUBMITTED'
    attempt.auto_submitted = auto
    attempt.submitted_at = min(at, utc(attempt.ends_at)) if auto else at
    attempt.current_index = len(attempt.plan)
    db.flush()
    record_best(db, attempt)


def record_best(db, attempt):
    """The best submitted attempt becomes the student's mark for this assessment."""
    from app.api.routes.teaching import write_scores
    work = db.get(Coursework, attempt.coursework_id)
    best = db.query(QuizAttempt).filter_by(institution_id=attempt.institution_id, coursework_id=work.id, student_id=attempt.student_id,
                                           status='SUBMITTED').order_by(QuizAttempt.score.desc()).first()
    existing = db.query(Score).filter_by(institution_id=attempt.institution_id, coursework_id=work.id, student_id=attempt.student_id).first()
    entry = SimpleNamespace(student_id=attempt.student_id, score=min(best.score, work.max_score), competency_label=None,
                            feedback=existing.feedback if existing else '')
    write_scores(db, SimpleNamespace(institution_id=attempt.institution_id), work, db.get(Subject, work.subject_id), [entry],
                 {attempt.student_id: existing} if existing else {})


def finish_expired(db, work):
    """Submit every open attempt whose time is over, so marks are complete for staff."""
    open_attempts = db.query(QuizAttempt).filter_by(institution_id=work.institution_id, coursework_id=work.id, status='IN_PROGRESS').all()
    if not open_attempts:
        return
    by_id = {str(q.id): q for q in questions_for(db, work)}
    for attempt in open_attempts:
        catch_up(db, attempt, by_id)


def results_visible(work, settings):
    return not settings.hide_results_until_close or closed(work)


def answers_visible(work, settings, used, allowed):
    """Correct answers appear after the quiz closes, or after the last attempt when results aren't hidden."""
    return closed(work) or (not settings.hide_results_until_close and used >= allowed)
