import { useId } from "react";
import "./RecordChart.css";

export default function RecordChart({ title, entries }) {
  const id = useId();
  const values = entries.map(([label, value]) => [label.replaceAll("_", " "), Number(value)]);
  const maximum = Math.max(1, ...values.map(([, value]) => value));
  return <section className="teaching-panel record-chart" aria-labelledby={id}><h2 id={id}>{title}</h2>
    {!values.length ? <p>No records yet.</p> : <><ul className="record-chart__bars" aria-label={title}>
      {values.map(([label, value], index) => <li key={`${label}:${index}`}><span className="record-chart__label">{label}</span><span className="record-chart__track" aria-hidden="true"><span style={{ width: `${value / maximum * 100}%` }} /></span><span>{value}</span></li>)}
    </ul><details><summary>View data table</summary><div className="table-wrapper" role="region" aria-label={`${title} data`} tabIndex={0}><table className="data-table record-chart__table"><thead><tr><th>Category</th><th>Records</th></tr></thead><tbody>{values.map(([label, value], index) => <tr key={`${label}:${index}`}><th scope="row">{label}</th><td>{value}</td></tr>)}</tbody></table></div></details></>}
  </section>;
}
