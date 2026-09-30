import { useState } from "react";
import { Link, useParams } from "react-router-dom";
import { useTeachingMutation, useTeachingQuery } from "../teacher/teachingQueries";
import { Field, MutationState, PageHeading, QueryState } from "../teacher/TeachingUI";
import { assignmentStatus, formatDateTime } from "./learningFormat";

export default function StudentAssignmentPage() {
  const { assignmentId } = useParams();
  const query = useTeachingQuery("/api/student/assignments");
  const work = query.data?.find(w => w.id === assignmentId);
  return <><QueryState query={query} />{query.data && !work && <p className="form-error" role="alert">This assessment is not available to your account. <Link to="/student/assignments">Back to assignments</Link></p>}
    {work && <Assignment key={work.id} work={work} reload={query.refetch} />}
  </>;
}

function Assignment({ work, reload }) {
  const mutation = useTeachingMutation();
  const [finalAnswer, setFinalAnswer] = useState(null);
  const [validationError, setValidationError] = useState("");
  const receipt = work.submission;
  const status = assignmentStatus(work);
  const locked = receipt?.status === "SUBMITTED" || work.score !== null || work.kind === "EXAM";
  const closed = status === "Closed";

  async function save(body) {
    try {
      await mutation.mutateAsync({ path: `/api/student/assignments/${work.id}/submission`, method: "PUT", body });
      setFinalAnswer(null);
    } catch { /* Preserve unsaved input and show MutationState. */ }
  }

  function review(event) {
    event.preventDefault();
    setValidationError("");
    const form = Object.fromEntries(new FormData(event.currentTarget));
    const body = { answer: form.answer.trim(), link_url: form.link_url.trim() || null, expected_version: receipt?.version || 0,
      submit: event.nativeEvent.submitter?.value === "submit" };
    if (body.submit && !body.answer && !body.link_url) {
      setValidationError("Add your answer or a document link before submitting."); return;
    }
    if (body.submit) setFinalAnswer(body);
    else save(body);
  }

  return <><PageHeading title={work.title}>{work.subject_name} · {work.kind.toLowerCase()}</PageHeading>
    <section className="teaching-panel"><div className="student-course-meta"><span>{formatDateTime(work.due_at)}</span><span>Maximum score: {work.max_score}</span><span className="student-status">{status}</span></div>
      <h2>Instructions</h2><p className="teaching-instructions">{work.instructions}</p>
      {work.kind !== "EXAM" && <p className="teaching-muted">{work.allow_late_submissions ? "Late submissions are accepted and marked late." : "Final submissions close at the deadline."}</p>}
      {work.score !== null && <><p className="teaching-notice">Your score: {work.score} / {work.max_score}</p>{work.feedback && <p className="teaching-instructions"><strong>Teacher feedback:</strong> {work.feedback}</p>}</>}
    </section>
    <section className="teaching-panel student-submission"><h2>{receipt?.status === "SUBMITTED" ? "Submission receipt" : "My work"}</h2>
      <MutationState mutation={mutation} message={receipt?.status === "SUBMITTED" ? "Your final submission has been received." : "Draft saved. It has not been submitted to your teacher."} />
      {validationError && <p className="form-error" role="alert">{validationError}</p>}
      {receipt?.status === "SUBMITTED" && <><p>Received {formatDateTime(receipt.submitted_at)}{receipt.is_late ? " · Late submission" : " · Submitted on time"}</p><p className="teaching-muted">Receipt: {receipt.id}</p></>}
      {locked ? <>
        {receipt && <><p className="teaching-instructions">{receipt.answer}</p>{receipt.link_url && <a href={receipt.link_url} target="_blank" rel="noopener noreferrer">Open submitted document (new tab)</a>}</>}
        <p className="teaching-notice">{work.kind === "EXAM" ? "Follow your teacher’s instructions for this examination. Online submission is not enabled." : "This work is locked. Contact your teacher if you need to make a correction."}</p>
      </> : <>
        {closed && <p className="teaching-notice">The deadline has passed. You can keep a draft, but final submission is closed.</p>}
        {receipt && <p className="teaching-muted">Draft last saved {formatDateTime(receipt.updated_at)}. Only you can see draft answers.</p>}
        <form key={receipt?.version || 0} className="teaching-form" onSubmit={review}>
          <div className="form-field"><label htmlFor="student-answer">Your answer</label><textarea id="student-answer" name="answer" maxLength={50000} defaultValue={receipt?.answer || ""} disabled={mutation.isPending || Boolean(finalAnswer)} /></div>
          <Field label="Document link (optional)" name="link_url" type="url" maxLength={2000} placeholder="https://…" defaultValue={receipt?.link_url || ""} disabled={mutation.isPending || Boolean(finalAnswer)} />
          <p className="teaching-muted">If you share a document link, give your teacher access to it. Final submissions cannot be edited.</p>
          <div className="teaching-actions"><button type="submit" value="draft" disabled={mutation.isPending || Boolean(finalAnswer)}>Save draft</button><button type="submit" value="submit" className="btn btn--primary" disabled={closed || mutation.isPending || Boolean(finalAnswer)}>Review & submit</button></div>
        </form>
        {mutation.error?.status === 409 && <button type="button" onClick={async () => { await reload(); setFinalAnswer(null); mutation.reset(); }}>Reload saved work</button>}
        {finalAnswer && <section className="teaching-notice" aria-label="Review final submission"><h3>Submit this final version?</h3><p>Your teacher will receive it, and editing will be locked.</p><details><summary>Review my answer</summary><p className="teaching-instructions">{finalAnswer.answer || "No typed answer"}</p>{finalAnswer.link_url && <p>{finalAnswer.link_url}</p>}</details><div className="teaching-actions"><button type="button" className="btn btn--primary" disabled={mutation.isPending} onClick={() => save(finalAnswer)}>{mutation.isPending ? "Submitting…" : "Confirm submission"}</button><button type="button" disabled={mutation.isPending} onClick={() => setFinalAnswer(null)}>Keep editing</button></div></section>}
      </>}
    </section><Link to="/student/assignments">Back to assignments</Link>
  </>;
}
