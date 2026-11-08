import { useMemo, useRef, useState } from "react";
import { Link, useSearchParams } from "react-router-dom";
import { useQueryClient } from "@tanstack/react-query";
import { apiRequest } from "../../api/client";
import { useAuth } from "../../context/useAuth";
import { useTeachingQuery } from "../teacher/teachingQueries";
import { Empty, Field, QueryState } from "../teacher/TeachingUI";
import { STATUS, kindLabel, shortDate, studentWorkLink } from "../elearning/format";
import { TodayLessons } from "../timetable/TimetableViews";
import "../elearning/Elearning.css";

/* ---------- Course covers: a soft pattern per course, always the same for that course ---------- */

const HUES = ["#026aa7", "#075c8d", "#2f7d95", "#4a6aa5", "#6b5b95", "#3f7a68"];

function hash(text) {
  let h = 7;
  for (const ch of text) h = (h * 31 + ch.charCodeAt(0)) >>> 0;
  return h;
}

function coverArt(name) {
  let seed = hash(name) || 1;
  const rand = () => { seed = (seed * 1664525 + 1013904223) >>> 0; return seed / 4294967296; };
  const color = HUES[seed % HUES.length];
  let shapes = "";
  if (rand() < 0.5) {
    // Overlapping circles
    for (let i = 0; i < 8; i++) {
      const x = Math.round(rand() * 320), y = Math.round(rand() * 120), r = Math.round(36 + rand() * 54);
      shapes += `<circle cx="${x}" cy="${y}" r="${r}" fill="${i % 3 ? "#fff" : "#000"}" fill-opacity="${(i % 3 ? 0.08 + rand() * 0.08 : 0.06).toFixed(3)}"/>`;
    }
  } else {
    // Triangle mosaic
    for (let row = 0; row < 3; row++) for (let col = 0; col < 9; col++) {
      const x = col * 40 - (row % 2) * 20, y = row * 40, o = (rand() * 0.16).toFixed(3);
      shapes += `<path d="M${x} ${y + 40}L${x + 20} ${y}L${x + 40} ${y + 40}Z" fill="#fff" fill-opacity="${o}"/><path d="M${x + 20} ${y}L${x + 60} ${y}L${x + 40} ${y + 40}Z" fill="#000" fill-opacity="${(o / 2).toFixed(3)}"/>`;
    }
  }
  const svg = `<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 320 120" preserveAspectRatio="xMidYMid slice"><rect width="320" height="120" fill="${color}"/>${shapes}</svg>`;
  return { "--cover": color, backgroundImage: `url("data:image/svg+xml,${encodeURIComponent(svg)}")` };
}

function useStars(userId) {
  const key = `skynet:starred:${userId}`;
  const [stars, setStars] = useState(() => { try { return new Set(JSON.parse(localStorage.getItem(key) || "[]")); } catch { return new Set(); } });
  const toggle = id => setStars(old => {
    const next = new Set(old);
    if (next.has(id)) next.delete(id); else next.add(id);
    try { localStorage.setItem(key, JSON.stringify([...next])); } catch { /* starring still works for this visit */ }
    return next;
  });
  return [stars, toggle];
}

function Star({ on, onToggle, name }) {
  return <button type="button" className="cover-card__star" aria-pressed={on} aria-label={on ? `Unstar ${name}` : `Star ${name}`}
    onClick={event => { event.preventDefault(); event.stopPropagation(); onToggle(); }}>
    <svg viewBox="0 0 24 24" width="16" height="16" aria-hidden="true" fill={on ? "currentColor" : "none"} stroke="currentColor" strokeWidth="1.6" strokeLinejoin="round">
      <path d="m12 3 2.8 5.7 6.2.9-4.5 4.4 1 6.2L12 17.3l-5.5 2.9 1-6.2L3 9.6l6.2-.9Z" /></svg>
  </button>;
}

