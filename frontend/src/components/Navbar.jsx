export default function Navbar({ totalEmails, onRefresh, isLoading }) {
  return (
    <nav className="bg-white shadow-md border-b border-gray-200">
      <div className="max-w-full px-6 py-4 flex items-center justify-between">
        {/* Logo */}
        <div className="flex items-center gap-2">
          <div className="w-8 h-8 bg-gradient-to-br from-blue-600 to-blue-800 rounded-lg flex items-center justify-center">
            <span className="text-white font-bold text-lg">S</span>
          </div>
          <h1 className="text-2xl font-bold text-gray-900">SalesAI Admin</h1>
        </div>

        {/* Right Section */}
        <div className="flex items-center gap-6">
          {/* Total Count */}
          <div className="flex items-center gap-3 px-4 py-2 bg-gray-100 rounded-lg">
            <span className="text-gray-600 text-sm font-medium">Total Emails:</span>
            <span className="text-gray-900 font-bold text-lg">{totalEmails}</span>
          </div>

          {/* Refresh Button */}
          <button
            onClick={onRefresh}
            disabled={isLoading}
            className="px-4 py-2 bg-blue-600 hover:bg-blue-700 text-white rounded-lg transition-colors font-medium disabled:bg-gray-400 disabled:cursor-not-allowed flex items-center gap-2"
          >
            <svg
              className={`w-4 h-4 ${isLoading ? 'animate-spin' : ''}`}
              fill="none"
              stroke="currentColor"
              viewBox="0 0 24 24"
            >
              <path
                strokeLinecap="round"
                strokeLinejoin="round"
                strokeWidth={2}
                d="M4 4v5h.582m15.356 2A8.001 8.001 0 004.582 9m0 0H9m11 11v-5h-.581m0 0a8.003 8.003 0 01-15.357-2m15.357 2H15"
              />
            </svg>
            Refresh
          </button>
        </div>
      </div>
    </nav>
  )
}
