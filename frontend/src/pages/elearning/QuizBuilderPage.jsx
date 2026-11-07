import { useState } from "react";
import { Link, useLocation, useParams } from "react-router-dom";
import { useAuth } from "../../context/useAuth";
import { useTeachingMutation, useTeachingQuery } from "../teacher/teachingQueries";
import { Empty, Field, MutationState, PageHeading, QueryState } from "../teacher/TeachingUI";
import { portalBase, shortDate } from "./format";
import "./Elearning.css";

const KINDS = { SINGLE: "One correct answer", MULTIPLE: "Several correct answers", TRUE_FALSE: "True or false" };
const LETTERS = "abcdefgh";

function blankQuestion() {
  return { kind: "SINGLE", prompt: "", options: [{ id: "a", text: "" }, { id: "b", text: "" }], correct: [], points: 1, time_limit_seconds: "" };
}

function fromServer(q) {
  return { kind: q.kind, prompt: q.prompt, options: q.options, correct: q.correct, points: Number(q.points), time_limit_seconds: q.time_limit_seconds || "" };
}

function problems(questions) {
  return questions.flatMap((q, i) => {
    const n = `Question ${i + 1}`;
    const out = [];
    if (!q.prompt.trim()) out.push(`${n}: write the question.`);
    if (q.kind !== "TRUE_FALSE" && q.options.some(o => !o.text.trim())) out.push(`${n}: fill in every option or remove empty ones.`);
    if (!q.correct.length) out.push(`${n}: mark the correct answer.`);
    if (q.time_limit_seconds !== "" && (q.time_limit_seconds < 10 || q.time_limit_seconds > 3600)) out.push(`${n}: a time limit must be 10 to 3600 seconds.`);
    return out;
  });
}

function QuestionEditor({ q, index, total, change, remove, move, disabled }) {
  const set = patch => change({ ...q, ...patch });
  function setKind(kind) {
    if (kind === "TRUE_FALSE") set({ kind, options: [{ id: "true", text: "True" }, { id: "false", text: "False" }], correct: [] });
    else if (q.kind === "TRUE_FALSE") set({ kind, options: [{ id: "a", text: "" }, { id: "b", text: "" }], correct: [] });
    else set({ kind, correct: kind === "SINGLE" ? q.correct.slice(0, 1) : q.correct });
  }
  function toggleCorrect(id) {
    if (q.kind === "MULTIPLE") set({ correct: q.correct.includes(id) ? q.correct.filter(x => x !== id) : [...q.correct, id] });
    else set({ correct: [id] });
  }
  function addOption() {
    const id = [...LETTERS].find(l => !q.options.some(o => o.id === l));
    if (id) set({ options: [...q.options, { id, text: "" }] });
  }
  return <fieldset className="teaching-panel quiz-editor" disabled={disabled}>
    <legend>Question {index + 1}</legend>
    <div className="quiz-editor__row">
      <Field label="Type" value={q.kind} onChange={e => setKind(e.target.value)}>{Object.entries(KINDS).map(([k, v]) => <option key={k} value={k}>{v}</option>)}</Field>
      <Field label="Marks" type="number" min="0.5" max="1000" step="0.5" required value={q.points} onChange={e => set({ points: e.target.value === "" ? "" : Number(e.target.value) })} />
      <Field label="Time limit in seconds (optional)" type="number" min="10" max="3600" step="1" value={q.time_limit_seconds}
        onChange={e => set({ time_limit_seconds: e.target.value === "" ? "" : Number(e.target.value) })} />
    </div>
    <div className="form-field"><label htmlFor={`prompt-${index}`}>Question</label><textarea id={`prompt-${index}`} required maxLength={5000} value={q.prompt} onChange={e => set({ prompt: e.target.value })} /></div>
    <p className="teaching-muted">{q.kind === "MULTIPLE" ? "Tick every correct option. Students score only if they pick exactly these." : "Choose the correct option."}</p>
    <ul className="quiz-editor__options">{q.options.map(o => <li key={o.id}>
      <label className="quiz-editor__correct"><input type={q.kind === "MULTIPLE" ? "checkbox" : "radio"} name={`correct-${index}`} checked={q.correct.includes(o.id)} onChange={() => toggleCorrect(o.id)} /><span className="records-hidden">Correct</span></label>
      {q.kind === "TRUE_FALSE" ? <span>{o.text}</span> : <input aria-label={`Option ${o.id.toUpperCase()}`} value={o.text} maxLength={500} onChange={e => set({ options: q.options.map(x => (x.id === o.id ? { ...x, text: e.target.value } : x)) })} />}
      {q.kind !== "TRUE_FALSE" && q.options.length > 2 && <button type="button" onClick={() => set({ options: q.options.filter(x => x.id !== o.id), correct: q.correct.filter(x => x !== o.id) })}>Remove</button>}
    </li>)}</ul>
    <div className="teaching-actions">
      {q.kind !== "TRUE_FALSE" && q.options.length < 8 && <button type="button" onClick={addOption}>Add option</button>}
      <button type="button" onClick={() => move(-1)} disabled={index === 0}>Move up</button>
      <button type="button" onClick={() => move(1)} disabled={index === total - 1}>Move down</button>
      <button type="button" onClick={remove}>Delete question</button>
    </div>
  </fieldset>;
}

