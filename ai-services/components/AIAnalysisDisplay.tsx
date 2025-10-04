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
        <div className="card-enhanced bg-gray-800/50 p-6 rounded-lg border border-gray-700">
            <div className="flex items-center gap-2 mb-4">
                <svg className="w-5 h-5 text-cyan-400" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                    <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M9 19v-6a2 2 0 00-2-2H5a2 2 0 00-2 2v6a2 2 0 002 2h2a2 2 0 002-2zm0 0V9a2 2 0 012-2h2a2 2 0 012 2v10m-6 0a2 2 0 002 2h2a2 2 0 002-2m0 0V5a2 2 0 012-2h2a2 2 0 012 2v14a2 2 0 01-2 2h-2a2 2 0 01-2-2z" />
                </svg>
                <h3 className="text-xl font-semibold text-white">Общий анализ настроений</h3>
            </div>
            <div className="space-y-3">
                <div>
                    <div className="flex justify-between mb-1 text-sm font-medium text-green-400">
                        <span>Позитивные</span>
                        <span>{sentimentDistribution.positive.toFixed(1)}%</span>
                    </div>
                    <div className="progress-bar w-full bg-gray-700 rounded-full h-2.5">
                        <div
                            className="bg-gradient-to-r from-green-500 to-green-400 h-2.5 rounded-full transition-all duration-700"
                            style={{ width: `${sentimentDistribution.positive}%` }}
                        ></div>
                    </div>
                </div>
                 <div>
                    <div className="flex justify-between mb-1 text-sm font-medium text-red-400">
                        <span>Негативные</span>
                        <span>{sentimentDistribution.negative.toFixed(1)}%</span>
                    </div>
                    <div className="progress-bar w-full bg-gray-700 rounded-full h-2.5">
                        <div
                            className="bg-gradient-to-r from-red-500 to-red-400 h-2.5 rounded-full transition-all duration-700"
                            style={{ width: `${sentimentDistribution.negative}%` }}
                        ></div>
                    </div>
                </div>
                 <div>
                    <div className="flex justify-between mb-1 text-sm font-medium text-gray-400">
                        <span>Нейтральные</span>
                        <span>{sentimentDistribution.neutral.toFixed(1)}%</span>
                    </div>
                    <div className="progress-bar w-full bg-gray-700 rounded-full h-2.5">
                        <div
                            className="bg-gradient-to-r from-gray-500 to-gray-400 h-2.5 rounded-full transition-all duration-700"
                            style={{ width: `${sentimentDistribution.neutral}%` }}
                        ></div>
                    </div>
                </div>
            </div>
        </div>
    );
};

export default AIAnalysisDisplay;
