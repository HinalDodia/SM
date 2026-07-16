import React from 'react';
import './Headlines.css';

const SentimentOverview = ({ sentiment, distribution, insights }) => {
  if (!sentiment) return null;

  const score = sentiment.score || 50;
  const label = sentiment.label?.toLowerCase() || 'neutral';

  return (
    <div className="sentiment-overview">
      <div className="sentiment-main">
        <span className="sentiment-label">Overall Sentiment</span>
        <div className={`sentiment-badge ${label}`}>
          {sentiment.label || 'Neutral'}
        </div>
      </div>

      <div className="sentiment-gauge-container">
        <div className="sentiment-label" style={{ textAlign: 'center' }}>
          Sentiment Strength: {score}%
        </div>
        <div className="gauge-track">
          <div 
            className={`gauge-fill ${label}`} 
            style={{ width: `${score}%` }}
          ></div>
        </div>
        {insights && insights.length > 0 && (
          <div className="ai-insight" style={{ fontSize: '13px', color: '#cbd5e1', fontStyle: 'italic', marginTop: '4px' }}>
             " {insights[0]} "
          </div>
        )}
      </div>

      <div className="sentiment-distribution">
        <div className="dist-item">
          <span className="dist-count" style={{ color: 'var(--accent-green)' }}>
            {distribution?.bullish || 0}
          </span>
          <span className="dist-label">Bullish</span>
        </div>
        <div className="dist-item">
          <span className="dist-count" style={{ color: 'var(--muted)' }}>
            {distribution?.neutral || 0}
          </span>
          <span className="dist-label">Neutral</span>
        </div>
        <div className="dist-item">
          <span className="dist-count" style={{ color: '#FF6B6B' }}>
            {distribution?.bearish || 0}
          </span>
          <span className="dist-label">Bearish</span>
        </div>
      </div>
    </div>
  );
};

export default SentimentOverview;
