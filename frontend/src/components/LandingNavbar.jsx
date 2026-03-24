import { Link } from 'react-router-dom'

export default function LandingNavbar() {
  return (
    <header className="sticky top-0 z-30 border-b border-slate-200/80 bg-white/85 backdrop-blur-md">
      <div className="mx-auto flex h-16 w-full max-w-6xl items-center justify-between px-4 md:px-6">
        <Link to="/" className="text-xl font-bold tracking-tight text-slate-900">
          SalesAI
        </Link>

        <nav className="flex items-center gap-3">
          <Link
            to="/login"
            className="rounded-lg border border-slate-300 px-4 py-2 text-sm font-semibold text-slate-700 transition hover:border-slate-400 hover:bg-slate-100"
          >
            Login
          </Link>
          <Link
            to="/signup"
            className="rounded-lg bg-emerald-600 px-4 py-2 text-sm font-semibold text-white shadow-sm transition hover:bg-emerald-500"
          >
            Sign Up
          </Link>
        </nav>
      </div>
    </header>
  )
}
