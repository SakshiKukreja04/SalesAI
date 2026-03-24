import { Link, NavLink } from 'react-router-dom'
import { ALLOWED_INTENTS } from '../constants/intents'

const linkBase =
  'flex items-center rounded-lg px-3 py-2 text-sm transition-colors hover:bg-slate-100 hover:text-slate-900'

export default function Sidebar({ isAdmin, assignedIntents = [], expanded, onToggle }) {
  const intentList = isAdmin
    ? ALLOWED_INTENTS
    : ALLOWED_INTENTS.filter((item) => assignedIntents.includes(item))

  return (
    <aside
      className={`border-r border-slate-200 bg-white ${expanded ? 'w-72' : 'w-20'} transition-all duration-300`}
    >
      <div className="flex h-16 items-center justify-between border-b border-slate-100 px-4">
        <Link to="/dashboard" className="text-lg font-semibold text-slate-900">
          {expanded ? 'SalesAI Desk' : 'SA'}
        </Link>
        <button
          type="button"
          onClick={onToggle}
          className="rounded-md p-2 text-slate-500 hover:bg-slate-100"
          aria-label="Toggle sidebar"
        >
          {expanded ? '<' : '>'}
        </button>
      </div>

      <nav className="space-y-1 p-3">
        <NavLink
          to="/dashboard"
          className={({ isActive }) => `${linkBase} ${isActive ? 'bg-slate-900 text-white' : 'text-slate-700'}`}
        >
          {expanded ? 'Dashboard' : 'D'}
        </NavLink>

        <NavLink
          to="/emails"
          className={({ isActive }) => `${linkBase} ${isActive ? 'bg-slate-900 text-white' : 'text-slate-700'}`}
        >
          {expanded ? 'Emails' : 'E'}
        </NavLink>

        <div className="pt-2">
          <p className={`px-3 text-xs uppercase tracking-wider text-slate-400 ${expanded ? '' : 'text-center'}`}>
            {expanded ? 'Intents' : 'I'}
          </p>
          <div className="mt-2 space-y-1">
            {intentList.map((intent) => (
              <NavLink
                key={intent}
                to={`/intent/${encodeURIComponent(intent)}`}
                className={({ isActive }) =>
                  `${linkBase} ${isActive ? 'bg-emerald-100 text-emerald-900' : 'text-slate-600'}`
                }
              >
                {expanded ? intent : intent.charAt(0)}
              </NavLink>
            ))}
          </div>
        </div>

        <NavLink
          to="/analytics"
          className={({ isActive }) => `${linkBase} ${isActive ? 'bg-slate-900 text-white' : 'text-slate-700'}`}
        >
          {expanded ? 'Analytics' : 'A'}
        </NavLink>

        {isAdmin && (
          <NavLink
            to="/team"
            className={({ isActive }) => `${linkBase} ${isActive ? 'bg-slate-900 text-white' : 'text-slate-700'}`}
          >
            {expanded ? 'Team Management' : 'T'}
          </NavLink>
        )}
      </nav>
    </aside>
  )
}
