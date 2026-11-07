import { useEffect, useState } from "react";
import { useQueryClient } from "@tanstack/react-query";
import { Link, useNavigate, useParams } from "react-router-dom";
import { apiRequest } from "../../api/client";
import { describe } from "../../api/errors";
import { useAuth } from "../../context/useAuth";
import { useTeachingQuery } from "../teacher/teachingQueries";
import { PageHeading, QueryState } from "../teacher/TeachingUI";
import { shortDate } from "./format";
import "./Elearning.css";

const BLOCKED = {
  NOT_OPEN: "This quiz has not opened yet.",
  CLOSED: "This quiz has closed.",
  NO_ATTEMPTS_LEFT: "You have used all your attempts.",
};

function clock(ms) {
  const total = Math.max(0, Math.ceil(ms / 1000));
  const h = Math.floor(total / 3600), m = Math.floor((total % 3600) / 60), s = total % 60;
  return h ? `${h}:${String(m).padStart(2, "0")}:${String(s).padStart(2, "0")}` : `${m}:${String(s).padStart(2, "0")}`;
}

function score(value, max) {
  return `${Number(value)} / ${Number(max)}`;
}

export function StudentQuizPage() {
  const { quizId } = useParams();
  const navigate = useNavigate();
  const { readOnly } = useAuth();
  const query = useTeachingQuery(`/api/student/quizzes/${quizId}`);
  const [starting, setStarting] = useState(false);
  const [error, setError] = useState("");
  const quiz = query.data;
  async function start() {
    setError(""); setStarting(true);
    try {
      const attempt = await apiRequest(`/api/student/quizzes/${quizId}/attempts`, { method: "POST" });
      navigate(`/student/quiz-attempts/${attempt.id}`);
    } catch (err) { setError(describe(err, { saving: true }).text); setStarting(false); }
  }
  if (!quiz) return <><PageHeading title="Quiz" /><QueryState query={query} /></>;
  const r = quiz.rules;
  const left = quiz.attempts_allowed - quiz.attempts_used;
  return <><PageHeading title={quiz.title}>{quiz.subject_name} · quiz</PageHeading>
    <section className="teaching-panel">
      <div className="student-course-meta">{quiz.opens_at && <span>Opens {shortDate(quiz.opens_at)}</span>}<span>Closes {shortDate(quiz.due_at)}</span><span>Out of {Number(quiz.max_score)}</span></div>
      {quiz.instructions && <p className="teaching-instructions">{quiz.instructions}</p>}
      <h2>Before you start</h2>
      <ul className="quiz-rules">
        <li>{r.question_count} question{r.question_count === 1 ? "" : "s"}{r.time_limit_minutes ? `, ${r.time_limit_minutes} minutes in total` : ""}.</li>
        {r.timed_questions > 0 && <li>{r.timed_questions === r.question_count ? "Every question has its" : "Some questions have their"} own time limit. When the time runs out, the quiz moves to the next question.</li>}
        {r.one_at_a_time && <li>Questions come one at a time. You cannot go back to an earlier question.</li>}
        {r.shuffled && <li>Questions or answers may appear in a different order for each student.</li>}
        {r.log_tab_switches && <li>Leaving this page during the quiz is recorded and shown to your teacher.</li>}
        <li>The clock keeps running if you close the page or lose your connection. When time is up, your answers are handed in automatically.</li>
        <li>{left > 0 ? `You have ${left} attempt${left === 1 ? "" : "s"} left.` : "You have no attempts left."}{quiz.attempts_allowed > 1 ? " Your best score counts." : ""}</li>
        {r.hide_results_until_close && <li>Scores and answers are shown after the quiz closes.</li>}
      </ul>
      {error && <p className="form-error" role="alert">{error}</p>}
      {quiz.open_attempt_id ? <button type="button" className="btn btn--primary" onClick={() => navigate(`/student/quiz-attempts/${quiz.open_attempt_id}`)}>Continue quiz</button>
        : quiz.can_start ? <button type="button" className="btn btn--primary" disabled={starting || readOnly} onClick={start}>{starting ? "Starting…" : quiz.attempts_used ? "Start another attempt" : "Start quiz"}</button>
          : <p className="teaching-notice">{BLOCKED[quiz.blocked_reason]}</p>}
    </section>
    {quiz.attempts.length > 0 && <section className="teaching-panel"><h2>Your attempts</h2>
      <table className="data-table"><thead><tr><th scope="col">Attempt</th><th scope="col">Handed in</th><th scope="col">Score</th><th scope="col" /></tr></thead>
        <tbody>{quiz.attempts.map(a => <tr key={a.id}><td>{a.number}</td><td>{a.status === "SUBMITTED" ? `${shortDate(a.submitted_at)}${a.auto_submitted ? " (time ran out)" : ""}` : "In progress"}</td>
          <td>{a.score !== null && a.score !== undefined ? score(a.score, a.max_score) : a.status === "SUBMITTED" ? "After the quiz closes" : "—"}</td>
          <td>{a.status === "SUBMITTED" && <Link to={`/student/quiz-attempts/${a.id}`}>Review</Link>}</td></tr>)}</tbody></table>
    </section>}
    <p><Link to={`/student/courses/${quiz.subject_id}`}>Back to course</Link></p>
  </>;
}

