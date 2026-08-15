import { Route, Routes } from "react-router-dom";
import { Layout } from "./components/Layout/Layout";
import { Landing } from "./pages/Landing/Landing";
import { Login } from "./pages/Login/Login";
import { ProfileSetup } from "./pages/ProfileSetup/ProfileSetup";
import { Home } from "./pages/Home/Home";
import { RequireAuth } from "./routes/RequireAuth";
import { RequireProfile } from "./routes/RequireProfile";

// Routing skeleton for Day 3. Upload/results screens each get their
// own <Route> here as they're built, all nested inside the same
// <Layout /> shell. /profile-setup and /home require a signed-in
// session (RequireAuth); /home additionally requires a completed
// profile (RequireProfile) - a first-time visitor is sent to set one
// up before they can go further.
function App() {
  return (
    <Routes>
      <Route path="/" element={<Layout />}>
        <Route index element={<Landing />} />
        <Route path="login" element={<Login />} />
        <Route element={<RequireAuth />}>
          <Route path="profile-setup" element={<ProfileSetup />} />
          <Route element={<RequireProfile />}>
            <Route path="home" element={<Home />} />
          </Route>
        </Route>
      </Route>
    </Routes>
  );
}

export default App;
