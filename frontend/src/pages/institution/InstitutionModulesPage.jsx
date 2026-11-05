import { useTeachingQuery } from '../teacher/teachingQueries';
import { PageHeading, QueryState } from '../teacher/TeachingUI';
import { moduleLabels, presetLabels } from '../../modules/institutionModules';
import '../../components/common/ModuleEditor.css';

export default function InstitutionModulesPage() {
  const query = useTeachingQuery('/api/institution/modules');
  const data = query.data;
  const preset = data && Object.entries(data.presets).find(([, value]) => Object.keys(value).every(key => value[key] === data.modules[key]))?.[0];
  return <><PageHeading title="Institution package">Features enabled for your institution. Contact the platform administrator to change your package.</PageHeading><QueryState query={query} />{data && <section className="teaching-panel"><h2>{presetLabels[preset] || 'Custom configuration'}</h2><p>Module availability applies to the whole institution. Your account role and assigned teaching responsibilities determine what you can do within each enabled feature.</p><div className="module-grid">{Object.entries(moduleLabels).map(([key, [label, description]]) => <div key={key} className={`module-option ${data.modules[key] ? 'is-enabled' : ''}`}><span><strong>{label} · {data.modules[key] ? 'Enabled' : 'Disabled'}</strong><small>{description}</small></span></div>)}</div><p>Turning features off retains existing records. They become available again when the feature is enabled.</p></section>}</>;
}
