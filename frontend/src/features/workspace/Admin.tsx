import { useCallback, useState, type FormEvent } from 'react'
import { useSearchParams } from 'react-router'
import { data, page, type Role, type User } from './api'
import { Badge, ErrorNotice, Heading, Pagination, Section, Timestamp, field, message, readable, useResource } from './ui'

type Named = { id: string; name: string; is_active: boolean }
type Setting = Named & { code: string; description: string | null; organization_id?: string }
type Mapping = { organization_id: string; department_id: string }
type Audit = {
  id: string; actor_id: string | null; actor_name: string | null; action: string; entity_type: string; entity_id: string | null;
  organization_id: string | null; event_metadata: Record<string, unknown> | null; created_at: string
}
const api = '/admin'
const organizations = () => data<Named[]>(api + '/organizations')

function useSave() {
  const [busy, setBusy] = useState(false)
  const [error, setError] = useState<string>()
  const [notice, setNotice] = useState<string>()
  async function save(action: () => Promise<void>, success: string) {
    setBusy(true)
    setError(undefined)
    setNotice(undefined)
    try {
      await action()
      setNotice(success)
    } catch (failure) {
      setError(message(failure))
    } finally {
      setBusy(false)
    }
  }
  return { busy, save, error, notice }
}

function SaveNotice({ error, notice }: { error?: string; notice?: string }) {
  return <>{error && <ErrorNotice error={error} />}{notice && <p className="workspace-success" role="status">{notice}</p>}</>
}

function OrganizationSelect({ items, value, change }: { items: Named[]; value: string; change: (value: string) => void }) {
  return <label>Organization<select name="organization_id" required value={value} onChange={(event) => change(event.target.value)}>
    <option value="">Select an organization</option>
    {items.map(({ id, name, is_active }) => <option value={id} key={id} disabled={!is_active}>{name}{is_active ? '' : ' (inactive)'}</option>)}
  </select></label>
}

function ProvisionStaff({ items, onCreated }: { items: Named[]; onCreated: () => void }) {
  const [organization, setOrganization] = useState('')
  const load = useCallback(async () => {
    if (!organization) return { departments: [], areas: [] }
    const query = '?organization_id=' + encodeURIComponent(organization)
    const [departments, areas] = await Promise.all([
      data<Named[]>(api + '/departments' + query), data<Named[]>(api + '/service-areas' + query),
    ])
    return { departments: departments.filter(({ is_active }) => is_active), areas: areas.filter(({ is_active }) => is_active) }
  }, [organization])
  const options = useResource(load)
  const mutation = useSave()

  function submit(event: FormEvent<HTMLFormElement>) {
    event.preventDefault()
    const form = event.currentTarget
    const values = new FormData(form)
    void mutation.save(async () => {
      await data(api + '/staff', { method: 'POST', body: {
        organization_id: organization, full_name: field(values, 'name'), email: field(values, 'email'),
        password: String(values.get('password')), staff_title: field(values, 'title') || null,
        department_ids: values.getAll('department_ids'), service_area_ids: values.getAll('service_area_ids'),
      } })
      form.reset()
      setOrganization('')
      onCreated()
    }, 'Staff account created.')
  }

  return <Section title="Provision staff">
    <form className="workspace-form" onSubmit={submit}>
      <SaveNotice {...mutation} />
      <label>Full name<input name="name" required maxLength={120} /></label>
      <label>Email address<input name="email" type="email" required maxLength={255} /></label>
      <label>Initial password<span>Use at least 12 characters.</span>
        <input name="password" type="password" autoComplete="new-password" required minLength={12} maxLength={128} />
      </label>
      <label>Staff title <span>(optional)</span><input name="title" maxLength={120} /></label>
      <OrganizationSelect items={items} value={organization} change={setOrganization} />
      {options.error && <ErrorNotice error={options.error} />}
      {organization && options.loading && <p role="status">Loading staff scope…</p>}
      {organization && options.value && <div className="workspace-checklists" key={organization}>
        <ScopeOptions title="Departments" name="department_ids" items={options.value.departments} />
        <ScopeOptions title="Service areas" name="service_area_ids" items={options.value.areas} />
      </div>}
      <button className="button button-primary" disabled={mutation.busy || !options.value?.departments.length
        || !options.value?.areas.length}>Create staff account</button>
    </form>
  </Section>
}

