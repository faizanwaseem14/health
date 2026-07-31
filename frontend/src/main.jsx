import React from "react";
import ReactDOM from "react-dom/client";
import App from "./App.jsx";

// This is where React "attaches" itself to the <div id="root"> in index.html.
ReactDOM.createRoot(document.getElementById("root")).render(
  <React.StrictMode>
    <App />
  </React.StrictMode>,
);
