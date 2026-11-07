import { useMemo, useState } from "react";
import { Link, useLocation, useParams } from "react-router-dom";
import { useTeachingQuery } from "../teacher/teachingQueries";
import { Empty, Field, PageHeading, QueryState } from "../teacher/TeachingUI";
import { FileLink } from "./files";
import { STATUS, kindLabel, portalBase, shortDate, studentWorkLink } from "./format";
import "./Elearning.css";

// Exercise-book covers in Skynet blues; each course keeps the same shade.
const COVERS = ["#075c8d", "#026aa7", "#2b5f80", "#3d6a8a", "#1f4e6e"];
function cover(text) {
  let hash = 0;
  for (const ch of text) hash = (hash * 31 + ch.charCodeAt(0)) % 997;
  return COVERS[hash % COVERS.length];
}

function CourseSearch({ search, setSearch, sort, setSort, sorts }) {
  return <div className="course-toolbar">
    <Field label="Search courses" type="search" value={search} onChange={e => setSearch(e.target.value)} />
    <Field label="Sort by" value={sort} onChange={e => setSort(e.target.value)}>{Object.entries(sorts).map(([k, v]) => <option key={k} value={k}>{v}</option>)}</Field>
  </div>;
}

function useFiltered(rows, search, sort, sorters) {
  return useMemo(() => {
    const q = search.trim().toLowerCase();
    const found = (rows || []).filter(c => !q || `${c.name} ${c.class_name} ${c.teacher_name || ""}`.toLowerCase().includes(q));
    return [...found].sort(sorters[sort]);
  }, [rows, search, sort, sorters]);
}

const STUDENT_SORTS = {
  name: (a, b) => a.name.localeCompare(b.name),
  due: (a, b) => (a.next_due?.due_at || "9999").localeCompare(b.next_due?.due_at || "9999"),
};

export function StudentCoursesPage() {
  const query = useTeachingQuery("/api/student/courses");
  const [search, setSearch] = useState("");
  const [sort, setSort] = useState("name");
  const rows = useFiltered(query.data, search, sort, STUDENT_SORTS);
  return <><PageHeading title="My courses">Your subjects and units, with their materials, assignments and quizzes.</PageHeading><QueryState query={query} />
    {query.data?.length === 0 && <Empty>You are not registered for any courses yet.</Empty>}
    {query.data?.length > 0 && <CourseSearch search={search} setSearch={setSearch} sort={sort} setSort={setSort} sorts={{ name: "Course name", due: "Next deadline" }} />}
    {query.data?.length > 0 && rows.length === 0 && <Empty>No course matches “{search}”.</Empty>}
    <div className="course-cards">{rows.map(c => <Link key={c.id} to={`/student/courses/${c.id}`} className="course-card">
      <span className="course-card__band" style={{ "--course-cover": cover(c.name) }} aria-hidden="true" />
      <span className="course-card__body"><strong>{c.name}</strong><span className="teaching-muted">{c.class_name} · {c.academic_year}</span>
        <span className="teaching-muted">{c.teacher_name}</span>
        <span className="course-card__meta">{c.to_do > 0 ? `${c.to_do} to do` : "Nothing due"}{c.materials ? ` · ${c.materials} material${c.materials === 1 ? "" : "s"}` : ""}</span>
        {c.next_due && <span className="course-card__due">Next: {c.next_due.title}, {shortDate(c.next_due.due_at)}</span>}</span>
    </Link>)}</div>
  </>;
}

function MaterialItem({ m }) {
  return <article className="course-item course-item--material">
    <div className="course-item__head"><span className="course-item__kind">Material</span><strong>{m.title}</strong>{m.published === false && <span className="status-badge status-badge--archived">Draft</span>}</div>
    {m.body && <p className="teaching-instructions">{m.body}</p>}
    <div className="teaching-actions">{m.file && <FileLink file={m.file} />}{m.link_url && <a href={m.link_url} target="_blank" rel="noopener noreferrer">Open link (new tab)</a>}</div>
  </article>;
}

function Sections({ sections, renderWork }) {
  if (!sections.length) return <Empty>Nothing has been posted to this course yet.</Empty>;
  return sections.map(section => <section key={section.name || "general"} className="teaching-panel course-section" aria-label={section.name || "General"}>
    <h2>{section.name || "General"}</h2>
    {section.materials.map(m => <MaterialItem key={m.id} m={m} />)}
    {section.work.map(renderWork)}
  </section>);
}

export function StudentCoursePage() {
  const { subjectId } = useParams();
  const query = useTeachingQuery(`/api/student/courses/${subjectId}`);
  const course = query.data;
  return <><PageHeading title={course?.name || "Course"}>{course && `${course.class_name} · ${course.academic_year} · ${course.teacher_name}`}</PageHeading><QueryState query={query} />
    {course && <Sections sections={course.sections} renderWork={w => <article key={w.id} className="course-item">
      <div className="course-item__head"><span className="course-item__kind">{kindLabel(w)}</span><Link to={studentWorkLink(w)}><strong>{w.title}</strong></Link>
        <span className={`course-status course-status--${w.status}`}>{STATUS[w.status]}</span></div>
      <p className="teaching-muted">{w.opens_at && w.status === "UPCOMING" ? `Opens ${shortDate(w.opens_at)} · ` : ""}{w.due_at ? `Due ${shortDate(w.due_at)}` : "No deadline"}</p>
    </article>} />}
    <p><Link to="/student/courses">All courses</Link></p>
  </>;
}

