import { useState } from "react";
import { useAuth } from "../../context/useAuth";
import { useTeachingMutation, useTeachingQuery } from "../teacher/teachingQueries";
import { Empty, Field, MutationState, PageHeading, QueryState } from "../teacher/TeachingUI";
import { shortDate } from "./format";

/** Teachers message classes they teach (or one student in them). Admins can message any class and read every message. */
export default function StudentMessagesStaffPage() {
  const { user, readOnly } = useAuth();
  const admin = user.role === "INSTITUTION_ADMIN";
  const audiences = useTeachingQuery("/api/teaching/student-messages/audiences");
  const sent = useTeachingQuery("/api/teaching/student-messages");
  const mutation = useTeachingMutation();
  const [classId, setClassId] = useState("");
  const cls = audiences.data?.find(c => c.id === classId);

  async function send(event) {
    event.preventDefault();
    const form = event.currentTarget;
    const values = Object.fromEntries(new FormData(form));
    const body = { class_id: values.class_id, title: values.title, body: values.body, student_user_id: values.student_user_id || null };
    try { await mutation.mutateAsync({ path: "/api/teaching/student-messages", body }); form.reset(); setClassId(""); } catch { /* shown below */ }
  }

  return <><PageHeading title="Messages to students">{admin
    ? "Send a message to a class or one student. You can read every message staff have sent."
    : "Send a message to a class you teach, or to one student in it. Students can read messages but cannot reply."}</PageHeading>
    {!readOnly && <section className="teaching-panel" aria-labelledby="new-message"><h2 id="new-message">New message</h2>
      <QueryState query={audiences} />
      {audiences.data && !audiences.data.length && <Empty>You don't teach any classes yet.</Empty>}
      {audiences.data?.length > 0 && <form className="teaching-form" onSubmit={send}>
        <Field label="Class" name="class_id" required value={classId} onChange={e => setClassId(e.target.value)}>
          <option value="">Choose a class</option>{audiences.data.map(c => <option key={c.id} value={c.id}>{c.name} · {c.academic_year} ({c.students.length})</option>)}</Field>
        <Field label="Send to" name="student_user_id" disabled={!cls}>
          <option value="">Whole class</option>{cls?.students.map(s => <option key={s.user_id} value={s.user_id}>{s.name} · {s.admission_number}</option>)}</Field>
        <Field label="Subject" name="title" required minLength={2} maxLength={160} />
        <div className="form-field"><label htmlFor="message-body">Message</label><textarea id="message-body" name="body" required maxLength={4000} rows={5} /></div>
        <p className="teaching-muted">Students see this in Messages and get a notification. {admin ? "" : "Your school admin can read messages you send."}</p>
        <div className="teaching-actions"><button className="btn btn--primary" disabled={mutation.isPending}>Send message</button></div>
      </form>}
      <MutationState mutation={mutation} message="Message sent." />
    </section>}
    <section className="teaching-panel" aria-labelledby="sent-messages"><h2 id="sent-messages">{admin ? "All messages" : "Sent"}</h2>
      <QueryState query={sent} />
      {sent.data && !sent.data.length && <Empty>No messages yet.</Empty>}
      {sent.data?.length > 0 && <div className="table-scroll"><table className="data-table"><thead><tr><th>Sent</th>{admin && <th>From</th>}<th>To</th><th>Subject</th><th>Read</th></tr></thead>
        <tbody>{sent.data.map(m => <tr key={m.id}><td>{shortDate(m.sent_at)}</td>{admin && <td>{m.sender_name}</td>}
          <td>{m.student_name ? `${m.student_name} (${m.class_name})` : m.class_name}</td>
          <td><details><summary>{m.title}</summary><p style={{ whiteSpace: "pre-wrap" }}>{m.body}</p></details></td>
          <td>{m.read} of {m.recipients}</td></tr>)}</tbody></table></div>}
    </section>
  </>;
}
