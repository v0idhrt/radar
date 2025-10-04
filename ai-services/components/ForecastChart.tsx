import React, { useState } from 'react';
import { StockPoint, AnalyzedNews, ForecastData } from '../types';
import { generatePriceForecast } from '../services/financialService';
import { ComposedChart, Line, XAxis, YAxis, CartesianGrid, Tooltip, Legend, ResponsiveContainer, Area } from 'recharts';
import { LoadingSpinner } from './icons/LoadingSpinner';

interface ForecastChartProps {
  ticker: string;
  stockData: StockPoint[];
  analyzedNews: AnalyzedNews[];
}

const ForecastChart: React.FC<ForecastChartProps> = ({ ticker, stockData, analyzedNews }) => {
    const [forecastData, setForecastData] = useState<ForecastData | null>(null);
    const [isForecasting, setIsForecasting] = useState(false);
    const [error, setError] = useState<string | null>(null);

    const handleGenerateForecast = async () => {
        setIsForecasting(true);
        setError(null);
        setForecastData(null);
        try {
            const result = await generatePriceForecast(ticker, stockData, analyzedNews);
            setForecastData(result);
        } catch (err) {
            setError(err instanceof Error ? err.message : "Не удалось сгенерировать прогноз. Пожалуйста, попробуйте снова.");
            console.error(err);
        } finally {
            setIsForecasting(false);
        }
    };
    
    // Fix: Explicitly type combinedData to allow for the 'forecastPrice' property, preventing a TypeScript error.
    const combinedData: (StockPoint & { forecastPrice?: number })[] = forecastData
        ? [...stockData, ...forecastData.forecast.map(p => ({ ...p, forecastPrice: p.price }))]
        : stockData;
        
    if (forecastData && stockData.length > 0) {
        const lastHistoricPoint = stockData[stockData.length - 1];
        const firstForecastPoint = forecastData.forecast[0];
        // Ensure seamless connection
        combinedData[stockData.length] = { ...firstForecastPoint, price: lastHistoricPoint.price, forecastPrice: firstForecastPoint.price };
    }


    return (
        <div className="bg-gray-800/50 p-6 rounded-lg border border-gray-700 h-full flex flex-col">
            <h3 className="text-xl font-semibold text-white mb-4">Прогноз на базе ИИ</h3>

            {!forecastData && !isForecasting && (
                <div className="flex-grow flex flex-col items-center justify-center text-center">
                    <svg xmlns="http://www.w3.org/2000/svg" className="mx-auto h-12 w-12 text-cyan-500" fill="none" viewBox="0 0 24 24" stroke="currentColor">
                        <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M9.663 17h4.673M12 3v1m6.364 1.636l-.707.707M21 12h-1M4 12H3m3.343-5.657l-.707-.707m2.828 9.9a5 5 0 117.072 0l-.548.547A3.374 3.374 0 0014 18.469V19a2 2 0 11-4 0v-.531c0-.895-.356-1.754-.988-2.386l-.548-.547z" />
                    </svg>
                    <p className="mt-2 font-semibold">Получите 7-дневный прогноз цен на акции.</p>
                    <button
                        onClick={handleGenerateForecast}
                        className="mt-4 bg-cyan-600 hover:bg-cyan-500 text-white font-bold py-2 px-6 rounded-lg transition-colors"
                    >
                        Сгенерировать AI-прогноз
                    </button>
                </div>
            )}

            {isForecasting && (
                <div className="flex-grow flex flex-col items-center justify-center space-y-4">
                    <LoadingSpinner />
                    <p className="text-lg text-gray-400">AI генерирует прогноз...</p>
                </div>
            )}
            
            {error && <p className="flex-grow flex items-center justify-center text-center text-red-500">{error}</p>}

            {forecastData && (
                <div className="space-y-4">
                    <ResponsiveContainer width="100%" height={250}>
                        <ComposedChart data={combinedData}>
                             <defs>
                                <linearGradient id="colorPrice" x1="0" y1="0" x2="0" y2="1">
                                    <stop offset="5%" stopColor="#2DD4BF" stopOpacity={0.8}/>
                                    <stop offset="95%" stopColor="#2DD4BF" stopOpacity={0}/>
                                </linearGradient>
                            </defs>
                            <CartesianGrid strokeDasharray="3 3" stroke="#4A5568" />
                            <XAxis dataKey="date" stroke="#A0AEC0" tick={{ fontSize: 12 }} />
                            <YAxis stroke="#A0AEC0" tick={{ fontSize: 12 }} domain={['auto', 'auto']} allowDataOverflow={true} />
                            <Tooltip
                                contentStyle={{ backgroundColor: '#1A202C', border: '1px solid #4A5568' }}
                                labelStyle={{ color: '#E2E8F0' }}
                            />
                            <Legend wrapperStyle={{ color: '#E2E8F0' }} />
                            <Area type="monotone" dataKey="price" name="Историческая цена" stroke="#2DD4BF" fill="url(#colorPrice)" />
                            <Line type="monotone" dataKey="forecastPrice" name="Прогноз" stroke="#A78BFA" strokeWidth={2} strokeDasharray="5 5" />
                        </ComposedChart>
                    </ResponsiveContainer>
                    <div>
                        <h4 className="font-semibold text-white mb-2">Обоснование прогноза от AI:</h4>
                        <p className="text-sm text-gray-300 italic p-3 bg-gray-900/50 rounded-md border-l-4 border-cyan-500">{forecastData.analysis}</p>
                    </div>
                     <p className="text-xs text-center text-gray-500 pt-2">
                        <strong>Дисклеймер:</strong> Этот прогноз сгенерирован ИИ и не является финансовой рекомендацией. Всегда проводите собственное исследование.
                    </p>
                </div>
            )}
        </div>
    );
};

export default ForecastChart;
