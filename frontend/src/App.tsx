import { useCallback, useEffect, useRef, useState, type FormEvent } from 'react'

import { Link, Route, Routes, useLocation } from 'react-router-dom'

import { ArrowRight, BadgeCheck, Check, CircleHelp, KeyRound, Layers3, LoaderCircle, LockKeyhole, LogOut, RefreshCw, ShieldCheck, Trophy, X } from 'lucide-react'

import { api, ApiError, message, normalizeTeam, validTeam, type Entry, type Overview, type RoundStatus } from './api'

export const CHALLENGE_URL = 'https://www.tinkercad.com/things/e0rRfKME55S-chronohunt-round-2?sharecode=VeiDzHbY9Qn6XCGbZ-gGXkVBzr3exrW9k3CJ_ojiKvo'

function Logo({ large = false }: { large?: boolean }) {

  const [failed, setFailed] = useState(false)

  const logo = import.meta.env.VITE_LOGO_URL || '/chronohunt-logo.png'

  return !failed ? <img className={large ? 'brand-image large' : 'brand-image'} src={logo} alt="ChronoHunt logo" decoding="async" onError={() => setFailed(true)} /> : <span className={large ? 'logo-slot large' : 'logo-slot'} aria-label="Replaceable logo placeholder"><Layers3 size={large ? 28 : 19} aria-hidden="true" />{large && <span>LOGO PLACEHOLDER</span>}</span>

}

function Notice({ text, success = false }: { text: string; success?: boolean }) {

  return <div className={`notice ${success ? 'success' : ''}`} role={success ? 'status' : 'alert'}>{success ? <Check size={17} /> : <CircleHelp size={17} />}<span>{text}</span></div>

}

function StatusPill({ round }: { round: RoundStatus | null }) {

  return <span className={`status-pill ${round?.submissions_enabled ? 'active' : ''}`}><i />{round?.submissions_enabled ? 'SUBMISSIONS OPEN' : 'SERVER UNAVAILABLE'}</span>

}

function Participant({ round, reload }: { round: RoundStatus | null; reload: () => Promise<void> }) {

  const [team, setTeam] = useState(''), [code, setCode] = useState('')

  const [busy, setBusy] = useState(false), [error, setError] = useState(''), [accepted, setAccepted] = useState('')


  async function submit(event: FormEvent) {

    event.preventDefault(); setError('')

    if (!validTeam(team)) { setError('Enter a nonempty Team ID of at most 32 characters.'); return }

    if (!code.trim() || code.trim().length > 256) { setError('Enter the PIN revealed by your Tinkercad circuit.'); return }

    setBusy(true)

    try {

      const data = await api<{ team_id: string; accepted: boolean }>('/submissions', { body: { team_id: normalizeTeam(team), code: code.trim() } })

      if (data.accepted !== true || data.team_id !== normalizeTeam(team)) throw new Error('The server did not confirm recording. Please contact the organizer before retrying.')

      setAccepted(data.team_id); setCode('')

    } catch (e) { setError(message(e)) }

    finally { setBusy(false); void reload() }

  }

  return <main className="participant-main"><div className="eyebrow stage-marker"><span>01 / BUILD</span><i /><span>02 / PIN</span><i /><span className="selected">03 / SUBMIT</span></div>

    <section className="glass submission-card" aria-labelledby="submission-heading">

      {accepted ? <div className="accepted"><div className="accepted-icon"><BadgeCheck size={40} /></div><p className="eyebrow">SUBMISSION RECORDED</p><h1 id="submission-heading">Submission recorded.</h1><p>Submission recorded successfully. Thank you for participating in ChronoHunt Round 2.</p></div> : <>

        <div className="logo-well"><Logo large /></div><div className="card-heading"><div className="eyebrow cyan">CHRONOHUNT · ROUND 2</div><h1 id="submission-heading">Tinkercad challenge<span className="cyan">.</span></h1><p>Complete the Tinkercad circuit,<br className="desktop-break" /> then enter your Team ID and PIN.</p><a className="secondary challenge-link" href={CHALLENGE_URL} target="_blank" rel="noopener noreferrer">Open Tinkercad challenge <ArrowRight size={16} /></a></div>


        {round && !round.submissions_enabled && <Notice text="The submission database is unavailable. Please retry or contact the organizer." />}

        {!round && <Notice text="The submission server is unavailable. Waiting to reconnect." />}

        {error && <Notice text={error} />}

        <form onSubmit={submit} className="submission-form">

          <label htmlFor="team">TEAM ID <span>YOUR TEAM IDENTIFIER</span></label><div className="input-wrap"><input id="team" name="team_id" placeholder="e.g. CH01" value={team} onChange={e => setTeam(e.target.value)} onBlur={() => setTeam(normalizeTeam(team))} maxLength={32} required autoComplete="off" autoCapitalize="characters" spellCheck={false} disabled={busy} /><BadgeCheck size={19} aria-hidden="true" /></div>

          <label htmlFor="code">PIN <span>CIRCUIT PIN</span></label><div className="input-wrap"><input id="code" name="code" placeholder="Enter your circuit PIN" value={code} onChange={e => setCode(e.target.value)} required maxLength={256} autoComplete="off" spellCheck={false} disabled={busy} /><KeyRound size={19} aria-hidden="true" /></div>

          <button className="primary" type="submit" disabled={busy || !round?.submissions_enabled}>{busy ? <><LoaderCircle className="spin" size={18} /> Recording submission</> : <>Submit<ArrowRight size={18} /></>}</button>

        </form><div className="card-bottom"><span><ShieldCheck size={14} /> ONE SUBMISSION PER TEAM</span><span>ROUND 02</span></div>

      </>}

    </section><p className="below-card"><LockKeyhole size={13} /> Once accepted, your submission cannot be changed.</p>

  </main>

}

