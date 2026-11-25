// @vitest-environment jsdom
import { cleanup, fireEvent, render, screen, waitFor, within } from '@testing-library/react'
import { MemoryRouter } from 'react-router'
import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest'
import { App } from './App'
import { ApiError, data, page, restoreSession, signIn, signOut, type Role } from './api'
import { CountChart } from './CountChart'
import type { Notification } from './notificationModel'

const chart = vi.hoisted(() => ({ mount: vi.fn(), unmount: vi.fn() }))
vi.mock('chart.js', () => ({
  Chart: class {
    static register() { /* Chart components are registered by the production module. */ }
    constructor(_element: HTMLCanvasElement, config: unknown) { chart.mount(config) }
    destroy() { chart.unmount() }
  },
  BarController: {}, BarElement: {}, CategoryScale: {}, LinearScale: {}, Tooltip: {},
}))
vi.mock('./api', async (original) => ({
  ...await original<typeof import('./api')>(), data: vi.fn(), page: vi.fn(), restoreSession: vi.fn(),
  signIn: vi.fn(), signOut: vi.fn(),
}))

const date = '2026-11-25T12:30:00Z'
const reportPath = '/citizen/complaints/report-id'
const report = {
  id: 'report-id', public_reference: 'CF-SYNTHETIC', title: 'Leaking pipe', status: 'RESOLVED',
  description: 'A pipe is leaking next to the road.', created_at: date, location_label: 'Water district',
}

function session(role: Role) {
  vi.mocked(restoreSession).mockResolvedValue({
    id: 'viewer-' + role, full_name: 'Synthetic viewer', email: 'viewer@example.com', role, is_active: true,
  })
}

function open(path: string) {
  return render(<MemoryRouter initialEntries={[path]}><App /></MemoryRouter>)
}

beforeEach(() => {
  session('CITIZEN')
  vi.mocked(data).mockImplementation(async (path) => {
    if (path === '/notifications/unread-count') return { count: 0 } as never
    throw new Error(`Unexpected data request ${path}`)
  })
})

afterEach(() => {
  cleanup()
  vi.clearAllMocks()
})

describe('citizen experience', () => {
  it('links the dashboard empty state to the working report form', async () => {
    vi.mocked(data).mockImplementation(async (path) => {
      if (path === '/citizen/dashboard') return { total: 0, open: 0, resolved: 0, recent: [], by_status: [] } as never
      if (path === '/notifications/unread-count') return { count: 0 } as never
      throw new Error(`Unexpected data request ${path}`)
    })
    vi.mocked(page).mockResolvedValue({ data: [], meta: { total: 0, page: 1, page_size: 20 } })
    open('/citizen/dashboard')
    const first = await screen.findByRole('link', { name: 'Report your first issue' })
    expect(first.getAttribute('href')).toBe('/citizen/complaints/new')
    fireEvent.click(first)
    await screen.findByRole('heading', { name: 'Report an issue' })
    expect((screen.getByLabelText('Latitude') as HTMLInputElement).required).toBe(true)
  })

  it('shows dated progress and submits feedback from a resolved complaint', async () => {
    vi.mocked(data).mockImplementation(async (path, options) => {
      if (path === '/complaints/report-id') return report as never
      if (path.endsWith('/feedback')) {
        return (options?.method === 'POST' ? { id: 'rating', rating: 5, comment: 'Restored', created_at: date } : null) as never
      }
      return { count: 0 } as never
    })
    vi.mocked(page).mockResolvedValue({
      data: [{ id: 'progress', created_at: date, new_status: 'RESOLVED', message: 'Service restored.' }],
      meta: { total: 1, page: 1, page_size: 20 },
    })
    open(reportPath)
    const update = await screen.findByText('Service restored.')
    expect(update.closest('li')?.querySelector('time')?.dateTime).toBe(date)
    fireEvent.change(await screen.findByLabelText('Rating'), { target: { value: '5' } })
    fireEvent.change(screen.getByLabelText('Comment (optional)'), { target: { value: 'Restored' } })
    fireEvent.click(screen.getByRole('button', { name: 'Submit feedback' }))
    await screen.findByText('Feedback submitted.')
    expect(data).toHaveBeenCalledWith('/complaints/report-id/feedback', {
      method: 'POST', body: { rating: 5, comment: 'Restored' },
    })
  })

  it('shows an API denial for another report and avoids loading its history or feedback', async () => {
    vi.mocked(data).mockImplementation(async (path) => {
      if (path === '/notifications/unread-count') return { count: 0 } as never
      throw new ApiError(404, 'Resource not found.')
    })
    open(reportPath)
    expect((await screen.findByRole('alert')).textContent).toContain('Resource not found.')
    expect(page).not.toHaveBeenCalled()
    expect(data).not.toHaveBeenCalledWith('/complaints/report-id/feedback')
    expect(screen.queryByRole('button', { name: 'Submit feedback' })).toBeNull()
  })

  it('keeps the citizen out of staff routes before fetching staff data', async () => {
    open('/authority/dashboard')
    await screen.findByRole('heading', { name: 'Access denied' })
    expect(data).not.toHaveBeenCalled()
  })

  it('clears a private return route when the citizen signs out', async () => {
    vi.mocked(signOut).mockResolvedValue(undefined)
    vi.mocked(signIn).mockResolvedValue({
      id: 'another-citizen', full_name: 'Another citizen', email: 'another@example.com', role: 'CITIZEN', is_active: true,
    })
    vi.mocked(data).mockImplementation(async (path) => {
      if (path === '/complaints/report-id') return report as never
      if (path === '/citizen/dashboard') return { total: 0, open: 0, resolved: 0, recent: [], by_status: [] } as never
      if (path.endsWith('/feedback')) return null as never
      return { count: 0 } as never
    })
    vi.mocked(page).mockResolvedValue({ data: [], meta: { total: 0, page: 1, page_size: 20 } })
    open(reportPath)
    await screen.findByRole('heading', { name: report.title })
    fireEvent.click(screen.getByRole('button', { name: 'Sign out' }))
    fireEvent.change(await screen.findByLabelText('Email address'), { target: { value: 'another@example.com' } })
    fireEvent.change(screen.getByLabelText('Password'), { target: { value: 'synthetic test phrase' } })
    fireEvent.click(screen.getByRole('button', { name: 'Sign in' }))
    await screen.findByRole('heading', { name: 'Citizen dashboard' })
    expect(vi.mocked(data).mock.calls.filter(([path]) => path === '/complaints/report-id')).toHaveLength(1)
  })
})

