
import { GoogleGenAI, Type } from "@google/genai";
import { NewsArticle, AnalyzedNews, Sentiment, StockPoint, ForecastData } from '../../types';

const API_KEY = process.env.GEMINI_API_KEY;

function isSentiment(value: string): value is Sentiment {
    return Object.values(Sentiment).includes(value as Sentiment);
}

const analysisSchema = {
    type: Type.ARRAY,
    items: {
      type: Type.OBJECT,
      properties: {
        id: { type: Type.STRING },
        sentiment: { type: Type.STRING, enum: Object.values(Sentiment) },
        summary: { type: Type.STRING },
      },
      required: ["id", "sentiment", "summary"],
    },
};

const forecastSchema = {
    type: Type.OBJECT,
    properties: {
        forecast: {
            type: Type.ARRAY,
            items: {
                type: Type.OBJECT,
                properties: {
                    date: { type: Type.STRING },
                    price: { type: Type.NUMBER },
                },
                required: ["date", "price"],
            },
        },
        analysis: { type: Type.STRING },
    },
    required: ["forecast", "analysis"],
};

export const analyzeNewsWithGemini = async (articles: NewsArticle[]): Promise<AnalyzedNews[]> => {
    if (!API_KEY) throw new Error("GEMINI_API_KEY is not set.");
    if (!articles || articles.length === 0) return [];

    const ai = new GoogleGenAI({ apiKey: API_KEY });
    const prompt = `Analyze the sentiment of the following financial news articles. For each article, provide its original 'id', 'sentiment' (one of: 'Positive', 'Negative', 'Neutral'), and a brief 'summary' in Russian.
    Articles JSON:
    ${JSON.stringify(articles.map(a => ({ id: a.id, headline: a.headline, content: a.content.substring(0, 500) })))}
    Respond ONLY with a valid JSON array.`;

    try {
        const response = await ai.models.generateContent({
            model: process.env.GEMINI_MODEL || "gemini-1.5-flash",
            contents: prompt,
            config: {
                responseMimeType: "application/json",
                responseSchema: analysisSchema,
            },
        });

        const analysisResults: { id: string; sentiment: string; summary: string }[] = JSON.parse(response.text.trim());
        const articlesById = new Map(articles.map(article => [article.id, article]));

        return analysisResults.map(result => {
            const originalArticle = articlesById.get(result.id);
            if (!originalArticle) return null;
            const sentiment = isSentiment(result.sentiment) ? result.sentiment : Sentiment.Neutral;
            return { ...originalArticle, sentiment, summary: result.summary };
        }).filter((article): article is AnalyzedNews => article !== null);

    } catch (error) {
        console.error("Error analyzing news with Gemini:", error);
        throw new Error("Failed to analyze news with Gemini.");
    }
};

export const generateForecastWithGemini = async (ticker: string, stockData: StockPoint[], analyzedNews: AnalyzedNews[]): Promise<ForecastData> => {
    if (!API_KEY) throw new Error("GEMINI_API_KEY is not set.");

    const ai = new GoogleGenAI({ apiKey: API_KEY });
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
        Respond ONLY with a valid JSON object.`;

    try {
        const response = await ai.models.generateContent({
            model: process.env.GEMINI_MODEL || "gemini-1.5-flash",
            contents: prompt,
            config: {
                responseMimeType: "application/json",
                responseSchema: forecastSchema,
            },
        });

        const forecastResult: ForecastData = JSON.parse(response.text.trim());
        if (!forecastResult.forecast || forecastResult.forecast.length !== 7 || !forecastResult.analysis) {
            throw new Error("Invalid forecast data structure from AI.");
        }
        return forecastResult;
    } catch (error) {
        console.error("Error generating forecast with Gemini:", error);
        throw new Error("Failed to generate forecast with Gemini.");
    }
};
