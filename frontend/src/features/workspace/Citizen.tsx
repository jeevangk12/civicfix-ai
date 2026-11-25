import { useCallback, useRef, useState, type FormEvent } from 'react'
import { Link, useLocation, useNavigate, useParams } from 'react-router'
import { data, page } from './api'
import { NoReports, ReportList } from './ReportList'
import { getCategories, type ReportSummary, type Status } from './reportModel'
import { Badge, ErrorNotice, Heading, Pagination, Section, Timestamp, field, message, useResource } from './ui'

const reportsPath = '/citizen/complaints'

type Report = ReportSummary & {
  description: string; latitude: number; longitude: number; location_label: string | null
}
type Progress = {
  id: string; old_status: Status | null; new_status: Status | null; message: string | null; created_at: string
}
type Feedback = { id: string; rating: number; comment: string | null; created_at: string }

export function CitizenReports() {
  const [number, setPage] = useState(1)
  const load = useCallback(() => page<ReportSummary>(`/complaints/mine?page=${number}`), [number])
  const reports = useResource(load)
  return <>
    <Heading title="My reports">
      {reports.value && reports.value.meta.total > 0 &&
        <Link className="button button-primary" to={reportsPath + '/new'}>Report an issue</Link>}
    </Heading>
    {reports.loading && <p role="status">Loading reports…</p>}
    {reports.error && <ErrorNotice error={reports.error} retry={reports.retry} />}
    {reports.value && (reports.value.meta.total === 0 ? <NoReports /> : <>
      <ReportList reports={reports.value.data} base={reportsPath} />
      <Pagination meta={reports.value.meta} change={setPage} />
    </>)}
  </>
}

function ReportHistory({ endpoint }: { endpoint: string }) {
  const [number, setPage] = useState(1)
  const load = useCallback(() => page<Progress>(`${endpoint}/updates?page=${number}`), [endpoint, number])
  const history = useResource(load)
  return <Section title="Progress history">
    {history.loading && <p role="status">Loading progress…</p>}
    {history.error && <ErrorNotice error={history.error} retry={history.retry} />}
    {history.value && (history.value.meta.total ? <>
      <ol className="workspace-history">{history.value.data.map((item) => <li key={item.id}>
        <header>{item.new_status && <Badge value={item.new_status} />}<Timestamp value={item.created_at} /></header>
        {item.message && <p>{item.message}</p>}
      </li>)}</ol>
      <Pagination meta={history.value.meta} change={setPage} />
    </> : <p>No progress updates yet.</p>)}
  </Section>
}

function ResolutionFeedback({ endpoint, status }: { endpoint: string; status: Status }) {
  const load = useCallback(() => data<Feedback | null>(endpoint + '/feedback'), [endpoint])
  const resource = useResource(load)
  const [saved, setSaved] = useState<Feedback>()
  const [busy, setBusy] = useState(false)
  const [error, setError] = useState<string>()
  const eligible = status === 'RESOLVED' || status === 'CLOSED'
  const feedback = saved ?? resource.value

  async function submit(event: FormEvent<HTMLFormElement>) {
    event.preventDefault()
    const values = new FormData(event.currentTarget)
    setBusy(true)
    setError(undefined)
    try {
      setSaved(await data<Feedback>(endpoint + '/feedback', {
        method: 'POST', body: { rating: Number(field(values, 'rating')), comment: field(values, 'comment') || null },
      }))
    } catch (failure) {
      setError(message(failure))
    } finally {
      setBusy(false)
    }
  }

  return <Section title="Resolution feedback">
    {saved && <p role="status" className="workspace-success">Feedback submitted.</p>}
    {resource.loading && <p role="status">Checking feedback…</p>}
    {resource.error && <ErrorNotice error={resource.error} retry={resource.retry} />}
    {feedback && <>
      <p><strong>{feedback.rating} out of 5</strong> · <Timestamp value={feedback.created_at} /></p>
      {feedback.comment && <p className="workspace-multiline">{feedback.comment}</p>}
    </>}
    {resource.value === null && !saved && (eligible ? <form className="workspace-form" onSubmit={submit}>
      <p>How satisfied are you with the resolution?</p>
      {error && <ErrorNotice error={error} />}
      <label>Rating<select name="rating" defaultValue="" required>
        <option value="">Choose a rating</option>
        <option value="5">5 · Very satisfied</option><option value="4">4 · Satisfied</option>
        <option value="3">3 · Neutral</option><option value="2">2 · Unsatisfied</option>
        <option value="1">1 · Very unsatisfied</option>
      </select></label>
      <label>Comment <span>(optional)</span><textarea name="comment" maxLength={1000} rows={3} /></label>
      <button className="button button-primary" disabled={busy}>{busy ? 'Submitting…' : 'Submit feedback'}</button>
    </form> : <p>You can leave feedback once this report is resolved.</p>)}
  </Section>
}

