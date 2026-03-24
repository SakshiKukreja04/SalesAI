import TeamForm from '../components/TeamForm'

export default function TeamManagementPage() {
  return (
    <div className="space-y-4">
      <h2 className="text-xl font-semibold text-slate-900">Team Management</h2>
      <p className="text-sm text-slate-600">
        Add team members, assign roles and intents, and queue invite emails for onboarding.
      </p>
      <TeamForm />
    </div>
  )
}
