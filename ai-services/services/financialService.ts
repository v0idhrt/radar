import { StockPoint, NewsArticle, AnalyzedNews, Sentiment } from '../types';

// API Configuration
const RADAR_API_URL = import.meta.env.VITE_RADAR_API_URL || 'http://localhost:8000';
const FINAM_API_URL = import.meta.env.VITE_FINAM_API_URL || 'http://localhost:8001';

interface CompanyInfo {
  ticker: string;
  company_name: string;
}

export interface TickerSuggestion {
  ticker: string;
  company_name: string;
  exchange?: string;
}

/**
 * Fetch stock data from Radar API (proxied from Finam)
 */
export const fetchStockData = async (ticker: string): Promise<StockPoint[]> => {
  console.log(`Fetching stock data for ${ticker} from Radar API...`);

  try {
    // Получить котировки через Radar API (проксирует Finam)
    const response = await fetch(`${RADAR_API_URL}/api/quotes/${ticker}`);

    if (response.ok) {
      const data = await response.json();
      console.log(`Fetched ${data.quotes?.length || 0} quote points for ${ticker}`);
      return data.quotes || [];
    }

    // Fallback на mock данные
    console.warn('Finam data unavailable, using mock data');
    return generateMockStockData();

  } catch (error) {
    console.error('Error fetching stock data:', error);
    return generateMockStockData();
  }
};

/**
 * Generate mock stock data as fallback
 */
function generateMockStockData(): StockPoint[] {
  const data: StockPoint[] = [];
  let price = 150 + Math.random() * 50;
  const today = new Date();

  for (let i = 60; i >= 0; i--) {
    const date = new Date(today);
    date.setDate(today.getDate() - i);
    price += (Math.random() - 0.5) * 5;
    if (price < 10) price = 10;
    data.push({
      date: date.toISOString().split('T')[0],
      price: parseFloat(price.toFixed(2)),
    });
  }
  return data;
}

/**
 * Fetch impactful anomalies (important events for homepage)
 */
export const fetchImpactfulAnomalies = async (limit: number = 10): Promise<any[]> => {
  try {
    const response = await fetch(`${RADAR_API_URL}/api/anomalies/impactful?limit=${limit}`);

    if (response.ok) {
      const data = await response.json();
      return data.anomalies || [];
    }

    return [];
  } catch (error) {
    console.error('Error fetching impactful anomalies:', error);
    return [];
  }
};

export const fetchAvailableTickers = async (): Promise<TickerSuggestion[]> => {
  try {
    const response = await fetch(`${RADAR_API_URL}/api/tickers`);
    if (!response.ok) {
      throw new Error(`Failed to fetch tickers (${response.status})`);
    }
    const data = await response.json();
    if (!data || !Array.isArray(data.tickers)) {
      return [];
    }
    return data.tickers;
  } catch (error) {
    console.error('Error fetching tickers:', error);
    return [];
  }
};

/**
 * Fetch news from Radar API by ticker
 */
export const fetchRecentNews = async (ticker: string, limit: number = 50): Promise<NewsArticle[]> => {
  console.log(`Fetching news for ${ticker} from Radar API...`);

  try {
    // Calculate date range (last 30 days)
    const endDate = new Date();
    const startDate = new Date();
    startDate.setDate(endDate.getDate() - 30);

    const sanitizedLimit = Math.max(1, Math.min(limit, 100));
    const url = `${RADAR_API_URL}/api/news/ticker/${ticker}?` +
                `start_date=${startDate.toISOString()}&` +
                `end_date=${endDate.toISOString()}&` +
                `limit=${sanitizedLimit}`;

    const response = await fetch(url);

    if (!response.ok) {
      if (response.status === 404) {
        console.warn(`Ticker ${ticker} not found in database`);
        return [];
      }
      throw new Error(`HTTP error! status: ${response.status}`);
    }

    const articles: NewsArticle[] = await response.json();
    console.log(`Fetched ${articles.length} news articles for ${ticker}`);
    return articles;

  } catch (error) {
    console.error('Error fetching news from Radar API:', error);
    // Return empty array instead of failing
    return [];
  }
};

/**
 * Fetch company name for a ticker
 */
