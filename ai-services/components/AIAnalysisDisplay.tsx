import React, { useMemo } from 'react';
import { AnalyzedNews, Sentiment } from '../types';

interface AIAnalysisDisplayProps {
    analyzedNews: AnalyzedNews[];
}

const AIAnalysisDisplay: React.FC<AIAnalysisDisplayProps> = ({ analyzedNews }) => {
    const sentimentDistribution = useMemo(() => {
        const counts = {
            [Sentiment.Positive]: 0,
            [Sentiment.Negative]: 0,
            [Sentiment.Neutral]: 0,
        };
        
        analyzedNews.forEach(article => {
            counts[article.sentiment]++;
        });

        const total = analyzedNews.length;
        if (total === 0) {
            return {
                positive: 0,
                negative: 0,
                neutral: 0,
            };
        }

        return {
            positive: (counts[Sentiment.Positive] / total) * 100,
            negative: (counts[Sentiment.Negative] / total) * 100,
            neutral: (counts[Sentiment.Neutral] / total) * 100,
        };
    }, [analyzedNews]);

    return (
        <div className="bg-gray-800/50 p-6 rounded-lg border border-gray-700">
            <h3 className="text-xl font-semibold text-white mb-4">Общий анализ настроений</h3>
            <div className="space-y-3">
                <div>
                    <div className="flex justify-between mb-1 text-sm font-medium text-green-400">
                        <span>Позитивные</span>
                        <span>{sentimentDistribution.positive.toFixed(1)}%</span>
                    </div>
                    <div className="w-full bg-gray-700 rounded-full h-2.5">
                        <div className="bg-green-500 h-2.5 rounded-full" style={{ width: `${sentimentDistribution.positive}%` }}></div>
                    </div>
                </div>
                 <div>
                    <div className="flex justify-between mb-1 text-sm font-medium text-red-400">
                        <span>Негативные</span>
                        <span>{sentimentDistribution.negative.toFixed(1)}%</span>
                    </div>
                    <div className="w-full bg-gray-700 rounded-full h-2.5">
                        <div className="bg-red-500 h-2.5 rounded-full" style={{ width: `${sentimentDistribution.negative}%` }}></div>
                    </div>
                </div>
                 <div>
                    <div className="flex justify-between mb-1 text-sm font-medium text-gray-400">
                        <span>Нейтральные</span>
                        <span>{sentimentDistribution.neutral.toFixed(1)}%</span>
                    </div>
                    <div className="w-full bg-gray-700 rounded-full h-2.5">
                        <div className="bg-gray-500 h-2.5 rounded-full" style={{ width: `${sentimentDistribution.neutral}%` }}></div>
                    </div>
                </div>
            </div>
        </div>
    );
};

export default AIAnalysisDisplay;
