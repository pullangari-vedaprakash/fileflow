import React from 'react';

const IMAGE_OPERATIONS = [
  { id: 'resize', label: 'Smart Resize', desc: 'Rescales image proportionally to max 800x600' },
  { id: 'compress', label: 'JPEG Compress', desc: 'Optimizes file weight with balanced quality' },
  { id: 'thumbnail', label: 'Thumbnail Generation', desc: 'Creates a square 200x200 preview thumbnail' },
];

const PDF_OPERATIONS = [
  { id: 'extract_text', label: 'Text Extraction', desc: 'Extracts full UTF-8 text contents from all pages' },
  { id: 'generate_preview', label: 'First-Page Preview', desc: 'Renders high-res 2x PNG rendering of page 1' },
];

export default function OperationSelector({ fileType, selectedOps, onToggleOp }) {
  const isPdf = fileType === 'application/pdf' || fileType?.endsWith('.pdf');
  const operations = isPdf ? PDF_OPERATIONS : IMAGE_OPERATIONS;

  return (
    <div>
      <div className="flex items-center justify-between mb-2">
        <label className="block text-sm font-semibold text-gray-800">
          Target Operations ({isPdf ? 'PDF Pipeline' : 'Image Pipeline'})
        </label>
        <span className="text-xs text-gray-500">Select one or more</span>
      </div>

      <div className="space-y-2.5">
        {operations.map((op) => {
          const checked = selectedOps.includes(op.id);
          return (
            <label
              key={op.id}
              className={`flex items-start gap-3 p-3.5 rounded-xl border cursor-pointer transition ${
                checked
                  ? 'border-blue-500 bg-blue-50/20'
                  : 'border-gray-200 bg-white hover:bg-gray-50'
              }`}
            >
              <input
                type="checkbox"
                checked={checked}
                onChange={() => onToggleOp(op.id)}
                className="mt-0.5 h-4 w-4 text-blue-600 rounded border-gray-300 focus:ring-blue-500"
              />
              <div className="flex-1">
                <span className="text-sm font-semibold text-gray-900 block">{op.label}</span>
                <span className="text-xs text-gray-500 block mt-0.5">{op.desc}</span>
              </div>
            </label>
          );
        })}
      </div>
    </div>
  );
}
