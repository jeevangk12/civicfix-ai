import { useCallback, useEffect, useState, type FormEvent, type ReactNode } from 'react'
import { Link, useParams, useSearchParams } from 'react-router'
import { data, page } from './api'
import { getCategories, statuses, type Category, type ReportSummary, type Status } from './reportModel'
import { Badge, ErrorNotice, Heading, Pagination, Section, Timestamp, field, message, readable, useResource } from './ui'

const scope = '/authority/complaints'
const priorities = ['LOW', 'MEDIUM', 'HIGH', 'CRITICAL'] as const
type Priority = typeof priorities[number]
type Case = ReportSummary & {
  description: string; location_label: string | null; latitude: number; longitude: number;
  category_confirmed: boolean; confirmed_priority: Priority | null; priority_override_reason: string | null;
  assigned_department_id: string | null; assigned_staff_id: string | null; resolution_description: string | null;
  resolved_at: string | null
}
type Analysis = {
  status: 'PENDING' | 'PROCESSING' | 'SUCCEEDED' | 'FAILED' | 'SKIPPED'; summary: string | null;
  category: string | null; priority: Priority | null; priority_reason: string | null; department: string | null;
  confidence: number | null; needs_human_review: boolean
}
type Person = { id: string; name: string }
type Department = Person & { staff: Person[] }
type Suggestion = {
  id: string; candidate_id: string; public_reference: string; title: string; similarity_score: number;
  distance_meters: number; review_status: 'PENDING' | 'CONFIRMED_DUPLICATE' | 'NOT_DUPLICATE'; reviewed_at: string | null
}
type Update = {
  id: string; actor_id: string; created_at: string; new_status: Status | null; message: string | null; reason: string;
  visibility: 'PUBLIC' | 'INTERNAL'
}

const transitions: Record<Status, Status[]> = {
  SUBMITTED: ['UNDER_REVIEW', 'REJECTED'],
  UNDER_REVIEW: ['REJECTED'],
  ASSIGNED: ['IN_PROGRESS', 'UNDER_REVIEW'],
  IN_PROGRESS: ['RESOLVED'],
  RESOLVED: ['CLOSED', 'IN_PROGRESS'],
  CLOSED: [],
  REJECTED: [],
}
const categoryName = (categories: Category[], id: string | null) => id
  ? categories.find((category) => category.id === id)?.name ?? 'Archived category'
  : 'Uncategorized'

export function Queue() {
  const [query, setQuery] = useSearchParams()
  const pageNumber = Number(query.get('page')) || 1
  const status = query.get('status') ?? ''
  const category = query.get('category_id') ?? ''
  const load = useCallback(() => {
    const params = new URLSearchParams({ page: String(pageNumber) })
    if (status) params.set('status', status)
    if (category) params.set('category_id', category)
    return page<ReportSummary>(`${scope}?${params}`)
  }, [pageNumber, status, category])
  const cases = useResource(load)
  const categories = useResource(getCategories)

  function filter(name: string, value: string) {
    const next = new URLSearchParams(query)
    if (value) next.set(name, value)
    else next.delete(name)
    if (name !== 'page') next.delete('page')
    setQuery(next)
  }

  return <>
    <Heading title="Complaint queue">
      <p>Review and update reports within your assigned departments and service areas.</p>
    </Heading>
    <div className="workspace-filters">
      <label>Status<select value={status} onChange={(event) => filter('status', event.target.value)}>
        <option value="">All statuses</option>{statuses.map((option) => <option key={option} value={option}>{readable(option)}</option>)}
      </select></label>
      <label>Category<select value={category} onChange={(event) => filter('category_id', event.target.value)}>
        <option value="">All categories</option>{categories.value?.map(({ id, name }) => <option key={id} value={id}>{name}</option>)}
      </select></label>
    </div>
    {categories.error && <ErrorNotice error={categories.error} retry={categories.retry} />}
    {cases.error && <ErrorNotice error={cases.error} retry={cases.retry} />}
    {cases.loading && <p role="status">Loading complaints…</p>}
    {cases.value && <>
      <p className="workspace-count">{cases.value.meta.total} {cases.value.meta.total === 1 ? 'report' : 'reports'}</p>
      {cases.value.data.length ? <div className="workspace-table-wrap">
        <table className="workspace-table">
          <thead><tr><th scope="col">Report</th><th scope="col">Category</th><th scope="col">Status</th><th scope="col">Submitted</th></tr></thead>
          <tbody>{cases.value.data.map((row) => <tr key={row.id}>
            <td><Link className="workspace-record-link" to={row.id}>
              <strong>{row.title}</strong><small>{row.public_reference}</small>
            </Link></td>
            <td>{categories.value ? categoryName(categories.value, row.category_id) : '—'}</td>
            <td><Badge value={row.status} /></td><td><Timestamp value={row.created_at} /></td>
          </tr>)}</tbody>
        </table>
      </div> : <p className="workspace-panel">No complaints match these filters.</p>}
      <Pagination meta={cases.value.meta} change={(number) => filter('page', String(number))} />
    </>}
  </>
}

