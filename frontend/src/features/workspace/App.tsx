import { lazy, Suspense, useCallback, useEffect, useState, type FormEvent, type ReactNode } from 'react'
import { Link, Navigate, NavLink, Outlet, Route, Routes, useLocation, useOutletContext } from 'react-router'
import { Brand } from '../landing/Brand'
import { ApiError, registerAccount, restoreSession, signIn, signOut, type Role, type User } from './api'
import { AdminAudit, AdminSettings, AdminUsers } from './Admin'
import { Complaint, Queue } from './Authority'
import { CitizenComplaint, CitizenReports, NewComplaint } from './Citizen'
import { Inbox } from './Inbox'
import { getUnread, type InboxContext } from './notificationModel'
import { ErrorNotice, Heading, message } from './ui'
import './workspace.css'

const Homepage = lazy(async () => ({ default: (await import('../landing/Homepage')).Homepage }))
const PublicMap = lazy(() => import('./PublicMap'))
const CitizenDashboard = lazy(async () => ({ default: (await import('./Dashboards')).CitizenDashboard }))
const StaffDashboard = lazy(async () => ({ default: (await import('./Dashboards')).StaffDashboard }))
const AdminDashboard = lazy(async () => ({ default: (await import('./Dashboards')).AdminDashboard }))
const startAt: Record<Role, string> = { ADMIN: '/admin/users', STAFF: '/authority/complaints', CITIZEN: '/citizen/dashboard' }
const menus = {
  STAFF: [['Dashboard', '/authority/dashboard'], ['Complaint queue', '/authority/complaints'],
    ['Notifications', '/authority/notifications']],
  ADMIN: [
    ['Dashboard', '/admin/dashboard'], ['Users', '/admin/users'], ['Departments', '/admin/departments'],
    ['Categories', '/admin/categories'], ['Audit history', '/admin/audit-logs'],
  ],
  CITIZEN: [['Dashboard', '/citizen/dashboard'], ['My reports', '/citizen/complaints'],
    ['Notifications', '/citizen/notifications']],
}
const menuLabels: Record<Role, string> = { ADMIN: 'Administration', STAFF: 'Authority', CITIZEN: 'Citizen' }

type Session = {
  user: User | null
  setUser: (user: User | null) => void
  signedOutFrom: string | undefined
  endSession: (locationKey: string) => void
}

function SessionLayout() {
  const [user, setUser] = useState<User | null>()
  const [error, setError] = useState<string>()
  const [attempt, setAttempt] = useState(0)
  const [signedOutFrom, setSignedOutFrom] = useState<string>()
  useEffect(() => {
    let active = true
    restoreSession().then(
      (current) => { if (active) setUser(current) },
      (failure: unknown) => {
        if (!active) return
        if (!(failure instanceof ApiError) || failure.status !== 401) setError(message(failure))
        else setUser(null)
      },
    )
    return () => { active = false }
  }, [attempt])
  return user === undefined
    ? <Shell>{error ? <ErrorNotice error={error} retry={() => { setError(undefined); setAttempt((n) => n + 1) }} />
      : <p role="status">Checking your session…</p>}</Shell>
    : <Outlet context={{
      user, setUser, signedOutFrom,
      endSession: (locationKey) => { setSignedOutFrom(locationKey); setUser(null) },
    } satisfies Session} />
}

