import React, { useState, useEffect, useMemo } from 'react';
import { fetchHeadlines } from '../api';
import SentimentOverview from './SentimentOverview';
import NewsCard from './NewsCard';
import TopicChips from './TopicChips';
import LoadingSkeleton from './LoadingSkeleton';
import './Headlines.css';

const ITEMS_PER_PAGE = 8;

const HeadlinesView = ({ symbol }) => {
  const [data, setData] = useState(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState(null);
  
  const [search, setSearch] = useState('');
  const [sentimentFilter, setSentimentFilter] = useState('all');
  const [activeTopic, setActiveTopic] = useState(null);
  const [sortBy, setSortBy] = useState('newest');
  const [visibleCount, setVisibleCount] = useState(ITEMS_PER_PAGE);

  useEffect(() => {
    let cancelled = false;
    setLoading(true);
    setError(null);
    setData(null);

    fetchHeadlines(symbol)
      .then(res => {
        if (!cancelled) {
          setData(res);
          setLoading(false);
        }
      })
      .catch(err => {
        if (!cancelled) {
          setError(err.message || 'Failed to fetch headlines');
          setLoading(false);
        }
      });

    return () => { cancelled = true; };
  }, [symbol]);

  // DERIVED: Filtered News
  const filteredNews = useMemo(() => {
    if (!data?.news) return [];

    return data.news.filter(article => {
      const matchesSearch = article.title?.toLowerCase().includes(search.toLowerCase()) || 
                            article.summary?.toLowerCase().includes(search.toLowerCase());
      const matchesSentiment = sentimentFilter === 'all' || article.sentiment?.label === sentimentFilter;
      const matchesTopic = !activeTopic || (article.topics && article.topics.includes(activeTopic));

      return matchesSearch && matchesSentiment && matchesTopic;
    });
  }, [data?.news, search, sentimentFilter, activeTopic]);

  // DERIVED: Sorted News
  const sortedNews = useMemo(() => {
    const news = [...filteredNews];
    
    if (sortBy === 'newest') {
      return news; // Assuming backend returns newest first
    } else if (sortBy === 'impact') {
      const impactMap = { 'High': 3, 'Medium': 2, 'Low': 1 };
      return news.sort((a, b) => (impactMap[b.impact] || 0) - (impactMap[a.impact] || 0));
    } else if (sortBy === 'sentiment') {
      const sentimentMap = { 'bullish': 3, 'neutral': 2, 'bearish': 1 };
      return news.sort((a, b) => (sentimentMap[b.sentiment?.label] || 0) - (sentimentMap[a.sentiment?.label] || 0));
    }
    
    return news;
  }, [filteredNews, sortBy]);

  // DERIVED: Displayed News (Pagination)
  const displayedNews = useMemo(() => {
    return sortedNews.slice(0, visibleCount);
  }, [sortedNews, visibleCount]);

  // DERIVED: Sentiment Aggregations for current view (if needed, otherwise use global from data)
  const currentSentiment = useMemo(() => {
    if (!data) return null;
    return data.overall_sentiment;
  }, [data]);

  const currentDistribution = useMemo(() => {
    if (!data) return null;
    return data.sentiment_distribution;
  }, [data]);

  if (loading) return <LoadingSkeleton />;
  if (error) return <div className="empty" style={{ color: '#FF6B6B' }}>Error: {error}</div>;
  if (!data || data.news_count === 0) return <div className="empty">No headlines found for {symbol}.</div>;

  return (
    <div className="headlines-container">
      {/* COMPANY INFO (Implicit in StockDetailPage, so we focus on News data) */}
      
      <SentimentOverview 
        sentiment={currentSentiment} 
        distribution={currentDistribution}
        insights={data.ai_market_insights}
      />

      <div className="filter-bar">
        <input 
          type="text" 
          className="search-input" 
          placeholder="Search headlines or summaries..." 
          value={search}
          onChange={(e) => setSearch(e.target.value)}
        />
        
        <div style={{ display: 'flex', gap: '12px' }}>
          <select 
            className="filter-select"
            value={sentimentFilter}
            onChange={(e) => setSentimentFilter(e.target.value)}
          >
            <option value="all">All Sentiments</option>
            <option value="bullish">Bullish</option>
            <option value="neutral">Neutral</option>
            <option value="bearish">Bearish</option>
          </select>

          <select 
            className="filter-select"
            value={sortBy}
            onChange={(e) => setSortBy(e.target.value)}
          >
            <option value="newest">Newest First</option>
            <option value="impact">Highest Impact</option>
            <option value="sentiment">Most Bullish</option>
          </select>
        </div>
      </div>

      <TopicChips 
        topics={data.top_topics} 
        activeTopic={activeTopic}
        onTopicClick={setActiveTopic}
      />

      <div className="news-feed">
        {displayedNews.length > 0 ? (
          displayedNews.map(article => (
            <NewsCard 
              key={article.id} 
              article={article} 
              fallbackImage={data.company_meta?.logo_url} 
            />
          ))
        ) : (
          <div className="empty">No news matches your filters.</div>
        )}
      </div>

      {visibleCount < sortedNews.length && (
        <div className="load-more-container">
          <button 
            className="load-more-btn"
            onClick={() => setVisibleCount(prev => prev + ITEMS_PER_PAGE)}
          >
            Load More Articles
          </button>
        </div>
      )}
    </div>
  );
};

export default HeadlinesView;
