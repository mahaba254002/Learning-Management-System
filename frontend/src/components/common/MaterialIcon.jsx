import icons from '../../assets/material-symbols/icons.json';
import './MaterialIcon.css';

export default function MaterialIcon({ name, size = 20, className = '' }) {
  const icon = icons[name] || icons.chevron_right;
  return <svg className={`material-icon ${className}`.trim()} viewBox={icon.viewBox} width={size} height={size} fill="currentColor" aria-hidden="true" focusable="false">
    {icon.paths.map((path, index) => <path key={index} d={path} />)}
  </svg>;
}
