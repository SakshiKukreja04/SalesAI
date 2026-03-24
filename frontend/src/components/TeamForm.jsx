import { useState } from 'react'
import toast from 'react-hot-toast'

import { ALLOWED_INTENTS } from '../constants/intents'
import { useAuth } from '../context/AuthContext'
import { inviteUser } from '../services/api'

const initialState = {
  name: '',
  email: '',
  role: 'manager',
  assignedIntents: [],
}

export default function TeamForm() {
  const [form, setForm] = useState(initialState)
  const [saving, setSaving] = useState(false)
  const [inviteLink, setInviteLink] = useState('')
  const [teamMembers, setTeamMembers] = useState([])
  const { profile } = useAuth()

  const toggleIntent = (intent) => {
    setForm((prev) => {
      const exists = prev.assignedIntents.includes(intent)
      return {
        ...prev,
        assignedIntents: exists
          ? prev.assignedIntents.filter((item) => item !== intent)
          : [...prev.assignedIntents, intent],
      }
    })
  }

  const onSubmit = async (event) => {
    event.preventDefault()

    if (!form.email || !form.name) {
      toast.error('Name and email are required')
      return
    }

    if (form.assignedIntents.length === 0) {
      toast.error('Assign at least one intent to manager')
      return
    }

    setSaving(true)
    setInviteLink('')
    try {
      const payload = {
        name: form.name,
        email: form.email,
        role: 'manager',
        assigned_intents: form.assignedIntents,
        business_id: profile.businessId || 'salesai-business',
      }

      const response = await inviteUser(payload)
      setInviteLink(response?.invite_link || '')
      if (response?.user) {
        setTeamMembers((prev) => {
          const filtered = prev.filter((member) => member.email !== response.user.email)
          return [response.user, ...filtered]
        })
      }

      toast.success('Invite created successfully')
      setForm(initialState)
    } catch (error) {
      const message = error?.response?.data?.detail || 'Failed to invite user'
      toast.error(message)
    } finally {
      setSaving(false)
    }
  }

  return (
    <form onSubmit={onSubmit} className="space-y-5 rounded-xl border border-slate-200 bg-white p-6">
      <div className="grid gap-4 md:grid-cols-2">
        <label className="space-y-2">
          <span className="text-sm font-medium text-slate-700">Name</span>
          <input
            value={form.name}
            onChange={(event) => setForm((prev) => ({ ...prev, name: event.target.value }))}
            className="w-full rounded-lg border border-slate-300 px-3 py-2 text-sm"
            placeholder="Manager Name"
          />
        </label>

        <label className="space-y-2">
          <span className="text-sm font-medium text-slate-700">Email</span>
          <input
            type="email"
            value={form.email}
            onChange={(event) => setForm((prev) => ({ ...prev, email: event.target.value.toLowerCase() }))}
            className="w-full rounded-lg border border-slate-300 px-3 py-2 text-sm"
            placeholder="member@company.com"
          />
        </label>
      </div>

      <div className="space-y-2">
        <p className="text-sm font-medium text-slate-700">Role</p>
        <div className="rounded-lg border border-slate-200 bg-slate-50 px-3 py-2 text-sm text-slate-700">Manager</div>
      </div>

      <div className="space-y-2">
        <p className="text-sm font-medium text-slate-700">Assign intents</p>
        <div className="grid grid-cols-1 gap-2 sm:grid-cols-2 lg:grid-cols-3">
          {ALLOWED_INTENTS.map((intent) => (
            <label key={intent} className="flex items-center gap-2 rounded-lg border border-slate-200 px-3 py-2 text-sm">
              <input
                type="checkbox"
                checked={form.assignedIntents.includes(intent)}
                onChange={() => toggleIntent(intent)}
              />
              {intent}
            </label>
          ))}
        </div>
      </div>

      <button
        type="submit"
        disabled={saving}
        className="rounded-lg bg-slate-900 px-4 py-2 text-sm font-medium text-white disabled:cursor-not-allowed disabled:opacity-60"
      >
        {saving ? 'Sending Invite...' : 'Invite Team Member'}
      </button>

      {inviteLink && (
        <div className="rounded-lg border border-emerald-200 bg-emerald-50 px-3 py-2 text-sm text-emerald-900">
          Invite Link: {inviteLink}
        </div>
      )}

      {teamMembers.length > 0 && (
        <div className="space-y-3 rounded-xl border border-slate-200 bg-slate-50 p-4">
          <h3 className="text-base font-semibold text-slate-900">Team Members</h3>

          <div className="overflow-x-auto">
            <table className="min-w-full text-left text-sm">
              <thead>
                <tr className="border-b border-slate-200 text-slate-600">
                  <th className="px-2 py-2 font-medium">Name</th>
                  <th className="px-2 py-2 font-medium">Email</th>
                  <th className="px-2 py-2 font-medium">Role</th>
                  <th className="px-2 py-2 font-medium">Status</th>
                  <th className="px-2 py-2 font-medium">Assigned Intents</th>
                </tr>
              </thead>
              <tbody>
                {teamMembers.map((member) => (
                  <tr key={member.email} className="border-b border-slate-200 last:border-b-0">
                    <td className="px-2 py-2 text-slate-800">{member.name || '-'}</td>
                    <td className="px-2 py-2 text-slate-800">{member.email}</td>
                    <td className="px-2 py-2 text-slate-800 capitalize">{member.role || 'manager'}</td>
                    <td className="px-2 py-2 text-amber-700 capitalize">{member.status || 'invited'}</td>
                    <td className="px-2 py-2 text-slate-800">{(member.assigned_intents || []).join(', ') || '-'}</td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        </div>
      )}
    </form>
  )
}