function Admin({ refresh, onSignedOut }: { refresh: () => Promise<void>; onSignedOut: () => void }) {
  const [overview, setOverview] = useState<Overview | null>(null)
  const [busy, setBusy] = useState(false), [error, setError] = useState(''), [note, setNote] = useState('')
  const [confirm, setConfirm] = useState(false)
  const dialog = useRef<HTMLDialogElement>(null)
  useEffect(() => { if (confirm) dialog.current?.showModal(); else dialog.current?.close() }, [confirm])
  const load = useCallback(async () => {
    try { setOverview(await api<Overview>('/admin/overview')); setError('') }
    catch (e) { setError(message(e)); if (e instanceof ApiError && e.status === 401) { setOverview(null); onSignedOut() } }
  }, [onSignedOut])
  useEffect(() => { void load() }, [load])
  async function logout() {
    if (!overview) return
    setBusy(true)
    try { await api('/admin/logout', { body: {}, csrf: overview.csrf_token }); setOverview(null); onSignedOut() }
    catch (e) { setError(message(e)) } finally { setBusy(false) }
  }
  async function reset() {
    if (!overview || busy) return
    setBusy(true); setError(''); setNote('')
    try {
      const result = await api<{reset: boolean; deleted: number}>('/admin/reset', {body:{confirmation:'DELETE ALL SIMPLIFIED SUBMISSIONS'},csrf:overview.csrf_token})
      if (result.reset !== true || !Number.isInteger(result.deleted) || result.deleted < 0) throw new Error('The server did not confirm the reset. Refresh before retrying.')
      setConfirm(false); await Promise.all([load(), refresh()]); setNote(`Reset complete. ${result.deleted} submissions deleted.`)
    } catch (e) { setError(message(e)); if (e instanceof ApiError && e.status === 401) { setOverview(null); onSignedOut() } }
    finally { setBusy(false) }
  }
  if (!overview) return error ? <Notice text={error} /> : null
  return <aside className="glass admin-panel" aria-label="Administrator controls"><div className="admin-title"><span><ShieldCheck size={16} /> ORGANIZER CONTROLS</span><button className="text-button" disabled={busy} onClick={logout}><LogOut size={14} /> Sign out</button></div><p>{overview.accepted} recorded submissions</p><button className="text-button" onClick={() => void Promise.all([load(), refresh()])}><RefreshCw size={14} /> Refresh submissions</button>{!overview.submission_policy_ready && <Notice text="The organizer database upgrade (007) is required." />}<div className="admin-actions"><button className="danger" disabled={busy || !overview.submission_policy_ready} onClick={() => {setError('');setConfirm(true)}}>Reset All Submissions</button></div>{note && <Notice text={note} success />}{error && !confirm && <Notice text={error} />}
    <dialog ref={dialog} className="glass confirm-dialog" onCancel={e => {if(busy)e.preventDefault();else setConfirm(false)}} onClose={() => setConfirm(false)}><button className="dialog-close text-button" aria-label="Close reset confirmation" disabled={busy} onClick={() => setConfirm(false)}><X size={20} /></button><LockKeyhole className="cyan" size={28} /><h2>Reset all submissions?</h2><p>All submissions and leaderboard entries in this simplified ChronoHunt application will be permanently deleted. Teams can submit again. This cannot be undone.</p><p>The original competition and Google records are untouched.</p>{error && <Notice text={error} />}<div className="admin-actions"><button className="secondary" disabled={busy} onClick={() => setConfirm(false)}>Cancel</button><button className="danger" disabled={busy} onClick={() => void reset()}>{busy ? 'Resetting…' : 'Confirm permanent reset'}</button></div></dialog></aside>
}