function CoverCard({ course, star }) {
  return <Link to={`/student/courses/${course.id}`} className="cover-card">
    <span className="cover-card__art" style={coverArt(course.name)} aria-hidden="true" />
    {star}
    <span className="cover-card__body">
      <span className="cover-card__name">{course.name}</span>
      <span className="cover-card__meta">{course.class_name} · {course.academic_year}</span>
      {course.next_due ? <span className="cover-card__due">Next: {course.next_due.title}, {shortDate(course.next_due.due_at)}</span>
        : <span className="cover-card__due">{course.to_do ? `${course.to_do} to do` : "Nothing due"}</span>}
    </span>
  </Link>;
}

/* ---------- Dashboard ---------- */

export function StudentDashboardPage() {
  const { user } = useAuth();
  return <>
    <h1 className="learner-title">Dashboard</h1>
    <div className="learner-dashboard">
      <div><RecentCourses /><Timeline /><TodayLessons /></div>
      <aside aria-label="Side blocks"><OnlineUsers /><UpcomingEvents />
        <section className="learner-panel"><h2>Hello, {user.first_name}</h2><p className="teaching-muted">Your grades, attendance and reports are in the menu under your name.</p></section>
      </aside>
    </div>
  </>;
}

function RecentCourses() {
  const query = useTeachingQuery("/api/student/courses");
  const strip = useRef(null);
  const courses = useMemo(() => [...(query.data || [])].sort((a, b) =>
    (b.last_visited_at || "").localeCompare(a.last_visited_at || "") || a.name.localeCompare(b.name)).slice(0, 9), [query.data]);
  const move = dir => strip.current?.scrollBy({ left: dir * strip.current.clientWidth, behavior: "smooth" });
  return <section className="learner-panel" aria-labelledby="recent-courses">
    <div className="learner-panel__head"><h2 id="recent-courses">Recently accessed courses</h2>
      {courses.length > 3 && <div className="strip-arrows"><button type="button" aria-label="Previous courses" onClick={() => move(-1)}>‹</button>
        <button type="button" aria-label="Next courses" onClick={() => move(1)}>›</button></div>}</div>
    <QueryState query={query} />
    {query.data && !courses.length && <Empty>You are not registered for any courses yet.</Empty>}
    <div className="course-strip" ref={strip}>{courses.map(c => <CoverCard key={c.id} course={c} />)}</div>
  </section>;
}

const RANGES = { 7: "Next 7 days", 30: "Next 30 days", overdue: "Overdue" };

function Timeline() {
  const query = useTeachingQuery("/api/student/deadlines");
  const [range, setRange] = useState("7");
  const [order, setOrder] = useState("date");
  const [now] = useState(() => Date.now());
  const items = useMemo(() => {
    const rows = (query.data || []).filter(i => {
      const due = new Date(i.due_at).getTime();
      if (range === "overdue") return due < now && i.status !== "DONE";
      return due >= now && due <= now + Number(range) * 86400000;
    });
    return order === "course" ? [...rows].sort((a, b) => a.subject_name.localeCompare(b.subject_name) || a.due_at.localeCompare(b.due_at)) : rows;
  }, [query.data, range, order, now]);
  const groups = [];
  for (const item of items) {
    const label = order === "course" ? item.subject_name : new Date(item.due_at).toLocaleDateString(undefined, { weekday: "long", day: "numeric", month: "long" });
    if (groups.at(-1)?.label !== label) groups.push({ label, items: [] });
    groups.at(-1).items.push(item);
  }
  return <section className="learner-panel" aria-labelledby="timeline">
    <div className="learner-panel__head"><h2 id="timeline">Timeline</h2>
      <div className="timeline-tools">
        <Field label="Show" value={range} onChange={e => setRange(e.target.value)}>{Object.entries(RANGES).map(([k, v]) => <option key={k} value={k}>{v}</option>)}</Field>
        <Field label="Sort by" value={order} onChange={e => setOrder(e.target.value)}><option value="date">Date</option><option value="course">Course</option></Field>
      </div></div>
    <QueryState query={query} />
    {query.data && !items.length && <Empty>{range === "overdue" ? "Nothing overdue." : "No activities require action."}</Empty>}
    {groups.map(g => <div key={g.label}><h3 className="timeline-day">{g.label}</h3>
      {g.items.map(i => <div key={i.id} className="timeline-item">
        <time dateTime={i.due_at}>{new Date(i.due_at).toLocaleTimeString(undefined, { hour: "2-digit", minute: "2-digit" })}</time>
        <span><Link to={studentWorkLink(i)}>{i.title}</Link><small>{kindLabel(i)} · {i.subject_name}</small></span>
        <span className={`course-status course-status--${i.status}`}>{STATUS[i.status]}</span>
      </div>)}</div>)}
  </section>;
}

