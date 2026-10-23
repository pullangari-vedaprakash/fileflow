import React, { useState } from 'react';
import { useNavigate } from 'react-router-dom';
import api from '../api';
import UploadZone from '../components/UploadZone';
import OperationSelector from '../components/OperationSelector';
import PrioritySelector from '../components/PrioritySelector';

export default function UploadPage({ onJobCreated }) {
  const [file, setFile] = useState(null);
  const [selectedOps, setSelectedOps] = useState([]);
  const [priority, setPriority] = useState('NORMAL');
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState('');
  const navigate = useNavigate();

  const handleSelectFile = (newFile) => {
    setFile(newFile);
    setError('');
    // Auto-select default operation based on file type
    if (newFile.type === 'application/pdf' || newFile.name.endsWith('.pdf')) {
      setSelectedOps(['extract_text']);
    } else {
      setSelectedOps(['resize', 'thumbnail']);
    }
  };

  const handleClearFile = () => {
    setFile(null);
    setSelectedOps([]);
    setError('');
  };

  const handleToggleOp = (opId) => {
    setSelectedOps((prev) =>
      prev.includes(opId) ? prev.filter((o) => o !== opId) : [...prev, opId]
    );
  };

  const handleSubmit = async (e) => {
    e.preventDefault();
    if (!file) {
      setError('Please select a file to process');
      return;
    }
    if (selectedOps.length === 0) {
      setError('Please select at least one operation');
      return;
    }

    setLoading(true);
    setError('');

    try {
      // 1. Upload binary file
      const formData = new FormData();
      formData.append('file', file);

      const uploadRes = await api.post('/files/upload', formData, {
        headers: { 'Content-Type': 'multipart/form-data' },
      });
      const fileId = uploadRes.data.id;

      // 2. Create asynchronous job
      const jobRes = await api.post('/jobs/', {
        file_id: fileId,
        operations: selectedOps,
        priority: priority,
      });

      if (onJobCreated) {
        onJobCreated(jobRes.data);
      }

      navigate(`/jobs/${jobRes.data.id}`);
    } catch (err) {
      setError(err.response?.data?.detail || err.message || 'Failed to create job');
      setLoading(false);
    }
  };

  return (
    <div className="max-w-2xl mx-auto space-y-6">
      <div>
        <h1 className="text-2xl font-bold text-gray-900 tracking-tight">Create Asynchronous Job</h1>
        <p className="text-sm text-gray-500 mt-1">
          Upload media, select processing transformations, and assign queue priority.
        </p>
      </div>

      {error && (
        <div className="p-4 rounded-xl bg-rose-50 border border-rose-200 text-rose-700 text-sm font-medium">
          {error}
        </div>
      )}

      <form onSubmit={handleSubmit} className="bg-white border border-gray-200 rounded-2xl p-6 shadow-xs space-y-6">
        <UploadZone
          file={file}
          onSelectFile={handleSelectFile}
          onClearFile={handleClearFile}
        />

        {file && (
          <OperationSelector
            fileType={file.type || file.name}
            selectedOps={selectedOps}
            onToggleOp={handleToggleOp}
          />
        )}

        <PrioritySelector
          selected={priority}
          onChange={setPriority}
        />

        <div className="pt-2">
          <button
            type="submit"
            disabled={loading || !file || selectedOps.length === 0}
            className="w-full py-3 px-4 rounded-xl bg-blue-600 hover:bg-blue-700 text-white font-semibold text-sm transition shadow-sm disabled:opacity-50 disabled:cursor-not-allowed flex items-center justify-center gap-2"
          >
            {loading ? (
              <>
                <svg className="animate-spin h-4 w-4 text-white" fill="none" viewBox="0 0 24 24">
                  <circle className="opacity-25" cx="12" cy="12" r="10" stroke="currentColor" strokeWidth="4"></circle>
                  <path className="opacity-75" fill="currentColor" d="M4 12a8 8 0 018-8v8H4z"></path>
                </svg>
                <span>Enqueueing Job to Redis...</span>
              </>
            ) : (
              <span>Submit to Distributed Queue</span>
            )}
          </button>
        </div>
      </form>
    </div>
  );
}