function ScopeOptions({ title, name, items }: { title: string; name: string; items: Named[] }) {
  return <fieldset className="workspace-checklist">
    <legend>{title} <span>(select at least one)</span></legend>
    {items.length ? items.map(({ id, name: label }) => <label key={id}>
      <input type="checkbox" name={name} value={id} />{label}
    </label>) : <p>No active options.</p>}
  </fieldset>
}

export function AdminUsers() {
  const [role, setRole] = useState<Role | ''>('STAFF')
  const [number, setPage] = useState(1)
  const load = useCallback(() => page<User>(`${api}/users?page=${number}${role ? `&role=${role}` : ''}`), [number, role])
  const users = useResource(load)
  const orgs = useResource(organizations)
  return <>
    <Heading title="Users"><p>Review accounts and provision scoped access for authority staff.</p></Heading>
    <div className="workspace-columns">
      <Section title="Account directory">
        <div className="workspace-filters">
          <label>Role<select value={role} onChange={(event) => { setRole(event.target.value as Role | ''); setPage(1) }}>
            <option value="">All roles</option><option value="STAFF">Staff</option>
            <option value="ADMIN">Admin</option><option value="CITIZEN">Citizen</option>
          </select></label>
        </div>
        {users.error && <ErrorNotice error={users.error} retry={users.retry} />}
        {users.loading && <p role="status">Loading users…</p>}
        {users.value && <>
          {users.value.data.length ? <div className="workspace-table-wrap"><table className="workspace-table">
            <thead><tr><th scope="col">Account</th><th scope="col">Role</th><th scope="col">Status</th></tr></thead>
            <tbody>{users.value.data.map((user) => <tr key={user.id}>
              <td><strong>{user.full_name}</strong><small>{user.email}</small></td>
              <td>{readable(user.role)}</td><td><Badge value={user.is_active ? 'ACTIVE' : 'INACTIVE'} /></td>
            </tr>)}</tbody>
          </table></div> : <p>No users match this filter.</p>}
          <Pagination meta={users.value.meta} change={setPage} />
        </>}
      </Section>
      {orgs.loading && <p role="status">Loading organizations…</p>}
      {orgs.error && <ErrorNotice error={orgs.error} retry={orgs.retry} />}
      {orgs.value && <ProvisionStaff items={orgs.value} onCreated={() => { setRole('STAFF'); setPage(1); users.retry() }} />}
    </div>
  </>
}

type Kind = 'categories' | 'departments'

function EditSetting({ item, kind, orgs, changed, cancel }: {
  item?: Setting; kind: Kind; orgs: Named[]; changed: () => void; cancel: () => void
}) {
  const department = kind === 'departments'
  const noun = department ? 'department' : 'category'
  const [organization, setOrganization] = useState(item?.organization_id ?? '')
  const mutation = useSave()
  function submit(event: FormEvent<HTMLFormElement>) {
    event.preventDefault()
    const form = event.currentTarget
    const values = new FormData(form)
    void mutation.save(async () => {
      await data(`${api}/${kind}${item ? '/' + item.id : ''}`, { method: item ? 'PATCH' : 'POST', body: {
        ...(!item && department && { organization_id: organization }), code: field(values, 'code'),
        name: field(values, 'name'), description: field(values, 'description') || null, is_active: values.has('is_active'),
      } })
      if (!item) { form.reset(); setOrganization('') }
      changed()
    }, item ? `The ${noun} was updated.` : `The ${noun} was created.`)
  }

  return <Section title={item ? `Edit ${noun}` : `Create ${noun}`}>
    <form className="workspace-form" onSubmit={submit}>
      <SaveNotice {...mutation} />
      {department && (item ? <p className="workspace-muted">{orgs.find(({ id }) => id === organization)?.name}</p>
        : <OrganizationSelect value={organization} change={setOrganization} items={orgs} />)}
      <label>Name<input name="name" defaultValue={item?.name} maxLength={120} required /></label>
      <label>Code<input name="code" defaultValue={item?.code} maxLength={60} pattern="[A-Za-z0-9_\-]+" required /></label>
      <label>Description <span>(optional)</span>
        <textarea name="description" defaultValue={item?.description ?? ''} maxLength={5000} rows={3} />
      </label>
      <label className="workspace-check"><input type="checkbox" name="is_active" defaultChecked={item?.is_active ?? true} />Active</label>
      <div className="workspace-actions">
        <button className="button button-primary" disabled={mutation.busy}>{item ? 'Save changes' : `Create ${noun}`}</button>
        {item && <button className="button button-secondary" type="button" onClick={cancel}>Cancel edit</button>}
      </div>
    </form>
  </Section>
}

