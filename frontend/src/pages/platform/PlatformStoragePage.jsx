import { useTeachingQuery } from "../teacher/teachingQueries";
import { Empty, PageHeading, QueryState } from "../teacher/TeachingUI";
import { fileSize } from "../elearning/format";
import "../records/Records.css";

export default function PlatformStoragePage() {
  const query = useTeachingQuery("/api/platform/storage");
  const data = query.data;
  const share = data ? Math.min(100, (data.total_bytes / data.free_bytes) * 100) : 0;
  return <><PageHeading title="File storage">Files teachers and students upload (materials, question papers and answers). Each file can be up to 10 MB.</PageHeading>
    <QueryState query={query} />
    {data && <>
      {!data.enabled && <p className="teaching-notice">Uploads are off. Add the Cloudflare R2 settings on the server (STORAGE_BACKEND=r2 and the R2 keys) to switch them on.</p>}
      <dl className="records-totals"><div><dt>Used</dt><dd>{fileSize(data.total_bytes)}</dd></div><div><dt>Free allowance</dt><dd>10 GB</dd></div>
        <div><dt>Of the free allowance</dt><dd>{share < 1 && data.total_bytes ? "under 1" : Math.round(share)}%</dd></div></dl>
      {data.schools.length === 0 ? <Empty>No files uploaded yet.</Empty> : <div className="table-wrapper"><table className="data-table">
        <thead><tr><th scope="col">School</th><th scope="col">Files</th><th scope="col">Space used</th></tr></thead>
        <tbody>{data.schools.map(s => <tr key={s.institution_id}><td>{s.name}</td><td>{s.files}</td><td>{fileSize(s.bytes)}</td></tr>)}</tbody></table></div>}
    </>}
  </>;
}
