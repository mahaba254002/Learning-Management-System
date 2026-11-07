import { useState } from "react";
import { useAuth } from "../../context/useAuth";
import { useTeachingMutation, useTeachingQuery } from "../teacher/teachingQueries";
import { Empty, Field, MutationState, PageHeading, QueryState } from "../teacher/TeachingUI";
import "./Records.css";

const AUDIENCE = { EVERYONE: "Everyone", STAFF: "Staff and teachers", STUDENTS: "All students", CLASS: "One class" };
const when = value => new Date(value).toLocaleString("en-KE", { timeZone: "Africa/Nairobi", dateStyle: "medium", timeStyle: "short" });

function Composer({ row, onDone }) {
  const mutation = useTeachingMutation();
  const classes = useTeachingQuery("/api/teaching/classes");
  const [audience, setAudience] = useState(row?.audience || "EVERYONE");
  async function submit(event) {
    event.preventDefault();
    const v = Object.fromEntries(new FormData(event.currentTarget));
    const body = { title: v.title, body: v.body, audience, class_id: audience === "CLASS" ? v.class_id : null, expires_on: v.expires_on || null };
    try { await mutation.mutateAsync(row ? { path: `/api/announcements/${row.id}`, method: "PUT", body } : { path: "/api/announcements", body }); onDone(); } catch { /* Shown below. */ }
  }
  return <form className="teaching-form" onSubmit={submit} aria-label={row ? "Edit announcement" : "New announcement"}>
    <Field label="Title" name="title" required minLength={3} maxLength={160} defaultValue={row?.title} />
    <label htmlFor="announcement-body">Message</label><textarea id="announcement-body" name="body" rows={6} required minLength={3} maxLength={10000} defaultValue={row?.body} />
    <Field label="Who sees it" value={audience} onChange={e => setAudience(e.target.value)}>{Object.entries(AUDIENCE).map(([k, v]) => <option key={k} value={k}>{v}</option>)}</Field>
    {audience === "CLASS" && <Field label="Class" name="class_id" required defaultValue={row?.class_id || ""}><option value="" disabled>Choose a class</option>{(classes.data || []).map(c => <option key={c.id} value={c.id}>{c.name} · {c.academic_year}</option>)}</Field>}
    <Field label="Hide after (optional)" name="expires_on" type="date" defaultValue={row?.expires_on || ""} />
    <MutationState mutation={mutation} />
    <div className="records-actions"><button className="btn btn--primary" disabled={mutation.isPending}>{row ? "Save changes" : "Post announcement"}</button><button className="btn" type="button" onClick={onDone}>Cancel</button></div>
  </form>;
}

export default function AnnouncementsPage() {
  const { user, workspace } = useAuth();
  const admin = user.role === "INSTITUTION_ADMIN";
  const [showExpired, setShowExpired] = useState(false);
  const [editing, setEditing] = useState(null);
  const query = useTeachingQuery(`/api/announcements${admin && showExpired ? "?include_expired=true" : ""}`);
  const remove = useTeachingMutation();
  const canManage = admin && !workspace;
  return <><PageHeading title="Announcements">{canManage ? "Post notices for everyone, staff, students or one class." : "Notices from your institution."}</PageHeading>
    {canManage && (editing === "new" ? <section className="teaching-panel"><Composer onDone={() => setEditing(null)} /></section>
      : <div className="records-actions"><button className="btn btn--primary" type="button" onClick={() => setEditing("new")}>New announcement</button>
        <label className="attendance-late"><span><input type="checkbox" checked={showExpired} onChange={e => setShowExpired(e.target.checked)} /> Show hidden ones</span></label></div>)}
    <QueryState query={query} /><MutationState mutation={remove} message="Announcement removed." />
    {query.data && (!query.data.length ? <Empty>No announcements.</Empty> : <ul className="records-list">{query.data.map(a => <li key={a.id}>
      {editing === a.id ? <Composer row={a} onDone={() => setEditing(null)} /> : <>
        <h3>{a.title}</h3>
        <div className="teaching-muted">{when(a.created_at)}{a.author && ` · ${a.author}`}{canManage && ` · ${a.audience === "CLASS" ? a.class_name : AUDIENCE[a.audience]}`}{a.expires_on && ` · until ${a.expires_on}`}</div>
        <p className="records-announcement">{a.body}</p>
        {canManage && <div className="records-actions"><button className="btn" type="button" onClick={() => setEditing(a.id)}>Edit</button>
          <button className="btn" type="button" disabled={remove.isPending} onClick={() => window.confirm(`Remove "${a.title}"?`) && remove.mutate({ path: `/api/announcements/${a.id}`, method: "DELETE" })}>Remove</button></div>}
      </>}
    </li>)}</ul>)}
  </>;
}
