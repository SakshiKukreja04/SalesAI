import { useAuth } from '../context/AuthContext'

export default function TopBar() {
  const { user, profile, logout } = useAuth()

  return (
    <header className="flex h-16 items-center justify-between border-b border-slate-200 bg-white px-6">
      <div>
        <p className="text-xs uppercase tracking-wide text-slate-500">SalesAI Email Agent</p>
        <h1 className="text-lg font-semibold text-slate-900">Operations Dashboard</h1>
      </div>

      <div className="flex items-center gap-4">
        <div className="text-right">
          <p className="text-sm font-medium text-slate-800">{profile.name || user?.email}</p>
          <p className="text-xs uppercase text-slate-500">{profile.role}</p>
        </div>
        <button
          type="button"
          onClick={logout}
          className="rounded-lg border border-slate-300 px-3 py-2 text-sm font-medium text-slate-700 hover:bg-slate-100"
        >
          Logout
        </button>
      </div>
    </header>
  )
}