it('links a notification to its report and refreshes unread counts after marking one or all', async () => {
  const records: Notification[] = [
    { id: 'notice-one', type: 'COMPLAINT_RESOLVED', title: 'Report resolved', body: 'Open the report for details.',
      resource_type: 'complaint', resource_id: 'report-id', read_at: null, created_at: date },
    { id: 'notice-two', type: 'COMPLAINT_SUBMITTED', title: 'Report received', body: 'Report received.',
      resource_type: 'complaint', resource_id: 'report-id', read_at: null, created_at: date },
  ]
  vi.mocked(page).mockImplementation(async () => ({
    data: records.map((item) => ({ ...item })), meta: { page: 1, page_size: 20, total: records.length },
  }))
  vi.mocked(data).mockImplementation(async (path) => {
    if (path === '/notifications/unread-count') return { count: records.filter((item) => item.read_at === null).length } as never
    if (path === '/notifications/notice-one/read') { records[0].read_at = date; return records[0] as never }
    if (path === '/notifications/read-all') { records[1].read_at = date; return { updated: 1 } as never }
    throw new Error(`Unexpected data request ${path}`)
  })
  open('/citizen/notifications')
  const link = await screen.findByRole('link', { name: 'Open report · Report resolved' })
  expect(link.getAttribute('href')).toBe(reportPath)
  await screen.findByLabelText('2 unread notifications')
  fireEvent.click(screen.getByRole('button', { name: 'Mark as read · Report resolved' }))
  await screen.findByLabelText('1 unread notifications')
  await waitFor(() => expect(screen.queryByRole('button', { name: 'Mark as read · Report resolved' })).toBeNull())
  fireEvent.click(screen.getByRole('button', { name: 'Mark all as read' }))
  await screen.findByLabelText('0 unread notifications')
  expect(data).toHaveBeenCalledWith('/notifications/read-all', { method: 'PATCH' })
})

it('hands server counts to Chart.js and includes equivalent labeled table data', () => {
  const values = [{ label: 'Open', count: 2 }, { label: 'Resolved', count: 3 }]
  const view = render(<CountChart title="Reports by status" values={values} />)
  expect(chart.mount).toHaveBeenCalledWith(expect.objectContaining({
    data: expect.objectContaining({ labels: ['Open', 'Resolved'], datasets: [expect.objectContaining({ data: [2, 3] })] }),
  }))
  fireEvent.click(screen.getByText('View chart data'))
  const table = screen.getByRole('table', { name: 'Reports by status data' })
  expect(within(table).getByRole('row', { name: 'Resolved 3' }).textContent).toBe('Resolved3')
  view.unmount()
  expect(chart.unmount).toHaveBeenCalledTimes(1)
})
