import React, { useState } from 'react';
import axios from 'axios';
import { toast } from 'react-toastify';
import './forgot.css';
import { API_URL } from "./config";
const ForgotPassword = () => {
  const [phone, setPhone] = useState('');
  const [newPassword, setNewPassword] = useState('');

  const handleReset = async (e) => {
    e.preventDefault();

    try {
      const response = await axios.post(`${API_URL}/forgot-password`, {
        phone,
        newPassword,
      });
      toast.success(response.data.message || 'Password updated');
    } catch (err) {
      toast.error(err.response?.data?.message || 'Reset failed');
    }
  };

  return (
    <div className="forgot-page-body">
      <div className="forgot-container">
        <h2>Reset Your Password</h2>
        <form onSubmit={handleReset}>
          <div className="form-group">
            <label htmlFor="phone">Phone Number</label>
            <input
              type="text"
              id="phone"
              name="phone"
              placeholder="Enter your phone"
              value={phone}
              onChange={(e) => setPhone(e.target.value)}
              pattern="\d{10}"
              required
            />
          </div>

          <div className="form-group">
            <label htmlFor="newPassword">New Password</label>
            <input
              type="password"
              id="newPassword"
              name="newPassword"
              placeholder="Enter new password"
              value={newPassword}
              onChange={(e) => setNewPassword(e.target.value)}
              required
            />
          </div>

          <button type="submit" className="reset-btn">Reset Password</button>
        </form>
      </div>
    </div>
  );
};

export default ForgotPassword;
