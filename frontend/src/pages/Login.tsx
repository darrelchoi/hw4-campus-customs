import { useState } from 'react'
import type { FormEvent } from 'react'
import { Link, useLocation, useNavigate } from 'react-router-dom'
import { useAuth } from '../auth'

export default function Login() {
  const { login } = useAuth()
  const navigate = useNavigate()
  const location = useLocation()
  const [error, setError] = useState<string | null>(null)
  const [submitting, setSubmitting] = useState(false)
  const justSignedOut = (location.state as { signedOut?: boolean } | null)?.signedOut

  async function handleSubmit(e: FormEvent<HTMLFormElement>) {
    e.preventDefault()
    const data = new FormData(e.currentTarget)
    setError(null)
    setSubmitting(true)
    try {
      await login(String(data.get('email')), String(data.get('password')))
      navigate('/', { replace: true })
    } catch (err) {
      setError(err instanceof Error ? err.message : 'Could not log in.')
    } finally {
      setSubmitting(false)
    }
  }

  return (
    <section className="container section auth">
      <div className="auth-card">
        <p className="eyebrow">Welcome back</p>
        <h1>Log in</h1>
        {justSignedOut && <p className="notice">You have been logged out.</p>}
        <form onSubmit={handleSubmit} className="form">
          <label>
            Email
            <input type="email" name="email" autoComplete="email" required />
          </label>
          <label>
            Password
            <input type="password" name="password" autoComplete="current-password" required />
          </label>
          <button className="btn" type="submit" disabled={submitting}>
            {submitting ? 'Logging in…' : 'Log in'}
          </button>
        </form>
        {error && (
          <p className="form-error" role="alert">
            {error}
          </p>
        )}
        <p className="muted auth-switch">
          New here? <Link to="/create-account">Create an account</Link>
        </p>
      </div>
    </section>
  )
}
