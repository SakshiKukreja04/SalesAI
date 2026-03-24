import { useState } from 'react'
import { Link, Navigate } from 'react-router-dom'
import toast from 'react-hot-toast'

import { useAuth } from '../context/AuthContext'

export default function LoginPage() {
  const { login, isAuthenticated, defaultDashboardRoute } = useAuth()
  const [email, setEmail] = useState('')
  const [password, setPassword] = useState('')
  const [submitting, setSubmitting] = useState(false)
  const [errorMessage, setErrorMessage] = useState('')

  if (isAuthenticated) {
    return <Navigate to={defaultDashboardRoute} replace />
  }

  const handleSubmit = async (event) => {
    event.preventDefault()
    setErrorMessage('')
    setSubmitting(true)
    try {
      await login(email, password)
    } catch (error) {
      const message = error?.message || 'Invalid credentials'
      setErrorMessage(message)
      toast.error('Invalid credentials')
    } finally {
      setSubmitting(false)
    }
  }

  return (
    <div className="flex min-h-screen items-center justify-center bg-slate-100 px-4">
      <form onSubmit={handleSubmit} className="w-full max-w-md rounded-2xl border border-slate-200 bg-white p-8 shadow-sm">
        <h1 className="text-2xl font-semibold text-slate-900">SalesAI Dashboard</h1>
        <p className="mt-1 text-sm text-slate-500">Sign in with Firebase account</p>

        <div className="mt-6 space-y-4">
          <label className="block space-y-2">
            <span className="text-sm font-medium text-slate-700">Email</span>
            <input
              type="email"
              required
              value={email}
              onChange={(event) => setEmail(event.target.value)}
              className="w-full rounded-lg border border-slate-300 px-3 py-2 text-sm"
            />
          </label>

          <label className="block space-y-2">
            <span className="text-sm font-medium text-slate-700">Password</span>
            <input
              type="password"
              required
              value={password}
              onChange={(event) => setPassword(event.target.value)}
              className="w-full rounded-lg border border-slate-300 px-3 py-2 text-sm"
            />
          </label>
        </div>

        <button
          type="submit"
          disabled={submitting}
          className="mt-6 w-full rounded-lg bg-slate-900 px-4 py-2 text-sm font-medium text-white disabled:opacity-60"
        >
          {submitting ? 'Signing in...' : 'Login'}
        </button>

        {errorMessage && <p className="mt-3 text-sm text-red-600">{errorMessage}</p>}

        <p className="mt-4 text-center text-sm text-slate-600">
          Need an account?{' '}
          <Link to="/signup" className="font-medium text-slate-900 underline">
            Sign Up
          </Link>
        </p>
      </form>
    </div>
  )
}
