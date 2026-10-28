import { useTeachingQuery } from "../../pages/teacher/teachingQueries";
import { QueryState } from "../../pages/teacher/TeachingUI";
import { useAuth } from "../../context/useAuth";

export default function InstitutionWorkspace({ children }) {
  const { workspace } = useAuth();
  const query = useTeachingQuery("/api/institution/subscription", { refetchInterval: 30000 });
  if (query.isLoading || query.isError) return <QueryState query={query} />;
  const state = query.data;
  if (state.frozen && workspace?.actor.role !== "PLATFORM_ADMIN") return <section className="teaching-panel" aria-labelledby="subscription-frozen"><h1 id="subscription-frozen">Institution access is frozen</h1><p>Your institution’s subscription needs attention. Your academic records are preserved.</p><p>Please contact the platform administrator: <a href={`mailto:${state.support_email}`}>{state.support_email || "Contact your institution administrator"}</a>.</p></section>;
  if (state.frozen) return <><p className="teaching-notice">This institution is frozen. You retain platform administrator access; institution accounts remain blocked.</p>{children}</>;
  return <>{state.status === "GRACE" && <section className="teaching-notice" role="status"><strong>Subscription payment overdue.</strong> Access will freeze on {state.freeze_date} at 00:00 Kenya time. Please contact <a href={`mailto:${state.support_email}`}>{state.support_email}</a>.</section>}{children}</>;
}
