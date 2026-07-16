import React from 'react';
import './Headlines.css';

export const SentimentSkeleton = () => (
  <div className="sentiment-overview" style={{ padding: '28px 32px', gap: '40px' }}>
    <div className="sentiment-main" style={{ width: '120px' }}>
      <div className="skeleton" style={{ width: '60px', height: '12px', marginBottom: '8px' }}></div>
      <div className="skeleton" style={{ width: '100px', height: '32px', borderRadius: '999px' }}></div>
    </div>
    <div className="sentiment-gauge-container">
      <div className="skeleton" style={{ width: '120px', height: '12px', marginBottom: '10px' }}></div>
      <div className="gauge-track skeleton"></div>
    </div>
    <div className="sentiment-distribution" style={{ gap: '16px' }}>
      {[1, 2, 3].map(i => (
        <div key={i} className="dist-item">
          <div className="skeleton" style={{ width: '24px', height: '24px', marginBottom: '4px' }}></div>
          <div className="skeleton" style={{ width: '40px', height: '10px' }}></div>
        </div>
      ))}
    </div>
  </div>
);

export const NewsCardSkeleton = () => (
  <div className="news-card" style={{ padding: '20px', gap: '28px', gridTemplateColumns: '240px 1fr' }}>
    <div className="news-image-container skeleton" style={{ width: '240px', aspectRatio: '16/10' }}></div>
    <div className="news-content">
      <div className="news-meta">
        <div className="skeleton" style={{ width: '80px', height: '12px' }}></div>
        <div className="skeleton" style={{ width: '60px', height: '12px' }}></div>
      </div>
      <div className="skeleton" style={{ width: '100%', height: '24px', margin: '8px 0' }}></div>
      <div className="skeleton" style={{ width: '100%', height: '40px' }}></div>
      <div className="news-footer" style={{ marginTop: 'auto' }}>
        <div className="skeleton" style={{ width: '50px', height: '16px' }}></div>
        <div className="skeleton" style={{ width: '50px', height: '16px' }}></div>
        <div className="skeleton" style={{ width: '80px', height: '16px' }}></div>
      </div>
    </div>
  </div>
);

const LoadingSkeleton = () => (
  <div className="headlines-container">
    <SentimentSkeleton />
    <div className="news-feed">
      {[1, 2, 3, 4].map(i => <NewsCardSkeleton key={i} />)}
    </div>
  </div>
);

export default LoadingSkeleton;
