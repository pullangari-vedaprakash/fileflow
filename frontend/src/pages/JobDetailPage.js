import React, { useState, useEffect } from 'react';
import { useParams, Link } from 'react-router-dom';
import api from '../api';
import StatusBadge from '../components/StatusBadge';
import ProgressBar from '../components/ProgressBar';
import LoadingState from '../components/LoadingState';

export default function JobDetailPage({ jobs, onCancelJob, onRetryJob, actionLoadingId }) {
  const { id } = useParams();
  const [job, setJob] = useState(null);
  const [results, setResults] = useState([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState('');

  // Keep job in sync with WebSocket updates passed from parent App.js
  useEffect(() => {
    const matched = jobs.find((j) => String(j.id) === String(id));
    if (matched) {
      setJob(matched);
    }
  }, [jobs, id]);

  useEffect(() => {
    setLoading(true);
    Promise.all([
      api.get(`/jobs/${id}`),
      api.get(`/jobs/${id}/results`),
    ])
      .then(([jobRes, resultsRes]) => {
        setJob(jobRes.data);
        setResults(resultsRes.data);
      })
      .catch((err) => {
        setError(err.response?.data?.detail || 'Failed to load job details');
      })
      .finally(() => setLoading(false));
  }, [id]);

  // Re-fetch results when job transitions to COMPLETED
  useEffect(() => {
    if (job?.status === 'COMPLETED' && results.length === 0) {
      api.get(`/jobs/${id}/results`)
        .then((res) => setResults(res.data))
        .catch(() => {});
    }
  }, [job?.status, id, results.length]);

  if (loading && !job) {
    return <LoadingState message={`Fetching job #${id}...`} />;
  }

  if (error || !job) {
    return (
      <div className="max-w-2xl mx-auto p-6 bg-white rounded-xl border border-gray-200 text-center">
        <h2 className="text-lg font-bold text-gray-900">Job Not Found</h2>
        <p className="text-sm text-gray-500 mt-1">{error || 'This job does not exist or is unauthorized.'}</p>
        <Link to="/jobs" className="mt-4 inline-block text-sm font-semibold text-blue-600 hover:underline">
          ← Back to All Jobs
        </Link>
      </div>
    );
  }

  const isActionLoading = actionLoadingId === job.id;

  return (
    <div className="max-w-4xl mx-auto space-y-6">
      {/* Breadcrumb Header */}
      <div className="flex flex-col sm:flex-row sm:items-center sm:justify-between gap-4">
        <div>
          <div className="flex items-center gap-2 text-xs font-semibold text-gray-500 mb-1">
            <Link to="/jobs" className="hover:text-blue-600">Jobs</Link>
            <span>/</span>
            <span>Job #{job.id}</span>
          </div>
          <h1 className="text-2xl font-bold text-gray-900 tracking-tight flex items-center gap-3">
            <span>Job #{job.id}</span>
            <StatusBadge status={job.status} />
          </h1>
        </div>

        <div className="flex items-center gap-3">
          {job.status === 'QUEUED' && (
            <button
              onClick={() => onCancelJob(job.id)}
              disabled={isActionLoading}
              className="px-3.5 py-2 rounded-lg border border-slate-300 bg-white hover:bg-slate-50 text-slate-700 font-semibold text-xs transition disabled:opacity-50"
            >
              {isActionLoading ? 'Cancelling...' : 'Cancel Job'}
            </button>
          )}

          {job.status === 'FAILED' && (
            <button
              onClick={() => onRetryJob(job.id)}
              disabled={isActionLoading || job.retry_count >= 3}
              className="px-3.5 py-2 rounded-lg bg-blue-600 hover:bg-blue-700 text-white font-semibold text-xs transition shadow-sm disabled:opacity-50"
            >
              {isActionLoading ? 'Requeueing...' : `Retry (${job.retry_count || 0}/3)`}
            </button>
          )}
        </div>
      </div>

      {/* Progress & Live Status Card */}
      <div className="bg-white rounded-2xl border border-gray-200 p-6 shadow-xs space-y-4">
        <div className="flex justify-between items-center">
          <span className="text-xs font-semibold uppercase tracking-wider text-gray-500">Live Execution Progress</span>
          <span className="text-sm font-bold text-gray-900">{job.progress?.toFixed(0) || 0}%</span>
        </div>
        <ProgressBar progress={job.progress} status={job.status} />
        {job.error_message && (
          <div className="p-4 rounded-xl bg-rose-50 border border-rose-200 text-rose-700 text-xs font-medium">
            <span className="font-bold">Error:</span> {job.error_message}
          </div>
        )}
      </div>

      {/* Details Grid */}
      <div className="grid grid-cols-1 md:grid-cols-2 gap-6">
        <div className="bg-white rounded-2xl border border-gray-200 p-6 shadow-xs space-y-4">
          <h3 className="text-sm font-bold text-gray-900 uppercase tracking-wider">Job Parameters</h3>
          <dl className="divide-y divide-gray-100 text-sm">
            <div className="py-2.5 flex justify-between">
              <dt className="text-gray-500">Associated File ID</dt>
              <dd className="font-mono font-medium text-gray-900">#{job.file_id}</dd>
            </div>
            <div className="py-2.5 flex justify-between">
              <dt className="text-gray-500">Scheduled Priority</dt>
              <dd className="font-semibold text-gray-900">{job.priority}</dd>
            </div>
            <div className="py-2.5 flex justify-between">
              <dt className="text-gray-500">Retries Attempted</dt>
              <dd className="font-medium text-gray-900">{job.retry_count || 0} / 3 max</dd>
            </div>
            <div className="py-2.5 flex justify-between items-center">
              <dt className="text-gray-500">Pipeline Operations</dt>
              <dd className="flex flex-wrap gap-1 justify-end">
                {job.operations?.map((op) => (
                  <span key={op} className="text-xs px-2 py-0.5 rounded bg-gray-100 font-medium text-gray-700">
                    {op}
                  </span>
                ))}
              </dd>
            </div>
          </dl>
        </div>

        <div className="bg-white rounded-2xl border border-gray-200 p-6 shadow-xs space-y-4">
          <h3 className="text-sm font-bold text-gray-900 uppercase tracking-wider">Timestamps & Lifecycle</h3>
          <dl className="divide-y divide-gray-100 text-sm">
            <div className="py-2.5 flex justify-between">
              <dt className="text-gray-500">Created</dt>
              <dd className="text-gray-900">{new Date(job.created_at).toLocaleString()}</dd>
            </div>
            <div className="py-2.5 flex justify-between">
              <dt className="text-gray-500">Started</dt>
              <dd className="text-gray-900">
                {job.started_at ? new Date(job.started_at).toLocaleString() : 'Waiting in queue...'}
              </dd>
            </div>
            <div className="py-2.5 flex justify-between">
              <dt className="text-gray-500">Completed</dt>
              <dd className="text-gray-900">
                {job.completed_at ? new Date(job.completed_at).toLocaleString() : '—'}
              </dd>
            </div>
          </dl>
        </div>
      </div>

      {/* Generated Results Section */}
      <div className="bg-white rounded-2xl border border-gray-200 p-6 shadow-xs space-y-4">
        <h3 className="text-sm font-bold text-gray-900 uppercase tracking-wider">
          Processed Deliverables ({results.length})
        </h3>

        {results.length === 0 ? (
          <p className="text-sm text-gray-500 italic py-4 text-center">
            {job.status === 'COMPLETED'
              ? 'No artifacts stored for this job.'
              : 'Deliverables will appear here once worker processing finishes.'}
          </p>
        ) : (
          <div className="divide-y divide-gray-100">
            {results.map((r) => (
              <div key={r.id} className="py-3.5 flex items-center justify-between gap-4">
                <div className="flex items-center gap-3">
                  <span className="w-8 h-8 rounded-lg bg-emerald-50 text-emerald-600 flex items-center justify-center font-bold text-xs uppercase">
                    ✓
                  </span>
                  <div>
                    <p className="text-sm font-semibold text-gray-900">{r.file_name || r.type}</p>
                    <p className="text-xs text-gray-400 font-mono truncate max-w-xs">{r.storage_key}</p>
                  </div>
                </div>

                {r.download_url && (
                  <a
                    href={r.download_url}
                    target="_blank"
                    rel="noreferrer"
                    download
                    className="inline-flex items-center gap-1.5 px-3 py-1.5 rounded-lg border border-blue-200 text-blue-700 bg-blue-50/50 hover:bg-blue-100/60 font-semibold text-xs transition"
                  >
                    <svg className="w-4 h-4" fill="none" viewBox="0 0 24 24" stroke="currentColor">
                      <path strokeLinecap="round" strokeLinejoin="round" strokeWidth="2" d="M4 16v1a3 3 0 003 3h10a3 3 0 003-3v-1m-4-4l-4 4m0 0l-4-4m4 4V4" />
                    </svg>
                    Direct Download
                  </a>
                )}
              </div>
            ))}
          </div>
        )}
      </div>
    </div>
  );
}