function OnlineUsers() {
  const query = useTeachingQuery("/api/student/online", { refetchInterval: 60000 });
  const data = query.data;
  return <section className="learner-panel" aria-labelledby="online-users"><h2 id="online-users">Online users</h2>
    {data && <p className="teaching-muted">{data.count} online (last {data.minutes} minutes)</p>}
    {data?.people.length > 0 && <ul className="online-list">{data.people.map(p => <li key={p.id}><span className="online-dot" aria-hidden="true" />{p.name}{p.teacher && <small>Teacher</small>}</li>)}</ul>}
    {data && data.count > data.people.length && <p className="teaching-muted">and {data.count - data.people.length} more</p>}
    {query.isError && <p className="teaching-muted">Not available right now.</p>}
  </section>;
}

function UpcomingEvents() {
  const query = useTeachingQuery("/api/student/deadlines");
  const [now] = useState(() => Date.now());
  const items = (query.data || []).filter(i => new Date(i.due_at).getTime() >= now).slice(0, 5);
  return <section className="learner-panel" aria-labelledby="upcoming-events"><h2 id="upcoming-events">Upcoming events</h2>
    {query.data && !items.length && <p className="teaching-muted">There are no upcoming events.</p>}
    <ul className="event-list">{items.map(i => { const d = new Date(i.due_at); return <li key={i.id}>
      <span className="event-date"><strong>{d.getDate()}</strong><small>{d.toLocaleDateString(undefined, { month: "short" })}</small></span>
      <span><Link to={studentWorkLink(i)}>{i.title}</Link><p>{kindLabel(i)} · {i.subject_name} · {d.toLocaleTimeString(undefined, { hour: "2-digit", minute: "2-digit" })}</p></span>
    </li>; })}</ul>
    {items.length > 0 && <p><Link to="/student/assignments">Go to assignments</Link></p>}
  </section>;
}

/* ---------- My courses ---------- */

const SORTS = {
  name: ["Course name", (a, b) => a.name.localeCompare(b.name)],
  recent: ["Last accessed", (a, b) => (b.last_visited_at || "").localeCompare(a.last_visited_at || "") || a.name.localeCompare(b.name)],
  due: ["Next deadline", (a, b) => (a.next_due?.due_at || "9999").localeCompare(b.next_due?.due_at || "9999")],
};

function remembered(key, fallback) {
  try { return localStorage.getItem(key) || fallback; } catch { return fallback; }
}

