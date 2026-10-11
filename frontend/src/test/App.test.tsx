import { render, screen, waitFor } from '@testing-library/react'
import userEvent from '@testing-library/user-event'
import { MemoryRouter } from 'react-router-dom'
import { beforeEach, describe, expect, it, vi } from 'vitest'
import App, { CHALLENGE_URL } from '../App'

let signedIn = false
let accepted = false
let enabled = true
let offline = false
let resetCalls = 0
let cleared = false
let submitted: Record<string, unknown> | null = null
const fetchMock = vi.fn(async (url: string, options?: RequestInit) => {
  if (offline) throw new Error('offline')
  const path = url.replace('/api', '')
  let status = 200, data: unknown = {}
  if (path === '/competition/status') data = { submissions_enabled: enabled }
  if (path === '/admin/leaderboard') data = cleared ? [] : [{ rank: 1, team_id: 'FIRST', accepted_at: '2026-10-11T10:00:00Z' }, { rank: 2, team_id: 'SECOND', accepted_at: '2026-10-11T10:01:00Z' }]
  if (path === '/admin/overview') {
    if (!signedIn) { status = 401; data = { error: { code: 'unauthorized', message: 'Login required.' } } }
    else data = { teams: 2, accepted: 2, csrf_token: 'fixture-csrf', submission_policy_ready: true }
  }
  if (path === '/admin/reset') {resetCalls++; cleared = true; data = {reset:true,deleted:2}}
  if (path === '/admin/login') signedIn = true
  if (path === '/admin/logout') signedIn = false
  if (path === '/submissions') {
    submitted = JSON.parse(options?.body as string)
    if (accepted) { status = 409; data = { error: { code: 'duplicate_submission', message: 'Already recorded.' } } }
    else { accepted = true; data = { accepted: true, team_id: submitted?.team_id } }
  }
  return { ok: status < 400, status, json: async () => data } as Response
})
const mount = (path = '/') => render(<MemoryRouter initialEntries={[path]}><App /></MemoryRouter>)
beforeEach(() => {
  signedIn = accepted = offline = cleared = false; enabled = true; submitted = null; resetCalls = 0
  HTMLDialogElement.prototype.showModal = function(){this.setAttribute('open','')}
  HTMLDialogElement.prototype.close = function(){this.removeAttribute('open')}
  fetchMock.mockClear(); vi.stubGlobal('fetch', fetchMock)
})

