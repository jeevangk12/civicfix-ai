import { useCallback, useState } from 'react'
import { Link } from 'react-router'
import { data } from './api'
import { CountChart, type Bucket } from './CountChart'
import { NoReports, ReportList } from './ReportList'
import { getCategories, type ReportSummary } from './reportModel'
import { ErrorNotice, Heading, Section, readable, useResource } from './ui'

type Counts = { total: number; open: number; resolved: number; by_status: Bucket[] }
type CitizenCounts = Counts & { recent: ReportSummary[] }
type StaffCounts = Counts & {
  assigned_open: number; by_priority: Bucket[]; oldest_pending: ReportSummary[]; areas: { id: string; name: string }[]
}
type AdminCounts = Counts & {
  trend: Bucket[]; by_category: Bucket[]; by_department: Bucket[]; by_priority: Bucket[];
  by_analysis_status: Bucket[]; by_duplicate_decision: Bucket[]; average_resolution_hours: number | null
}

const myReports = '/citizen/complaints'
const getCitizenCounts = () => data<CitizenCounts>('/citizen/dashboard')
const getOrganizations = () => data<{ id: string; name: string }[]>('/admin/organizations')
const labelEnums = (buckets: Bucket[]) => buckets.map((item) => ({ ...item, label: readable(item.label) }))

function Stats({ values }: { values: [string, number | string][] }) {
  return <dl className="workspace-stats">
    {values.map(([label, value]) => <div key={label}><dt>{label}</dt><dd>{value.toLocaleString()}</dd></div>)}
  </dl>
}

export function CitizenDashboard() {
  const dashboard = useResource(getCitizenCounts)
  const counts = dashboard.value
  return <>
    <Heading title="Citizen dashboard">
      <p>Track your reports and see their latest status.</p>
      {counts && counts.total > 0 && <Link className="button button-primary" to={myReports + '/new'}>Report an issue</Link>}
    </Heading>
    {dashboard.loading && <p role="status">Loading dashboard…</p>}
    {dashboard.error && <ErrorNotice error={dashboard.error} retry={dashboard.retry} />}
    {counts && <>
      <Stats values={ [['Total reports', counts.total], ['Open reports', counts.open], ['Resolved reports', counts.resolved]] } />
      {counts.total === 0 ? <NoReports /> : <div className="workspace-columns">
        <Section title="Recent reports">
          <ReportList reports={counts.recent} base={myReports} />
          <Link className="workspace-back" to={myReports}>View all reports →</Link>
        </Section>
        <CountChart title="Reports by status" values={labelEnums(counts.by_status)} />
      </div>}
    </>}
  </>
}

export function StaffDashboard() {
  const [category, setCategory] = useState('')
  const [area, setArea] = useState('')
  const load = useCallback(() => {
    const params = new URLSearchParams()
    if (category) params.set('category_id', category)
    if (area) params.set('service_area_id', area)
    return data<StaffCounts>(`/authority/dashboard?${params}`)
  }, [category, area])
  const dashboard = useResource(load)
  const categories = useResource(getCategories)
  const counts = dashboard.value
  return <>
    <Heading title="Authority dashboard"><p>Complaint activity within your assigned scope.</p></Heading>
    <div className="workspace-filters">
      <label>Category<select value={category} onChange={(event) => setCategory(event.target.value)}>
        <option value="">All categories</option>
        {categories.value?.map(({ id, name }) => <option key={id} value={id}>{name}</option>)}
      </select></label>
      <label>Service area<select value={area} disabled={dashboard.loading} onChange={(event) => setArea(event.target.value)}>
        <option value="">All service areas</option>
        {counts?.areas.map(({ id, name }) => <option key={id} value={id}>{name}</option>)}
      </select></label>
    </div>
    {categories.error && <ErrorNotice error={categories.error} retry={categories.retry} />}
    {dashboard.error && <ErrorNotice error={dashboard.error} retry={dashboard.retry} />}
    {dashboard.loading && <p role="status">Loading dashboard…</p>}
    {counts && <>
      <Stats values={ [['Reports in scope', counts.total], ['Open reports', counts.open], ['Open and assigned to you', counts.assigned_open]] } />
      <div className="workspace-columns workspace-equal">
        <CountChart title="Reports by status" values={labelEnums(counts.by_status)} />
        <CountChart title="Reports by confirmed priority" values={labelEnums(counts.by_priority)} />
      </div>
      <Section title="Oldest open reports">
        {counts.oldest_pending.length ? <ReportList reports={counts.oldest_pending} base="/authority/complaints" />
          : <p>No open reports match these filters.</p>}
      </Section>
    </>}
  </>
}

export function AdminDashboard() {
  const [organization, setOrganization] = useState('')
  const load = useCallback(() => data<AdminCounts>(
    organization ? '/admin/dashboard?organization_id=' + encodeURIComponent(organization) : '/admin/dashboard',
  ), [organization])
  const dashboard = useResource(load)
  const organizations = useResource(getOrganizations)
  const counts = dashboard.value
  return <>
    <Heading title="Admin dashboard"><p>Reporting, resolution, and triage activity across the platform.</p></Heading>
    <div className="workspace-filters">
      <label>Organization<select value={organization} onChange={(event) => setOrganization(event.target.value)}>
        <option value="">All organizations</option>
        {organizations.value?.map(({ id, name }) => <option key={id} value={id}>{name}</option>)}
      </select></label>
    </div>
    {organizations.error && <ErrorNotice error={organizations.error} retry={organizations.retry} />}
    {dashboard.error && <ErrorNotice error={dashboard.error} retry={dashboard.retry} />}
    {dashboard.loading && <p role="status">Loading dashboard…</p>}
    {counts && <>
      <Stats values={ [
        ['Total complaints', counts.total],
        ['Open complaints', counts.open],
        ['Resolved complaints', counts.resolved],
        ['Average time to resolution', counts.average_resolution_hours === null ? 'No data' : `${counts.average_resolution_hours.toLocaleString()} h`],
      ] } />
      <p className="workspace-muted">Resolution time runs from submission to the latest resolution for reports currently resolved or closed.</p>
      <CountChart title="30-day reporting trend" values={counts.trend} trend>Reports submitted each day (UTC).</CountChart>
      <div className="workspace-columns workspace-equal">
        <CountChart title="Complaints by status" values={labelEnums(counts.by_status)} />
        <CountChart title="Complaints by category" values={counts.by_category} />
        <CountChart title="Complaints by confirmed priority" values={labelEnums(counts.by_priority)} />
        <CountChart title="Complaints by assigned department" values={counts.by_department} />
        <CountChart title="AI analysis outcomes" values={labelEnums(counts.by_analysis_status)} />
        <CountChart title="Duplicate review outcomes" values={labelEnums(counts.by_duplicate_decision)} />
      </div>
    </>}
  </>
}
