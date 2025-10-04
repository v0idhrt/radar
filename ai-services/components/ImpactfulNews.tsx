import React from 'react';

interface Anomaly {
  id: number;
  ticker: string;
  company_name: string;
  z_score: number;
  delta: number;
  direction: string;
  price: number;
  timestamp: string;
  timeframe: string;
  news_count: number;
  top_news: {
    headline: string;
    url: string;
    source: string;
  } | null;
}

interface ImpactfulNewsProps {
  anomalies: Anomaly[];
  onTickerClick: (ticker: string) => void;
  compact?: boolean;
}

const ImpactfulNews: React.FC<ImpactfulNewsProps> = ({ anomalies, onTickerClick, compact = false }) => {
  if (!anomalies || anomalies.length === 0) {
    return null;
  }

  const getDirectionBadge = (direction: string, z_score: number, isCompact: boolean = false) => {
    const isBuy = direction === 'buy';
    const absScore = Math.abs(z_score).toFixed(1);

    if (isCompact) {
      return (
        <span className={`text-lg ${isBuy ? 'text-green-400' : 'text-red-400'}`}>
          {isBuy ? '🟢' : '🔴'}
        </span>
      );
    }

    return (
      <div className={`flex items-center gap-2 px-3 py-1 rounded-full text-sm font-semibold ${
        isBuy ? 'bg-green-500/20 text-green-400' : 'bg-red-500/20 text-red-400'
      }`}>
        <span>{isBuy ? '🟢' : '🔴'}</span>
        <span>{isBuy ? 'BUY' : 'SELL'}</span>
        <span className="text-xs opacity-75">Z: {absScore}</span>
      </div>
    );
  };

  const formatTimestamp = (timestamp: string) => {
    const date = new Date(timestamp);
    const now = new Date();
    const diffMs = now.getTime() - date.getTime();
    const diffMins = Math.floor(diffMs / 60000);

    if (diffMins < 60) return `${diffMins}м назад`;
    if (diffMins < 1440) return `${Math.floor(diffMins / 60)}ч назад`;
    return date.toLocaleDateString('ru-RU');
  };

  // Компактный режим - горизонтальная прокрутка
  if (compact) {
    return (
      <div className="mb-8 glass-effect bg-gray-800/40 border border-gray-700/50 rounded-2xl p-6 animate-fade-in">
        <div className="flex items-center justify-between mb-5">
          <div className="flex items-center gap-3">
            <div className="flex items-center justify-center w-10 h-10 bg-gradient-to-br from-yellow-500 to-orange-500 rounded-xl">
              <svg className="w-6 h-6 text-white" fill="currentColor" viewBox="0 0 20 20">
                <path d="M11 3a1 1 0 10-2 0v1a1 1 0 102 0V3zM15.657 5.757a1 1 0 00-1.414-1.414l-.707.707a1 1 0 001.414 1.414l.707-.707zM18 10a1 1 0 01-1 1h-1a1 1 0 110-2h1a1 1 0 011 1zM5.05 6.464A1 1 0 106.464 5.05l-.707-.707a1 1 0 00-1.414 1.414l.707.707zM5 10a1 1 0 01-1 1H3a1 1 0 110-2h1a1 1 0 011 1zM8 16v-1h4v1a2 2 0 11-4 0zM12 14c.015-.34.208-.646.477-.859a4 4 0 10-4.954 0c.27.213.462.519.476.859h4.002z" />
              </svg>
            </div>
            <div>
              <h3 className="text-xl font-bold text-white">Горячие новости</h3>
              <div className="flex items-center gap-2 mt-1">
                <div className="flex items-center gap-1">
                  <div className="w-2 h-2 bg-green-500 rounded-full animate-pulse"></div>
                  <span className="text-xs text-gray-400">Обновляется каждые 30 секунд</span>
                </div>
              </div>
            </div>
          </div>
          <div className="hidden sm:flex items-center gap-2 text-xs text-gray-500">
            <svg className="w-4 h-4" fill="none" stroke="currentColor" viewBox="0 0 24 24">
              <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M13 5l7 7-7 7M5 5l7 7-7 7" />
            </svg>
            <span>Прокрутите →</span>
          </div>
        </div>

        <div className="flex gap-4 overflow-x-auto pb-3 -mx-2 px-2 custom-scrollbar">
          {anomalies.slice(0, 10).map((anomaly, index) => (
            <div
              key={anomaly.id}
              onClick={() => onTickerClick(anomaly.ticker.replace('@MISX', ''))}
              className="hot-news-card anomaly-card flex-shrink-0 w-72 bg-gradient-to-br from-gray-800/80 to-gray-900/80 border border-gray-700/50 rounded-xl p-4 cursor-pointer hover:border-cyan-500/50 transition-all"
              style={{ animationDelay: `${index * 0.1}s` }}
            >
              <div className="flex items-start justify-between mb-3">
                <div className="flex items-center gap-2">
                  {getDirectionBadge(anomaly.direction, anomaly.z_score, true)}
                  <div>
                    <span className="font-bold text-white text-lg block">{anomaly.ticker.replace('@MISX', '')}</span>
                    <span className="text-xs text-gray-500">{anomaly.company_name}</span>
                  </div>
                </div>
                <div className="text-right">
                  <span className="text-xs text-gray-400 block">{formatTimestamp(anomaly.timestamp)}</span>
                  <span className="text-xs text-cyan-400 block mt-1">{anomaly.news_count} новостей</span>
                </div>
              </div>

              {anomaly.top_news && (
                <div className="mt-3 pt-3 border-t border-gray-700/50">
                  <p className="text-sm text-gray-300 line-clamp-3 leading-relaxed">
                    {anomaly.top_news.headline}
                  </p>
                  <div className="flex items-center gap-2 mt-2">
                    <svg className="w-3 h-3 text-gray-500" fill="currentColor" viewBox="0 0 20 20">
                      <path fillRule="evenodd" d="M12.586 4.586a2 2 0 112.828 2.828l-3 3a2 2 0 01-2.828 0 1 1 0 00-1.414 1.414 4 4 0 005.656 0l3-3a4 4 0 00-5.656-5.656l-1.5 1.5a1 1 0 101.414 1.414l1.5-1.5zm-5 5a2 2 0 012.828 0 1 1 0 101.414-1.414 4 4 0 00-5.656 0l-3 3a4 4 0 105.656 5.656l1.5-1.5a1 1 0 10-1.414-1.414l-1.5 1.5a2 2 0 11-2.828-2.828l3-3z" clipRule="evenodd" />
                    </svg>
                    <span className="text-xs text-gray-500 truncate">{anomaly.top_news.source}</span>
                  </div>
                </div>
              )}
            </div>
          ))}
        </div>
      </div>
    );
  }

  // Обычный режим - сетка
  return (
    <div className="mb-12 animate-fade-in">
      <div className="flex items-center justify-between mb-6">
        <div className="flex items-center gap-3">
          <div className="flex items-center justify-center w-12 h-12 bg-gradient-to-br from-yellow-500 to-orange-500 rounded-xl shadow-lg shadow-yellow-500/30">
            <svg className="w-7 h-7 text-white" fill="currentColor" viewBox="0 0 20 20">
              <path d="M11 3a1 1 0 10-2 0v1a1 1 0 102 0V3zM15.657 5.757a1 1 0 00-1.414-1.414l-.707.707a1 1 0 001.414 1.414l.707-.707zM18 10a1 1 0 01-1 1h-1a1 1 0 110-2h1a1 1 0 011 1zM5.05 6.464A1 1 0 106.464 5.05l-.707-.707a1 1 0 00-1.414 1.414l.707.707zM5 10a1 1 0 01-1 1H3a1 1 0 110-2h1a1 1 0 011 1zM8 16v-1h4v1a2 2 0 11-4 0zM12 14c.015-.34.208-.646.477-.859a4 4 0 10-4.954 0c.27.213.462.519.476.859h4.002z" />
            </svg>
          </div>
          <div>
            <h2 className="text-2xl font-bold text-white">Важные события</h2>
            <p className="text-sm text-gray-400 mt-0.5">События с сильным влиянием на котировки</p>
          </div>
        </div>
      </div>

      <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 gap-5">
        {anomalies.slice(0, 6).map((anomaly, index) => (
          <div
            key={anomaly.id}
            onClick={() => onTickerClick(anomaly.ticker.replace('@MISX', ''))}
            className="anomaly-card card-enhanced bg-gradient-to-br from-gray-800/80 to-gray-900/80 border border-gray-700/50 rounded-xl p-5 cursor-pointer group"
            style={{ animationDelay: `${index * 0.1}s` }}
          >
            <div className="flex items-start justify-between mb-4">
              <div className="flex-1">
                <div className="flex items-center gap-2 mb-1">
                  {getDirectionBadge(anomaly.direction, anomaly.z_score, false)}
                  <h3 className="text-xl font-bold text-white group-hover:text-cyan-400 transition-colors">
                    {anomaly.ticker.replace('@MISX', '')}
                  </h3>
                </div>
                <p className="text-sm text-gray-400">{anomaly.company_name}</p>
              </div>
            </div>

            {anomaly.top_news && (
              <div className="mb-4 pb-4 border-b border-gray-700/50">
                <p className="text-sm text-gray-300 line-clamp-3 leading-relaxed mb-2">
                  {anomaly.top_news.headline}
                </p>
                <div className="flex items-center gap-2">
                  <svg className="w-3 h-3 text-gray-500 flex-shrink-0" fill="currentColor" viewBox="0 0 20 20">
                    <path fillRule="evenodd" d="M12.586 4.586a2 2 0 112.828 2.828l-3 3a2 2 0 01-2.828 0 1 1 0 00-1.414 1.414 4 4 0 005.656 0l3-3a4 4 0 00-5.656-5.656l-1.5 1.5a1 1 0 101.414 1.414l1.5-1.5zm-5 5a2 2 0 012.828 0 1 1 0 101.414-1.414 4 4 0 00-5.656 0l-3 3a4 4 0 105.656 5.656l1.5-1.5a1 1 0 10-1.414-1.414l-1.5 1.5a2 2 0 11-2.828-2.828l3-3z" clipRule="evenodd" />
                  </svg>
                  <span className="text-xs text-gray-500 truncate">{anomaly.top_news.source}</span>
                </div>
              </div>
            )}

            <div className="flex items-center justify-between">
              <div className="flex items-center gap-2 text-xs text-gray-400">
                <svg className="w-3.5 h-3.5" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                  <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M12 8v4l3 3m6-3a9 9 0 11-18 0 9 9 0 0118 0z" />
                </svg>
                <span>{formatTimestamp(anomaly.timestamp)}</span>
              </div>
              <div className="flex items-center gap-4 text-xs">
                <span className="text-gray-500">{anomaly.timeframe}</span>
                <div className="flex items-center gap-1 text-cyan-400">
                  <svg className="w-3.5 h-3.5" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                    <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M19 20H5a2 2 0 01-2-2V6a2 2 0 012-2h10a2 2 0 012 2v1m2 13a2 2 0 01-2-2V7m2 13a2 2 0 002-2V9a2 2 0 00-2-2h-2m-4-3H9M7 16h6M7 8h6v4H7V8z" />
                  </svg>
                  <span className="font-medium">{anomaly.news_count}</span>
                </div>
              </div>
            </div>
          </div>
        ))}
      </div>
    </div>
  );
};

export default ImpactfulNews;
