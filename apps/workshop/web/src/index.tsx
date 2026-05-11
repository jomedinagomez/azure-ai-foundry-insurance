import React, { useEffect, useState } from "react";
import ReactDOM from "react-dom/client";
import "./Styles/index.css";
import App from "./App";
import {
  FluentProvider,
  teamsLightTheme,
  teamsDarkTheme,
  tokens,
  makeStyles,
} from "@fluentui/react-components";

const useStyles = makeStyles({
  appContainer: {
    height: "100vh",
    backgroundColor: tokens.colorNeutralBackground3,
  },
});

const Index: React.FC = () => {
  const [isDarkMode, setIsDarkMode] = useState(
    () => window.matchMedia("(prefers-color-scheme: dark)").matches
  );

  useEffect(() => {
    const mq = window.matchMedia("(prefers-color-scheme: dark)");
    const handler = (e: MediaQueryListEvent) => setIsDarkMode(e.matches);
    mq.addEventListener("change", handler);
    return () => mq.removeEventListener("change", handler);
  }, []);

  const toggleTheme = () => setIsDarkMode((prev) => !prev);
  const styles = useStyles();

  return (
    <FluentProvider theme={isDarkMode ? teamsDarkTheme : teamsLightTheme}>
      <div className={styles.appContainer}>
        <App isDarkMode={isDarkMode} toggleTheme={toggleTheme} />
      </div>
    </FluentProvider>
  );
};

const root = ReactDOM.createRoot(
  document.getElementById("root") as HTMLElement
);
root.render(<Index />);
