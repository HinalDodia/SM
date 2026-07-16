import React from 'react';
import './Headlines.css';

const NewsCard = ({ article, fallbackImage }) => {
  if (!article) return null;

  const {
    title,
    summary,
    source,
    published_at,
    url,
    image,
    sentiment,
    impact,
    action,
    topics,
  } = article;

  const FINAL_FALLBACK = "https://images.unsplash.com/photo-1611974717484-217357c9b20e?q=80&w=400&auto=format&fit=crop";
  const displayImage = image || fallbackImage || FINAL_FALLBACK;

  return (
    <a href={url} target="_blank" rel="noopener noreferrer" className="news-card">
      <div className="news-image-container">
        <img 
          src={displayImage} 
          alt={title} 
          className="news-image" 
          style={{ 
            objectFit: image ? 'cover' : 'contain', 
            padding: (image || !fallbackImage) ? '0' : '12%',
            background: (image) ? 'transparent' : 'linear-gradient(135deg, rgba(30, 41, 59, 0.8), rgba(15, 23, 42, 1))'
          }}
          loading="lazy" 
        />
      </div>
      <div className="news-content">
        <div className="news-meta">
          <span className="news-source">{source}</span>
          <span className="news-time">{published_at || 'Recently'}</span>
        </div>
        <h4 className="news-headline">{title}</h4>
        <p className="news-summary">{summary}</p>
        <div className="news-footer">
          {sentiment && (
            <span className={`sentiment-badge ${sentiment.label}`}>
              {sentiment.label}
              {sentiment.confidence && ` (${Math.round(sentiment.confidence * 100)}%)`}
            </span>
          )}
          <span className={`badge impact-${impact?.toLowerCase() || 'medium'}`}>
            {impact || 'Medium'} Impact
          </span>
          {action && <span className="action-signal">Signal: {action}</span>}
          {topics && topics.slice(0, 2).map((t, idx) => (
            <span key={idx} className="tag">{t}</span>
          ))}
        </div>
      </div>
    </a>
  );
};

export default NewsCard;
