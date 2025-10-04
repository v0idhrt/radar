import React, { useState, useCallback, useEffect } from 'react';
import { StockPoint, AnalyzedNews, NewsArticle } from './types';
import {
    fetchStockData,
    fetchRecentNews,
    fetchImpactfulAnomalies,
    fetchCompanyInfo,
    queueNewsAnalysis,
    fetchAnalysisStatus,
    mergeAnalysisResults,
    AnalysisStatus,
    fetchAvailableTickers,
    TickerSuggestion,
} from './services/financialService';
import TickerInput from './components/TickerInput';
import Dashboard from './components/Dashboard';
import ImpactfulNews from './components/ImpactfulNews';
import { LoadingSpinner } from './components/icons/LoadingSpinner';

const App: React.FC = () => {
    const [ticker, setTicker] = useState<string | null>(null);
    const [companyName, setCompanyName] = useState<string | null>(null);
    const [stockData, setStockData] = useState<StockPoint[]>([]);
    const [newsArticles, setNewsArticles] = useState<NewsArticle[]>([]);
    const [analyzedNews, setAnalyzedNews] = useState<AnalyzedNews[]>([]);
    const [isLoading, setIsLoading] = useState(false);
    const [isAnalyzingNews, setIsAnalyzingNews] = useState(false);
    const [error, setError] = useState<string | null>(null);
    const [impactfulAnomalies, setImpactfulAnomalies] = useState<any[]>([]);
    const [analysisStatuses, setAnalysisStatuses] = useState<Record<string, AnalysisStatus>>({});
    const [availableTickers, setAvailableTickers] = useState<TickerSuggestion[]>([]);

    const mergeStatusMap = useCallback((prev: Record<string, AnalysisStatus>, updates: AnalysisStatus[]) => {
        if (!updates.length) return prev;
        const next = { ...prev };
        updates.forEach(status => {
            next[status.articleId] = status;
        });
        return next;
    }, []);

    const resolveTicker = useCallback((input: string) => {
        const trimmed = input.trim();
        if (!trimmed) {
            return null;
        }

        const upper = trimmed.toUpperCase();
        const suggestions = availableTickers;

        const direct = suggestions.find(item => item.ticker.toUpperCase() === upper);
        if (direct) {
            return direct;
        }

        if (!upper.includes('@')) {
            const withSuffix = `${upper}@MISX`;
            const bySuffix = suggestions.find(item => item.ticker.toUpperCase() === withSuffix);
            if (bySuffix) {
                return bySuffix;
            }
        }

        const byCompany = suggestions.find(item => item.company_name.toLowerCase() === trimmed.toLowerCase());
        if (byCompany) {
            return byCompany;
        }

        const partialCompany = suggestions.find(item => item.company_name.toLowerCase().includes(trimmed.toLowerCase()));
        if (partialCompany) {
            return partialCompany;
        }

        return null;
    }, [availableTickers]);

    const handleTickerSubmit = useCallback(async (submittedTicker: string) => {
        setIsLoading(true);
        setIsAnalyzingNews(false);
        setError(null);
        const resolved = resolveTicker(submittedTicker);
        if (!resolved) {
            setIsLoading(false);
            setError('Не удалось найти тикер для введённого значения. Попробуйте выбрать из списка.');
            return;
        }

        const upperTicker = resolved.ticker.toUpperCase();
        setTicker(upperTicker);
        setStockData([]);
        setNewsArticles([]);
        setAnalyzedNews([]);
        setCompanyName(resolved.company_name ?? null);
        setAnalysisStatuses({});

        try {
            const [company, stock, rawNews] = await Promise.all([
                fetchCompanyInfo(upperTicker),
                fetchStockData(upperTicker),
                fetchRecentNews(upperTicker, 10),
            ]);

            if (company?.company_name) {
                setCompanyName(company.company_name);
            }

            setStockData(stock);
            setIsLoading(false);

            if (!rawNews || rawNews.length === 0) {
                setIsAnalyzingNews(false);
                return;
            }

            setNewsArticles(rawNews);
            const queueResponse = await queueNewsAnalysis(upperTicker, rawNews);
            const initialMap: Record<string, AnalysisStatus> = {};
            queueResponse.results.forEach(status => {
                initialMap[status.articleId] = status;
            });
            setAnalysisStatuses(initialMap);
            setIsAnalyzingNews(queueResponse.pending > 0);

        } catch (err) {
            console.error("Failed to fetch or analyze data:", err);
            setError("Failed to retrieve and analyze data. Please try again.");
            setIsAnalyzingNews(false);
        } finally {
            setIsLoading(false);
        }
    }, [resolveTicker, mergeStatusMap]);

    // Polling для важных аномалий
    useEffect(() => {
        const loadAnomalies = async () => {
            const anomalies = await fetchImpactfulAnomalies(10);
            setImpactfulAnomalies(anomalies);
        };

        // Загрузить сразу
        loadAnomalies();

        // Обновлять каждые 5 секунд
        const interval = setInterval(loadAnomalies, 5000);

        return () => clearInterval(interval);
    }, []);

    useEffect(() => {
        const loadTickers = async () => {
            const tickers = await fetchAvailableTickers();
            setAvailableTickers(tickers);
        };
        loadTickers();
    }, []);

    const handleAnomalyClick = useCallback((ticker: string) => {
        handleTickerSubmit(ticker);
    }, [handleTickerSubmit]);

    useEffect(() => {
        if (!ticker || newsArticles.length === 0) {
            setAnalyzedNews([]);
            return;
        }

        setAnalyzedNews(mergeAnalysisResults(newsArticles, analysisStatuses));
    }, [ticker, newsArticles, analysisStatuses]);

    useEffect(() => {
        if (!ticker || !isAnalyzingNews || newsArticles.length === 0) {
            return;
        }

        let cancelled = false;

        const poll = async () => {
            try {
                const statuses = await fetchAnalysisStatus(ticker);
                if (cancelled) {
                    return;
                }
                setAnalysisStatuses(prev => {
                    const next = mergeStatusMap(prev, statuses);
                    const hasPending = newsArticles.some(article => {
                        const status = next[article.id];
                        return !status || status.status === 'pending';
                    });

                    if (!hasPending) {
                        setIsAnalyzingNews(false);
                    }

                    return next;
                });
            } catch (pollError) {
                console.error('Failed to poll analysis status:', pollError);
            }
        };

        poll();
        const interval = setInterval(poll, 2000);

        return () => {
            cancelled = true;
            clearInterval(interval);
        };
    }, [ticker, isAnalyzingNews, newsArticles, mergeStatusMap]);

    return (
        <div className="bg-gray-900 min-h-screen text-white font-sans">
            <header className="py-8 text-center border-b border-gray-800 animate-fade-in">
                <div className="container mx-auto px-4">
                     <h1 className="shimmer-text text-5xl font-bold tracking-tight mb-2">
                        РАДАР: Анализ финансовых новостей
                    </h1>
                     <p className="text-xl text-gray-400">Анализ настроений в новостях на базе ИИ</p>
                </div>
            </header>
            <main className="container mx-auto p-4 md:p-8">
                <section id="input-section" className="mb-12 text-center">
                    <TickerInput
                        onSubmit={handleTickerSubmit}
                        isLoading={isLoading || isAnalyzingNews}
                        suggestions={availableTickers}
                    />
                </section>

                {/* Важные события - показывать всегда если есть данные */}
                {!isLoading && impactfulAnomalies.length > 0 && (
                    <div className={ticker ? "mb-8 animate-fade-in" : "animate-fade-in"}>
                        <ImpactfulNews
                            anomalies={impactfulAnomalies}
                            onTickerClick={handleAnomalyClick}
                            compact={!!ticker}
                        />
                    </div>
                )}

                {isLoading && (
                    <div className="flex flex-col items-center justify-center space-y-4">
                        <LoadingSpinner />
                        <p className="text-lg text-gray-400">Анализ данных... Это может занять несколько секунд.</p>
                    </div>
                )}

                {!isLoading && isAnalyzingNews && (
                    <div className="flex flex-col items-center justify-center space-y-3 mb-10">
                        <LoadingSpinner />
                        <p className="text-lg text-gray-400 text-center">
                            ИИ анализирует новости для {companyName ?? ticker}. Вы можете изучать графики и ждать результатов.
                        </p>
                    </div>
                )}
                
                {error && <p className="text-center text-red-500 text-lg">{error}</p>}

                {!isLoading && !error && ticker && stockData.length > 0 && (
                    <Dashboard
                        ticker={ticker}
                        companyName={companyName}
                        stockData={stockData}
                        analyzedNews={analyzedNews}
                        isAnalyzingNews={isAnalyzingNews}
                    />
                )}

                {!isLoading && !ticker && (
                    <div className="text-center text-gray-500">
                        <p>Начните с ввода тикера акции для получения анализа.</p>
                    </div>
                )}
            </main>
        </div>
    );
};

export default App;
