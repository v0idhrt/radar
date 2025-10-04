import { analyzeNewsWithOpenRouter, generateForecastWithOpenRouter } from './openrouter';
import { analyzeNewsWithOllama, generateForecastWithOllama } from './ollama';
import { analyzeNewsWithGemini, generateForecastWithGemini } from './gemini';
import { NewsArticle, AnalyzedNews, StockPoint, ForecastData, Sentiment } from '../../types';

const ANALYSIS_BATCH_SIZE = Number(import.meta.env.VITE_ANALYSIS_BATCH_SIZE ?? '1');

const runNewsAnalysisBatch = async (articles: NewsArticle[]): Promise<AnalyzedNews[]> => {
    if (articles.length === 0) {
        return [];
    }

    try {
        console.log(`Attempting analysis with OpenRouter for ${articles.length} article(s)...`);
        return await analyzeNewsWithOpenRouter(articles);
    } catch (error) {
        console.warn("OpenRouter failed, falling back to Ollama:", error);
        try {
            console.log(`Attempting analysis with Ollama for ${articles.length} article(s)...`);
            return await analyzeNewsWithOllama(articles);
        } catch (error) {
            console.warn("Ollama failed, falling back to Gemini:", error);
            try {
                console.log(`Attempting analysis with Gemini for ${articles.length} article(s)...`);
                return await analyzeNewsWithGemini(articles);
            } catch (error) {
                console.error("All LLM providers failed for news analysis:", error);
                return articles.map(article => ({
                    ...article,
                    sentiment: Sentiment.Neutral,
                    summary: `AI analysis failed. (Mock summary)`
                }));
            }
        }
    }
};

// Primary function for news sentiment analysis with batching
export const analyzeNews = async (articles: NewsArticle[]): Promise<AnalyzedNews[]> => {
    const batchSize = Number.isFinite(ANALYSIS_BATCH_SIZE) && ANALYSIS_BATCH_SIZE > 0 ? Math.floor(ANALYSIS_BATCH_SIZE) : 1;
    const effectiveBatchSize = Math.max(1, batchSize);

    const results: AnalyzedNews[] = [];

    for (let i = 0; i < articles.length; i += effectiveBatchSize) {
        const batch = articles.slice(i, i + effectiveBatchSize);
        console.info(`Analyzing batch ${i / effectiveBatchSize + 1} (${batch.length} article(s)) out of ${Math.ceil(articles.length / effectiveBatchSize)}...`);
        const analyzedBatch = await runNewsAnalysisBatch(batch);
        results.push(...analyzedBatch);
    }

    return results;
};

// Primary function for price forecasting with fallback logic
export const generatePriceForecast = async (ticker: string, stockData: StockPoint[], analyzedNews: AnalyzedNews[]): Promise<ForecastData> => {
    try {
        console.log("Attempting forecast generation with OpenRouter...");
        return await generateForecastWithOpenRouter(ticker, stockData, analyzedNews);
    } catch (error) {
        console.warn("OpenRouter forecast failed, falling back to Ollama:", error);
        try {
            console.log("Attempting forecast generation with Ollama...");
            return await generateForecastWithOllama(ticker, stockData, analyzedNews);
        } catch (error) {
            console.warn("Ollama forecast failed, falling back to Gemini:", error);
            try {
                console.log("Attempting forecast generation with Gemini...");
                return await generateForecastWithGemini(ticker, stockData, analyzedNews);
            } catch (error) {
                console.error("Forecast generation failed with all available providers:", error);
                throw new Error("Failed to generate forecast.");
            }
        }
    }
};
