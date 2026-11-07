import { useState } from "react";
import { useTeachingMutation, useTeachingQuery } from "../teacher/teachingQueries";
import { Empty, Field, MutationState, PageHeading, QueryState } from "../teacher/TeachingUI";
import { WeekGrid } from "./TimetableViews";
import { DAYS, addDays, isoWeekday, kenyaToday, longDate } from "./timetableFormat";
import "../records/Records.css";
import "./Timetable.css";

const form = event => Object.fromEntries(new FormData(event.currentTarget));

/** Shows clashes from a refused save and lets the administrator save anyway with a reason. */
function ClashNotice({ mutation, onOverride }) {
  const [reason, setReason] = useState("");
  const clashes = mutation.error?.status === 409 ? mutation.error.details?.detail?.clashes : null;
  if (!clashes) return <MutationState mutation={mutation} />;
  return <div className="timetable-clash" role="alert">
    <strong>This clashes with the timetable</strong>
    <ul>{clashes.map((c, i) => <li key={i}>{c.message}</li>)}</ul>
    <Field label="Reason for saving anyway" value={reason} minLength={5} maxLength={300} onChange={e => setReason(e.target.value)} placeholder="For example: combined class for this lesson" />
    <div className="records-actions"><button className="btn" type="button" disabled={reason.trim().length < 5 || mutation.isPending} onClick={() => onOverride(reason.trim())}>Save anyway</button></div>
  </div>;
}

function BellSchedule({ detail, periodId }) {
  const mutation = useTeachingMutation();
  const [editing, setEditing] = useState(null);
  const [days, setDays] = useState(detail.weekdays);
  async function saveSlot(event, slot) {
    event.preventDefault();
    const v = form(event);
    const weekdays = [...new FormData(event.currentTarget).getAll("slot_days")].map(Number);
    const body = { label: v.label, start_time: v.start_time, end_time: v.end_time, is_break: v.is_break === "on", weekdays };
    try {
      await mutation.mutateAsync(slot ? { path: `/api/timetable/slots/${slot.id}`, method: "PUT", body } : { path: `/api/timetable/terms/${periodId}/slots`, body });
      setEditing(null);
      if (!slot) event.target.reset();
    } catch { /* Shown below. */ }
  }
  const slotForm = slot => <form className="records-filters" onSubmit={e => saveSlot(e, slot)} aria-label={slot ? `Edit ${slot.label}` : "Add a period"}>
    <Field label="Name" name="label" required maxLength={40} defaultValue={slot?.label} placeholder="Lesson 1" />
    <Field label="Starts" name="start_time" type="time" required defaultValue={slot?.start_time} />
    <Field label="Ends" name="end_time" type="time" required defaultValue={slot?.end_time} />
    <label className="attendance-late"><span><input type="checkbox" name="is_break" defaultChecked={slot?.is_break} /> Break or lunch</span></label>
    <fieldset className="timetable-days"><legend className="teaching-muted">Only on (leave blank for every teaching day)</legend>
      {detail.weekdays.map(d => <label key={d}><input type="checkbox" name="slot_days" value={d} defaultChecked={slot?.weekdays.includes(d)} />{DAYS[d].slice(0, 3)}</label>)}</fieldset>
    <div className="records-actions"><button className="btn btn--primary" disabled={mutation.isPending}>{slot ? "Save" : "Add period"}</button>{slot && <button className="btn" type="button" onClick={() => setEditing(null)}>Cancel</button>}</div>
  </form>;
  return <>
    <section className="teaching-panel" aria-labelledby="teaching-days"><h2 id="teaching-days">Teaching days</h2>
      <div className="timetable-days">{[1, 2, 3, 4, 5, 6, 7].map(d => <label key={d}><input type="checkbox" checked={days.includes(d)} onChange={e => setDays(e.target.checked ? [...days, d].sort() : days.filter(x => x !== d))} />{DAYS[d]}</label>)}</div>
      <button className="btn" type="button" disabled={!days.length || mutation.isPending} onClick={() => mutation.mutate({ path: `/api/timetable/terms/${periodId}`, method: "PUT", body: { weekdays: days } })}>Save teaching days</button>
    </section>
    <section className="teaching-panel" aria-labelledby="bell-schedule"><h2 id="bell-schedule">Lesson periods and breaks</h2>
      <MutationState mutation={mutation} />
      {!detail.slots.length ? <Empty>No periods yet. Add the day's lessons and breaks in order.</Empty> : <div className="table-wrapper"><table className="data-table">
        <thead><tr><th>Name</th><th>Time</th><th>Days</th><th><span className="records-hidden">Actions</span></th></tr></thead>
        <tbody>{detail.slots.map(s => editing === s.id ? <tr key={s.id}><td colSpan={4}>{slotForm(s)}</td></tr> : <tr key={s.id} className={s.is_break ? "timetable-break" : undefined}>
          <td>{s.label}{s.is_break && <span className="teaching-muted"> · break</span>}</td><td>{s.start_time}–{s.end_time}</td>
          <td>{s.weekdays.length ? s.weekdays.map(d => DAYS[d].slice(0, 3)).join(", ") : "Every teaching day"}</td>
          <td><div className="records-actions"><button className="btn" type="button" onClick={() => setEditing(s.id)}>Edit</button>
            <button className="btn" type="button" disabled={mutation.isPending} onClick={() => window.confirm(`Remove ${s.label}?`) && mutation.mutate({ path: `/api/timetable/slots/${s.id}`, method: "DELETE" })}>Remove</button></div></td>
        </tr>)}</tbody></table></div>}
      <h3>Add a period</h3>{slotForm(null)}
    </section>
  </>;
}

