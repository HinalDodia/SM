import React from 'react';
import './Headlines.css';

const TopicChips = ({ topics, activeTopic, onTopicClick }) => {
  if (!topics || topics.length === 0) return null;

  return (
    <div className="topics-section">
      <div 
        className={`topic-chip ${!activeTopic ? 'active' : ''}`}
        onClick={() => onTopicClick(null)}
      >
        All Topics
      </div>
      {topics.map((t, idx) => (
        <div 
          key={t.topic || idx} 
          className={`topic-chip ${activeTopic === t.topic ? 'active' : ''}`}
          onClick={() => onTopicClick(t.topic)}
        >
          {t.topic} ({t.count})
        </div>
      ))}
    </div>
  );
};

export default TopicChips;