function CategoryMapping({ category, orgs }: { category: Setting; orgs: Named[] }) {
  const [organization, setOrganization] = useState('')
  const mutation = useSave()
  const path = `${api}/categories/${category.id}/mappings`
  const load = useCallback(async () => {
    if (!organization) return { current: undefined, departments: [] }
    const [mappings, departments] = await Promise.all([
      data<Mapping[]>(path), data<Setting[]>(api + '/departments?organization_id=' + encodeURIComponent(organization)),
    ])
    return { current: mappings.find(({ organization_id }) => organization_id === organization)?.department_id, departments }
  }, [organization, path])
  const options = useResource(load)

  function submit(event: FormEvent<HTMLFormElement>) {
    event.preventDefault()
    const department = field(new FormData(event.currentTarget), 'department_id')
    void mutation.save(async () => {
      await data(path + '/' + organization, { method: 'PATCH', body: { department_id: department || null } })
      options.retry()
    }, 'Department mapping updated.')
  }

  return <Section title="Default department">
    <form className="workspace-form" onSubmit={submit}>
      <p className="workspace-muted">Set the fallback department for this category in an organization.</p>
      <SaveNotice {...mutation} />
      <OrganizationSelect value={organization} change={setOrganization} items={orgs} />
      {options.error && <ErrorNotice error={options.error} />}
      {organization && options.loading && <p role="status">Loading mapping…</p>}
      {organization && options.value && <>
        <label>Department<select key={organization} name="department_id" defaultValue={options.value.current ?? ''}>
          <option value="">No default department</option>
          {options.value.departments.map(({ id, name, is_active }) => <option key={id} value={id} disabled={!is_active}>
            {name}{is_active ? '' : ' (inactive)'}
          </option>)}
        </select></label>
        <button className="button button-primary" disabled={mutation.busy}>Save mapping</button>
      </>}
    </form>
  </Section>
}

export function AdminSettings({ kind }: { kind: Kind }) {
  const [editing, setEditing] = useState<Setting>()
  const load = useCallback(() => data<Setting[]>(api + '/' + kind), [kind])
  const settings = useResource(load)
  const orgs = useResource(organizations)
  return <>
    <Heading title={readable(kind)} />
    <div className="workspace-columns">
      <div>
        {settings.loading && <p role="status">Loading {kind}…</p>}
        {settings.error && <ErrorNotice error={settings.error} retry={settings.retry} />}
        {settings.value && (settings.value.length ? <div className="workspace-table-wrap"><table className="workspace-table">
          <thead><tr><th scope="col">Name</th>{kind === 'departments' && <th scope="col">Organization</th>}
            <th scope="col">Status</th><th scope="col"><span className="workspace-sr-only">Actions</span></th></tr></thead>
          <tbody>{settings.value.map((item) => <tr key={item.id}>
            <td><strong>{item.name}</strong><small>{item.code}</small></td>
            {kind === 'departments' && <td>{orgs.value?.find(({ id }) => id === item.organization_id)?.name ?? '—'}</td>}
            <td><Badge value={item.is_active ? 'ACTIVE' : 'INACTIVE'} /></td>
            <td><button className="button button-secondary" aria-label={`Edit ${item.name}`}
              onClick={() => setEditing(item)}>Edit</button></td>
          </tr>)}</tbody>
        </table></div> : <p className="workspace-panel">No {kind} have been configured.</p>)}
      </div>
      <div className="workspace-stack">
        {orgs.error && <ErrorNotice error={orgs.error} retry={orgs.retry} />}
        {orgs.loading && <p role="status">Loading organizations…</p>}
        {orgs.value && <EditSetting key={editing?.id ?? 'create'} kind={kind} item={editing} orgs={orgs.value}
          changed={settings.retry} cancel={() => setEditing(undefined)} />}
        {editing && orgs.value && kind === 'categories' && <CategoryMapping key={editing.id} category={editing} orgs={orgs.value} />}
      </div>
    </div>
  </>
}

