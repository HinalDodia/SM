import React, { useState, useContext } from 'react';
import { useNavigate, Link } from 'react-router-dom';
import axios from 'axios';
import { toast } from 'react-toastify';
import './Signup.css';
import { UserContext } from './UserContext';
import { API_URL } from "./config";
const Signup = () => {
  const { setUser } = useContext(UserContext) || {};
  const [name, setName] = useState('');
  const [email, setEmail] = useState('');
  const [password, setPassword] = useState('');
  const [confirmPassword, setConfirmPassword] = useState('');
  const navigate = useNavigate();

  const handleSubmit = async (e) => {
    e.preventDefault();

    if (password !== confirmPassword) {
      toast.error("Passwords do not match!");
      return;
    }

    try {
      const response = await axios.post(`${API_URL}/auth/signup`, {
        name,
        email,
        password,
      }, { headers: { 'Content-Type': 'application/json' } });
      if (response.data?.status === 'success' && response.data?.user) {
        toast.success(response.data.message || 'Signup successful!');
        if (typeof setUser === 'function') setUser(response.data.user);
        navigate('/dashboard', { replace: true });
      } else {
        toast.error(response.data?.message || 'Signup failed!');
      }
    } catch (err) {
      toast.error(err.response?.data?.message || 'Signup failed!');
    }
  };

  return (
    <div className="signup-page-body">
      <div className="signup-container">
        <h2>Create Your FINWISE Account</h2>
        <form onSubmit={handleSubmit} className="signup-form">
          <div className="form-group">
            <label htmlFor="name">Full Name</label>
            <input
              type="text"
              id="name"
              name="name"
              placeholder="Enter your full name"
              value={name}
              required
              onChange={(e) => setName(e.target.value)}
            />
          </div>

          <div className="form-group">
            <label htmlFor="email">Email</label>
            <input
              type="email"
              id="email"
              name="email"
              placeholder="your@email.com"
              value={email}
              required
              onChange={(e) => setEmail(e.target.value)}
            />
          </div>

          <div className="form-group">
            <label htmlFor="password">Create Password</label>
            <input
              type="password"
              id="password"
              name="password"
              placeholder="Create a strong password"
              value={password}
              required
              onChange={(e) => setPassword(e.target.value)}
            />
          </div>

          <div className="form-group">
            <label htmlFor="confirmPassword">Confirm Password</label>
            <input
              type="password"
              id="confirmPassword"
              name="confirmPassword"
              placeholder="Re-enter your password"
              value={confirmPassword}
              required
              onChange={(e) => setConfirmPassword(e.target.value)}
            />
          </div>

          <button type="submit" className="signup-btn">Sign Up</button>

          <p className="signup-text">
            Already have an account? <Link to="/Log">Login</Link>
          </p>
        </form>
      </div>
    </div>
  );
};

export default Signup;
