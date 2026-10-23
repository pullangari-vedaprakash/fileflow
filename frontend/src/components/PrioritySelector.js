import React from 'react';

const PRIORITIES = [
  {
    id: 'HIGH',
    label: 'High Priority',
    desc: 'Weight 100 • Processed immediately',
    badge: 'Fast-Track',
    borderColor: 'border-blue-500 bg-blue-50/30 ring-1 ring-blue-500',
  },
  {
    id: 'NORMAL',
    label: 'Normal Priority',
    desc: 'Weight 50 • Standard processing queue',
    badge: 'Balanced',
    borderColor: 'border-blue-500 bg-blue-50/30 ring-1 ring-blue-500',
  },
  {
    id: 'LOW',
    label: 'Low Priority',
    desc: 'Weight 20 • Linear aging + starvation protection',
    badge: 'Aged Fairness',
    borderColor: 'border-blue-500 bg-blue-50/30 ring-1 ring-blue-500',
  },
];

export default function PrioritySelector({ selected, onChange }) {
  return (
    <div>
      <label className="block text-sm font-semibold text-gray-800 mb-2">
        Execution Priority
      </label>
      <div className="grid grid-cols-1 sm:grid-cols-3 gap-3">
        {PRIORITIES.map((p) => {
          const isSelected = selected === p.id;
          return (
            <div
              key={p.id}
              onClick={() => onChange(p.id)}
              className={`cursor-pointer rounded-xl border p-4 transition-all duration-150 ${
                isSelected ? p.borderColor : 'border-gray-200 bg-white hover:border-gray-300'
              }`}
            >
              <div className="flex items-center justify-between mb-1">
                <span className={`text-sm font-bold ${isSelected ? 'text-blue-900' : 'text-gray-900'}`}>
                  {p.label}
                </span>
                <span className="text-[10px] font-semibold px-2 py-0.5 rounded bg-gray-100 text-gray-600">
                  {p.badge}
                </span>
              </div>
              <p className="text-xs text-gray-500 leading-normal">{p.desc}</p>
            </div>
          );
        })}
      </div>
    </div>
  );
}
