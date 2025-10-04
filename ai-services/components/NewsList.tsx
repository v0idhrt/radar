import React from 'react';
import { AnalyzedNews, Sentiment } from '../types';

interface NewsListProps {
    articles: AnalyzedNews[];
    onSelectArticle: (article: AnalyzedNews) => void;
    selectedArticleId: string | null;
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
        <span className={`inline-flex items-center px-2.5 py-0.5 rounded-full text-xs font-medium ${style.bg} ${style.text}`}>
            {style.label}
        </span>
    );
};

const NewsList: React.FC<NewsListProps> = ({ articles, onSelectArticle, selectedArticleId }) => {
    return (
        <div className="space-y-4">
            {articles.sort((a,b) => b.timestamp - a.timestamp).map(article => (
                <div
                    key={article.id}
                    onClick={() => onSelectArticle(article)}
                    className={`p-4 rounded-lg cursor-pointer transition-all duration-200 ease-in-out border-2 ${selectedArticleId === article.id ? 'bg-gray-700 border-cyan-500' : 'bg-gray-900/50 border-gray-700 hover:border-cyan-600 hover:bg-gray-800/60'}`}
                >
                    <div className="flex justify-between items-start mb-2">
                        <h4 className="font-bold text-md text-white pr-4">{article.headline}</h4>
                        <SentimentBadge sentiment={article.sentiment} />
                    </div>
                    <p className="text-sm text-gray-400 mb-3 line-clamp-2">{article.summary}</p>
                    <div className="flex justify-between items-center text-xs text-gray-500">
                        <span>{article.source}</span>
                        <span>{new Date(article.timestamp).toLocaleDateString()}</span>
                    </div>
                </div>
            ))}
        </div>
    );
};

export default NewsList;
