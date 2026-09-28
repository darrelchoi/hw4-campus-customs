import { useState } from 'react'
import type { FormEvent } from 'react'
import { Link, useNavigate } from 'react-router-dom'
import { useAuth } from '../auth'

export default function CreateAccount() {
  const { signup } = useAuth()
  const navigate = useNavigate()
  const [error, setError] = useState<string | null>(null)
  const [submitting, setSubmitting] = useState(false)

  async function handleSubmit(e: FormEvent<HTMLFormElement>) {
    e.preventDefault()
    const data = new FormData(e.currentTarget)
    const field = (name: string) => String(data.get(name) ?? '')
    if (field('password') !== field('confirm_password')) {
      setError('Passwords do not match.')
      return
    }
    setError(null)
    setSubmitting(true)
    try {
      await signup({
        first_name: field('first_name'),
        last_name: field('last_name'),
        email: field('email'),
        password: field('password'),
        confirm_password: field('confirm_password'),
      })
      navigate('/', { replace: true })
    } catch (err) {
      setError(err instanceof Error ? err.message : 'Could not create account.')
    } finally {
      setSubmitting(false)
    }
  }

  return (
    <section className="container section auth">
      <div className="auth-card">
        <p className="eyebrow">Join the pack</p>
        <h1>Create account</h1>
        <form onSubmit={handleSubmit} className="form">
          <div className="form-row">
            <label>
              First name
              <input name="first_name" autoComplete="given-name" maxLength={50} required />
            </label>
            <label>
              Last name
              <input name="last_name" autoComplete="family-name" maxLength={50} required />
            </label>
          </div>
          <label>
            Email
            <input type="email" name="email" autoComplete="email" required />
          </label>
          <label>
            Password
            <input type="password" name="password" autoComplete="new-password" minLength={8} maxLength={128} required />
            <span className="hint">At least 8 characters.</span>
          </label>
          <label>
            Confirm password
            <input
              type="password"
              name="confirm_password"
              autoComplete="new-password"
              minLength={8}
              maxLength={128}
              required
            />
          </label>
          <button className="btn" type="submit" disabled={submitting}>
            {submitting ? 'Creating account…' : 'Create account'}
          </button>
        </form>
        {error && (
          <p className="form-error" role="alert">
            {error}
          </p>
        )}
        <p className="muted auth-switch">
          Already have an account? <Link to="/login">Log in</Link>
        </p>
      </div>
    </section>
  )
}
