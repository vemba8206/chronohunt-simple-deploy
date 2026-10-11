export type RoundStatus = { submissions_enabled: boolean }

export type Entry = { rank: number; team_id: string; accepted_at: string }

export type Overview = { teams: number; accepted: number; csrf_token: string; submission_policy_ready: boolean; submissions_enabled: boolean }



export class ApiError extends Error {

  constructor(public status: number, public code: string, message: string) { super(message) }

}



const base = (import.meta.env.VITE_API_BASE_URL || '').replace(/\/$/, '')



export async function api<T>(path: string, options: { body?: unknown; csrf?: string; signal?: AbortSignal } = {}): Promise<T> {

  const controller = new AbortController()

  const abort = () => controller.abort()

  options.signal?.addEventListener('abort', abort, { once: true })

  if (options.signal?.aborted) controller.abort()

  const timeout = window.setTimeout(abort, 45000)

  try {

    const response = await fetch(base + '/api' + path, {

      method: options.body === undefined ? 'GET' : 'POST', credentials: 'include',

      headers: { ...(options.body === undefined ? {} : { 'Content-Type': 'application/json' }), ...(options.csrf ? { 'X-CSRF-Token': options.csrf } : {}) },

      body: options.body === undefined ? undefined : JSON.stringify(options.body), signal: controller.signal,

    })

    const data = await response.json().catch(() => null)

    if (!response.ok) throw new ApiError(response.status, data?.error?.code || 'request_failed', data?.error?.message || 'The request could not be completed. Please try again.')

    if (data === null) throw new Error('The competition server returned an unexpected response.')

    return data as T

  } catch (error) {

    if (error instanceof ApiError) throw error

    if (options.signal?.aborted) throw error

    throw new Error('Cannot reach the competition server. Check your connection and try again.')

  } finally { window.clearTimeout(timeout); options.signal?.removeEventListener('abort', abort) }

}



export const message = (error: unknown) => error instanceof Error ? error.message : 'Something went wrong. Please try again.'

export const normalizeTeam = (value: string) => value.trim().toUpperCase()

export const validTeam = (value: string) => {
  const team = normalizeTeam(value)
  return team.length > 0 && team.length <= 32 && [...team].every(c => c.charCodeAt(0) >= 32 && c.charCodeAt(0) !== 127)
}

