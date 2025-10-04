import React from 'react';

export const LoadingSpinner: React.FC = () => (
    <div className="relative inline-flex">
        <div className="absolute inset-0 rounded-full bg-gradient-to-r from-cyan-400 to-teal-500 opacity-30 blur-md animate-pulse"></div>
        <svg
            className="animate-spin -ml-1 mr-3 h-10 w-10 relative z-10"
            xmlns="http://www.w3.org/2000/svg"
            fill="none"
            viewBox="0 0 24 24"
        >
            <defs>
                <linearGradient id="spinner-gradient" x1="0%" y1="0%" x2="100%" y2="100%">
                    <stop offset="0%" stopColor="#06b6d4" />
                    <stop offset="100%" stopColor="#14b8a6" />
                </linearGradient>
            </defs>
            <circle
                className="opacity-20"
                cx="12"
                cy="12"
                r="10"
                stroke="url(#spinner-gradient)"
                strokeWidth="3"
            ></circle>
            <path
                className="opacity-90"
                fill="url(#spinner-gradient)"
                d="M4 12a8 8 0 018-8V0C5.373 0 0 5.373 0 12h4zm2 5.291A7.962 7.962 0 014 12H0c0 3.042 1.135 5.824 3 7.938l3-2.647z"
            ></path>
        </svg>
    </div>
);
