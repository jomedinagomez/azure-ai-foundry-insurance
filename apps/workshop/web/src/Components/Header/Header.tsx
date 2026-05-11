import React from "react";
import {
  Avatar,
  Subtitle2,
  Tooltip,
  Button,
  TabList,
  Tab,
  TabValue,
} from "@fluentui/react-components";
import {
  WeatherMoonRegular,
  WeatherSunnyRegular,
  DocumentSplitHintRegular,
  BuildingRegular,
  FlowRegular,
  InfoRegular,
} from "@fluentui/react-icons";
import "./Header.css";

interface HeaderProps {
  isDarkMode: boolean;
  toggleTheme: () => void;
  selectedTab: TabValue;
  onTabChange: (value: TabValue) => void;
}

const tabConfigs = [
  {
    icon: <DocumentSplitHintRegular />,
    value: "compare",
    label: "Analyzer Compare",
  },
  {
    icon: <BuildingRegular />,
    value: "sov",
    label: "SOV Extraction",
  },
  {
    icon: <FlowRegular />,
    value: "pipelines",
    label: "Pipelines",
  },
];

const HeaderComponent: React.FC<HeaderProps> = ({
  isDarkMode,
  toggleTheme,
  selectedTab,
  onTabChange,
}) => {
  return (
    <header>
      {/* Brand */}
      <div className="headerTitle">
        <Avatar
          initials="AC"
          shape="square"
          color="brand"
          style={{ flexShrink: 0 }}
        />
        <div className="headerTitleText">
          <Subtitle2 style={{ whiteSpace: "nowrap" }}>
            Analyzer Compare
            <span style={{ fontWeight: 400 }}> | Tool</span>
          </Subtitle2>
        </div>
      </div>

      {/* Navigation */}
      <div className="headerNav">
        <TabList
          selectedValue={selectedTab}
          onTabSelect={(_, data) => onTabChange(data.value)}
          size="small"
        >
          {tabConfigs.map(({ icon, value, label }) => (
            <Tab key={value} icon={icon} value={value}>
              {label}
            </Tab>
          ))}
        </TabList>
      </div>

      {/* AI disclaimer */}
      <div className="headerTag">
        <InfoRegular />
        <span>AI-generated content may be incorrect</span>
      </div>

      {/* Theme toggle */}
      <div className="headerTools">
        <Tooltip
          content={isDarkMode ? "Switch to light mode" : "Switch to dark mode"}
          relationship="label"
        >
          <Button
            appearance="subtle"
            icon={isDarkMode ? <WeatherSunnyRegular /> : <WeatherMoonRegular />}
            onClick={toggleTheme}
            size="small"
          />
        </Tooltip>
      </div>
    </header>
  );
};

export default HeaderComponent;
