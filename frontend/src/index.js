import React from "react";
import ReactDOM from "react-dom/client";
import { Buffer } from "buffer";
import "@/index.css";
import App from "@/App";

// Polyfill for WalletConnect / Reown AppKit
window.Buffer = Buffer;

const root = ReactDOM.createRoot(document.getElementById("root"));
root.render(
  <React.StrictMode>
    <App />
  </React.StrictMode>,
);
