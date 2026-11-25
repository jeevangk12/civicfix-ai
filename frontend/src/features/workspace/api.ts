const baseUrl = (import.meta.env.VITE_API_BASE_URL || 'http://localhost:8000/api/v1').replace(/\/$/, '')
let accessToken: string | null = null
let refreshRequest: Promise<void> | undefined

export class ApiError extends Error {
  readonly status: number

  constructor(status: number, message: string) {
    super(message)
    this.status = status
  }
}

export type Role = 'CITIZEN' | 'STAFF' | 'ADMIN'
export type User = { id: string; full_name: string; email: string; role: Role; is_active: boolean }
export type Page<T> = { data: T[]; meta: { page: number; page_size: number; total: number } }
type Token = { access_token: string }
type Options = { method?: 'POST' | 'PATCH'; body?: object; idempotencyKey?: string }

async function request<T>(path: string, options: Options = {}, token: string | null = null, auth = false): Promise<T> {
  const headers = new Headers()
  const body = options.body instanceof FormData ? options.body : options.body ? JSON.stringify(options.body) : undefined
  if (typeof body === 'string') headers.set('Content-Type', 'application/json')
  if (options.idempotencyKey) headers.set('Idempotency-Key', options.idempotencyKey)
  if (token) headers.set('Authorization', `Bearer ${token}`)
  if (auth) headers.set('X-CivicFix-CSRF', '1')

  let response: Response
  try {
    response = await fetch(baseUrl + path, {
      method: options.method, body,
      headers, credentials: auth ? 'include' : 'omit',
    })
  } catch {
    throw new ApiError(0, 'The CivicFix API is unreachable. Check your connection and try again.')
  }
  if (!response.ok) {
    const result = await response.json().catch(() => null) as
      { error?: { message?: string; details?: { field: string }[] } } | null
    const fields = result?.error?.details?.map(({ field }) => field.split('.').at(-1)?.replaceAll('_', ' '))
    const message = result?.error?.message || `The request failed (HTTP ${response.status}).`
    throw new ApiError(response.status, fields?.length ? `${message} Check ${fields.join(', ')}.` : message)
  }
  return response.status === 204 ? undefined as T : response.json() as Promise<T>
}

function refresh() {
  refreshRequest ??= request<{ data: Token }>('/auth/refresh', { method: 'POST' }, null, true)
    .then(({ data }) => { accessToken = data.access_token })
    .catch((error: unknown) => { accessToken = null; throw error })
    .finally(() => { refreshRequest = undefined })
  return refreshRequest
}

async function authorized<T>(path: string, options?: Options) {
  const attemptedToken = accessToken
  try {
    return await request<T>(path, options, attemptedToken)
  } catch (error) {
    if (!(error instanceof ApiError) || error.status !== 401) throw error
    if (!accessToken || accessToken === attemptedToken) await refresh()
    return request<T>(path, options, accessToken)
  }
}

export async function data<T>(path: string, options?: Options) {
  return (await authorized<{ data: T }>(path, options)).data
}

export function page<T>(path: string) {
  return authorized<Page<T>>(path)
}

export function publicPage<T>(path: string) {
  return request<Page<T>>(path)
}

export async function registerAccount(full_name: string, email: string, password: string) {
  await request('/auth/register', { method: 'POST', body: { full_name, email, password } })
}

export async function restoreSession() {
  if (!accessToken) await refresh()
  return data<User>('/auth/me')
}

export async function signIn(email: string, password: string) {
  const result = await request<{ data: Token }>('/auth/login', { method: 'POST', body: { email, password } }, null, true)
  accessToken = result.data.access_token
  return data<User>('/auth/me')
}

export async function signOut() {
  try {
    await request('/auth/logout', { method: 'POST' }, accessToken, true)
  } catch (error) {
    if (!(error instanceof ApiError) || error.status !== 401) throw error
    try {
      await refresh()
      await request('/auth/logout', { method: 'POST' }, accessToken, true)
    } catch (refreshError) {
      if (!(refreshError instanceof ApiError) || refreshError.status !== 401) throw refreshError
    }
  }
  accessToken = null
}
