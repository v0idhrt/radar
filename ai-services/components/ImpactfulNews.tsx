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
      <div className="mb-8 bg-gray-800/30 border border-gray-700/50 rounded-lg p-4">
        <div className="flex items-center gap-3 mb-4">
          <h3 className="text-lg font-bold text-white">⚡ Горячие новости</h3>
          <span className="text-xs text-gray-500">Обновляется каждые 30 секунд</span>
        </div>
        
        <div className="flex gap-3 overflow-x-auto pb-2 custom-scrollbar">
          {anomalies.slice(0, 10).map((anomaly) => (
            <div
              key={anomaly.id}
              onClick={() => onTickerClick(anomaly.ticker.replace('@MISX', ''))}
              className="flex-shrink-0 w-64 bg-gray-800/70 border border-gray-700 rounded-lg p-3 hover:bg-gray-800 hover:border-cyan-500/50 transition-all cursor-pointer"
            >
              <div className="flex items-center justify-between mb-2">
                <div className="flex items-center gap-2">
                  {getDirectionBadge(anomaly.direction, anomaly.z_score, true)}
                  <span className="font-bold text-white">{anomaly.ticker.replace('@MISX', '')}</span>
                </div>
                <span className="text-xs text-gray-500">{formatTimestamp(anomaly.timestamp)}</span>
              </div>
              
              {anomaly.top_news && (
                <p className="text-xs text-gray-300 line-clamp-2 mb-1">
                  {anomaly.top_news.headline}
                </p>
              )}
              
              <div className="flex items-center justify-between text-xs text-gray-500">
                <span>{anomaly.company_name}</span>
                <span>{anomaly.news_count} новостей</span>
              </div>
            </div>
          ))}
        </div>
      </div>
    );
  }

  // Обычный режим - сетка
  return (
    <div className="mb-12">
      <div className="flex items-center gap-3 mb-6">
        <h2 className="text-2xl font-bold text-white">⚡ Важные события</h2>
        <span className="text-sm text-gray-400">События с сильным влиянием на котировки</span>
      </div>

      <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 gap-4">
        {anomalies.slice(0, 6).map((anomaly) => (
          <div
            key={anomaly.id}
            onClick={() => onTickerClick(anomaly.ticker.replace('@MISX', ''))}
            className="bg-gray-800/50 border border-gray-700 rounded-lg p-4 hover:bg-gray-800 hover:border-cyan-500/50 transition-all cursor-pointer"
          >
            <div className="flex items-start justify-between mb-3">
              <div>
                <h3 className="text-lg font-bold text-white">{anomaly.ticker.replace('@MISX', '')}</h3>
                <p className="text-sm text-gray-400">{anomaly.company_name}</p>
              </div>
              {getDirectionBadge(anomaly.direction, anomaly.z_score)}
            </div>

            {anomaly.top_news && (
              <div className="mb-3">
                <p className="text-sm text-gray-300 line-clamp-2">
                  {anomaly.top_news.headline}
                </p>
                <p className="text-xs text-gray-500 mt-1">{anomaly.top_news.source}</p>
              </div>
            )}

            <div className="flex items-center justify-between text-xs text-gray-500">
              <span>{formatTimestamp(anomaly.timestamp)}</span>
              <span>{anomaly.timeframe} · {anomaly.news_count} новостей</span>
            </div>
          </div>
        ))}
      </div>
    </div>
  );
};

export default ImpactfulNews;