function ChangeForm({ lesson, detail, onDone }) {
  const mutation = useTeachingMutation();
  const [kind, setKind] = useState("SUBSTITUTE");
  const [values, setValues] = useState(null);
  const next = (() => { let d = kenyaToday(); while (isoWeekday(d) !== lesson.weekday) d = addDays(d, 1); return d; })();
  async function save(body) {
    try { await mutation.mutateAsync({ path: `/api/timetable/entries/${lesson.id}/changes`, body }); onDone(); } catch { /* Shown below. */ }
  }
  function submit(event) {
    event.preventDefault();
    const v = form(event);
    const body = { lesson_date: v.lesson_date, kind, note: v.note, substitute_id: kind === "SUBSTITUTE" ? v.substitute_id : null,
      new_date: kind === "MOVED" ? v.new_date : null, new_slot_id: kind === "MOVED" ? v.new_slot_id : null };
    setValues(body);
    save(body);
  }
  return <section className="teaching-panel" aria-labelledby="change-title">
    <h3 id="change-title">Change one {DAYS[lesson.weekday]}: {lesson.subject_name}, {lesson.start_time}</h3>
    <form className="records-filters" onSubmit={submit}>
      <Field label="Date" name="lesson_date" type="date" required defaultValue={next} min={detail.period.start_date} max={detail.period.end_date} />
      <Field label="Change" value={kind} onChange={e => setKind(e.target.value)}><option value="SUBSTITUTE">Another teacher covers it</option><option value="MOVED">Move it</option><option value="CANCELLED">Cancel it</option></Field>
      {kind === "SUBSTITUTE" && <Field label="Covering teacher" name="substitute_id" required defaultValue=""><option value="" disabled>Choose</option>{detail.teachers.filter(t => t.id !== lesson.teacher_id).map(t => <option key={t.id} value={t.id}>{t.name}</option>)}</Field>}
      {kind === "MOVED" && <><Field label="New date" name="new_date" type="date" required min={detail.period.start_date} max={detail.period.end_date} />
        <Field label="New period" name="new_slot_id" required defaultValue=""><option value="" disabled>Choose</option>{detail.slots.filter(s => !s.is_break).map(s => <option key={s.id} value={s.id}>{s.label} ({s.start_time})</option>)}</Field></>}
      <Field label="Note for the teacher" name="note" maxLength={300} placeholder={kind === "CANCELLED" ? "Sports day" : ""} />
      <div className="records-actions"><button className="btn btn--primary" disabled={mutation.isPending}>Save change</button><button className="btn" type="button" onClick={onDone}>Cancel</button></div>
    </form>
    <ClashNotice mutation={mutation} onOverride={reason => save({ ...values, override_reason: reason })} />
  </section>;
}