function ReportPage({ id }: { id: string }) {
  const { state } = useLocation()
  const endpoint = '/complaints/' + encodeURIComponent(id)
  const load = useCallback(() => data<Report>(endpoint), [endpoint])
  const report = useResource(load)
  return <>
    <Link className="workspace-back" to={reportsPath}>← My reports</Link>
    {report.loading && <p role="status">Loading report…</p>}
    {report.error && <ErrorNotice error={report.error} retry={report.retry} />}
    {report.value && <>
      {state?.photoAttached && <p role="status" className="workspace-success">Photo attached privately.</p>}
      <Heading title={report.value.title}>
        <div className="workspace-case-meta">
          <code>{report.value.public_reference}</code><Badge value={report.value.status} />
          <Timestamp value={report.value.created_at} />
        </div>
      </Heading>
      <Section title="Your report">
        <p className="workspace-multiline">{report.value.description}</p>
        {report.value.location_label && <p className="workspace-muted">{report.value.location_label}</p>}
      </Section>
      <div className="workspace-columns">
        <ReportHistory endpoint={endpoint} />
        <ResolutionFeedback endpoint={endpoint} status={report.value.status} />
      </div>
    </>}
  </>
}

export function CitizenComplaint() {
  const { id } = useParams()
  return id ? <ReportPage key={id} id={id} /> : <Heading title="Report not found" />
}

export function NewComplaint() {
  const categories = useResource(getCategories)
  const navigate = useNavigate()
  const draft = useRef<{ json: string; key: string }>(null)
  const [busy, setBusy] = useState(false)
  const [error, setError] = useState<string>()
  const [attachment, setAttachment] = useState<{ report: Report; photo: File }>()

  function openReport(report: Report, photoAttached = false) {
    navigate(`${reportsPath}/${report.id}`, { replace: true, state: { photoAttached } })
  }

  async function attach(report: Report, photo: File) {
    setBusy(true)
    setError(undefined)
    try {
      const payload = new FormData()
      payload.set('file', photo)
      await data(`/complaints/${report.id}/images`, { method: 'POST', body: payload })
      openReport(report, true)
    } catch (failure) {
      setError(message(failure))
    } finally {
      setBusy(false)
    }
  }

  async function submit(event: FormEvent<HTMLFormElement>) {
    event.preventDefault()
    const values = new FormData(event.currentTarget)
    const body = {
      title: field(values, 'title'), description: field(values, 'description'),
      latitude: Number(field(values, 'latitude')), longitude: Number(field(values, 'longitude')),
      location_label: field(values, 'location_label') || null, category_id: field(values, 'category_id') || null,
    }
    const json = JSON.stringify(body)
    if (draft.current?.json !== json) draft.current = { json, key: crypto.randomUUID() }
    setBusy(true)
    setError(undefined)
    try {
      const report = await data<Report>('/complaints', { method: 'POST', body, idempotencyKey: draft.current.key })
      const photo = values.get('photo')
      if (photo instanceof File && photo.size > 0) {
        setAttachment({ report, photo })
        await attach(report, photo)
      } else {
        openReport(report)
      }
    } catch (failure) {
      setError(message(failure))
    } finally {
      setBusy(false)
    }
  }

  if (attachment) return <>
    <Heading title="Report submitted"><p>Tracking reference <strong>{attachment.report.public_reference}</strong></p></Heading>
    <Section title="Optional photo">
      {busy && <p role="status">Uploading photo…</p>}
      {error && <ErrorNotice error={error} />}
      <div className="workspace-actions">
        <button className="button button-primary" disabled={busy}
          onClick={() => openReport(attachment.report)}>Continue without photo</button>
        <button className="button button-secondary" disabled={busy}
          onClick={() => void attach(attachment.report, attachment.photo)}>Retry photo</button>
      </div>
    </Section>
  </>

  return <>
    <Link className="workspace-back" to={reportsPath}>← My reports</Link>
    <Heading title="Report an issue" />
    <form className="workspace-panel workspace-form workspace-report-form" onSubmit={submit}>
      {error && <ErrorNotice error={error} />}
      <label>Title<input name="title" minLength={5} maxLength={120} required /></label>
      <label>Description<textarea name="description" minLength={20} maxLength={5000} rows={5} required /></label>
      <label>Category <span>(optional)</span><select name="category_id" disabled={categories.loading || !!categories.error}>
        <option value="">Choose a category</option>
        {categories.value?.map(({ id, name }) => <option value={id} key={id}>{name}</option>)}
      </select></label>
      {categories.error && <ErrorNotice error={categories.error} retry={categories.retry} />}
      <label>Location label <span>(optional)</span><input name="location_label" maxLength={255} /></label>
      <p className="workspace-muted">Enter latitude and longitude in decimal degrees. Staff use the location to route and investigate your report. A public marker requires staff approval and can use an approximate location.</p>
      <div className="workspace-coordinate-fields">
        <label>Latitude<input name="latitude" type="number" min={-90} max={90} step="any" required /></label>
        <label>Longitude<input name="longitude" type="number" min={-180} max={180} step="any" required /></label>
      </div>
      <label>Photo <span>(optional)</span><input name="photo" type="file" accept="image/jpeg,image/png,image/webp" /></label>
      <button className="button button-primary" disabled={busy}>{busy ? 'Submitting report…' : 'Submit report'}</button>
    </form>
  </>
}
