import { useEffect, useRef, useState } from "react";
import { useQuery, useQueryClient } from "@tanstack/react-query";
import { useNavigate } from "react-router-dom";
import { apiRequest } from "../../api/client";
import { useAuth } from "../../context/useAuth";

const PATH = "/api/notifications";

function when(value) {
  const date = new Date(value);
  const minutes = Math.round((Date.now() - date.getTime()) / 60000);
  if (minutes < 1) return "Just now";
  if (minutes < 60) return `${minutes} min ago`;
  if (minutes < 24 * 60) return `${Math.round(minutes / 60)} h ago`;
  return date.toLocaleDateString(undefined, { day: "numeric", month: "short" });
}

function dueIn(value) {
  const hours = Math.round((new Date(value).getTime() - Date.now()) / 3600000);
  return hours <= 1 ? "Due within the hour" : `Due in ${hours} hours`;
}

/** In-app notifications: new work and materials, released marks, registration decisions, and work due within 48 hours. */
export default function NotificationBell() {
  const { user, readOnly } = useAuth();
  const navigate = useNavigate();
  const client = useQueryClient();
  const [open, setOpen] = useState(false);
  const panel = useRef(null);
  const key = ["teaching", user.id, PATH];
  const query = useQuery({ queryKey: key, queryFn: () => apiRequest(PATH), refetchInterval: 120000, refetchOnWindowFocus: true });

  useEffect(() => {
    if (!open) return undefined;
    const close = event => { if (event.key === "Escape" || (event.type === "mousedown" && !panel.current?.contains(event.target))) setOpen(false); };
    document.addEventListener("mousedown", close);
    document.addEventListener("keydown", close);
    return () => { document.removeEventListener("mousedown", close); document.removeEventListener("keydown", close); };
  }, [open]);

  async function markRead(body) {
    if (readOnly) return;
    try {
      const { unread } = await apiRequest(`${PATH}/read`, { method: "POST", body });
      client.setQueryData(key, old => old && ({ ...old, unread, items: old.items.map(n => (body.all || body.ids.includes(n.id) ? { ...n, read: true } : n)) }));
    } catch { /* The list refreshes on its own; marking read can wait. */ }
  }

  function go(link) {
    setOpen(false);
    if (link) navigate(link);
  }

  const data = query.data;
  const count = (data?.unread || 0) + (data?.due_soon?.length || 0);
  return <div className="notification-bell" ref={panel}>
    <button type="button" className="notification-bell__button" aria-expanded={open} aria-haspopup="true"
      aria-label={count ? `Notifications, ${count} new` : "Notifications"} onClick={() => setOpen(o => !o)}>
      <svg viewBox="0 0 24 24" width="20" height="20" aria-hidden="true" fill="none" stroke="currentColor" strokeWidth="1.7" strokeLinecap="round" strokeLinejoin="round">
        <path d="M6 8a6 6 0 1 1 12 0c0 7 3 9 3 9H3s3-2 3-9" /><path d="M10.3 21a1.94 1.94 0 0 0 3.4 0" />
      </svg>
      {count > 0 && <span className="notification-bell__count">{count > 99 ? "99+" : count}</span>}
    </button>
    {open && <div className="notification-bell__panel" role="dialog" aria-label="Notifications">
      <div className="notification-bell__head"><strong>Notifications</strong>
        {data?.unread > 0 && !readOnly && <button type="button" onClick={() => markRead({ all: true })}>Mark all read</button>}</div>
      {query.isError && !data && <p className="teaching-muted">Notifications could not be loaded. They will refresh shortly.</p>}
      {data?.due_soon?.length > 0 && <section aria-label="Due soon"><h3>Due soon</h3>
        {data.due_soon.map(item => <button type="button" key={item.id} className="notification-item notification-item--due"
          onClick={() => go(item.delivery === "QUIZ" ? `/student/quizzes/${item.id}` : `/student/assignments/${item.id}`)}>
          <span>{item.title}</span><small>{item.subject_name} · {dueIn(item.due_at)}</small></button>)}
      </section>}
      {data && (data.items.length ? <section aria-label="Recent"><h3>Recent</h3>
        {data.items.map(n => <button type="button" key={n.id} className={`notification-item${n.read ? "" : " notification-item--unread"}`}
          onClick={() => { if (!n.read) markRead({ ids: [n.id] }); go(n.link); }}>
          <span>{n.title}</span>{n.body && <small>{n.body}</small>}<small>{when(n.created_at)}</small></button>)}
      </section> : !data.due_soon?.length && <p className="teaching-muted">Nothing new.</p>)}
    </div>}
  </div>;
}
