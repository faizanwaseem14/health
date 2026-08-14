import { Route, Routes } from "react-router-dom";
import { Layout } from "./components/Layout/Layout";
import { Landing } from "./pages/Landing/Landing";

// Routing skeleton for Day 3. Only the landing page exists so far —
// login, upload, and results screens each get their own <Route> here
// as they're built, all nested inside the same <Layout /> shell.
function App() {
  return (
    <Routes>
      <Route path="/" element={<Layout />}>
        <Route index element={<Landing />} />
      </Route>
    </Routes>
  );
}

export default App;
