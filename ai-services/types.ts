// Fix: Defining all the necessary types for the application.
export interface StockPoint {
  date: string;
  price: number;
}

export interface NewsArticle {
  id: string;
  headline: string;
  content: string;
  source: string;
  timestamp: number;
  url: string;
}

export enum Sentiment {
  Positive = 'Positive',
  Negative = 'Negative',
  Neutral = 'Neutral',
}

export interface AnalyzedNews extends NewsArticle {
  sentiment: Sentiment;
  summary: string;
}

export interface SentimentChartData {
  date: string;
  averageSentiment: number;
  articles: AnalyzedNews[];
}

export interface ForecastPoint {
    date: string;
    price: number;
}

export interface ForecastData {
    forecast: ForecastPoint[];
    analysis: string;
}