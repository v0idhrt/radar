import { NewsArticle, AnalyzedNews, Sentiment, StockPoint, ForecastData } from '../../types';

const API_KEY = process.env.OPENROUTER_API_KEY;
const OPENROUTER_API_URL = 'https://openrouter.ai/api/v1';

export const analyzeNewsWithOpenRouter = async (articles: NewsArticle[]): Promise<AnalyzedNews[]> => {
    if (!API_KEY) throw new Error("OPENROUTER_API_KEY is not set.");

    const articlesForPrompt = articles.map(({ id, headline, content }) => ({ id, headline, content: content.substring(0, 500) }));
    const prompt = `Analyze the sentiment of the following financial news articles. For each article, provide its original 'id', 'sentiment' (one of: 'Positive', 'Negative', 'Neutral'), and a brief 'summary' in Russian.\nArticles JSON:\n${JSON.stringify(articlesForPrompt)}\nRespond ONLY with a valid JSON array.`;

    try {
        const response = await fetch(`${OPENROUTER_API_URL}/chat/completions`, {
            method: 'POST',
            headers: {
                'Content-Type': 'application/json',
                'Authorization': `Bearer ${API_KEY}`,
                'HTTP-Referer': 'http://localhost:3000', // Example referrer
                'X-Title': 'Financial News Analyzer' // Example title
            },
            body: JSON.stringify({
                model: process.env.OPENROUTER_MODEL || 'google/gemma-2-9b-it',
                messages: [{ role: 'user', content: prompt }],
                response_format: { type: "json_object" },
            })
        });

        if (!response.ok) {
            const errorBody = await response.text();
            throw new Error(`OpenRouter API request failed with status ${response.status}: ${errorBody}`);
        }

        const result = await response.json();
        const analysisResults = JSON.parse(result.choices[0].message.content);
        
        const articlesById = new Map(articles.map(article => [article.id, article]));

        return analysisResults.map((result: any) => {
            const originalArticle = articlesById.get(result.id);
            if (!originalArticle) return null;
            return { ...originalArticle, sentiment: result.sentiment, summary: result.summary };
        }).filter((article: AnalyzedNews | null): article is AnalyzedNews => article !== null);

    } catch (error) {
        console.error("Error analyzing news with OpenRouter:", error);
        throw new Error("Failed to analyze news with OpenRouter.");
    }
};

export const generateForecastWithOpenRouter = async (ticker: string, stockData: StockPoint[], analyzedNews: AnalyzedNews[]): Promise<ForecastData> => {
    if (!API_KEY) throw new Error("OPENROUTER_API_KEY is not set.");

    const recentStockData = stockData.slice(-30);
    const recentNews = analyzedNews.slice(0, 15);

    const prompt = `
        Act as a senior financial analyst. Based on the provided historical stock price data and recent news analysis for ticker ${ticker}, generate a 7-day price forecast.
        Historical Data (last 30 days):
        ${JSON.stringify(recentStockData)}
        Recent News Analysis:
        ${JSON.stringify(recentNews.map(n => ({ headline: n.headline, sentiment: n.sentiment, summary: n.summary })))}
        Your task:
        1. Analyze the price trend, volatility, and news sentiment.
        2. Generate a daily price forecast for the next 7 days.
        3. Provide a brief, insightful text analysis (2-3 sentences) in Russian explaining your forecast's logic.
        Respond ONLY with a valid JSON object with keys "forecast" (an array of 7 objects with date and price) and "analysis" (a string).
    `;

    try {
        const response = await fetch(`${OPENROUTER_API_URL}/chat/completions`, {
            method: 'POST',
            headers: {
                'Content-Type': 'application/json',
                'Authorization': `Bearer ${API_KEY}`,
            },
            body: JSON.stringify({
                model: process.env.OPENROUTER_MODEL || 'google/gemma-2-9b-it',
                messages: [{ role: 'user', content: prompt }],
                response_format: { type: "json_object" },
            })
        });

        if (!response.ok) {
            const errorBody = await response.text();
            throw new Error(`OpenRouter API forecast request failed with status ${response.status}: ${errorBody}`);
        }

        const result = await response.json();
        const forecastResult: ForecastData = JSON.parse(result.choices[0].message.content);

        if (!forecastResult.forecast || forecastResult.forecast.length !== 7 || !forecastResult.analysis) {
            throw new Error("Invalid forecast data structure from AI.");
        }

        return forecastResult;

    } catch (error) {
        console.error("Error generating forecast with OpenRouter:", error);
        throw new Error("Failed to generate forecast with OpenRouter.");
    }
};