function Lessons({ detail, periodId }) {
  const [classId, setClassId] = useState(detail.classes[0]?.id || "");
  const [cell, setCell] = useState(null);
  const [changing, setChanging] = useState(null);
  const grid = useTeachingQuery(classId ? `/api/timetable/classes/${classId}?period_id=${periodId}` : null);
  const mutation = useTeachingMutation();
  const remove = useTeachingMutation();
  const [pending, setPending] = useState(null);
  const subjects = grid.data?.subjects || [];
  const [subjectId, setSubjectId] = useState("");
  const subject = subjects.find(s => s.id === subjectId);
  async function save(body) {
    try { await mutation.mutateAsync({ path: `/api/timetable/terms/${periodId}/entries`, body }); setCell(null); setPending(null); setSubjectId(""); } catch { /* Shown below. */ }
  }
  function submit(event) {
    event.preventDefault();
    const v = form(event);
    const body = { slot_id: cell.slot.id, weekday: cell.day, subject_id: v.subject_id, teacher_id: v.teacher_id || null };
    setPending(body);
    save(body);
  }
  if (!detail.classes.length) return <Empty>No classes for this term's academic year.</Empty>;
  if (!detail.slots.some(s => !s.is_break)) return <Empty>Add lesson periods under Bell schedule first.</Empty>;
  return <section className="teaching-panel" aria-labelledby="lessons-title"><h2 id="lessons-title">Lessons</h2>
    <Field label="Class" value={classId} onChange={e => { setClassId(e.target.value); setCell(null); setChanging(null); }}>{detail.classes.map(c => <option key={c.id} value={c.id}>{c.name}</option>)}</Field>
    <QueryState query={grid} /><MutationState mutation={remove} message="Lesson removed." />
    {grid.data && <WeekGrid data={grid.data} renderCell={(slot, day, lessons) => <>
      {lessons.map(e => <div key={e.id} className={`timetable-lesson${e.override_reason ? " timetable-lesson--override" : ""}`}>
        <strong>{e.subject_name}</strong><small>{e.teacher_name}</small>
        {e.override_reason && <small title={e.override_reason}>Clash allowed: {e.override_reason}</small>}
        <div className="records-actions">
          <button className="btn" type="button" onClick={() => { setChanging(e); setCell(null); }}>One-day change</button>
          <button className="btn" type="button" disabled={remove.isPending} onClick={() => window.confirm(`Remove ${e.subject_name} on ${DAYS[day]}?`) && remove.mutate({ path: `/api/timetable/entries/${e.id}`, method: "DELETE" })}>Remove</button>
        </div></div>)}
      <button className="btn" type="button" aria-label={`Add a lesson on ${DAYS[day]}, ${slot.label}`} onClick={() => { setCell({ slot, day }); setChanging(null); mutation.reset(); }}>Add</button>
    </>} />}
    {cell && <section className="teaching-panel" aria-labelledby="add-lesson"><h3 id="add-lesson">{DAYS[cell.day]}, {cell.slot.label} ({cell.slot.start_time}–{cell.slot.end_time})</h3>
      <form className="records-filters" onSubmit={submit}>
        <Field label="Subject" name="subject_id" required value={subjectId} onChange={e => setSubjectId(e.target.value)}><option value="" disabled>Choose</option>{subjects.map(s => <option key={s.id} value={s.id}>{s.name}{s.optional ? " (optional)" : ""}</option>)}</Field>
        {subject && subject.teachers.length > 1 && <Field label="Teacher" name="teacher_id" defaultValue={subject.lead_teacher_id}>{subject.teachers.map(t => <option key={t.id} value={t.id}>{t.name}</option>)}</Field>}
        {subject && subject.teachers.length === 1 && <p className="teaching-muted">Teacher: {subject.teachers[0].name}</p>}
        <div className="records-actions"><button className="btn btn--primary" disabled={mutation.isPending || !subjectId}>Add lesson</button><button className="btn" type="button" onClick={() => setCell(null)}>Cancel</button></div>
      </form>
      <ClashNotice mutation={mutation} onOverride={reason => save({ ...pending, override_reason: reason })} />
    </section>}
    {changing && <ChangeForm key={changing.id} lesson={changing} detail={detail} onDone={() => setChanging(null)} />}
  </section>;
}