type Mutation = { path: string; method: 'POST' | 'PATCH'; body: object; success: string }
type Action = (request: Mutation, node: HTMLFormElement) => Promise<void>

function ActionForm({ onAction, build, busy, label, children }: {
  onAction: Action; build: (values: FormData) => Mutation; busy: boolean; label: string; children: ReactNode
}) {
  function submit(event: FormEvent<HTMLFormElement>) {
    event.preventDefault()
    void onAction(build(new FormData(event.currentTarget)), event.currentTarget)
  }
  return <form className="workspace-form" onSubmit={submit}>
    {children}
    <button className="button button-primary" disabled={busy}>{label}</button>
  </form>
}

function PublicMessage() {
  return <label>Public progress message <span>(optional, visible to the citizen)</span>
    <textarea name="public_message" rows={2} maxLength={5000} />
  </label>
}

function Reason() {
  return <label>Internal reason<textarea name="reason" rows={2} maxLength={5000} required /></label>
}

function Assignment({ endpoint, options, caseData, busy, save }: {
  endpoint: string; options: Department[]; caseData: Case; busy: boolean; save: Action
}) {
  const [department, setDepartment] = useState(caseData.assigned_department_id ?? '')
  const [person, setPerson] = useState(caseData.assigned_staff_id ?? '')
  const assigned = options.find((option) => option.id === department)
  return <ActionForm label={caseData.status === 'UNDER_REVIEW' ? 'Assign complaint' : 'Save assignment'}
    busy={busy} onAction={save} build={(form) => ({
      path: endpoint + '/assignments', method: 'POST', success: 'Assignment saved.',
      body: { department_id: department, assigned_staff_id: person || null, reason: field(form, 'reason'),
        public_message: field(form, 'public_message') || null },
    })}>
    <label>Department<select required value={department} onChange={(event) => { setDepartment(event.target.value); setPerson('') }}>
      <option value="">Select a department</option>
      {options.map(({ id, name }) => <option value={id} key={id}>{name}</option>)}
    </select></label>
    <label>Staff member <span>(optional)</span><select value={person} disabled={!assigned} onChange={(event) => setPerson(event.target.value)}>
      <option value="">Leave with department</option>
      {assigned?.staff.map(({ id, name }) => <option value={id} key={id}>{name}</option>)}
    </select></label>
    <Reason /><PublicMessage />
  </ActionForm>
}

function StatusAction({ endpoint, current, busy, save }: { endpoint: string; current: Status; busy: boolean; save: Action }) {
  const [next, setNext] = useState<Status | ''>('')
  return transitions[current].length ? <ActionForm label="Update status" busy={busy} onAction={save} build={(form) => ({
    path: endpoint + (next === 'UNDER_REVIEW' ? '/review' : '/status'),
    method: 'POST', success: 'Status updated.',
    body: {
      ...(next !== 'UNDER_REVIEW' && { status: next, resolution_description: field(form, 'resolution') || null }),
      reason: field(form, 'reason'), public_message: field(form, 'public_message') || null,
    },
  })}>
    <label>New status<select value={next} onChange={(event) => setNext(event.target.value as Status | '')} required>
      <option value="">Select a status</option>
      {transitions[current].map((option) => <option value={option} key={option}>{readable(option)}</option>)}
    </select></label>
    <Reason />
    {next === 'RESOLVED' && <label>Resolution details <span>(internal)</span>
      <textarea name="resolution" maxLength={5000} rows={3} required />
    </label>}
    <PublicMessage />
  </ActionForm> : <p>No further status changes are available.</p>
}

function History({ id }: { id: string }) {
  const [pageNumber, setPage] = useState(1)
  const load = useCallback(() => page<Update>(`/complaints/${id}/updates?page=${pageNumber}&page_size=20`), [id, pageNumber])
  const history = useResource(load)
  return <Section title="Progress and notes">
    {history.error && <ErrorNotice error={history.error} retry={history.retry} />}
    {history.loading && <p role="status">Loading history…</p>}
    {history.value && <>
      <ol className="workspace-history">{history.value.data.map((row) => <li key={row.id}>
        <header><Badge value={row.visibility} />{row.new_status && <Badge value={row.new_status} />}
          <Timestamp value={row.created_at} />
        </header>
        {row.message && <p>{row.message}</p>}
        {row.message !== row.reason && <p className="workspace-muted">Internal reason · {row.reason}</p>}
      </li>)}</ol>
      <Pagination meta={history.value.meta} change={setPage} />
    </>}
  </Section>
}