function Shell({ user, children, unread }: { user?: User; children: ReactNode; unread?: number }) {
  const [busy, setBusy] = useState(false)
  const [error, setError] = useState<string>()
  const session = useOutletContext<Session | null>()
  const { key } = useLocation()

  async function logout() {
    if (!session) return
    setBusy(true)
    setError(undefined)
    try {
      await signOut()
      session.endSession(key)
    } catch (failure) {
      setError(message(failure))
    } finally {
      setBusy(false)
    }
  }

  return <div className="workspace">
    <header className="workspace-header">
      <div className="workspace-width workspace-header-inner">
        <a className="skip-link" href="#workspace-main">Skip to content</a>
        <Brand />
        {user && <div className="workspace-session">
          <span>{user.full_name}</span>
          <button className="button button-secondary" disabled={busy} onClick={logout}>Sign out</button>
        </div>}
      </div>
    </header>
    {user && <div className="workspace-nav">
      <nav className="workspace-width" aria-label={menuLabels[user.role]}>
        {menus[user.role].map(([label, to]) => <NavLink key={to} to={to} end={!to.endsWith('/complaints')}>
          {label}{label === 'Notifications' && unread !== undefined &&
            <span className="workspace-unread" aria-label={`${unread} unread notifications`}>{unread}</span>}
        </NavLink>)}
      </nav>
    </div>}
    <main className="workspace-width workspace-main" id="workspace-main" tabIndex={-1}>
      {error && <ErrorNotice error={error} />}
      {children}
    </main>
  </div>
}

function Login() {
  const { user, setUser } = useOutletContext<Session>()
  const location = useLocation()
  const [error, setError] = useState<string>()
  const [busy, setBusy] = useState(false)
  if (user) {
    const from = (location.state as { from?: string } | null)?.from
    const prefix = user.role === 'STAFF' ? '/authority/' : user.role === 'ADMIN' ? '/admin/' : '/citizen/'
    return <Navigate to={from?.startsWith(prefix) ? from : startAt[user.role]} replace />
  }

  async function submit(event: FormEvent<HTMLFormElement>) {
    event.preventDefault()
    const values = new FormData(event.currentTarget)
    setBusy(true)
    setError(undefined)
    try {
      setUser(await signIn(String(values.get('email')).trim(), String(values.get('password'))))
    } catch (failure) {
      setError(failure instanceof ApiError && failure.status === 401 ? 'Check your email and password and try again.' : message(failure))
    } finally {
      setBusy(false)
    }
  }

  return <Shell>
    <div className="workspace-login">
      <Heading title="Sign in" />
      <form className="workspace-form workspace-panel" onSubmit={submit}>
        {error && <ErrorNotice error={error} />}
        <label>Email address<input name="email" type="email" autoComplete="username" maxLength={255} required /></label>
        <label>Password<input name="password" type="password" autoComplete="current-password" maxLength={128} required /></label>
        <button className="button button-primary" disabled={busy}>{busy ? 'Signing in…' : 'Sign in'}</button>
        <Link className="workspace-record-link" to="/register" state={location.state}>Create a citizen account</Link>
      </form>
    </div>
  </Shell>
}

function Register() {
  const session = useOutletContext<Session>()
  const location = useLocation()
  const [busy, setBusy] = useState(false)
  const [error, setError] = useState<string>()
  const [registered, setRegistered] = useState(false)
  if (session.user) return <Navigate to="/login" replace state={location.state} />

  async function submit(event: FormEvent<HTMLFormElement>) {
    event.preventDefault()
    const values = new FormData(event.currentTarget)
    setBusy(true)
    setError(undefined)
    try {
      const email = String(values.get('email')).trim()
      const password = String(values.get('password'))
      await registerAccount(String(values.get('full_name')).trim(), email, password)
      setRegistered(true)
      session.setUser(await signIn(email, password))
    } catch (failure) {
      setError(message(failure))
    } finally {
      setBusy(false)
    }
  }

  return <Shell><div className="workspace-login">
    <Heading title="Create a citizen account" />
    <form className="workspace-panel workspace-form" onSubmit={submit}>
      {error && <ErrorNotice error={registered ? 'Your account was created. Use the sign-in page to continue.' : error} />}
      <label>Full name<input name="full_name" autoComplete="name" maxLength={120} required /></label>
      <label>Email address<input name="email" type="email" autoComplete="username" maxLength={255} required /></label>
      <label>Password<span>Use at least 12 characters.</span>
        <input name="password" type="password" autoComplete="new-password" minLength={12} maxLength={128} required />
      </label>
      <button className="button button-primary" disabled={busy || registered}>{busy ? 'Creating account…' : 'Create account'}</button>
      <Link className="workspace-record-link" to="/login" state={location.state}>Sign in</Link>
    </form>
  </div></Shell>
}

