import React from 'react';
import { AreaChart, Area, XAxis, YAxis, CartesianGrid, Tooltip, Legend, ResponsiveContainer } from 'recharts';
import { StockPoint } from '../types';

interface StockChartProps {
  data: StockPoint[];
}

const StockChart: React.FC<StockChartProps> = ({ data }) => {
  return (
    <>
      <h3 className="text-xl font-semibold text-white mb-4">Цена акции</h3>
      <ResponsiveContainer width="100%" height={300}>
        <AreaChart
          data={data}
          margin={{ top: 5, right: 30, left: 0, bottom: 5 }}
        >
          <defs>
            <linearGradient id="colorPrice" x1="0" y1="0" x2="0" y2="1">
              <stop offset="5%" stopColor="#2DD4BF" stopOpacity={0.8}/>
              <stop offset="95%" stopColor="#2DD4BF" stopOpacity={0}/>
            </linearGradient>
          </defs>
          <CartesianGrid strokeDasharray="3 3" stroke="#4A5568" />
          <XAxis dataKey="date" stroke="#A0AEC0" tick={{ fontSize: 12 }} />
          <YAxis stroke="#A0AEC0" tick={{ fontSize: 12 }} domain={['dataMin - 10', 'dataMax + 10']} allowDataOverflow={true} />
          <Tooltip
            contentStyle={{ backgroundColor: '#1A202C', border: '1px solid #4A5568' }}
            labelStyle={{ color: '#E2E8F0' }}
            formatter={(value: number) => [`$${value.toFixed(2)}`, 'Цена']}
          />
          <Legend wrapperStyle={{ color: '#E2E8F0' }} />
          <Area type="monotone" dataKey="price" name="Цена" stroke="#2DD4BF" strokeWidth={2} fillOpacity={1} fill="url(#colorPrice)" />
        </AreaChart>
      </ResponsiveContainer>
    </>
  );
};

export default StockChart;