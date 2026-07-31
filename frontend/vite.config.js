import { defineConfig } from "vite";
import react from "@vitejs/plugin-react";

// Basic Vite config for a React app. Nothing custom yet -
// we'll add things like the backend API URL as we need them.
export default defineConfig({
  plugins: [react()],
});