function Availability({ detail, periodId }) {
  const mutation = useTeachingMutation();
  async function submit(event) {
    event.preventDefault();
    const target = event.currentTarget;
    const v = form(event);
    try { await mutation.mutateAsync({ path: `/api/timetable/terms/${periodId}/unavailability`, body: { ...v, weekday: Number(v.weekday) } }); target.reset(); } catch { /* Shown below. */ }
  }
  const affected = mutation.data?.affected_lessons || [];
  return <section className="teaching-panel" aria-labelledby="availability-title"><h2 id="availability-title">When teachers are not available</h2>
    <p className="teaching-muted">For part-time staff or fixed duties. Lessons cannot be placed in these times without a reason.</p>
    {!detail.unavailability.length ? <Empty>Every teacher is available at all times.</Empty> : <div className="table-wrapper"><table className="data-table">
      <thead><tr><th>Teacher</th><th>Day</th><th>Time</th><th>Reason</th><th><span className="records-hidden">Actions</span></th></tr></thead>
      <tbody>{detail.unavailability.map(u => <tr key={u.id}><td>{u.teacher_name}</td><td>{DAYS[u.weekday]}</td><td>{u.start_time}–{u.end_time}</td><td>{u.reason}</td>
        <td><button className="btn" type="button" disabled={mutation.isPending} onClick={() => mutation.mutate({ path: `/api/timetable/unavailability/${u.id}`, method: "DELETE" })}>Remove</button></td></tr>)}</tbody></table></div>}
    <h3>Add a time</h3>
    <form className="records-filters" onSubmit={submit}>
      <Field label="Teacher" name="teacher_id" required defaultValue=""><option value="" disabled>Choose</option>{detail.teachers.map(t => <option key={t.id} value={t.id}>{t.name}</option>)}</Field>
      <Field label="Day" name="weekday" required defaultValue={detail.weekdays[0]}>{detail.weekdays.map(d => <option key={d} value={d}>{DAYS[d]}</option>)}</Field>
      <Field label="From" name="start_time" type="time" required />
      <Field label="To" name="end_time" type="time" required />
      <Field label="Reason" name="reason" maxLength={200} placeholder="Part-time" />
      <div className="records-actions"><button className="btn btn--primary" disabled={mutation.isPending}>Add</button></div>
    </form>
    <MutationState mutation={mutation} />
    {affected.length > 0 && <div className="timetable-clash" role="status"><strong>Lessons already placed in this time</strong><ul>{affected.map(a => <li key={a}>{a}</li>)}</ul>Move them under Lessons.</div>}
  </section>;
}

function Changes() {
  const today = kenyaToday();
  const query = useTeachingQuery(`/api/timetable/changes?start=${today}&end=${addDays(today, 60)}`);
  const remove = useTeachingMutation();
  const label = { CANCELLED: "Cancelled", MOVED: "Moved", SUBSTITUTE: "Covered" };
  return <section className="teaching-panel" aria-labelledby="changes-title"><h2 id="changes-title">Upcoming one-day changes</h2>
    <p className="teaching-muted">Add a change from a lesson under Lessons. Affected teachers see it on their timetable.</p>
    <QueryState query={query} /><MutationState mutation={remove} message="Change removed." />
    {query.data && (!query.data.length ? <Empty>No changes in the next 60 days.</Empty> : <div className="table-wrapper"><table className="data-table">
      <thead><tr><th>Date</th><th>Lesson</th><th>Change</th><th>Note</th><th><span className="records-hidden">Actions</span></th></tr></thead>
      <tbody>{query.data.map(c => <tr key={c.id}><td>{longDate(c.lesson_date)}</td>
        <td>{c.lesson ? `${c.lesson.subject_name}, ${c.lesson.class_name} · ${c.lesson.start_time}` : ""}<div className="teaching-muted">{c.lesson?.teacher_name}</div></td>
        <td>{label[c.kind]}{c.substitute_name ? ` by ${c.substitute_name}` : ""}{c.new_date ? ` to ${longDate(c.new_date)}, ${c.new_slot_label}` : ""}{c.override_reason && <div className="teaching-muted">Clash allowed: {c.override_reason}</div>}</td>
        <td>{c.note}</td>
        <td><button className="btn" type="button" disabled={remove.isPending} onClick={() => window.confirm("Remove this change?") && remove.mutate({ path: `/api/timetable/changes/${c.id}`, method: "DELETE" })}>Remove</button></td></tr>)}</tbody></table></div>)}
  </section>;
}

