import React, { useMemo, useState } from 'react';
import { TickerSuggestion } from '../services/financialService';

interface TickerInputProps {
    onSubmit: (value: string) => void | Promise<void>;
    isLoading: boolean;
    suggestions: TickerSuggestion[];
}

const TickerInput: React.FC<TickerInputProps> = ({ onSubmit, isLoading, suggestions }) => {
    const [query, setQuery] = useState('');
    const [isFocused, setIsFocused] = useState(false);

    const filteredSuggestions = useMemo(() => {
        if (!suggestions?.length) return [];
        const trimmed = query.trim().toLowerCase();
        if (!trimmed) {
            return suggestions.slice(0, 8);
        }
        return suggestions
            .filter(item =>
                item.ticker.toLowerCase().includes(trimmed) ||
                item.company_name.toLowerCase().includes(trimmed)
            )
            .slice(0, 8);
    }, [query, suggestions]);

    const handleSubmit = async (e: React.FormEvent) => {
        e.preventDefault();
        if (!query.trim()) return;
        await onSubmit(query.trim());
    };

    const handleSuggestionClick = async (suggestion: TickerSuggestion) => {
        setQuery(suggestion.ticker);
        await onSubmit(suggestion.ticker);
        setIsFocused(false);
    };

    const hasSuggestions = isFocused && filteredSuggestions.length > 0;

    const placeholder = suggestions.length
        ? 'Начните вводить название компании или тикер...'
        : 'Введите тикер акции...';

    const handleBlur = () => {
        setTimeout(() => setIsFocused(false), 120);
    };

    const handleFocus = () => {
        setIsFocused(true);
    };

    return (
        <div className="max-w-4xl mx-auto">
            <div className="text-center mb-10 animate-fade-in">
                <h2 className="text-4xl font-extrabold text-white mb-3 tracking-tight">
                    Мгновенный мониторинг финансовых новостей
                </h2>
                <p className="text-lg text-gray-400">
                    Введите название компании или тикер, затем выберите подходящую подсказку.
                </p>
            </div>

            <form onSubmit={handleSubmit}>
                <div className="flex flex-col sm:flex-row items-stretch gap-3">
                    <div className="flex-1 relative">
                        <div className="absolute inset-y-0 left-4 flex items-center pointer-events-none z-10">
                            <svg className="w-5 h-5 text-gray-500" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                                <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M21 21l-6-6m2-5a7 7 0 11-14 0 7 7 0 0114 0z" />
                            </svg>
                        </div>
                        <input
                            type="text"
                            value={query}
                            onChange={(e) => setQuery(e.target.value)}
                            onFocus={handleFocus}
                            onBlur={handleBlur}
                            placeholder={placeholder}
                            className="input-enhanced w-full bg-gray-800/80 border-2 border-gray-700 text-white placeholder-gray-500 text-base rounded-xl focus:ring-2 focus:ring-cyan-500 focus:border-transparent py-4 pl-12 pr-4 backdrop-blur-sm"
                            disabled={isLoading}
                            aria-autocomplete="list"
                            aria-expanded={hasSuggestions}
                            aria-controls="ticker-suggestions"
                        />

                        {hasSuggestions && (
                            <div
                                id="ticker-suggestions"
                                className="glass-effect animate-scale-in absolute top-full left-0 right-0 mt-3 bg-gray-900/98 border border-gray-700/50 rounded-xl shadow-2xl shadow-cyan-500/10 z-50"
                            >
                                <ul className="max-h-72 overflow-y-auto custom-scrollbar p-2">
                                    {filteredSuggestions.map((item) => (
                                        <li key={item.ticker}>
                                            <button
                                                type="button"
                                                onMouseDown={(event) => event.preventDefault()}
                                                onClick={() => handleSuggestionClick(item)}
                                                className="ripple w-full text-left px-4 py-3 hover:bg-gradient-to-r hover:from-cyan-900/30 hover:to-teal-900/30 rounded-lg transition-all group"
                                            >
                                                <div className="flex items-center justify-between">
                                                    <div className="flex-1">
                                                        <span className="block text-white font-semibold group-hover:text-cyan-400 transition-colors">
                                                            {item.company_name}
                                                        </span>
                                                        <span className="text-sm text-gray-500 group-hover:text-gray-400 transition-colors">
                                                            {item.ticker}
                                                        </span>
                                                    </div>
                                                    <svg className="w-4 h-4 text-gray-600 group-hover:text-cyan-500 transition-colors" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                                                        <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M9 5l7 7-7 7" />
                                                    </svg>
                                                </div>
                                            </button>
                                        </li>
                                    ))}
                                </ul>
                            </div>
                        )}
                    </div>
                    <button
                        type="submit"
                        className="btn-glow relative overflow-hidden bg-gradient-to-r from-cyan-600 to-teal-600 hover:from-cyan-500 hover:to-teal-500 disabled:from-gray-600 disabled:to-gray-700 disabled:cursor-not-allowed text-white font-semibold text-base py-4 px-10 rounded-xl transition-all transform hover:scale-105 active:scale-95 shadow-lg shadow-cyan-500/30"
                        disabled={isLoading}
                    >
                        <span className="relative z-10 flex items-center gap-2">
                            {isLoading ? (
                                <>
                                    <svg className="animate-spin h-5 w-5" fill="none" viewBox="0 0 24 24">
                                        <circle className="opacity-25" cx="12" cy="12" r="10" stroke="currentColor" strokeWidth="4"></circle>
                                        <path className="opacity-75" fill="currentColor" d="M4 12a8 8 0 018-8V0C5.373 0 0 5.373 0 12h4zm2 5.291A7.962 7.962 0 014 12H0c0 3.042 1.135 5.824 3 7.938l3-2.647z"></path>
                                    </svg>
                                    Анализ...
                                </>
                            ) : (
                                <>
                                    <svg className="w-5 h-5" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                                        <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M13 10V3L4 14h7v7l9-11h-7z" />
                                    </svg>
                                    Анализировать
                                </>
                            )}
                        </span>
                    </button>
                </div>
            </form>
        </div>
    );
};

export default TickerInput;