function AiRecommendations({ endpoint }: { endpoint: string }) {
  const load = useCallback(() => data<Analysis>(endpoint + '/analysis'), [endpoint])
  const { value: analysis, error, loading, retry } = useResource(load)
  const status = analysis?.status
  useEffect(() => {
    if (status !== 'PENDING' && status !== 'PROCESSING') return
    const timer = setTimeout(retry, 4000)
    return () => clearTimeout(timer)
  }, [status, retry])
  const analysisMessage = {
    PENDING: 'Analysis is queued.', PROCESSING: 'Analysis is in progress.', FAILED: 'Analysis is unavailable for this report.',
    SKIPPED: 'No AI analysis was requested for this report.', SUCCEEDED: '',
  }
  return <Section title="AI recommendations">
      {loading && <p role="status">Checking analysis…</p>}
      {error && <ErrorNotice error={error} retry={retry} />}
      {analysis && (analysis.status !== 'SUCCEEDED' ? <p>{analysisMessage[analysis.status]}</p> : <>
        <p>{analysis.summary}</p>
        <dl className="workspace-facts">
          <div><dt>Category</dt><dd>{analysis.category ?? 'No suggestion'}</dd></div>
          <div><dt>Priority</dt><dd>{analysis.priority ? <Badge value={analysis.priority} /> : 'No suggestion'}</dd></div>
          <div><dt>Department</dt><dd>{analysis.department ?? 'No suggestion'}</dd></div>
          <div><dt>Confidence</dt><dd>{analysis.confidence === null ? 'Unavailable' : `${Math.round(analysis.confidence * 100)}%`}</dd></div>
        </dl>
        {analysis.priority_reason && <p className="workspace-muted">{analysis.priority_reason}</p>}
        {analysis.needs_human_review && <p className="workspace-accent">Human review requested</p>}
      </>)}
    </Section>
}

function Recommendations({ endpoint, record, categories, options }: {
  endpoint: string; record: Case; categories: Category[]; options: Department[]
}) {
  const department = options.find(({ id }) => id === record.assigned_department_id)
  return <div className="workspace-columns workspace-equal">
    <AiRecommendations endpoint={endpoint} />
    <Section title="Staff-confirmed values">
      <dl className="workspace-facts">
        <div><dt>Category</dt><dd>{record.category_confirmed ? categoryName(categories, record.category_id)
          : record.category_id ? `${categoryName(categories, record.category_id)} (reported by citizen)` : 'Awaiting confirmation'}</dd></div>
        <div><dt>Priority</dt><dd>{record.confirmed_priority ? <Badge value={record.confirmed_priority} /> : 'Awaiting confirmation'}</dd></div>
        <div><dt>Department</dt><dd>{department?.name ?? 'Unassigned'}</dd></div>
        <div><dt>Staff member</dt><dd>{department?.staff.find(({ id }) => id === record.assigned_staff_id)?.name
          ?? (record.assigned_staff_id ? 'Staff member unavailable' : 'Unassigned')}</dd></div>
      </dl>
      {record.priority_override_reason && <p className="workspace-muted">Priority reason · {record.priority_override_reason}</p>}
    </Section>
  </div>
}