function TermPanel({ periodId, terms }) {
  const query = useTeachingQuery(`/api/timetable/terms/${periodId}`);
  const action = useTeachingMutation();
  const detail = query.data;
  const [tab, setTab] = useState(null);
  const current = tab || (detail?.slots.length ? "lessons" : "schedule");
  const sources = terms.filter(t => t.id !== periodId && t.lessons > 0);
  return <><QueryState query={query} />{detail && <>
    <div className="timetable-nav">
      <span className={`records-tag records-tag--${detail.published ? "PAID" : "PARTIAL"}`}>{detail.published ? "Published" : "Draft"}</span>
      <span className="teaching-muted">{longDate(detail.period.start_date)} to {longDate(detail.period.end_date)}</span>
      <button className="btn btn--primary" type="button" disabled={action.isPending}
        onClick={() => (detail.published ? window.confirm("Unpublish? Teachers and students will no longer see this timetable.") : true) && action.mutate({ path: `/api/timetable/terms/${periodId}/publish`, body: { published: !detail.published } })}>
        {detail.published ? "Unpublish" : "Publish to teachers and students"}</button>
      {!detail.slots.length && sources.length > 0 && <form className="timetable-nav" onSubmit={e => { e.preventDefault(); const v = form(e); action.mutate({ path: `/api/timetable/terms/${periodId}/copy?source_period_id=${v.source}` }); }}>
        <Field label="Start from" name="source" defaultValue={sources[0].id}>{sources.map(t => <option key={t.id} value={t.id}>{t.name} · {t.year}</option>)}</Field>
        <button className="btn" disabled={action.isPending}>Copy timetable</button></form>}
    </div>
    <MutationState mutation={action} message={action.data?.lessons !== undefined ? `Copied ${action.data.slots} periods and ${action.data.lessons} lessons.` : "Saved."} />
    <div className="timetable-tabs" role="group" aria-label="Timetable sections">
      {[["lessons", "Lessons"], ["schedule", "Bell schedule"], ["availability", "Teacher availability"], ["changes", "One-day changes"]].map(([key, text]) =>
        <button key={key} className="btn" type="button" aria-pressed={current === key} onClick={() => setTab(key)}>{text}</button>)}
    </div>
    {current === "schedule" && <BellSchedule key={detail.weekdays.join()} detail={detail} periodId={periodId} />}
    {current === "lessons" && <Lessons detail={detail} periodId={periodId} />}
    {current === "availability" && <Availability detail={detail} periodId={periodId} />}
    {current === "changes" && <Changes />}
  </>}</>;
}

export default function TimetableAdminPage() {
  const terms = useTeachingQuery("/api/timetable/terms");
  const [periodId, setPeriodId] = useState("");
  const list = terms.data || [];
  const chosen = periodId || list.find(t => t.current)?.id || list[0]?.id || "";
  return <><PageHeading title="Timetable">Set the bell schedule, place each lesson by hand and publish it. Teachers then see their lessons and take attendance from them.</PageHeading>
    <QueryState query={terms} />
    {terms.data && !list.length && <Empty>Add terms or semesters under Academic years first.</Empty>}
    {list.length > 0 && <Field label="Term or semester" value={chosen} onChange={e => setPeriodId(e.target.value)}>{list.map(t => <option key={t.id} value={t.id}>{t.name} · {t.year}{t.published ? " · published" : ""}</option>)}</Field>}
    {chosen && <TermPanel key={chosen} periodId={chosen} terms={list} />}
  </>;
}
