// Fix: Implementing the Dashboard component to display all analysis results.
import React, { useState, useMemo } from 'react';
import { StockPoint, AnalyzedNews, SentimentChartData, Sentiment } from '../types';
import StockChart from './StockChart';
import SentimentChart from './SentimentChart';
import NewsList from './NewsList';
import NewsDetail from './NewsDetail';
import AIAnalysisDisplay from './AIAnalysisDisplay';
import ForecastChart from './ForecastChart';
import { LoadingSpinner } from './icons/LoadingSpinner';

interface DashboardProps {
    ticker: string;
    stockData: StockPoint[];
    analyzedNews: AnalyzedNews[];
    isAnalyzingNews: boolean;
    companyName: string | null;
}

const sentimentToScore = (sentiment: Sentiment): number => {
    switch (sentiment) {
        case Sentiment.Positive: return 1;
        case Sentiment.Negative: return -1;
        case Sentiment.Neutral: return 0;
        default: return 0;
    }
};

const Dashboard: React.FC<DashboardProps> = ({ ticker, stockData, analyzedNews, isAnalyzingNews, companyName }) => {
    const [selectedArticle, setSelectedArticle] = useState<AnalyzedNews | null>(null);

    const sentimentChartData = useMemo<SentimentChartData[]>(() => {
        if (!analyzedNews || analyzedNews.length === 0) return [];
        
        const groupedByDate: Record<string, AnalyzedNews[]> = analyzedNews.reduce((acc, article) => {
            const date = new Date(article.timestamp).toISOString().split('T')[0];
            (acc[date] = acc[date] || []).push(article);
            return acc;
        }, {} as Record<string, AnalyzedNews[]>);

        const chartData = Object.entries(groupedByDate).map(([date, articles]) => ({
            date,
            averageSentiment: articles.reduce((sum, art) => sum + sentimentToScore(art.sentiment), 0) / articles.length,
            articles,
        }));

        return chartData.sort((a, b) => new Date(a.date).getTime() - new Date(b.date).getTime());
    }, [analyzedNews]);

    return (
        <div className="space-y-8 animate-fade-in">
            <div>
                <h2 className="text-4xl font-bold text-white">
                    Панель управления для <span className="text-cyan-400">{companyName ?? ticker}</span>
                </h2>
                {companyName && (
                    <p className="text-gray-400 text-lg mt-1">Тикер: {ticker}</p>
                )}
            </div>

            <div className="dashboard-grid grid grid-cols-1 lg:grid-cols-2 gap-8">
                <div className="card-enhanced bg-gray-800/50 p-6 rounded-lg border border-gray-700">
                    <StockChart data={stockData} />
                </div>
                <div className="card-enhanced bg-gray-800/50 p-6 rounded-lg border border-gray-700">
                    {isAnalyzingNews && analyzedNews.length === 0 ? (
                        <div className="flex flex-col items-center justify-center h-full space-y-4 text-center text-gray-400">
                            <LoadingSpinner />
                            <p>ИИ подготавливает анализ настроений...</p>
                        </div>
                    ) : sentimentChartData.length > 0 ? (
                        <SentimentChart data={sentimentChartData} />
                    ) : (
                        <div className="flex items-center justify-center h-full">
                            <p className="text-gray-500">Нет данных о настроениях для отображения.</p>
                        </div>
                    )}
                </div>
            </div>
            
            {isAnalyzingNews && analyzedNews.length === 0 && (
                <div className="bg-gray-800/50 p-6 rounded-lg border border-gray-700 flex flex-col items-center justify-center space-y-4 text-center text-gray-400">
                    <LoadingSpinner />
                    <p>Сводка новостей появится сразу после завершения анализа.</p>
                </div>
            )}

            {analyzedNews.length > 0 && (
                 <div className="space-y-8">
                    <h3 className="text-3xl font-bold text-white border-b border-gray-700 pb-2">Анализ новостей</h3>
                     <div className="grid grid-cols-1 lg:grid-cols-3 gap-8">
                         <div className="lg:col-span-1">
                            <AIAnalysisDisplay analyzedNews={analyzedNews} />
                         </div>
                         <div className="lg:col-span-2">
                            {/* Fix: Pass correct props to ForecastChart component. */}
                            <ForecastChart ticker={ticker} stockData={stockData} analyzedNews={analyzedNews} />
                         </div>
                    </div>
                    <div className="grid grid-cols-1 xl:grid-cols-2 gap-8" style={{minHeight: '500px'}}>
                        <div className="max-h-[500px] overflow-y-auto pr-2 custom-scrollbar">
                            <NewsList 
                                articles={analyzedNews} 
                                onSelectArticle={setSelectedArticle}
                                selectedArticleId={selectedArticle?.id ?? null}
                            />
                        </div>
                        <div className="h-full">
                             <NewsDetail article={selectedArticle} onClearSelection={() => setSelectedArticle(null)} />
                        </div>
                    </div>
                 </div>
            )}
        </div>
    );
};

export default Dashboard;