function Questions({ quiz }) {
  const mutation = useTeachingMutation();
  const [questions, setQuestions] = useState(() => (quiz.questions.length ? quiz.questions.map(fromServer) : [blankQuestion()]));
  const [issues, setIssues] = useState([]);
  const locked = quiz.locked;
  async function save() {
    const found = problems(questions);
    setIssues(found);
    if (found.length) return;
    const body = { questions: questions.map(q => ({ ...q, prompt: q.prompt.trim(), options: q.options.map(o => ({ ...o, text: o.text.trim() })), time_limit_seconds: q.time_limit_seconds === "" ? null : q.time_limit_seconds })) };
    try { await mutation.mutateAsync({ path: `/api/teaching/quizzes/${quiz.id}/questions`, method: "PUT", body }); } catch { /* shown below */ }
  }
  const total = questions.reduce((sum, q) => sum + (Number(q.points) || 0), 0);
  return <section aria-labelledby="quiz-questions">
    <h2 id="quiz-questions" className="section-header">Questions <span className="teaching-muted">{questions.length} · {total} marks</span></h2>
    {locked && <p className="teaching-notice">Students have started this quiz, so its questions can no longer change.</p>}
    {questions.map((q, i) => <QuestionEditor key={i} q={q} index={i} total={questions.length} disabled={locked}
      change={next => setQuestions(questions.map((x, j) => (j === i ? next : x)))}
      remove={() => setQuestions(questions.filter((_, j) => j !== i))}
      move={step => { const next = [...questions]; [next[i], next[i + step]] = [next[i + step], next[i]]; setQuestions(next); }} />)}
    {!locked && <div className="teaching-actions">
      <button type="button" onClick={() => setQuestions([...questions, blankQuestion()])} disabled={questions.length >= 200}>Add question</button>
      <button type="button" className="btn btn--primary" onClick={save} disabled={mutation.isPending || !questions.length}>{mutation.isPending ? "Saving…" : "Save questions"}</button>
    </div>}
    {issues.length > 0 && <ul className="form-error" role="alert">{issues.map(x => <li key={x}>{x}</li>)}</ul>}
    <MutationState mutation={mutation} message="Questions saved. The quiz is now out of the total of its marks." />
  </section>;
}

const RULES = [
  ["no_going_back", "No going back", "Questions come one at a time and earlier ones cannot be reopened."],
  ["shuffle_questions", "Shuffle questions", "Each student gets the questions in a different order."],
  ["shuffle_options", "Shuffle answer options", "The options inside each question are mixed for each student (not for true/false)."],
  ["hide_results_until_close", "Hide scores and answers until the quiz closes", "Stops students sharing answers while others are still taking it."],
  ["log_tab_switches", "Record when students leave the quiz page", "Shown to you in the results. It only flags; it cannot block."],
];

function Settings({ quiz }) {
  const mutation = useTeachingMutation();
  const [form, setForm] = useState({ ...quiz.settings, time_limit_minutes: quiz.settings.time_limit_minutes || "" });
  const set = patch => setForm({ ...form, ...patch });
  async function save(event) {
    event.preventDefault();
    try { await mutation.mutateAsync({ path: `/api/teaching/quizzes/${quiz.id}/settings`, method: "PUT", body: { ...form, time_limit_minutes: form.time_limit_minutes === "" ? null : Number(form.time_limit_minutes), attempts_allowed: Number(form.attempts_allowed) } }); }
    catch { /* shown below */ }
  }
  return <section className="teaching-panel" aria-labelledby="quiz-settings"><h2 id="quiz-settings">Rules</h2>
    {quiz.locked && <p className="teaching-notice">Students have started. You can now only allow more attempts or more time.</p>}
    <form className="teaching-form" onSubmit={save}>
      <div className="quiz-editor__row">
        <Field label="Time for the whole quiz, in minutes (optional)" type="number" min="1" max="600" value={form.time_limit_minutes} onChange={e => set({ time_limit_minutes: e.target.value })} />
        <Field label="Attempts per student" type="number" min="1" max="10" required value={form.attempts_allowed} onChange={e => set({ attempts_allowed: e.target.value })} />
      </div>
      {RULES.map(([key, label, help]) => <label key={key} className="teaching-checkbox"><input type="checkbox" checked={form[key]} disabled={quiz.locked} onChange={e => set({ [key]: e.target.checked })} />
        <span>{label}<small className="teaching-muted"> {help}</small></span></label>)}
      <p className="teaching-muted">Questions with their own time limit always come one at a time, with no going back. Without an overall limit, students have until the closing time.</p>
      <div className="teaching-actions"><button className="btn btn--primary" disabled={mutation.isPending}>Save rules</button></div>
    </form>
    <MutationState mutation={mutation} message="Rules saved." />
  </section>;
}