function ComplaintPage({ id }: { id: string }) {
  const endpoint = scope + '/' + encodeURIComponent(id)
  const [busy, setBusy] = useState(false)
  const [error, setError] = useState<string>()
  const [notice, setNotice] = useState<string>()
  const load = useCallback(async () => {
    const record = await data<Case>('/complaints/' + encodeURIComponent(id))
    const [duplicates, options, categories] = await Promise.all([
      data<Suggestion[]>(endpoint + '/duplicates'),
      data<Department[]>(endpoint + '/assignment-options'), getCategories(),
    ])
    return { record, duplicates, options, categories }
  }, [id, endpoint])
  const detail = useResource(load)

  const save: Action = async (request, node) => {
    if (busy) return
    setBusy(true)
    setError(undefined)
    setNotice(undefined)
    try {
      await data(request.path, { method: request.method, body: request.body })
      node.reset()
      setNotice(request.success)
      detail.retry()
    } catch (failure) {
      setError(message(failure))
    } finally {
      setBusy(false)
    }
  }

  return <>
    <Link className="workspace-back" to={scope}>← Complaint queue</Link>
    {detail.loading && <p role="status">Loading complaint…</p>}
    {detail.error && <ErrorNotice error={detail.error} retry={detail.retry} />}
    {notice && <p className="workspace-success" role="status">{notice}</p>}
    {detail.value && (() => {
      const { record, categories, duplicates, options } = detail.value
      return <>
        <Heading title={record.title}><div className="workspace-case-meta">
          <code>{record.public_reference}</code><Badge value={record.status} /><Timestamp value={record.created_at} />
        </div></Heading>
        <Section title="Citizen report">
          <p className="workspace-multiline">{record.description}</p>
          <p className="workspace-muted">{record.location_label && `${record.location_label} · `}{record.latitude}, {record.longitude}</p>
        </Section>
        <Recommendations endpoint={endpoint} record={record} categories={categories} options={options} />
        {error && <ErrorNotice error={error} />}
        <div className="workspace-columns">
          <div className="workspace-stack">
            <Section title="Change status">
              <StatusAction endpoint={endpoint} current={record.status} busy={busy} save={save} />
              {record.resolution_description && <div className="workspace-resolution">
                <strong>Resolution details</strong><p>{record.resolution_description}</p>
                {record.resolved_at && <Timestamp value={record.resolved_at} />}
              </div>}
            </Section>
            {['UNDER_REVIEW', 'ASSIGNED', 'IN_PROGRESS'].includes(record.status) && <Section title="Assignment">
              <Assignment endpoint={endpoint} options={options} caseData={record} busy={busy} save={save} />
            </Section>}
            <Section title="Possible duplicates">
              {duplicates.length ? <ul className="workspace-suggestions">{duplicates.map((item) => <li key={item.id}>
                <Link className="workspace-record-link" to={`${scope}/${item.candidate_id}`}>{item.public_reference} · {item.title}</Link>
                <p className="workspace-muted">{Math.round(item.similarity_score * 100)}% text similarity · {Math.round(item.distance_meters)} m away</p>
                {item.review_status === 'PENDING' ? <ActionForm label="Save duplicate review"
                  busy={busy} onAction={save} build={(form) => ({
                    path: '/authority/duplicates/' + item.id + '/review', method: 'POST', success: 'Duplicate review saved.',
                    body: { decision: field(form, 'decision'), reason: field(form, 'reason') },
                  })}>
                  <label>Duplicate decision<select name="decision" required defaultValue="">
                    <option value="">Select a decision</option>
                    <option value="CONFIRMED_DUPLICATE">Confirm duplicate</option><option value="NOT_DUPLICATE">Dismiss suggestion</option>
                  </select></label><Reason />
                </ActionForm> : <p><Badge value={item.review_status} /> {item.reviewed_at && <Timestamp value={item.reviewed_at} />}</p>}
              </li>)}</ul> : <p>No duplicate suggestions in your scope.</p>}
            </Section>
            <History id={id} />
          </div>
          <div className="workspace-stack">
            <Section title="Confirm category">
              <ActionForm label="Save category" busy={busy} onAction={save} build={(form) => ({
                path: endpoint + '/category', method: 'PATCH', success: 'Category confirmed.',
                body: { category_id: field(form, 'category_id'), reason: field(form, 'reason') },
              })}>
                <label>Category<select name="category_id" defaultValue={categories.some(({ id }) => id === record.category_id)
                  ? record.category_id ?? '' : ''} required>
                  <option value="">Select a category</option>
                  {categories.map(({ id, name }) => <option key={id} value={id}>{name}</option>)}
                </select></label><Reason />
              </ActionForm>
            </Section>
            <Section title="Confirm priority">
              <ActionForm label="Save priority" busy={busy} onAction={save} build={(form) => ({
                path: endpoint + '/priority', method: 'PATCH', success: 'Priority confirmed.',
                body: { priority: field(form, 'priority'), reason: field(form, 'reason') },
              })}>
                <label>Priority<select name="priority" defaultValue={record.confirmed_priority ?? ''} required>
                  <option value="">Select a priority</option>
                  {priorities.map((priority) => <option key={priority} value={priority}>{readable(priority)}</option>)}
                </select></label><Reason />
              </ActionForm>
            </Section>
            <Section title="Add progress or note">
              <ActionForm label="Save update" busy={busy} onAction={save} build={(form) => ({
                path: endpoint + '/updates', method: 'POST', success: 'Update saved.',
                body: { message: field(form, 'message'), visibility: field(form, 'visibility') },
              })}>
                <label>Audience<select name="visibility" defaultValue="INTERNAL">
                  <option value="INTERNAL">Internal staff only</option><option value="PUBLIC">Public progress (visible to citizen)</option>
                </select></label>
                <label>Message<textarea name="message" rows={3} maxLength={5000} required /></label>
              </ActionForm>
            </Section>
          </div>
        </div>
      </>
    })()}
  </>
}

export function Complaint() {
  const { id } = useParams()
  return id ? <ComplaintPage key={id} id={id} /> : <Heading title="Complaint not found" />
}
