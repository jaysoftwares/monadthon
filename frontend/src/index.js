import React from "react";
import ReactDOM from "react-dom/client";
import { Buffer } from "buffer";
import "@/index.css";
import App from "@/App";

// Polyfill for WalletConnect / Reown AppKit
window.Buffer = Buffer;

// Global error handler for unhandled promise rejections (e.g., wallet operations)
window.addEventListener('unhandledrejection', (event) => {
  const error = event.reason;
  const errorMessage = error?.message || error?.reason || String(error);

  // Check if this is a user rejection error from wallet
  const isUserRejection = (
    error?.code === 4001 ||
    error?.code === 'ACTION_REJECTED' ||
    error?.name === 'UserRejectedRequestError' ||
    errorMessage.toLowerCase().includes('user rejected') ||
    errorMessage.toLowerCase().includes('user denied') ||
    errorMessage.toLowerCase().includes('user cancelled') ||
    errorMessage.toLowerCase().includes('rejected the request')
  );

  if (isUserRejection) {
    // Silently ignore user rejections - this is expected behavior
    event.preventDefault();
    console.debug('User rejected wallet action');
    return;
  }

  // Log other errors but prevent them from showing as uncaught
  console.warn('Unhandled promise rejection:', error);
  event.preventDefault();
});

// Global error handler for uncaught errors
window.addEventListener('error', (event) => {
  const error = event.error;
  const errorMessage = error?.message || String(error);

  // Ignore certain expected errors
  if (
    errorMessage.includes('ResizeObserver') ||
    errorMessage.includes('Script error')
  ) {
    event.preventDefault();
    return;
  }

  console.warn('Uncaught error:', error);
});

const root = ReactDOM.createRoot(document.getElementById("root"));
root.render(
  <React.StrictMode>
    <App />
  </React.StrictMode>,
);
