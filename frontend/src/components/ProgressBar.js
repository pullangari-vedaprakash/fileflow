import React from 'react';

export default function ProgressBar({ progress = 0, status = 'PROCESSING' }) {
  const pct = Math.min(100, Math.max(0, Math.round(progress)));

  let barColor = 'bg-blue-600';
  if (status === 'COMPLETED') barColor = 'bg-emerald-500';
  if (status === 'FAILED') barColor = 'bg-rose-500';
  if (status === 'CANCELLED') barColor = 'bg-slate-400';

  return (
    <div className="w-full">
      <div className="flex justify-between items-center text-xs font-medium text-gray-500 mb-1">
        <span>{status === 'COMPLETED' ? 'Completed' : `${pct}%`}</span>
      </div>
      <div className="w-full bg-gray-200 rounded-full h-2 overflow-hidden">
        <div
          className={`h-2 rounded-full transition-all duration-300 ease-out ${barColor}`}
          style={{ width: `${pct}%` }}
        />
      </div>
    </div>
  );
}
