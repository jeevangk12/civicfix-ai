import { Link } from 'react-router'
import type { ReportSummary } from './reportModel'
import { Badge, Timestamp } from './ui'

export function ReportList({ reports, base }: { reports: ReportSummary[]; base: string }) {
  return <ul className="workspace-report-list">
    {reports.map((report) => <li key={report.id}>
      <Link className="workspace-record-link" to={`${base}/${report.id}`}>
        <strong>{report.title}</strong><span>{report.public_reference}</span>
      </Link>
      <div className="workspace-report-meta"><Badge value={report.status} /><Timestamp value={report.created_at} /></div>
    </li>)}
  </ul>
}

export function NoReports() {
  return <div className="workspace-empty">
    <h2>No reports yet</h2>
    <p>Report an issue to get a tracking reference and follow its progress here.</p>
    <Link className="button button-primary" to="/citizen/complaints/new">Report your first issue</Link>
  </div>
}