export const fetchCompanyInfo = async (ticker: string): Promise<CompanyInfo | null> => {
  console.log(`Fetching company info for ${ticker} from Radar API...`);

  try {
    const response = await fetch(`${RADAR_API_URL}/api/ticker/${ticker}/company`);

    if (!response.ok) {
      if (response.status === 404) {
        console.warn(`Company info not found for ticker ${ticker}`);
        return null;
      }
      throw new Error(`HTTP error! status: ${response.status}`);
    }

    const company: CompanyInfo = await response.json();
    return company;

  } catch (error) {
    console.error('Error fetching company info:', error);
    return null;
  }
};

export type AnalysisWorkerStatus = 'pending' | 'completed' | 'failed';

export interface AnalysisStatus {
  articleId: string;
  status: AnalysisWorkerStatus;
  sentiment?: Sentiment;
  summary?: string;
  error?: string;
  updatedAt: string;
}

interface QueueAnalysisResponse {
  ticker: string;
  queued: number;
  pending: number;
  results: AnalysisStatus[];
}

const mapRawStatus = (raw: any): AnalysisStatus => {
  const sentiment = raw.sentiment as string | undefined;
  let mappedSentiment: Sentiment | undefined;
  if (sentiment === Sentiment.Positive) mappedSentiment = Sentiment.Positive;
  if (sentiment === Sentiment.Negative) mappedSentiment = Sentiment.Negative;
  if (sentiment === Sentiment.Neutral) mappedSentiment = Sentiment.Neutral;

  return {
      articleId: raw.article_id,
      status: raw.status as AnalysisWorkerStatus,
      sentiment: mappedSentiment,
      summary: raw.summary,
      error: raw.error,
      updatedAt: raw.updated_at,
  };
};

export const queueNewsAnalysis = async (
  ticker: string,
  articles: NewsArticle[],
  force: boolean = false
): Promise<QueueAnalysisResponse> => {
  const response = await fetch(`${RADAR_API_URL}/api/analyze/news`, {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({ ticker, force, articles }),
  });

  if (!response.ok) {
    throw new Error(`Failed to queue analysis (${response.status})`);
  }

  const data = await response.json();

  return {
    ticker: data.ticker,
    queued: data.queued,
    pending: data.pending,
    results: Array.isArray(data.results) ? data.results.map(mapRawStatus) : [],
  };
};

export const fetchAnalysisStatus = async (ticker: string, articleIds?: string[]): Promise<AnalysisStatus[]> => {
  const params = new URLSearchParams();
  if (articleIds && articleIds.length > 0) {
    articleIds.forEach(id => params.append('article_ids', id));
  }

  const suffix = params.toString() ? `?${params.toString()}` : '';
  const response = await fetch(`${RADAR_API_URL}/api/analyze/news/${ticker}${suffix}`);

  if (!response.ok) {
    throw new Error(`Failed to fetch analysis status (${response.status})`);
  }

  const data = await response.json();
  return Array.isArray(data) ? data.map(mapRawStatus) : [];
};

export const mergeAnalysisResults = (
  articles: NewsArticle[],
  statuses: Record<string, AnalysisStatus>
): AnalyzedNews[] => {
  return articles
    .map(article => {
      const status = statuses[article.id];
      if (!status || status.status !== 'completed' || !status.sentiment || !status.summary) {
        return null;
      }

      return {
        ...article,
        sentiment: status.sentiment,
        summary: status.summary,
      };
    })
    .filter((item): item is AnalyzedNews => item !== null);
};

/**
 * Generate AI-based price forecast
 */
export const generatePriceForecast = async (
  ticker: string,
  stockData: StockPoint[],
  analyzedNews: AnalyzedNews[]
): Promise<{ forecast: StockPoint[], analysis: string }> => {
  console.log(`Generating forecast for ${ticker} with ${stockData.length} data points and ${analyzedNews.length} analyzed news`);

  try {
    const response = await fetch(`${RADAR_API_URL}/api/forecast/${ticker}`, {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({
        ticker,
        stock_data: stockData,
        analyzed_news: analyzedNews.map(news => ({
          id: news.id,
          headline: news.headline,
          sentiment: news.sentiment,
          summary: news.summary,
          timestamp: news.timestamp
        }))
      })
    });

    if (!response.ok) {
      const error = await response.text();
      throw new Error(`Forecast API error (${response.status}): ${error}`);
    }

    const data = await response.json();

    console.log(`Forecast generated: ${data.forecast.length} points`);

    return {
      forecast: data.forecast,
      analysis: data.analysis
    };

  } catch (error) {
    console.error('Error generating forecast:', error);
    throw error;
  }
};
