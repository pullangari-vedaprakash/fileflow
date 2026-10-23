import React from 'react';

const BADGE_STYLES = {
  QUEUED: 'bg-amber-50 text-amber-700 ring-1 ring-amber-600/20',
  PROCESSING: 'bg-blue-50 text-blue-700 ring-1 ring-blue-600/20 animate-pulse',
  COMPLETED: 'bg-emerald-50 text-emerald-700 ring-1 ring-emerald-600/20',
  FAILED: 'bg-rose-50 text-rose-700 ring-1 ring-rose-600/20',
  CANCELLED: 'bg-slate-100 text-slate-600 ring-1 ring-slate-500/20',
};

export default function StatusBadge({ status }) {
  const style = BADGE_STYLES[status] || 'bg-gray-100 text-gray-700';

  return (
    <span className={`inline-flex items-center gap-1.5 px-2.5 py-1 rounded-md text-xs font-semibold uppercase tracking-wider ${style}`}>
      {status === 'PROCESSING' && (
        <svg className="animate-spin h-3 w-3 text-blue-600" fill="none" viewBox="0 0 24 24">
          <circle className="opacity-25" cx="12" cy="12" r="10" stroke="currentColor" strokeWidth="4"></circle>
          <path className="opacity-75" fill="currentColor" d="M4 12a8 8 0 018-8v8H4z"></path>
        </svg>
      )}
      {status}
    </span>
  );
}