export function AdminAudit() {
  const [query, setQuery] = useSearchParams()
  const filter = query.toString()
  const load = useCallback(() => page<Audit>(`${api}/audit-logs?${filter}`), [filter])
  const logs = useResource(load)

  function search(event: FormEvent<HTMLFormElement>) {
    event.preventDefault()
    const form = new FormData(event.currentTarget)
    const next = new URLSearchParams()
    for (const key of ['entity_id', 'action']) {
      const value = field(form, key)
      if (value) next.set(key, value)
    }
    setQuery(next)
  }

  return <>
    <Heading title="Audit history"><p>Review recorded actions, actors, and timestamps.</p></Heading>
    <form className="workspace-filters" onSubmit={search} key={`${query.get('entity_id') ?? ''}:${query.get('action') ?? ''}`}>
      <label>Entity ID<input name="entity_id" defaultValue={query.get('entity_id') ?? ''}
        pattern="[0-9A-Fa-f]{8}(?:-[0-9A-Fa-f]{4}){3}-[0-9A-Fa-f]{12}" /></label>
      <label>Action code<input name="action" defaultValue={query.get('action') ?? ''} maxLength={100} placeholder="COMPLAINT_ASSIGNED" /></label>
      <button className="button button-primary">Filter audit history</button>
    </form>
    {logs.error && <ErrorNotice error={logs.error} retry={logs.retry} />}
    {logs.loading && <p role="status">Loading audit history…</p>}
    {logs.value && <>
      <p className="workspace-count">{logs.value.meta.total} {logs.value.meta.total === 1 ? 'event' : 'events'}</p>
      {logs.value.data.length ? <div className="workspace-table-wrap"><table className="workspace-table">
        <thead><tr><th scope="col">Action</th><th scope="col">Actor</th><th scope="col">Timestamp</th><th scope="col">Entity</th></tr></thead>
        <tbody>{logs.value.data.map((row) => <tr data-action={row.action} key={row.id}>
          <td><strong>{readable(row.action)}</strong>{row.event_metadata && <details>
            <summary>Event details</summary>
            <dl className="workspace-audit-details">{Object.entries(row.event_metadata).filter(([, value]) => value !== null)
              .map(([key, value]) => <div key={key}><dt>{readable(key)}</dt><dd>
                {typeof value === 'string' ? value : JSON.stringify(value)}
              </dd></div>)}</dl>
          </details>}</td>
          <td>{row.actor_name ?? 'System'}{row.actor_id && <small>{row.actor_id}</small>}</td>
          <td><Timestamp value={row.created_at} /></td>
          <td>{readable(row.entity_type)}{row.entity_id && <small>{row.entity_id}</small>}</td>
        </tr>)}</tbody>
      </table></div> : <p className="workspace-panel">No audit events match these filters.</p>}
      <Pagination meta={logs.value.meta} change={(nextPage) => {
        const next = new URLSearchParams(query)
        next.set('page', String(nextPage))
        setQuery(next)
      }} />
    </>}
  </>
}
