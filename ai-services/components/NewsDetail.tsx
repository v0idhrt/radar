import React from 'react';
import { AnalyzedNews, Sentiment } from '../types';

interface NewsDetailProps {
    article: AnalyzedNews | null;
    onClearSelection: () => void;
}

const SentimentBadge: React.FC<{ sentiment: Sentiment }> = ({ sentiment }) => {
    const sentimentStyles = {
        [Sentiment.Positive]: {
            bg: 'bg-green-500/20',
            text: 'text-green-400',
            label: 'Позитивный',
        },
        [Sentiment.Negative]: {
            bg: 'bg-red-500/20',
            text: 'text-red-400',
            label: 'Негативный',
        },
        [Sentiment.Neutral]: {
            bg: 'bg-gray-500/20',
            text: 'text-gray-400',
            label: 'Нейтральный',
        },
    };

    const style = sentimentStyles[sentiment];

    return (
        <span className={`inline-flex items-center px-3 py-1 rounded-full text-sm font-medium ${style.bg} ${style.text}`}>
            {style.label}
        </span>
    );
};

const NewsDetail: React.FC<NewsDetailProps> = ({ article, onClearSelection }) => {
    if (!article) {
        return (
            <div className="flex items-center justify-center h-full bg-gray-900/50 rounded-lg p-6 border-2 border-dashed border-gray-700">
                <p className="text-gray-400">Выберите новость для просмотра деталей</p>
            </div>
        );
    }

    return (
        <div className="bg-gray-900/50 rounded-lg p-6 border-2 border-gray-700 relative h-full flex flex-col">
            <button 
                onClick={onClearSelection}
                className="absolute top-3 right-3 text-gray-500 hover:text-white transition-colors"
                aria-label="Close details"
            >
                 <svg xmlns="http://www.w3.org/2000/svg" className="h-6 w-6" fill="none" viewBox="0 0 24 24" stroke="currentColor">
                    <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M6 18L18 6M6 6l12 12" />
                </svg>
            </button>
            <div className="flex-grow overflow-y-auto">
                <div className="flex justify-between items-center mb-4">
                    <h3 className="text-2xl font-bold text-white">{article.headline}</h3>
                </div>

                <div className="flex items-center space-x-4 text-sm text-gray-400 mb-4">
                    <span>{article.source}</span>
                    <span>&bull;</span>
                    <span>{new Date(article.timestamp).toLocaleString()}</span>
                </div>
                
                <div className="mb-6">
                     <SentimentBadge sentiment={article.sentiment} />
                </div>

                <div className="space-y-4 text-gray-300">
                    <div>
                        <h4 className="font-semibold text-white mb-2">Краткое резюме:</h4>
                        <p className="italic border-l-4 border-cyan-500 pl-4 py-2 bg-gray-800/50 rounded-r-md">{article.summary}</p>
                    </div>
                    <div>
                        <h4 className="font-semibold text-white mb-2">Содержание:</h4>
                        <p>{article.content}</p>
                    </div>
                </div>
            </div>
            <div className="mt-6 flex-shrink-0">
                 <a href={article.url} target="_blank" rel="noopener noreferrer" className="inline-block w-full text-center bg-cyan-600 hover:bg-cyan-500 text-white font-bold py-2 px-4 rounded-lg transition-colors">
                    Читать источник
                </a>
            </div>
        </div>
    );
};

export default NewsDetail;