export function StudentCoursesPage() {
  const { user } = useAuth();
  const query = useTeachingQuery("/api/student/courses");
  const [stars, toggleStar] = useStars(user.id);
  const [filter, setFilter] = useState("all");
  const [search, setSearch] = useState("");
  const [sort, setSort] = useState("name");
  const [view, setViewState] = useState(() => remembered("skynet:course-view", "card"));
  const setView = value => { setViewState(value); try { localStorage.setItem("skynet:course-view", value); } catch { /* per visit */ } };
  const rows = useMemo(() => {
    const q = search.trim().toLowerCase();
    return (query.data || []).filter(c => (filter === "all" || (filter === "todo" ? c.to_do > 0 : stars.has(c.id)))
      && (!q || `${c.name} ${c.class_name} ${c.teacher_name}`.toLowerCase().includes(q))).sort(SORTS[sort][1]);
  }, [query.data, filter, search, sort, stars]);
  const star = c => <Star on={stars.has(c.id)} name={c.name} onToggle={() => toggleStar(c.id)} />;
  return <>
    <h1 className="learner-title">My courses</h1>
    <section className="learner-panel" aria-labelledby="course-overview"><h2 id="course-overview">Course overview</h2>
      <div className="overview-toolbar">
        <Field label="Show" value={filter} onChange={e => setFilter(e.target.value)}><option value="all">All</option><option value="todo">With work to do</option><option value="starred">Starred</option></Field>
        <div className="overview-toolbar__search"><Field label="Search" type="search" value={search} onChange={e => setSearch(e.target.value)} /></div>
        <Field label="Sort by" value={sort} onChange={e => setSort(e.target.value)}>{Object.entries(SORTS).map(([k, [label]]) => <option key={k} value={k}>{label}</option>)}</Field>
        <Field label="View" value={view} onChange={e => setView(e.target.value)}><option value="card">Card</option><option value="list">List</option></Field>
      </div>
      <QueryState query={query} />
      {query.data?.length === 0 && <Empty>You are not registered for any courses yet.</Empty>}
      {query.data?.length > 0 && !rows.length && <Empty>{filter === "starred" && !search ? "Star a course to keep it here." : "No courses match."}</Empty>}
      {view === "card" ? <div className="cover-cards">{rows.map(c => <CoverCard key={c.id} course={c} star={star(c)} />)}</div>
        : rows.length > 0 && <div className="cover-list">{rows.map(c => <Link key={c.id} to={`/student/courses/${c.id}`} className="cover-row">
          <span className="cover-card__art" style={coverArt(c.name)} aria-hidden="true" />
          <span><span className="cover-card__name">{c.name}</span><span className="cover-card__meta"> · {c.class_name} · {c.teacher_name}</span></span>
          <span className="cover-row__side"><span className="cover-card__due">{c.to_do ? `${c.to_do} to do` : "Nothing due"}</span>{star(c)}</span>
        </Link>)}</div>}
    </section>
  </>;
}

/* ---------- Search course ---------- */

function Highlight({ text, term }) {
  const q = term.trim();
  if (!q) return text;
  const at = text.toLowerCase().indexOf(q.toLowerCase());
  if (at < 0) return text;
  return <>{text.slice(0, at)}<mark>{text.slice(at, at + q.length)}</mark>{text.slice(at + q.length)}</>;
}

export function CourseSearchPage() {
  const [params, setParams] = useSearchParams();
  const term = params.get("q") || "";
  const page = Number(params.get("page") || 1);
  const [draft, setDraft] = useState(term);
  const query = useTeachingQuery(`/api/student/course-search?q=${encodeURIComponent(term)}&page=${page}`);
  const data = query.data;
  const go = (q, p = 1) => setParams(q ? { q, page: String(p) } : { page: String(p) });
  const pages = data ? Array.from({ length: data.pages }, (_, i) => i + 1).filter(n => n === 1 || n === data.pages || Math.abs(n - page) <= 3) : [];
  return <>
    <ol className="crumbs"><li><Link to="/student/courses">Courses</Link></li><li aria-current={term ? undefined : "page"}>Search</li>{term && <li aria-current="page">{term}</li>}</ol>
    <h1 className="learner-title">Search courses</h1>
    <form className="search-bar" role="search" onSubmit={e => { e.preventDefault(); go(draft.trim()); }}>
      <input type="search" aria-label="Search courses" value={draft} onChange={e => setDraft(e.target.value)} placeholder="Course or class name" maxLength={80} />
      <button type="submit" aria-label="Search"><svg viewBox="0 0 24 24" width="18" height="18" aria-hidden="true" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round"><circle cx="11" cy="11" r="7" /><path d="m20 20-4-4" /></svg></button>
    </form>
    <QueryState query={query} />
    {data && <p className="search-count">{term ? "Search results" : "All courses"}: {data.total}</p>}
    {data && !data.results.length && <Empty>No course matches “{term}”.</Empty>}
    <div className="result-list">{data?.results.map(r => <article key={r.id} className="result">
      <div><h3>{r.mine ? <Link to={`/student/courses/${r.id}`}><Highlight text={r.name} term={term} /></Link> : <Highlight text={r.name} term={term} />}</h3>
        <p>{r.class_name} · {r.academic_year} · {r.teacher_name}</p></div>
      {r.mine ? <span className="status-badge status-badge--active">Enrolled</span> : <span className="teaching-muted">Not registered</span>}
    </article>)}</div>
    {data?.pages > 1 && <nav className="pager" aria-label="Result pages">
      <button type="button" disabled={page <= 1} onClick={() => go(term, page - 1)} aria-label="Previous page">«</button>
      {pages.map(n => <button key={n} type="button" aria-current={n === page ? "page" : undefined} disabled={n === page} onClick={() => go(term, n)}>{n}</button>)}
      <button type="button" disabled={page >= data.pages} onClick={() => go(term, page + 1)} aria-label="Next page">»</button>
    </nav>}
  </>;
}