const noSignedOut = () => {}

function Leaderboard({ reload, onSignedOut = noSignedOut, managed = false }: { reload: () => Promise<void>; onSignedOut?: () => void; managed?: boolean }) {

  const [round, setRound] = useState<RoundStatus | null>(null)

  const [rows, setRows] = useState<Entry[]>([]), [loading, setLoading] = useState(true), [error, setError] = useState('')

  const [refreshed, setRefreshed] = useState('')

  const fetching = useRef(false)

  const refresh = useCallback(async () => {

    if (fetching.current) return

    fetching.current = true

    try { const data = await api<Entry[]>('/admin/leaderboard'); const status = await api<RoundStatus>('/competition/status'); setRound(status); setRows(data); setError(''); setRefreshed(new Date().toLocaleTimeString([], { hour: '2-digit', minute: '2-digit', second: '2-digit' })) }

    catch (e) { setRows([]); setError(message(e)); if (managed && e instanceof ApiError && e.status === 401) onSignedOut() } finally { setLoading(false); fetching.current = false; await reload() }

  }, [reload, onSignedOut, managed])

  useEffect(() => { void refresh(); const timer = window.setInterval(() => { if (!document.hidden) void refresh() }, 10000); return () => window.clearInterval(timer) }, [refresh])

  return <main className="leaderboard-main"><div className="board-heading"><div><div className="eyebrow cyan">CHRONOHUNT · ROUND 2</div><h1>The leaderboard<span className="cyan">.</span></h1><p>Ordered by website acceptance time, earliest first. Times are shown in your local timezone.</p></div><StatusPill round={round} /></div>

    <section className="glass board" aria-label="Competition leaderboard"><div className="board-topline"><span><Trophy size={17} /> SUBMITTED TEAMS</span><button className="text-button" onClick={() => void refresh()} aria-label="Refresh leaderboard"><RefreshCw size={14} /> Refresh</button></div>{error && <Notice text={`${message(new Error(error))}${rows.length ? ' The displayed standings may be outdated.' : ''}`} />}

      {loading ? <div className="empty" role="status"><LoaderCircle size={28} className="spin" /><h2>Loading standings</h2><p>Connecting to the competition server…</p></div> : !rows.length ? <div className="empty"><Trophy size={36} /><h2>{error ? 'Standings unavailable' : 'The race is still unfolding'}</h2><p>{error ? 'Please retry when the server is available.' : 'Accepted submissions will appear here. Make your circuit count.'}</p>{!error && <Link className="text-button cyan" to="/">Go to submission <ArrowRight size={16} /></Link>}</div> : <table><thead><tr><th scope="col">POSITION</th><th scope="col">TEAM ID</th><th scope="col">ACCEPTED AT (LOCAL TIME)</th></tr></thead><tbody>{rows.map(row => <tr key={row.team_id} className={row.rank <= 3 ? `place-${row.rank}` : ''}><td><span className="rank">{String(row.rank).padStart(2, '0')}</span></td><td>{row.team_id}</td><td><time dateTime={row.accepted_at}>{new Date(row.accepted_at).toLocaleString(undefined, { dateStyle: 'medium', timeStyle: 'medium' })}</time></td></tr>)}</tbody></table>}

      <div className="board-bottom"><span><i /> AUTO-REFRESH EVERY 10 SECONDS</span><span>{refreshed ? `UPDATED ${refreshed}` : 'WAITING FOR SERVER'}</span></div></section>{managed && <Admin refresh={refresh} onSignedOut={onSignedOut} />}</main>

}

