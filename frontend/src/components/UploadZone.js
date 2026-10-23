import React, { useRef, useState } from 'react';

export default function UploadZone({ file, onSelectFile, onClearFile }) {
  const [isDragging, setIsDragging] = useState(false);
  const inputRef = useRef(null);

  const handleDragOver = (e) => {
    e.preventDefault();
    setIsDragging(true);
  };

  const handleDragLeave = () => {
    setIsDragging(false);
  };

  const handleDrop = (e) => {
    e.preventDefault();
    setIsDragging(false);
    if (e.dataTransfer.files && e.dataTransfer.files.length > 0) {
      onSelectFile(e.dataTransfer.files[0]);
    }
  };

  return (
    <div>
      <label className="block text-sm font-semibold text-gray-800 mb-2">Source Document or Image</label>

      {!file ? (
        <div
          onDragOver={handleDragOver}
          onDragLeave={handleDragLeave}
          onDrop={handleDrop}
          onClick={() => inputRef.current?.click()}
          className={`border-2 border-dashed rounded-2xl p-8 text-center cursor-pointer transition-all ${
            isDragging
              ? 'border-blue-500 bg-blue-50/50'
              : 'border-gray-300 hover:border-gray-400 bg-gray-50/50'
          }`}
        >
          <input
            type="file"
            ref={inputRef}
            className="hidden"
            accept=".jpg,.jpeg,.png,.webp,.pdf"
            onChange={(e) => {
              if (e.target.files && e.target.files[0]) {
                onSelectFile(e.target.files[0]);
              }
            }}
          />
          <div className="mx-auto w-12 h-12 rounded-full bg-blue-100/80 text-blue-600 flex items-center justify-center mb-3">
            <svg className="w-6 h-6" fill="none" viewBox="0 0 24 24" stroke="currentColor">
              <path strokeLinecap="round" strokeLinejoin="round" strokeWidth="2" d="M7 16a4 4 0 01-.88-7.903A5 5 0 1115.9 6L16 6a5 5 0 011 9.9M15 13l-3-3m0 0l-3 3m3-3v12" />
            </svg>
          </div>
          <p className="text-sm font-semibold text-gray-800">
            Click to upload or drag & drop
          </p>
          <p className="text-xs text-gray-500 mt-1">
            JPG, PNG, WebP, or PDF (Up to 50 MB)
          </p>
        </div>
      ) : (
        <div className="flex items-center justify-between p-4 bg-white border border-gray-200 rounded-xl shadow-xs">
          <div className="flex items-center gap-3 overflow-hidden">
            <div className="w-10 h-10 rounded-lg bg-blue-50 text-blue-600 flex items-center justify-center shrink-0">
              {file.type === 'application/pdf' ? (
                <span className="font-bold text-xs uppercase">PDF</span>
              ) : (
                <span className="font-bold text-xs uppercase">IMG</span>
              )}
            </div>
            <div className="truncate">
              <p className="text-sm font-semibold text-gray-900 truncate">{file.name}</p>
              <p className="text-xs text-gray-500">{(file.size / (1024 * 1024)).toFixed(2)} MB</p>
            </div>
          </div>
          <button
            type="button"
            onClick={onClearFile}
            className="text-xs font-semibold text-rose-600 hover:text-rose-700 px-3 py-1.5 rounded-lg border border-rose-200 hover:bg-rose-50 transition"
          >
            Remove
          </button>
        </div>
      )}
    </div>
  );
}
