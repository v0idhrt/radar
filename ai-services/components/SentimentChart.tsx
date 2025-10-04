import React from 'react';
import { AreaChart, Area, XAxis, YAxis, CartesianGrid, Tooltip, ResponsiveContainer, Legend } from 'recharts';
import { SentimentChartData, Sentiment } from '../types';

interface SentimentChartProps {
  data: SentimentChartData[];
}

const CustomTooltip = ({ active, payload, label }: any) => {
  if (active && payload && payload.length) {
    const data = payload[0].payload;
    return (
      <div className="p-3 bg-gray-800 border border-gray-600 rounded-md shadow-lg max-w-sm text-sm">
        <p className="font-bold text-gray-300 mb-2">{`Дата: ${label}`}</p>
        <p className="text-white mb-2">
          Среднее настроение: 
          <span className={data.averageSentiment > 0 ? 'text-green-400' : data.averageSentiment < 0 ? 'text-red-400' : 'text-gray-400'}>
            {` ${data.averageSentiment.toFixed(2)}`}
          </span>
        </p>
        <ul className="space-y-1 list-disc list-inside">
          {data.articles.map((article: any, index: number) => {
             let colorClass = 'text-gray-400';
             if (article.sentiment === Sentiment.Positive) colorClass = 'text-green-400';
             if (article.sentiment === Sentiment.Negative) colorClass = 'text-red-400';
             return <li key={index} className={`text-xs ${colorClass}`}>{article.headline}</li>
          })}
        </ul>
      </div>
    );
  }
  return null;
};

const gradientOffset = (data: SentimentChartData[]) => {
    const dataMax = Math.max(...data.map((i) => i.averageSentiment));
    const dataMin = Math.min(...data.map((i) => i.averageSentiment));

    if (dataMax <= 0) return 0;
    if (dataMin >= 0) return 1;

    return dataMax / (dataMax - dataMin);
};


const SentimentChart: React.FC<SentimentChartProps> = ({ data }) => {
    const off = gradientOffset(data);

    return (
    <>
      <h3 className="text-xl font-semibold text-white mb-4">Хронология настроений новостей</h3>
      <ResponsiveContainer width="100%" height={300}>
        <AreaChart
          data={data}
          margin={{ top: 5, right: 30, left: 0, bottom: 5 }}
        >
          <CartesianGrid strokeDasharray="3 3" stroke="#4A5568" opacity={0.3} />
          <XAxis
            dataKey="date"
            stroke="#A0AEC0"
            tick={{ fontSize: 12 }}
            tickLine={false}
          />
          <YAxis
            stroke="#A0AEC0"
            tick={{ fontSize: 12 }}
            domain={[-1.2, 1.2]}
            ticks={[-1, 0, 1]}
            tickLine={false}
            tickFormatter={(tick) => {
              if (tick === 1) return 'Позитив.';
              if (tick === 0) return 'Нейтрал.';
              if (tick === -1) return 'Негатив.';
              return '';
            }}
          />
          <Tooltip content={<CustomTooltip />} />
          <Legend wrapperStyle={{ color: '#E2E8F0' }} />
          <defs>
            <linearGradient id="splitColor" x1="0" y1="0" x2="0" y2="1">
              <stop offset={off} stopColor="#48BB78" stopOpacity={0.8}/>
              <stop offset={off} stopColor="#F56565" stopOpacity={0.8}/>
            </linearGradient>
            <filter id="sentimentGlow">
              <feGaussianBlur stdDeviation="1.5" result="coloredBlur"/>
              <feMerge>
                <feMergeNode in="coloredBlur"/>
                <feMergeNode in="SourceGraphic"/>
              </feMerge>
            </filter>
          </defs>
          <Area
            type="monotone"
            dataKey="averageSentiment"
            name="Среднее настроение"
            stroke="#718096"
            strokeWidth={2.5}
            fill="url(#splitColor)"
            filter="url(#sentimentGlow)"
            animationDuration={1500}
            animationEasing="ease-out"
          />
        </AreaChart>
      </ResponsiveContainer>
    </>
  );
};

export default SentimentChart;