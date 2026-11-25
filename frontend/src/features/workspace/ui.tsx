import { useCallback, useEffect, useState, type ReactNode } from 'react'
import type { Page } from './api'

export function message(error: unknown) {
  return error instanceof Error ? error.message : 'Something went wrong. Try again.'
}

export function useResource<T>(load: () => Promise<T>) {
  const [revision, setRevision] = useState(0)
  const retry = useCallback(() => setRevision((n) => n + 1), [])
  const [result, setResult] = useState<{ load: typeof load; revision: number; value?: T; error?: string }>()
  useEffect(() => {
    let active = true
    load().then(
      (value) => { if (active) setResult({ load, revision, value }) },
      (error: unknown) => { if (active) setResult({ load, revision, error: message(error) }) },
    )
    return () => { active = false }
  }, [load, revision])
  const current = result?.load === load && result.revision === revision ? result : undefined
  return { value: current?.value, error: current?.error, loading: current === undefined, retry }
}

export function ErrorNotice({ error, retry }: { error: string; retry?: () => void }) {
  return <div className="workspace-error" role="alert">
    <p>{error}</p>
    {retry && <button className="button button-secondary" type="button" onClick={retry}>Try again</button>}
  </div>
}

export function Section({ title, children }: { title: string; children: ReactNode }) {
  return <section className="workspace-panel">
    <h2>{title}</h2>
    {children}
  </section>
}

export function Heading({ title, children }: { title: string; children?: ReactNode }) {
  return <header className="workspace-heading">
    <h1>{title}</h1>
    {children}
  </header>
}

export const readable = (name: string) => name.toLowerCase().replaceAll('_', ' ').replace(/^./, (first) => first.toUpperCase())

export function Badge({ value }: { value: string }) {
  return <span className="workspace-badge" data-value={value}>{readable(value)}</span>
}

export function Timestamp({ value }: { value: string }) {
  return <time dateTime={value} title={value}>{new Date(value).toLocaleString(undefined, {
    dateStyle: 'medium', timeStyle: 'medium',
  })}</time>
}

export function Pagination({ meta, change }: { meta: Page<unknown>['meta']; change: (page: number) => void }) {
  const count = Math.max(1, Math.ceil(meta.total / meta.page_size))
  return count > 1 && <nav className="workspace-pagination" aria-label="Pagination">
    <button className="button button-secondary" type="button" disabled={meta.page <= 1} onClick={() => change(meta.page - 1)}>Previous</button>
    <span>Page {meta.page} of {count}</span>
    <button className="button button-secondary" type="button" disabled={meta.page >= count} onClick={() => change(meta.page + 1)}>Next</button>
  </nav>
}

export function field(form: FormData, name: string) {
  return String(form.get(name) ?? '').trim()
}