describe('simplified participant and leaderboard', () => {
  it('preserves real logo and challenge URL without registration instructions', async () => {
    mount(); await screen.findByRole('button', { name: 'Submit' })
    expect(screen.getByRole('link', { name: /Open Tinkercad challenge/ })).toHaveAttribute('href', CHALLENGE_URL)
    expect(screen.getAllByAltText('ChronoHunt logo')[0]).toHaveAttribute('src', '/chronohunt-logo.png')
    expect(screen.queryByText(/Register through the Google Form/)).not.toBeInTheDocument()
  })
  it('submits any valid ID and nonempty PIN to the backend', async () => {
    mount(); const user = userEvent.setup()
    await user.type(screen.getByLabelText(/TEAM ID/), ' new-team ')
    await user.type(screen.getByLabelText(/PIN/), 'arbitrary-pin')
    await waitFor(() => expect(screen.getByRole('button', { name: 'Submit' })).toBeEnabled())
    await user.click(screen.getByRole('button', { name: 'Submit' }))
    await screen.findByText('Submission recorded.')
    expect(submitted).toEqual({ team_id: 'NEW-TEAM', code: 'arbitrary-pin' })
    expect(screen.queryByText('arbitrary-pin')).not.toBeInTheDocument()
  })
  it('shows duplicate error without success', async () => {
    accepted = true; mount(); const user = userEvent.setup()
    await user.type(screen.getByLabelText(/TEAM ID/), 'FIRST'); await user.type(screen.getByLabelText(/PIN/), 'x')
    await waitFor(() => expect(screen.getByRole('button', { name: 'Submit' })).toBeEnabled())
    await user.click(screen.getByRole('button', { name: 'Submit' }))
    await screen.findByText('Already recorded.')
    expect(screen.queryByText('Submission recorded.')).not.toBeInTheDocument()
  })
  it('rejects whitespace PIN locally', async () => {
    mount(); const user = userEvent.setup()
    await user.type(screen.getByLabelText(/TEAM ID/), 'FIRST'); await user.type(screen.getByLabelText(/PIN/), '   ')
    await waitFor(() => expect(screen.getByRole('button', { name: 'Submit' })).toBeEnabled())
    await user.click(screen.getByRole('button', { name: 'Submit' }))
    await screen.findByText('Enter the PIN revealed by your Tinkercad circuit.')
    expect(submitted).toBeNull()
  })
  it('reports unavailable database without claiming acceptance', async () => {
    enabled = false; mount()
    await screen.findByText('The submission database is unavailable. Please retry or contact the organizer.')
    expect(screen.getByRole('button', { name: 'Submit' })).toBeDisabled()
  })
  it('reports offline state', async () => {
    offline = true; mount()
    await screen.findByText('The submission server is unavailable. Waiting to reconnect.')
  })
  it('participant has no standings links or requests', async () => {
    mount(); await screen.findByRole('button',{name:'Submit'})
    expect(screen.queryByRole('link',{name:/leaderboard/i})).not.toBeInTheDocument()
    expect(fetchMock.mock.calls.some(([url]) => url.includes('leaderboard'))).toBe(false)
  })
  it('guessed leaderboard URL requires organizer login', async () => {
    mount('/leaderboard');await screen.findByText('Organizer sign in')
    expect(screen.queryByRole('table')).not.toBeInTheDocument()
    expect(fetchMock.mock.calls.some(([url]) => url.includes('leaderboard'))).toBe(false)
  })
  it('keeps organizer page authenticated', async () => {
    mount('/admin'); await screen.findByText('Organizer sign in')
    expect(screen.queryByText('ORGANIZER CONTROLS')).not.toBeInTheDocument()
  })
  it('retains organizer refresh and sign out without deadline controls', async () => {
    signedIn = true; mount('/admin')
    await screen.findByText('ORGANIZER CONTROLS')
    expect(screen.getByRole('button', { name: 'Refresh submissions' })).toBeInTheDocument()
    expect(screen.queryByLabelText(/DEADLINE/)).not.toBeInTheDocument()
    expect(screen.queryByText(/END TINKERCAD ROUND|FREEZE|QUALIFIERS/)).not.toBeInTheDocument()
  })
  it('displays the actual timestamp in browser local time', async () => {
    signedIn = true; mount('/admin')
    await screen.findByText('FIRST')
    const time = document.querySelector('time')!
    expect(time.getAttribute('datetime')).toBe('2026-10-11T10:00:00Z')
    expect(time.textContent).toBe(new Date('2026-10-11T10:00:00Z').toLocaleString(undefined, {dateStyle:'medium',timeStyle:'medium'}))
  })
  it('confirmation is simple and contains no participant continuation controls', async () => {
    mount(); const user = userEvent.setup()
    await user.type(screen.getByLabelText(/TEAM ID/), 'new team')
    await user.type(screen.getByLabelText(/PIN/), 'arbitrary')
    await waitFor(() => expect(screen.getByRole('button', { name: 'Submit' })).toBeEnabled())
    await user.click(screen.getByRole('button', { name: 'Submit' }))
    await screen.findByText('Submission recorded successfully. Thank you for participating in ChronoHunt Round 2.')
    expect(screen.queryByRole('link',{name:/leaderboard/i})).not.toBeInTheDocument()
    expect(screen.queryByRole('button',{name:/another team/i})).not.toBeInTheDocument()
    expect(submitted).toEqual({team_id:'NEW TEAM',code:'arbitrary'})
  })
  it('cancel does not reset; explicit confirmation clears and refreshes standings', async () => {
    signedIn = true;mount('/admin');const user = userEvent.setup()
    await screen.findByText('FIRST');await screen.findByText('ORGANIZER CONTROLS')
    await user.click(screen.getByRole('button',{name:'Reset All Submissions'}))
    expect(await screen.findByText(/permanently deleted/)).toBeInTheDocument()
    expect(resetCalls).toBe(0)
    await user.click(screen.getByRole('button',{name:'Cancel'}))
    expect(resetCalls).toBe(0)
    await user.click(screen.getByRole('button',{name:'Reset All Submissions'}))
    await user.click(screen.getByRole('button',{name:'Confirm permanent reset'}))
    await screen.findByText('Reset complete. 2 submissions deleted.')
    expect(resetCalls).toBe(1)
    expect(screen.queryByText('FIRST')).not.toBeInTheDocument()
    const request=fetchMock.mock.calls.find(([url])=>url==='/api/admin/reset')
    expect(request?.[1]?.headers).toMatchObject({'X-CSRF-Token':'fixture-csrf'})
    expect(JSON.parse(request?.[1]?.body as string)).toEqual({confirmation:'DELETE ALL SIMPLIFIED SUBMISSIONS'})
  })
  it('logout removes management controls', async () => {
    signedIn = true; mount('/admin'); const user = userEvent.setup()
    await screen.findByText('ORGANIZER CONTROLS')
    await user.click(screen.getByRole('button', { name: 'Sign out' }))
    await screen.findByText('Organizer sign in')
    expect(screen.queryByText('ORGANIZER CONTROLS')).not.toBeInTheDocument()
  })
})
