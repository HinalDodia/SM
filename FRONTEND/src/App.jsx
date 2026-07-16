import { BrowserRouter as Router, useLocation } from "react-router-dom";
import Navbar from "./Navbar.jsx";
import AppWrapper from "./AppWrapper.jsx";
import ARIABubble from "./components/ARIABubble.jsx";

function App() {

  // ✅ Wrapper to control Navbar visibility
  function Layout() {
    const location = useLocation();
    const hideNavbar = location.pathname === "/"; // hide only on Home

    return (
      <div className="watchlist-container">
        {!hideNavbar && <Navbar />}
        <AppWrapper />
        <ARIABubble />
      </div>
    );
  }

  return (
    <Router>
      <Layout />
    </Router>
  );
}

export default App;