const STAFF_SORTS = { name: (a, b) => a.name.localeCompare(b.name), class: (a, b) => a.class_name.localeCompare(b.class_name) || a.name.localeCompare(b.name) };

export function TeachingCoursesPage() {
  const { pathname } = useLocation();
  const base = portalBase(pathname);
  const query = useTeachingQuery("/api/teaching/courses");
  const [search, setSearch] = useState("");
  const [sort, setSort] = useState("name");
  const rows = useFiltered(query.data, search, sort, STAFF_SORTS);
  return <><PageHeading title="My courses">Each course you teach, with its materials, assignments and quizzes in one place.</PageHeading><QueryState query={query} />
    {query.data?.length === 0 && <Empty>No courses have been allocated to you yet.</Empty>}
    {query.data?.length > 0 && <CourseSearch search={search} setSearch={setSearch} sort={sort} setSort={setSort} sorts={{ name: "Course name", class: "Class" }} />}
    {query.data?.length > 0 && rows.length === 0 && <Empty>No course matches “{search}”.</Empty>}
    <div className="course-cards">{rows.map(c => <Link key={c.id} to={`${base}/courses/${c.id}`} className="course-card">
      <span className="course-card__band" style={{ "--course-cover": cover(c.name) }} aria-hidden="true" />
      <span className="course-card__body"><strong>{c.name}</strong><span className="teaching-muted">{c.class_name} · {c.academic_year}</span>
        <span className="course-card__meta">{c.materials} material{c.materials === 1 ? "" : "s"} · {c.work} assessment{c.work === 1 ? "" : "s"}</span>
        {c.to_mark > 0 && <span className="course-card__due">{c.to_mark} to mark</span>}</span>
    </Link>)}</div>
  </>;
}

export function TeachingCoursePage() {
  const { subjectId } = useParams();
  const { pathname } = useLocation();
  const base = portalBase(pathname);
  const query = useTeachingQuery(`/api/teaching/courses/${subjectId}`);
  const course = query.data;
  return <><PageHeading title={course?.name || "Course"}>{course && `${course.class_name} · ${course.academic_year} · ${course.students} student${course.students === 1 ? "" : "s"}`}</PageHeading><QueryState query={query} />
    {course && <div className="teaching-actions">
      <Link className="btn" to={`${base}/materials?subject=${course.id}`}>Add material</Link>
      <Link className="btn" to={`${base}/coursework?subject=${course.id}`}>Add assignment or quiz</Link>
      <Link className="btn" to={`${base}/scores?subject=${course.id}`}>Scores</Link>
    </div>}
    {course && <Sections sections={course.sections} renderWork={w => <article key={w.id} className="course-item">
      <div className="course-item__head"><span className="course-item__kind">{kindLabel(w)}</span><strong>{w.title}</strong>
        <span className={`status-badge status-badge--${w.published ? "active" : "archived"}`}>{w.published ? "Published" : "Draft"}</span></div>
      <p className="teaching-muted">{w.due_at ? `Due ${shortDate(w.due_at)}` : "No deadline"} · {w.handed_in} of {course.students} {w.delivery === "QUIZ" ? "attempted" : "handed in"}</p>
      <div className="teaching-actions">{w.delivery === "QUIZ" ? <Link to={`${base}/quizzes/${w.id}`}>Questions & results</Link> : <Link to={`${base}/scores?subject=${course.id}&assessment=${w.id}`}>Submissions & scores</Link>}</div>
    </article>} />}
    <p><Link to={`${base}/courses`}>All courses</Link></p>
  </>;
}

/** Dashboard list of work due soon (students) or closing soon (staff). */
export function UpcomingDeadlines({ staff = false }) {
  const { pathname } = useLocation();
  const query = useTeachingQuery(staff ? "/api/teaching/deadlines" : "/api/student/deadlines");
  const items = query.data || [];
  if (query.isError || !items.length) return null;
  const base = portalBase(pathname);
  return <section className="teaching-panel" aria-labelledby="upcoming-deadlines"><h2 id="upcoming-deadlines">{staff ? "Closing soon" : "Upcoming deadlines"}</h2>
    <ul className="deadline-list">{items.slice(0, 8).map(item => <li key={item.id} className={`deadline deadline--${item.status}`}>
      <time dateTime={item.due_at}>{shortDate(item.due_at)}</time>
      <span><Link to={staff ? (item.delivery === "QUIZ" ? `${base}/quizzes/${item.id}` : `${base}/scores?subject=${item.subject_id}&assessment=${item.id}`) : studentWorkLink(item)}>{item.title}</Link>
        <small className="teaching-muted"> {kindLabel(item)} · {item.subject_name}</small></span>
      <span className={`course-status course-status--${item.status}`}>{STATUS[item.status]}</span>
    </li>)}</ul>
  </section>;
}
