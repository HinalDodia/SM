import React, { useState, useEffect } from "react";
import { Joyride, STATUS } from "react-joyride";

export default function AppTour({ run, userId, onFinish }) {
  const [runTour, setRunTour] = useState(false);

  useEffect(() => {
    if (!userId || !run) {
      setRunTour(false);
      return;
    }

    const key = `tour_seen_${userId}`;
    const alreadySeen = localStorage.getItem(key);
    if (!alreadySeen) {
      setRunTour(true);
    } else {
      setRunTour(false);
    }
  }, [run, userId]);

  const steps = [
    {
      target: ".tour-nav-watchlist",
      content: (
        <div>
          <strong style={{ color: "#2dd4bf", fontSize: 16 }}>1. Watchlist Recommendations</strong>
          <p style={{ margin: "6px 0 0", fontSize: 13, color: "#e2e8f0" }}>
            Each stock in your Watchlist displays an AI rating badge (BUY, HOLD, or SELL) and suggested position allocation based on your risk profile.
          </p>
        </div>
      ),
      disableBeacon: true,
    },
    {
      target: ".tour-nav-portfolio",
      content: (
        <div>
          <strong style={{ color: "#2dd4bf", fontSize: 16 }}>2. Portfolio Position Advice</strong>
          <p style={{ margin: "6px 0 0", fontSize: 13, color: "#e2e8f0" }}>
            Your stock holdings in Portfolio double as &quot;what to do with existing positions&quot; guidance — showing whether to <strong>BUY MORE</strong>, <strong>HOLD</strong>, or <strong>SELL</strong>.
          </p>
        </div>
      ),
      disableBeacon: true,
    },
    {
      target: ".tour-nav-account",
      content: (
        <div>
          <strong style={{ color: "#2dd4bf", fontSize: 16 }}>3. Account &amp; Profile Control</strong>
          <p style={{ margin: "6px 0 0", fontSize: 13, color: "#e2e8f0" }}>
            Update your risk tolerance, investment horizon, or capital budget anytime inside Account Settings under the <strong>Investment Profile</strong> tab.
          </p>
        </div>
      ),
      disableBeacon: true,
    },
  ];

  const handleJoyrideCallback = (data) => {
    const { status } = data;
    const finishedStatuses = [STATUS.FINISHED, STATUS.SKIPPED];

    if (finishedStatuses.includes(status)) {
      setRunTour(false);
      if (userId) {
        localStorage.setItem(`tour_seen_${userId}`, "true");
      }
      if (typeof onFinish === "function") {
        onFinish();
      }
    }
  };

  if (!runTour || !userId) return null;

  return (
    <Joyride
      steps={steps}
      run={runTour}
      continuous
      showSkipButton
      showProgress
      callback={handleJoyrideCallback}
      styles={{
        options: {
          zIndex: 10000,
          backgroundColor: "#0f172a",
          textColor: "#f8fafc",
          primaryColor: "#2dd4bf",
          arrowColor: "#0f172a",
          overlayColor: "rgba(0, 0, 0, 0.65)",
        },
        tooltipContainer: {
          textAlign: "left",
        },
        buttonNext: {
          backgroundColor: "#2dd4bf",
          color: "#0f172a",
          fontWeight: 700,
          borderRadius: 6,
          padding: "8px 14px",
        },
        buttonBack: {
          color: "#94a3b8",
          marginRight: 10,
        },
        buttonSkip: {
          color: "#94a3b8",
        },
      }}
    />
  );
}
