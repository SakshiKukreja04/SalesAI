import { Link, Navigate } from 'react-router-dom'

import LandingNavbar from '../components/LandingNavbar'
import { useAuth } from '../context/AuthContext'

const features = [
  {
    title: 'Intent Detection',
    description: 'Classify incoming messages into support intents with high confidence and routing clarity.',
    icon: (
      <svg viewBox="0 0 24 24" fill="none" className="h-5 w-5 text-emerald-600" aria-hidden="true">
        <path d="M4 7h16M4 12h10M4 17h7" stroke="currentColor" strokeWidth="1.8" strokeLinecap="round" />
      </svg>
    ),
  },
  {
    title: 'Emotion Analysis',
    description: 'Detect customer sentiment to prioritize critical threads and reduce churn risk early.',
    icon: (
      <svg viewBox="0 0 24 24" fill="none" className="h-5 w-5 text-emerald-600" aria-hidden="true">
        <circle cx="12" cy="12" r="8" stroke="currentColor" strokeWidth="1.8" />
        <path d="M9 10h.01M15 10h.01M9 14c.8.8 1.8 1.2 3 1.2s2.2-.4 3-1.2" stroke="currentColor" strokeWidth="1.8" strokeLinecap="round" />
      </svg>
    ),
  },
  {
    title: 'Automated Replies',
    description: 'Generate on-brand responses grounded in policy and context, ready for approval or send.',
    icon: (
      <svg viewBox="0 0 24 24" fill="none" className="h-5 w-5 text-emerald-600" aria-hidden="true">
        <path d="M5 6h14v9H8l-3 3V6z" stroke="currentColor" strokeWidth="1.8" strokeLinejoin="round" />
      </svg>
    ),
  },
  {
    title: 'Analytics Dashboard',
    description: 'Track response quality, throughput, and intent trends with clear executive-ready metrics.',
    icon: (
      <svg viewBox="0 0 24 24" fill="none" className="h-5 w-5 text-emerald-600" aria-hidden="true">
        <path d="M5 18V9m7 9V6m7 12v-5" stroke="currentColor" strokeWidth="1.8" strokeLinecap="round" />
      </svg>
    ),
  },
  {
    title: 'Role-Based Access',
    description: 'Give admins and managers the right data visibility with secure, scope-aware controls.',
    icon: (
      <svg viewBox="0 0 24 24" fill="none" className="h-5 w-5 text-emerald-600" aria-hidden="true">
        <path d="M12 3l7 3v6c0 4.4-2.7 7.7-7 9-4.3-1.3-7-4.6-7-9V6l7-3z" stroke="currentColor" strokeWidth="1.8" />
      </svg>
    ),
  },
]

export default function HomePage() {
  const { isAuthenticated, loading, defaultDashboardRoute } = useAuth()

  if (!loading && isAuthenticated) {
    return <Navigate to={defaultDashboardRoute} replace />
  }

  return (
    <div className="min-h-screen bg-slate-100 text-slate-900">
      <LandingNavbar />

      <main>
        <section className="relative overflow-hidden bg-gradient-to-br from-emerald-100 via-sky-100 to-slate-100">
          <div className="pointer-events-none absolute inset-0 bg-[radial-gradient(circle_at_20%_20%,rgba(16,185,129,0.18),transparent_40%),radial-gradient(circle_at_80%_30%,rgba(14,165,233,0.18),transparent_35%)]" />
          <div className="relative mx-auto flex max-w-5xl flex-col items-center px-4 py-20 text-center md:px-6 md:py-28">
            <p className="inline-flex rounded-full border border-white/70 bg-white/70 px-3 py-1 text-xs font-semibold uppercase tracking-widest text-emerald-700 shadow-sm">
              SalesAI Platform
            </p>
            <h1 className="mt-6 max-w-4xl text-4xl font-bold leading-tight md:text-6xl">
              AI-Powered Email Intelligence for Your Business
            </h1>
            <p className="mt-5 max-w-2xl text-base text-slate-700 md:text-lg">
              Automatically understand, respond, and analyze customer emails with smart AI agents.
            </p>
            <div className="mt-8 flex flex-wrap items-center justify-center gap-3">
              <Link
                to="/signup"
                className="rounded-xl bg-emerald-600 px-6 py-3 text-sm font-semibold text-white shadow-md shadow-emerald-200 transition hover:-translate-y-0.5 hover:bg-emerald-500"
              >
                Get Started
              </Link>
              <Link
                to="/login"
                className="rounded-xl border border-slate-300 bg-white px-6 py-3 text-sm font-semibold text-slate-700 transition hover:-translate-y-0.5 hover:bg-slate-100"
              >
                View Dashboard
              </Link>
            </div>
          </div>
        </section>

        <section className="mx-auto max-w-6xl px-4 py-16 md:px-6 md:py-20">
          <div className="mb-10 text-center">
            <h2 className="text-3xl font-bold md:text-4xl">Everything Your Support Team Needs</h2>
            <p className="mx-auto mt-3 max-w-2xl text-slate-600">
              Built for high-volume teams that need precision, speed, and visibility across every customer interaction.
            </p>
          </div>

          <div className="grid gap-5 sm:grid-cols-2 lg:grid-cols-3">
            {features.map((feature) => (
              <article
                key={feature.title}
                className="rounded-2xl border border-slate-200 bg-white p-6 shadow-sm transition hover:-translate-y-1 hover:shadow-md"
              >
                <div className="inline-flex rounded-lg bg-emerald-50 p-2">{feature.icon}</div>
                <h3 className="mt-4 text-lg font-semibold">{feature.title}</h3>
                <p className="mt-2 text-sm text-slate-600">{feature.description}</p>
              </article>
            ))}
          </div>
        </section>

        <section className="mx-auto max-w-6xl px-4 pb-16 md:px-6 md:pb-20">
          <div className="rounded-3xl bg-slate-900 px-6 py-10 text-center text-white md:px-10 md:py-14">
            <h2 className="text-2xl font-bold md:text-3xl">Start automating your customer support today</h2>
            <p className="mx-auto mt-3 max-w-2xl text-sm text-slate-200 md:text-base">
              Join teams using SalesAI to reduce response time and improve customer experience at scale.
            </p>
            <Link
              to="/signup"
              className="mt-6 inline-flex rounded-xl bg-emerald-500 px-6 py-3 text-sm font-semibold text-white transition hover:bg-emerald-400"
            >
              Create Account
            </Link>
          </div>
        </section>
      </main>

      <footer className="border-t border-slate-200 bg-white/90">
        <div className="mx-auto flex max-w-6xl flex-col items-center justify-between gap-3 px-4 py-6 text-sm text-slate-600 md:flex-row md:px-6">
          <p className="font-semibold text-slate-900">SalesAI</p>
          <div className="flex items-center gap-4">
            <Link to="/login" className="hover:text-slate-900">
              Login
            </Link>
            <Link to="/signup" className="hover:text-slate-900">
              Signup
            </Link>
            <a href="mailto:support@salesai.com" className="hover:text-slate-900">
              Contact
            </a>
          </div>
        </div>
      </footer>
    </div>
  )
}