function Choices({ question, selected, onChange, disabled }) {
  const multiple = question.kind === "MULTIPLE";
  function toggle(id) {
    if (!multiple) onChange([id]);
    else onChange(selected.includes(id) ? selected.filter(x => x !== id) : [...selected, id]);
  }
  return <fieldset className="quiz-choices" disabled={disabled}>
    <legend className="records-hidden">{multiple ? "Choose all that apply" : "Choose one answer"}</legend>
    {question.options.map(o => <label key={o.id} className={`quiz-choice${selected.includes(o.id) ? " quiz-choice--selected" : ""}`}>
      <input type={multiple ? "checkbox" : "radio"} name={`q-${question.id}`} checked={selected.includes(o.id)} onChange={() => toggle(o.id)} />
      <span>{o.text}</span></label>)}
  </fieldset>;
}

function QuestionText({ question, number, total }) {
  return <><p className="quiz-question__number">Question {number}{total ? ` of ${total}` : ""} · {Number(question.points)} mark{Number(question.points) === 1 ? "" : "s"}
    {question.kind === "MULTIPLE" ? " · choose all that apply" : ""}</p>
    <p className="quiz-question__prompt">{question.prompt}</p></>;
}

function Review({ state }) {
  return <>
    <section className="teaching-panel">
      <h2>Handed in</h2>
      <p>{state.auto_submitted ? "Time ran out, so your answers were handed in automatically." : "Your answers have been handed in."}</p>
      {state.results_visible && state.score !== null ? <p className="quiz-score">Score: {score(state.score, state.max_score)}</p>
        : <p className="teaching-muted">Your score will be shown after the quiz closes.</p>}
      {!state.answers_visible && <p className="teaching-muted">Correct answers are shown after the quiz closes{state.results_visible ? " or once you have used all your attempts" : ""}.</p>}
    </section>
    {state.answers_visible && state.questions?.map((q, i) => <section key={q.id} className="teaching-panel quiz-question">
      <QuestionText question={q} number={i + 1} />
      <ul className="quiz-review">{q.options.map(o => {
        const chosen = q.selected.includes(o.id), right = q.correct?.includes(o.id);
        return <li key={o.id} className={right ? "quiz-review--correct" : chosen ? "quiz-review--wrong" : undefined}>
          {o.text}{chosen ? " · your answer" : ""}{right ? " · correct" : ""}</li>;
      })}</ul>
      <p className="teaching-muted">{q.selected.length ? `${Number(q.earned)} of ${Number(q.points)} marks` : "Not answered · 0 marks"}</p>
    </section>)}
    <p><Link to={`/student/quizzes/${state.quiz_id}`}>Back to the quiz</Link></p>
  </>;
}

