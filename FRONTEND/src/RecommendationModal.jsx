import React, { useEffect, useState } from "react";
import axios from "axios";
import { TrendingUp, TrendingDown, Star } from "lucide-react";
import { API_URL } from "./config";
export default function RecommendationModal({ onClose, userId }) {
  const [recommendations, setRecommendations] = useState([]);

  useEffect(() => {
    const fetchRecommendations = async () => {
      try {
        const res = await axios.get(
  `${API_URL}/recommendations/${userId}`,
  { withCredentials: true }
);
        setRecommendations(res.data.recommendations || []);

      } catch (err) {
        console.error("Error fetching recommendations:", err);
      }
    };
    fetchRecommendations();
  }, [userId]);

  if (!recommendations || recommendations.length === 0) return null;

  return (
    <div className="modal-backdrop">
      <div className="modal-card" style={{ maxWidth: '850px', width: '100%' }}>
        <div className="modal-head">
          <h3 style={{ color: '#2dd4bf' }}>Recommended Stocks for You</h3>
          <button onClick={onClose} className="close-x">✕</button>
        </div>

        <div className="reco-grid">
          {recommendations.map((stock) => (
            <div key={stock.stockname} className="reco-card">
              <div className="reco-header">
                <span className="reco-symbol">{stock.stockname}</span>
                {stock.buy_prob > 0.6 ? (
                  <TrendingUp className="green" size={20} />
                ) : (
                  <TrendingDown className="red" size={20} />
                )}
              </div>
              
              <p className="reco-company">{stock.companyname}</p>
              
              {stock.price && (
                <p className="reco-price">
                  ₹{Number(stock.price).toFixed(2)}
                </p>
              )}

              {/* You can add a 'reco-change' element here when your API provides it */}

              <div className="reco-match">
                <Star size={16} fill="currentColor" />
                <span>{(stock.buy_prob * 100).toFixed(1)}% Match</span>
              </div>
            </div>
          ))}
        </div>
      </div>
    </div>
  );
}