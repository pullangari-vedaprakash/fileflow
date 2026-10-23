import React from 'react';

export default function LoadingState({ message = 'Loading...' }) {
  return (
    <div className="flex flex-col items-center justify-center py-16">
      <div className="h-8 w-8 animate-spin rounded-full border-4 border-gray-200 border-t-blue-600"></div>
      <p className="mt-3 text-sm text-gray-500 font-medium">{message}</p>
    </div>
  );
}
