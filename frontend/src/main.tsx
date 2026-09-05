import React from "react";
import ReactDOM from "react-dom/client";
import { BrowserRouter } from "react-router-dom";
import App from "./App";
import { PhaseProvider } from "./lib/phaseContext";
import "./index.css";

ReactDOM.createRoot(document.getElementById("root")!).render(
  <React.StrictMode>
    <BrowserRouter>
      <PhaseProvider>
        <App />
      </PhaseProvider>
    </BrowserRouter>
  </React.StrictMode>
);