function AttemptReview({ attemptId }) {
  const query = useTeachingQuery(`/api/teaching/quiz-attempts/${attemptId}`);
  if (!query.data) return <QueryState query={query} />;
  return <ol className="quiz-review-list">{query.data.questions.map(q => <li key={q.id}><p>{q.prompt}</p>
    <p className="teaching-muted">Answer: {q.selected.length ? q.options.filter(o => q.selected.includes(o.id)).map(o => o.text).join(", ") : "none"} · {Number(q.earned)} / {Number(q.points)}</p></li>)}</ol>;
}

function Results({ quiz }) {
  const { readOnly } = useAuth();
  const query = useTeachingQuery(`/api/teaching/quizzes/${quiz.id}/results`);
  const mutation = useTeachingMutation();
  const [granting, setGranting] = useState(null);
  const [open, setOpen] = useState(null);
  const data = query.data;
  async function grant(event) {
    event.preventDefault();
    const reason = new FormData(event.currentTarget).get("reason").trim();
    try { await mutation.mutateAsync({ path: `/api/teaching/quizzes/${quiz.id}/extra-attempts`, body: { student_id: granting, reason } }); setGranting(null); } catch { /* shown below */ }
  }
  return <section className="teaching-panel" aria-labelledby="quiz-results"><h2 id="quiz-results">Results</h2><QueryState query={query} />
    <MutationState mutation={mutation} message="Another attempt is allowed." />
    {data && (data.students.length === 0 ? <Empty>No students take this course yet.</Empty> : <div className="table-wrapper"><table className="data-table">
      <thead><tr><th scope="col">Student</th><th scope="col">Attempts</th><th scope="col">Best score</th>{data.log_tab_switches && <th scope="col">Left the page</th>}<th scope="col" /></tr></thead>
      <tbody>{data.students.map(s => {
        const last = s.attempts[s.attempts.length - 1];
        return <tr key={s.student_id}>
          <td>{s.name}<br /><small className="teaching-muted">{s.admission_number}</small></td>
          <td>{s.attempts.length} of {s.allowed}{last?.status === "IN_PROGRESS" ? " · taking it now" : ""}{last?.auto_submitted ? " · time ran out" : ""}
            {s.extra_reasons.length > 0 && <><br /><small className="teaching-muted">Extra: {s.extra_reasons.join("; ")}</small></>}</td>
          <td>{s.best !== null ? `${Number(s.best)} / ${Number(data.max_score)}` : s.attempts.length ? "—" : "Not attempted"}</td>
          {data.log_tab_switches && <td>{s.attempts.reduce((n, a) => n + a.tab_switches, 0) || "—"}</td>}
          <td><div className="teaching-actions">
            {s.attempts.filter(a => a.status === "SUBMITTED").map(a => <button type="button" key={a.id} onClick={() => setOpen(open === a.id ? null : a.id)}>{open === a.id ? "Hide" : `Answers (attempt ${a.number})`}</button>)}
            {!readOnly && <button type="button" onClick={() => setGranting(s.student_id)}>Allow another attempt</button>}
          </div>
            {s.attempts.some(a => a.id === open) && <AttemptReview attemptId={open} />}
            {granting === s.student_id && <form className="teaching-form" onSubmit={grant}><Field label="Reason (kept on record)" name="reason" required minLength={3} maxLength={300} placeholder="e.g. power cut during the quiz" />
              <div className="teaching-actions"><button className="btn btn--primary" disabled={mutation.isPending}>Allow</button><button type="button" onClick={() => setGranting(null)}>Cancel</button></div></form>}
          </td></tr>;
      })}</tbody></table></div>)}
  </section>;
}

export default function QuizBuilderPage() {
  const { quizId } = useParams();
  const { pathname } = useLocation();
  const base = portalBase(pathname);
  const query = useTeachingQuery(`/api/teaching/quizzes/${quizId}`);
  const quiz = query.data;
  const [tab, setTab] = useState("questions");
  if (!quiz) return <><PageHeading title="Quiz" /><QueryState query={query} /></>;
  return <><PageHeading title={quiz.title}>{quiz.subject_name} · {quiz.published ? "Published" : "Draft"} · {quiz.opens_at ? `opens ${shortDate(quiz.opens_at)}, ` : ""}closes {shortDate(quiz.due_at)}</PageHeading>
    {!quiz.published && <p className="teaching-notice">Students cannot see this quiz yet. Save its questions, then publish it from <Link to={`${base}/coursework?subject=${quiz.subject_id}`}>Coursework</Link> by editing it and ticking “Publish”.</p>}
    <div className="quiz-tabs" role="tablist">{[["questions", "Questions"], ["rules", "Rules"], ["results", "Results"]].map(([k, v]) =>
      <button key={k} type="button" role="tab" aria-selected={tab === k} className={tab === k ? "is-active" : undefined} onClick={() => setTab(k)}>{v}</button>)}</div>
    {tab === "questions" && <Questions key={quiz.locked ? "locked" : "open"} quiz={quiz} />}
    {tab === "rules" && <Settings quiz={quiz} />}
    {tab === "results" && <Results quiz={quiz} />}
    <p><Link to={`${base}/courses/${quiz.subject_id}`}>Back to course</Link></p>
  </>;
}
