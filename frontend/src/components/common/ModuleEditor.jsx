import { changeModule, moduleLabels, presetLabels } from '../../modules/institutionModules';
import './ModuleEditor.css';

export default function ModuleEditor({ value, onChange, presets, dependencies, disabled = false }) {
  const selected = Object.entries(presets).find(([, preset]) => Object.keys(preset).every(key => preset[key] === value[key]))?.[0];
  return <div className="module-editor">
    <div className="module-presets" role="group" aria-label="Institution package">{Object.entries(presetLabels).map(([key, label]) =>
      <button type="button" key={key} disabled={disabled} aria-pressed={selected === key} onClick={() => onChange({ ...presets[key] })}>{label}</button>)}</div>
    <p>Choose a package, then adjust individual features. Required features are enabled together; turning a feature off also turns off features that depend on it.</p>
    <div className="module-grid">{Object.entries(moduleLabels).map(([key, [label, description]]) => <label className={`module-option ${value[key] ? 'is-enabled' : ''}`} key={key}>
      <input type="checkbox" checked={Boolean(value[key])} disabled={disabled} onChange={event => onChange(changeModule(value, key, event.target.checked, dependencies))} />
      <span><strong>{label}</strong><small>{description}</small></span>
    </label>)}</div>
  </div>;
}
