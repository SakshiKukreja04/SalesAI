import { useEffect, useState } from 'react'
import { Link, Navigate, useLocation, useNavigate } from 'react-router-dom'
import toast from 'react-hot-toast'

import { useAuth } from '../context/AuthContext'

const initialForm = {
  name: '',
  email: '',
  password: '',
  confirmPassword: '',
  businessId: '',
}

export default function SignupPage() {
  const navigate = useNavigate()
  const location = useLocation()
  const { signup, validateInvite, isAuthenticated, loading, defaultDashboardRoute } = useAuth()
  const [form, setForm] = useState(initialForm)
  const [submitting, setSubmitting] = useState(false)
  const [errorMessage, setErrorMessage] = useState('')
  const [inviteChecking, setInviteChecking] = useState(true)
  const [inviteContext, setInviteContext] = useState({
    isInviteFlow: false,
    isValidInvite: false,
    inviteEmail: '',
    inviteRole: 'manager',
    businessId: '',
  })

  const query = new URLSearchParams(location.search)
  const inviteFlag = query.get('invite') === 'true'
  const inviteEmail = (query.get('email') || '').trim().toLowerCase()

  useEffect(() => {
    let mounted = true

    const run = async () => {
      if (!inviteFlag) {
        if (mounted) {
          setInviteContext({
            isInviteFlow: false,
            isValidInvite: true,
            inviteEmail: '',
            inviteRole: 'admin',
            businessId: '',
          })
          setInviteChecking(false)
        }
        return
      }

      if (!inviteEmail) {
        if (mounted) {
          setInviteContext((prev) => ({ ...prev, isInviteFlow: true, isValidInvite: false }))
          setErrorMessage('You are not invited')
          setInviteChecking(false)
        }
        return
      }

      const inviteValidation = await validateInvite(inviteEmail)
      if (!mounted) {
        return
      }

      if (!inviteValidation.ok) {
        setInviteContext((prev) => ({
          ...prev,
          isInviteFlow: true,
          inviteEmail,
          isValidInvite: false,
        }))
        setErrorMessage('You are not invited')
        setInviteChecking(false)
        return
      }

      setInviteContext({
        isInviteFlow: true,
        isValidInvite: true,
        inviteEmail,
        inviteRole: inviteValidation.user?.role || 'manager',
        businessId: inviteValidation.user?.business_id || '',
      })
      setForm((prev) => ({ ...prev, email: inviteEmail }))
      setInviteChecking(false)
    }

    run()

    return () => {
      mounted = false
    }
  }, [inviteFlag, inviteEmail, validateInvite])

  if (!loading && isAuthenticated) {
    return <Navigate to={defaultDashboardRoute} replace />
  }

  const onSubmit = async (event) => {
    event.preventDefault()
    setErrorMessage('')

    if (form.password.length < 6) {
      setErrorMessage('Password must be at least 6 characters')
      toast.error('Password must be at least 6 characters')
      return
    }

    if (form.password !== form.confirmPassword) {
      setErrorMessage('Passwords do not match')
      toast.error('Passwords do not match')
      return
    }

    if (inviteContext.isInviteFlow && !inviteContext.isValidInvite) {
      setErrorMessage('You are not invited')
      toast.error('You are not invited')
      return
    }

    setSubmitting(true)
    try {
      const role = inviteContext.isInviteFlow ? 'manager' : 'admin'
      const signupEmail = inviteContext.isInviteFlow ? inviteContext.inviteEmail : form.email

      await signup({
        name: form.name,
        email: signupEmail.toLowerCase(),
        password: form.password,
        role,
        businessId: inviteContext.businessId || form.businessId,
        requireInvite: inviteContext.isInviteFlow,
      })

      const nextRoute = role === 'admin' ? '/dashboard' : '/emails'
      navigate(nextRoute, { replace: true })
    } catch (error) {
      const message = error?.message || 'Unable to create account. Please check details and retry.'
      setErrorMessage(message)
      toast.error('Unable to create account. Please check details and retry.')
    } finally {
      setSubmitting(false)
    }
  }

  if (inviteChecking) {
    return (
      <div className="flex min-h-screen items-center justify-center bg-slate-100 px-4 py-8">
        <div className="rounded-xl border border-slate-200 bg-white px-4 py-3 text-sm text-slate-700 shadow-sm">
          Validating invite...
        </div>
      </div>
    )
  }

  if (inviteContext.isInviteFlow && !inviteContext.isValidInvite) {
    return (
      <div className="flex min-h-screen items-center justify-center bg-slate-100 px-4 py-8">
        <div className="w-full max-w-md rounded-2xl border border-red-200 bg-white p-8 shadow-sm">
          <h1 className="text-xl font-semibold text-slate-900">Invite Required</h1>
          <p className="mt-2 text-sm text-red-600">You are not invited</p>
          <p className="mt-4 text-sm text-slate-600">
            Contact your SalesAI admin and request an invite link.
          </p>
          <Link to="/login" className="mt-5 inline-block text-sm font-medium text-slate-900 underline">
            Back to Login
          </Link>
        </div>
      </div>
    )
  }

  return (
    <div className="flex min-h-screen items-center justify-center bg-slate-100 px-4 py-8">
      <form onSubmit={onSubmit} className="w-full max-w-2xl rounded-2xl border border-slate-200 bg-white p-8 shadow-sm">
        <h1 className="text-2xl font-semibold text-slate-900">Create SalesAI Account</h1>
        <p className="mt-1 text-sm text-slate-500">
          {inviteContext.isInviteFlow
            ? 'Complete your invited signup and continue to your dashboard'
            : 'Create your admin account to set up your organization'}
        </p>

        <div className="mt-6 grid gap-4 md:grid-cols-2">
          <label className="space-y-2">
            <span className="text-sm font-medium text-slate-700">Full Name</span>
            <input
              required
              value={form.name}
              onChange={(event) => setForm((prev) => ({ ...prev, name: event.target.value }))}
              className="w-full rounded-lg border border-slate-300 px-3 py-2 text-sm"
            />
          </label>

          <label className="space-y-2">
            <span className="text-sm font-medium text-slate-700">Email</span>
            <input
              type="email"
              required
              value={inviteContext.isInviteFlow ? inviteContext.inviteEmail : form.email}
              onChange={(event) => setForm((prev) => ({ ...prev, email: event.target.value }))}
              disabled={inviteContext.isInviteFlow}
              className="w-full rounded-lg border border-slate-300 px-3 py-2 text-sm"
            />
          </label>

          <label className="space-y-2">
            <span className="text-sm font-medium text-slate-700">Password</span>
            <input
              type="password"
              required
              value={form.password}
              onChange={(event) => setForm((prev) => ({ ...prev, password: event.target.value }))}
              className="w-full rounded-lg border border-slate-300 px-3 py-2 text-sm"
            />
          </label>

          <label className="space-y-2">
            <span className="text-sm font-medium text-slate-700">Confirm Password</span>
            <input
              type="password"
              required
              value={form.confirmPassword}
              onChange={(event) => setForm((prev) => ({ ...prev, confirmPassword: event.target.value }))}
              className="w-full rounded-lg border border-slate-300 px-3 py-2 text-sm"
            />
          </label>
        </div>

        <label className="mt-4 block space-y-2">
          <span className="text-sm font-medium text-slate-700">Role</span>
          <input
            value={inviteContext.isInviteFlow ? 'Manager (Invited)' : 'Admin'}
            disabled
            className="w-full rounded-lg border border-slate-300 bg-slate-50 px-3 py-2 text-sm text-slate-700"
          />
        </label>

        {!inviteContext.isInviteFlow && (
          <label className="mt-4 block space-y-2">
            <span className="text-sm font-medium text-slate-700">Business ID</span>
            <input
              required
              value={form.businessId}
              onChange={(event) => setForm((prev) => ({ ...prev, businessId: event.target.value }))}
              className="w-full rounded-lg border border-slate-300 px-3 py-2 text-sm"
              placeholder="acme-corp"
            />
          </label>
        )}

        <button
          type="submit"
          disabled={submitting}
          className="mt-6 w-full rounded-lg bg-slate-900 px-4 py-2 text-sm font-medium text-white disabled:opacity-60"
        >
          {submitting ? 'Creating account...' : 'Sign Up'}
        </button>

        {errorMessage && <p className="mt-3 text-sm text-red-600">{errorMessage}</p>}

        <p className="mt-4 text-center text-sm text-slate-600">
          Already have an account?{' '}
          <Link to="/login" className="font-medium text-slate-900 underline">
            Login
          </Link>
        </p>
      </form>
    </div>
  )
}