/* ---------- Messages (read only) ---------- */

export function StudentMessagesPage() {
  const { user, readOnly } = useAuth();
  const client = useQueryClient();
  const query = useTeachingQuery("/api/student/messages");
  const [open, setOpen] = useState(null);
  async function show(m) {
    setOpen(open === m.id ? null : m.id);
    if (m.read || readOnly) return;
    try {
      await apiRequest(`/api/student/messages/${m.id}/read`, { method: "POST" });
      client.invalidateQueries({ queryKey: ["teaching", user.id, "/api/student/messages"] });
      client.invalidateQueries({ queryKey: ["teaching", user.id, "/api/notifications"] });
    } catch { /* stays unread; try again next time */ }
  }
  return <>
    <h1 className="learner-title">Messages</h1>
    <p className="teaching-muted learner-intro">Messages from your teachers and the school office. Replies are not possible here; speak to your teacher in person. The school can read these messages.</p>
    <QueryState query={query} />
    {query.data && !query.data.messages.length && <Empty>No messages yet.</Empty>}
    {query.data?.messages.length > 0 && <div className="message-list">{query.data.messages.map(m => <article key={m.id} className={`message${m.read ? " message--read" : ""}`}>
      <button type="button" aria-expanded={open === m.id} onClick={() => show(m)}>
        <span className="message__dot" aria-label={m.read ? undefined : "Unread"} />
        <span><strong>{m.title}</strong><span className="message__from">{m.sender_name}{m.audience === "CLASS" ? " · to your class" : ""}</span></span>
        <small>{shortDate(m.sent_at)}</small>
      </button>
      {open === m.id && <p className="message__body">{m.body}</p>}
    </article>)}</div>}
  </>;
}

/* ---------- Home: the school's notice board and today ---------- */

export function StudentHomePage() {
  const query = useTeachingQuery("/api/announcements");
  return <>
    <h1 className="learner-title">Home</h1>
    <div className="learner-dashboard">
      <section className="learner-panel" aria-labelledby="site-news"><h2 id="site-news">Announcements</h2>
        <QueryState query={query} />
        {query.data && !query.data.length && <Empty>No announcements.</Empty>}
        {query.data?.slice(0, 6).map(a => <article key={a.id} className="timeline-item" style={{ gridTemplateColumns: "1fr" }}>
          <span><strong>{a.title}</strong><small>{new Date(a.created_at).toLocaleDateString(undefined, { day: "numeric", month: "long", year: "numeric" })}{a.author && ` · ${a.author}`}</small>
            <p className="records-announcement">{a.body}</p></span></article>)}
        {query.data?.length > 6 && <p><Link to="/student/announcements">All announcements</Link></p>}
      </section>
      <aside><TodayLessons /><UpcomingEvents /></aside>
    </div>
  </>;
}