export function QuizAttemptPage() {
  const { attemptId } = useParams();
  const { readOnly } = useAuth();
  const { user } = useAuth();
  const client = useQueryClient();
  const path = `/api/student/quiz-attempts/${attemptId}`;
  const key = ["teaching", user.id, path];
  // Each answer can change the current question, so the cache never refreshes on its own.
  const query = useTeachingQuery(path, { refetchOnWindowFocus: false, staleTime: Infinity });
  const state = query.data;
  const [now, setNow] = useState(() => Date.now());
  const [error, setError] = useState("");
  const [notice, setNotice] = useState("");
  const [busy, setBusy] = useState(false);
  const [choice, setChoice] = useState({ question: null, selected: [] });
  const [confirming, setConfirming] = useState(false);
  const { refetch } = query;

  useEffect(() => {
    const timer = window.setInterval(() => setNow(Date.now()), 250);
    return () => window.clearInterval(timer);
  }, []);

  // The server's clock decides; this is how far the browser's clock is from it.
  const offset = state ? new Date(state.server_now).getTime() - query.dataUpdatedAt : 0;
  const inProgress = state?.status === "IN_PROGRESS";
  const serverNow = now + offset;
  const attemptLeft = state ? new Date(state.ends_at).getTime() - serverNow : 0;
  const questionLeft = state?.question_ends_at ? new Date(state.question_ends_at).getTime() - serverNow : null;
  const selected = choice.question === state?.question?.id ? choice.selected : [];
  const setSelected = next => setChoice({ question: state.question.id, selected: next });

  // When a clock reaches zero, ask the server every two seconds until it has moved on or handed in.
  // (The server allows a few seconds' grace for slow connections.)
  const timedOut = Math.max(-attemptLeft, state?.question?.time_limit_seconds && questionLeft !== null ? -questionLeft : -Infinity);
  const overdueTick = inProgress && timedOut >= 0 ? Math.floor(timedOut / 2000) : -1;
  useEffect(() => {
    if (overdueTick >= 0) refetch();
  }, [overdueTick, refetch]);

  useEffect(() => {
    if (!inProgress) return undefined;
    const warn = event => { event.preventDefault(); event.returnValue = ""; };
    window.addEventListener("beforeunload", warn);
    let left = () => {};
    if (state.log_tab_switches && !readOnly) {
      left = () => { if (document.visibilityState === "hidden") apiRequest(`${path}/events`, { method: "POST", body: { kind: "LEFT_PAGE" } }).catch(() => {}); };
      document.addEventListener("visibilitychange", left);
    }
    return () => { window.removeEventListener("beforeunload", warn); document.removeEventListener("visibilitychange", left); };
  }, [inProgress, state?.log_tab_switches, path, readOnly]);

  async function send(target, body, method = "PUT") {
    setBusy(true); setError(""); setNotice("");
    try { client.setQueryData(key, await apiRequest(target, { method, body })); }
    catch (err) {
      if (err.status === 409) { setNotice(err.message); await refetch(); }
      else setError(describe(err, { saving: true }).text);
    } finally { setBusy(false); }
  }

  async function saveAnswer(questionId, answer) {
    client.setQueryData(key, old => ({ ...old, questions: old.questions.map(q => (q.id === questionId ? { ...q, selected: answer } : q)) }));
    try { await apiRequest(`${path}/answer`, { method: "PUT", body: { question_id: questionId, selected: answer } }); setError(""); }
    catch (err) {
      if (err.status === 409) { setNotice(err.message); refetch(); }
      else setError(`${describe(err, { saving: true }).text} Choose the answer again to retry.`);
    }
  }

  if (!state) return <><PageHeading title="Quiz" /><QueryState query={query} /></>;
  if (!inProgress) return <><PageHeading title={state.title}>Attempt {state.number}</PageHeading><Review state={state} /></>;

  const lowTime = attemptLeft < 60000;
  return <><PageHeading title={state.title}>Attempt {state.number}</PageHeading>
    <div className={`quiz-clock${lowTime ? " quiz-clock--low" : ""}`} role="timer" aria-live="off">
      <span>Time left: <strong>{clock(attemptLeft)}</strong></span>
      {state.sequential && <span>Question {state.index + 1} of {state.total}</span>}
      {state.log_tab_switches && <span className="teaching-muted">Leaving this page is recorded</span>}
    </div>
    {notice && <p className="teaching-notice" role="status">{notice}</p>}
    {error && <p className="form-error" role="alert">{error}</p>}
    {state.sequential ? <section className="teaching-panel quiz-question" key={state.question.id}>
      {state.question.time_limit_seconds && questionLeft !== null && <div className="quiz-question-timer">
        <span>This question: <strong>{clock(questionLeft)}</strong></span>
        <span className="quiz-question-timer__bar" style={{ "--left": `${Math.max(0, Math.min(100, (questionLeft / (state.question.time_limit_seconds * 1000)) * 100))}%` }} aria-hidden="true" />
      </div>}
      <QuestionText question={state.question} number={state.index + 1} total={state.total} />
      <Choices question={state.question} selected={selected} onChange={setSelected} disabled={busy || readOnly} />
      <p className="teaching-muted">{selected.length ? "" : "You can move on without answering, but you cannot come back."}</p>
      <div className="teaching-actions"><button type="button" className="btn btn--primary" disabled={busy || readOnly}
        onClick={() => send(`/api/student/quiz-attempts/${attemptId}/answer`, { question_id: state.question.id, selected })}>
        {busy ? "Saving…" : state.index + 1 === state.total ? "Hand in" : "Next question"}</button></div>
    </section> : <>
      {state.questions.map((q, i) => <section key={q.id} className="teaching-panel quiz-question">
        <QuestionText question={q} number={i + 1} total={state.questions.length} />
        <Choices question={q} selected={q.selected} onChange={selected => saveAnswer(q.id, selected)} disabled={readOnly} />
      </section>)}
      <section className="teaching-panel">
        <p className="teaching-muted">{state.questions.filter(q => q.selected.length).length} of {state.questions.length} answered. Answers save as you choose them.</p>
        {confirming ? <div className="teaching-notice"><p>Hand in now? You cannot change your answers afterwards.</p>
          <div className="teaching-actions"><button type="button" className="btn btn--primary" disabled={busy || readOnly} onClick={() => send(`/api/student/quiz-attempts/${attemptId}/submit`, undefined, "POST")}>{busy ? "Handing in…" : "Yes, hand in"}</button>
            <button type="button" onClick={() => setConfirming(false)}>Keep working</button></div></div>
          : <button type="button" className="btn btn--primary" disabled={readOnly} onClick={() => setConfirming(true)}>Hand in</button>}
      </section>
    </>}
  </>;
}
