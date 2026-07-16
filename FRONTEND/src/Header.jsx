import React, { useContext } from "react";
import { Link } from "react-router-dom";
import { UserContext } from "./UserContext";


const Header = () => {
  const { username, setUsername } = useContext(UserContext);


  const handleLogout = () => {
    localStorage.removeItem("user");
    localStorage.removeItem("username");
    setUsername("");
  };

  return (
    <section id="header">
      <a href="/">
        <img src="/photos/Th3ee_Logo.png" className="logo" alt="Th3ee Logo" />
      </a>

      

      <ul id="navbar-right">
        {username ? (
          <li className="dropdown">
            <a href="#" className="dropbtn">Hi, {username} ▼</a>
            <ul className="dropdown-menu">
              <li><a href="#">Account</a></li>
              <li><a href="#" onClick={handleLogout}>Logout</a></li>
            </ul>
          </li>
        ) : (
          <li><Link to="/Log">Login</Link></li>
        )}

        
      </ul>
    </section>
  );
};

export default Header;
