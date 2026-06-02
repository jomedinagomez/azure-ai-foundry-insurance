import React from "react";
import "./Styles/App.css";
import { ToastContainer } from "react-toastify";
import "react-toastify/dist/ReactToastify.css";
import { HashRouter as Router, Routes, Route, Navigate } from "react-router-dom";
import Header from "./Components/Header/Header";
import ComparePage from "./Pages/ComparePage";
import SovPage from "./Pages/SovPage";
import SecPage from "./Pages/SecPage";
import PipelinesPage from "./Pages/PipelinesPage";
import ProPage from "./Pages/ProPage";
import { TabValue } from "@fluentui/react-components";
import { useNavigate, useLocation } from "react-router-dom";

type AppProps = {
  isDarkMode: boolean;
  toggleTheme: () => void;
};

const AppInner: React.FC<AppProps> = ({ isDarkMode, toggleTheme }) => {
  const navigate = useNavigate();
  const location = useLocation();

  const routeToTab: Record<string, TabValue> = {
    "/compare": "compare",
    "/sov": "sov",
    "/sec": "sec",
    "/pipelines": "pipelines",
    "/pro": "pro",
  };

  const currentTab =
    Object.keys(routeToTab).find((r) => location.pathname.startsWith(r)) ?? "/compare";

  const handleTabChange = (value: TabValue) => {
    if (value === "compare") navigate("/compare");
    if (value === "sov") navigate("/sov");
    if (value === "sec") navigate("/sec");
    if (value === "pipelines") navigate("/pipelines");
    if (value === "pro") navigate("/pro");
  };

  return (
    <div className="app-container">
      <Header
        isDarkMode={isDarkMode}
        toggleTheme={toggleTheme}
        selectedTab={routeToTab[currentTab] ?? "compare"}
        onTabChange={handleTabChange}
      />
      <main>
        <Routes>
          <Route path="/" element={<Navigate to="/compare" />} />
          <Route path="/compare" element={<ComparePage />} />
          <Route path="/sov" element={<SovPage />} />
          <Route path="/sec" element={<SecPage />} />
          <Route path="/pipelines" element={<PipelinesPage />} />
          <Route path="/pro" element={<ProPage />} />
          <Route path="*" element={<Navigate to="/compare" />} />
        </Routes>
      </main>
      <ToastContainer position="top-right" autoClose={3000} />
    </div>
  );
};

const App: React.FC<AppProps> = (props) => (
  <Router>
    <AppInner {...props} />
  </Router>
);

export default App;
