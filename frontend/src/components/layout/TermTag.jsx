import { useQuery } from "@tanstack/react-query";
import { apiRequest } from "../../api/client";
import { useAuth } from "../../context/useAuth";

/** The term or semester in session, e.g. "Term 3 · 2026". Shows nothing until an academic year is active. */
export default function TermTag() {
  const { user } = useAuth();
  const query = useQuery({ queryKey: ["teaching", user.id, "/api/institution/current-term"], queryFn: () => apiRequest("/api/institution/current-term"), staleTime: 30 * 60 * 1000 });
  const term = query.data;
  if (!term?.year) return null;
  return <span className="term-tag" title="Academic period in session">{term.period ? `${term.period} · ${term.year}` : term.year}</span>;
}
