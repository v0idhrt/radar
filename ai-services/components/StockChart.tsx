import React from 'react';
import { AreaChart, Area, XAxis, YAxis, CartesianGrid, Tooltip, Legend, ResponsiveContainer } from 'recharts';
import { StockPoint } from '../types';

interface StockChartProps {
  data: StockPoint[];
}

const StockChart: React.FC<StockChartProps> = ({ data }) => {
  // Фильтруем данные за последний месяц
  const lastMonthData = React.useMemo(() => {
    if (!data || data.length === 0) return [];

    const now = new Date();
    const oneMonthAgo = new Date(now.getTime() - 30 * 24 * 60 * 60 * 1000);

    return data.filter(point => {
      const pointDate = new Date(point.date);
      return pointDate >= oneMonthAgo;
    });
  }, [data]);

  return (
    <>
      <div className="flex items-center justify-between mb-4">
        <h3 className="text-xl font-semibold text-white">Цена акции</h3>
        <span className="text-xs text-gray-400 bg-gray-700/50 px-3 py-1 rounded-full">
          Последние 30 дней
        </span>
      </div>
      <ResponsiveContainer width="100%" height={300}>
        <AreaChart
          data={lastMonthData}
          margin={{ top: 5, right: 30, left: 0, bottom: 5 }}
        >
          <defs>
            <linearGradient id="colorPrice" x1="0" y1="0" x2="0" y2="1">
              <stop offset="5%" stopColor="#2DD4BF" stopOpacity={0.8}/>
              <stop offset="95%" stopColor="#2DD4BF" stopOpacity={0}/>
            </linearGradient>
            <filter id="glow">
              <feGaussianBlur stdDeviation="2" result="coloredBlur"/>
              <feMerge>
                <feMergeNode in="coloredBlur"/>
                <feMergeNode in="SourceGraphic"/>
              </feMerge>
            </filter>
          </defs>
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
            domain={['dataMin - 10', 'dataMax + 10']}
            allowDataOverflow={true}
            tickLine={false}
          />
          <Tooltip
            contentStyle={{
              backgroundColor: 'rgba(26, 32, 44, 0.95)',
              border: '1px solid #2DD4BF',
              borderRadius: '8px',
              boxShadow: '0 4px 12px rgba(45, 212, 191, 0.3)'
            }}
            labelStyle={{ color: '#E2E8F0', fontWeight: 'bold' }}
            formatter={(value: number) => [`₽${value.toFixed(2)}`, 'Цена']}
          />
          <Legend wrapperStyle={{ color: '#E2E8F0' }} />
          <Area
            type="monotone"
            dataKey="price"
            name="Цена"
            stroke="#2DD4BF"
            strokeWidth={3}
            fillOpacity={1}
            fill="url(#colorPrice)"
            filter="url(#glow)"
            animationDuration={1500}
            animationEasing="ease-out"
          />
        </AreaChart>
      </ResponsiveContainer>
    </>
  );
};

export default StockChart;