function Organizer({ reload }: { reload: () => Promise<void> }) {

  const [authenticated, setAuthenticated] = useState(false), [checking, setChecking] = useState(true)

  const [password, setPassword] = useState(''), [error, setError] = useState(''), [busy, setBusy] = useState(false)

  const signedOut = useCallback(() => { setAuthenticated(false); setPassword('') }, [])

  useEffect(() => {

    let active = true

    api<Overview>('/admin/overview').then(() => { if (active) setAuthenticated(true) }).catch(e => { if (active && !(e instanceof ApiError && e.status === 401)) setError(message(e)) }).finally(() => { if (active) setChecking(false) })

    return () => { active = false }

  }, [])

  async function login(event: FormEvent) {

    event.preventDefault(); setBusy(true); setError('')

    try { await api('/admin/login', { body: { password } }); setPassword(''); await api<Overview>('/admin/overview'); setAuthenticated(true) }

    catch (e) { setError(message(e)) } finally { setBusy(false) }

  }

  if (checking) return <main className="empty" role="status"><LoaderCircle className="spin" size={28} /><p>Verifying organizer session…</p></main>

  if (authenticated) return <Leaderboard reload={reload} onSignedOut={signedOut} managed />

  return <main className="participant-main"><section className="glass submission-card"><div className="card-heading"><LockKeyhole size={28} className="cyan" /><h1>Organizer sign in</h1><p>Sign in to access competition management.</p></div><form onSubmit={login} className="submission-form"><label htmlFor="organizer-password">Administrator password</label><input id="organizer-password" type="password" autoComplete="current-password" maxLength={1024} required value={password} onChange={e=>setPassword(e.target.value)} /><button className="primary" disabled={busy}>{busy ? 'Signing in…' : 'Sign in'}</button>{error && <Notice text={error} />}</form></section></main>

}

export default function App() {

  const [round, setRound] = useState<RoundStatus | null>(null)

  const location = useLocation()

  const reload = useCallback(async () => { try { setRound(await api<RoundStatus>('/competition/status')) } catch { setRound(null) } }, [])

  useEffect(() => { void reload(); const timer = window.setInterval(() => { if (!document.hidden) void reload() }, 10000); return () => window.clearInterval(timer) }, [reload])

  return <div className="app-shell"><a className="skip-link" href="#content">Skip to content</a><header><Link to="/" className="brand"><Logo /><span>CHRONOHUNT</span><span className="round-tag">ROUND 2</span></Link>{location.pathname !== '/' && <Link className="text-button" to="/">Participant portal</Link>}<div className="header-status"><StatusPill round={round} /></div></header><div id="content"><Routes><Route path="/" element={<Participant round={round} reload={reload} />} /><Route path="/admin" element={<Organizer reload={reload} />} /><Route path="/leaderboard" element={<Organizer reload={reload} />} /><Route path="*" element={<main className="empty"><h1>Page not found</h1><Link to="/">Return to submission</Link></main>} /></Routes></div><footer><span>CHRONOHUNT <b> / </b> THE CLOCK IS PART OF THE CHALLENGE.</span><span>ROUND 02 <b>·</b> TINKERCAD CHALLENGE</span></footer></div>

}

