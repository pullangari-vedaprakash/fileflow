import React from 'react';
import { Link } from 'react-router-dom';
import StatusBadge from './StatusBadge';
import ProgressBar from './ProgressBar';

export default function JobTable({ jobs, onCancel, onRetry, actionLoadingId }) {
  return (
    <div className="bg-white rounded-xl border border-gray-200 overflow-hidden shadow-xs">
      <div className="overflow-x-auto">
        <table className="w-full text-left border-collapse text-sm">
          <thead>
            <tr className="border-b border-gray-200 bg-gray-50/75 text-xs font-semibold text-gray-500 uppercase tracking-wider">
              <th className="py-3.5 px-4">Job ID</th>
              <th className="py-3.5 px-4">Status</th>
              <th className="py-3.5 px-4 min-w-[140px]">Progress</th>
              <th className="py-3.5 px-4">Priority</th>
              <th className="py-3.5 px-4">Operations</th>
              <th className="py-3.5 px-4">Created</th>
              <th className="py-3.5 px-4 text-right">Actions</th>
            </tr>
          </thead>
          <tbody className="divide-y divide-gray-200 text-gray-700">
            {jobs.map((job) => {
              const isLoading = actionLoadingId === job.id;
              return (
                <tr key={job.id} className="hover:bg-gray-50/75 transition-colors">
                  <td className="py-3.5 px-4 font-mono font-medium text-gray-900">#{job.id}</td>
                  <td className="py-3.5 px-4">
                    <StatusBadge status={job.status} />
                  </td>
                  <td className="py-3.5 px-4">
                    <ProgressBar progress={job.progress} status={job.status} />
                  </td>
                  <td className="py-3.5 px-4">
                    <span
                      className={`inline-block px-2 py-0.5 rounded text-xs font-semibold ${
                        job.priority === 'HIGH'
                          ? 'bg-rose-50 text-rose-700'
                          : job.priority === 'NORMAL'
                          ? 'bg-blue-50 text-blue-700'
                          : 'bg-gray-100 text-gray-700'
                      }`}
                    >
                      {job.priority}
                    </span>
                  </td>
                  <td className="py-3.5 px-4 text-xs font-medium text-gray-600">
                    <div className="flex flex-wrap gap-1">
                      {job.operations?.map((op) => (
                        <span key={op} className="bg-gray-100 px-1.5 py-0.5 rounded">
                          {op}
                        </span>
                      ))}
                    </div>
                  </td>
                  <td className="py-3.5 px-4 text-xs text-gray-500">
                    {new Date(job.created_at).toLocaleTimeString([], { hour: '2-digit', minute: '2-digit' })}
                  </td>
                  <td className="py-3.5 px-4 text-right space-x-2">
                    <Link
                      to={`/jobs/${job.id}`}
                      className="inline-flex items-center text-xs font-semibold text-blue-600 hover:text-blue-800"
                    >
                      Details
                    </Link>

                    {job.status === 'QUEUED' && onCancel && (
                      <button
                        onClick={() => onCancel(job.id)}
                        disabled={isLoading}
                        className="inline-flex items-center text-xs font-semibold text-slate-500 hover:text-slate-800 disabled:opacity-50"
                      >
                        Cancel
                      </button>
                    )}

                    {job.status === 'FAILED' && onRetry && (
                      <button
                        onClick={() => onRetry(job.id)}
                        disabled={isLoading}
                        className="inline-flex items-center text-xs font-semibold text-rose-600 hover:text-rose-800 disabled:opacity-50"
                      >
                        Retry ({job.retry_count || 0}/3)
                      </button>
                    )}
                  </td>
                </tr>
              );
            })}
          </tbody>
        </table>
      </div>
    </div>
  );
}
