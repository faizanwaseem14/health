import React from "react";
import ReactDOM from "react-dom/client";
import { BrowserRouter } from "react-router-dom";
import App from "./App.jsx";
import { AuthProvider } from "./context/AuthContext.jsx";
import "./styles/global.css";
import { ThemeProvider } from "./theme/ThemeProvider.jsx";

// This is where React "attaches" itself to the <div id="root"> in
// index.html. ThemeProvider and AuthProvider wrap the whole app once,
// here, so every screen (current and future) can read theme/auth
// state without re-wiring anything.
ReactDOM.createRoot(document.getElementById("root")).render(
  <React.StrictMode>
    <ThemeProvider>
      <AuthProvider>
        <BrowserRouter>
          <App />
        </BrowserRouter>
      </AuthProvider>
    </ThemeProvider>
  </React.StrictMode>,
);
