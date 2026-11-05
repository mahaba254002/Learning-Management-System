import { Link, useLocation } from 'react-router-dom';
import { useTeachingQuery } from '../../pages/teacher/teachingQueries';
import { QueryState } from '../../pages/teacher/TeachingUI';
import { pageEnabled, pageModules, moduleLabels } from '../../modules/institutionModules';
import { useAuth } from '../../context/useAuth';

export default function ModuleAccess({ children }) {
  const { pathname } = useLocation();
  const { user } = useAuth();
  const query = useTeachingQuery('/api/institution/modules', { refetchInterval: 30000 });
  if (!query.data) return <QueryState query={query} />;
  if (!pageEnabled(pathname, query.data.modules)) return <section className="teaching-panel"><h1>Feature unavailable</h1><p>This institution does not currently use {pageModules(pathname).filter(key => !query.data.modules[key]).map(key => moduleLabels[key][0].toLowerCase()).join(', ')}. Contact your institution administrator about access.</p>{user.role === 'INSTITUTION_ADMIN' && <Link to="/institution/modules">View institution package</Link>}</section>;
  return children;
}