function Guard({ role }: { role: Role }) {
  const { user, signedOutFrom } = useOutletContext<Session>()
  const { pathname, search, key } = useLocation()
  if (!user) return <Navigate to="/login" replace state={key === signedOutFrom ? null : { from: pathname + search }} />
  if (user.role !== role) return <Shell user={user}>
    <Heading title="Access denied"><p>Your account does not have access to this page.</p></Heading>
    <Link className="button button-secondary" to={startAt[user.role]}>Go to your account</Link>
  </Shell>
  return <Workspace key={user.id} user={user} />
}

function Workspace({ user }: { user: User }) {
  const { pathname } = useLocation()
  const [unread, setUnread] = useState<number>()
  const [revision, setRevision] = useState(0)
  const refreshUnread = useCallback(() => setRevision((number) => number + 1), [])
  useEffect(() => {
    if (user.role === 'ADMIN') return
    let active = true
    let reading = false
    async function refresh() {
      if (reading || document.visibilityState === 'hidden') return
      reading = true
      try {
        const result = await getUnread()
        if (active) setUnread(result.count)
      } catch {
        if (active) setUnread(undefined)
      } finally {
        reading = false
      }
    }
    void refresh()
    const timer = window.setInterval(() => void refresh(), 30000)
    window.addEventListener('focus', refresh)
    document.addEventListener('visibilitychange', refresh)
    return () => {
      active = false
      window.clearInterval(timer)
      window.removeEventListener('focus', refresh)
      document.removeEventListener('visibilitychange', refresh)
    }
  }, [user.role, pathname, revision])
  return <Shell user={user} unread={unread}>
    <Suspense fallback={<p role="status">Loading page…</p>}>
      <Outlet context={{ unread, refreshUnread } satisfies InboxContext} />
    </Suspense>
  </Shell>
}

export function App() {
  return <Routes>
    <Route path="/" element={<Suspense fallback={<Shell><p role="status">Loading CivicFix AI…</p></Shell>}><Homepage /></Suspense>} />
    <Route path="/map" element={<Shell><Suspense fallback={<p role="status">Loading public reports…</p>}><PublicMap /></Suspense></Shell>} />
    <Route element={<SessionLayout />}>
      <Route path="/login" element={<Login />} />
      <Route path="/register" element={<Register />} />
      <Route element={<Guard role="CITIZEN" />}>
        <Route path="/account" element={<Navigate to="/citizen/dashboard" replace />} />
        <Route path="/citizen">
          <Route index element={<Navigate to="dashboard" replace />} />
          <Route path="dashboard" element={<CitizenDashboard />} />
          <Route path="complaints" element={<CitizenReports />} />
          <Route path="complaints/new" element={<NewComplaint />} />
          <Route path="complaints/:id" element={<CitizenComplaint />} />
          <Route path="notifications" element={<Inbox role="CITIZEN" />} />
        </Route>
      </Route>
      <Route path="/authority" element={<Guard role="STAFF" />}>
        <Route index element={<Navigate to="complaints" replace />} />
        <Route path="dashboard" element={<StaffDashboard />} />
        <Route path="complaints" element={<Queue />} />
        <Route path="complaints/:id" element={<Complaint />} />
        <Route path="notifications" element={<Inbox role="STAFF" />} />
      </Route>
      <Route path="/admin" element={<Guard role="ADMIN" />}>
        <Route index element={<Navigate to="users" replace />} />
        <Route path="dashboard" element={<AdminDashboard />} />
        <Route path="users" element={<AdminUsers />} />
        <Route path="departments" element={<AdminSettings key="departments" kind="departments" />} />
        <Route path="categories" element={<AdminSettings key="categories" kind="categories" />} />
        <Route path="audit-logs" element={<AdminAudit />} />
      </Route>
    </Route>
    <Route path="*" element={<Shell><Heading title="Page not found" /><Link className="button button-secondary" to="/">Home</Link></Shell>} />
  </Routes>
}
