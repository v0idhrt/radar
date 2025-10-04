import React from 'react';
import { useState } from 'react';

interface TickerInputProps {
    onSubmit: (ticker: string) => void;
    isLoading: boolean;
}

const TickerInput: React.FC<TickerInputProps> = ({ onSubmit, isLoading }) => {
    const [ticker, setTicker] = useState('');

    const handleSubmit = (e: React.FormEvent) => {
        e.preventDefault();
        if (ticker.trim()) {
            onSubmit(ticker.trim());
        }
    };

    return (
        <div className="max-w-lg mx-auto">
            <h2 className="text-3xl font-extrabold text-white mb-2">Мгновенный мониторинг финансовых новостей</h2>
            <p className="text-lg text-gray-400 mb-8">Введите тикер акции (например, GOOG, TSLA), чтобы начать анализ.</p>
            <form onSubmit={handleSubmit} className="flex items-center justify-center gap-2">
                <input
                    type="text"
                    value={ticker}
                    onChange={(e) => setTicker(e.target.value)}
                    placeholder="Введите тикер акции..."
                    className="w-full max-w-sm bg-gray-800 border-2 border-gray-700 text-white placeholder-gray-500 text-lg rounded-lg focus:ring-cyan-500 focus:border-cyan-500 p-4 transition-colors"
                    disabled={isLoading}
                />
                <button
                    type="submit"
                    className="bg-cyan-600 hover:bg-cyan-500 disabled:bg-gray-600 disabled:cursor-not-allowed text-white font-bold text-lg py-4 px-8 rounded-lg transition-colors"
                    disabled={isLoading}
                >
                    {isLoading ? 'Анализ...' : 'Анализировать'}
                </button>
            </form>
        </div>
    );
};

export default TickerInput;