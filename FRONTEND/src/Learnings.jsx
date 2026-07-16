import React, { useState } from "react";
import "./Learnings.css";

function Learning() {

  const [selectedTopic, setSelectedTopic] = useState(null);
  const [showModal, setShowModal]         = useState(false);

  // ---------- Learning Topics ----------
  const learningTopics = [
    {
      id: 1,
      icon: "📈",
      title: "What is Stock?",
      summary: "Learn the fundamentals of stocks and equity ownership.",
      content: `
        <h3>Understanding Stocks</h3>
        <p>A stock represents a share in the ownership of a company...</p>
      `
    },
    {
      id: 2,
      icon: "💹",
      title: "How Trading Works",
      summary: "Understand buying and selling of stocks.",
      content: `
        <h3>How Stock Trading Works</h3>
        <p>Trading involves buying and selling shares...</p>
      `
    },
    {
      id: 3,
      icon: "🛡️",
      title: "Risk Management",
      summary: "Learn how to protect your investments.",
      content: `
        <h3>Risk Management Strategies</h3>
        <p>Managing risk is critical...</p>
      `
    },
    {
      id: 4,
      icon: "🌱",
      title: "Long Term Investment",
      summary: "Power of compounding & wealth building.",
      content: `
        <h3>Why Long-Term Investing Works</h3>
        <p>Compounding generates exponential returns...</p>
      `
    }
  ];



  const openModal  = (topic) => { setSelectedTopic(topic); setShowModal(true);  document.body.style.overflow = "hidden"; };
  const closeModal = ()      => { setSelectedTopic(null);  setShowModal(false); document.body.style.overflow = ""; };

  // ---------------- UI ----------------
  return (
    <div className="learning-container">

      <h2 className="section-title">Basic Terms and Terminologies</h2>

      <div className="learning-grid">
        {learningTopics.map(topic => (
          <div className="learning-card" key={topic.id}>
            <div className="icon">{topic.icon}</div>
            <h3>{topic.title}</h3>
            <p>{topic.summary}</p>
            <button onClick={() => openModal(topic)}>Learn More</button>
          </div>
        ))}
      </div>

      {/* Modal */}
      {showModal && selectedTopic && (
        <div className="modal-backdrop" onClick={closeModal}>
          <div className="modal-content" onClick={(e) => e.stopPropagation()}>
            <div dangerouslySetInnerHTML={{ __html: selectedTopic.content }} />
            <button className="close-btn" onClick={closeModal}>Close</button>
          </div>
        </div>
      )}

    </div>
  );
}

export default Learning;
