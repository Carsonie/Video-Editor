import { Tabs, Box } from "@mantine/core";
import { useNavigate, useLocation } from "react-router-dom";
import { useAuth } from "../context/AuthContext";
import { canAccessPage } from "../utils/permissions";

export default function Header() {
  const navigate = useNavigate();
  const location = useLocation();
  const { isAuthenticated, logout, user } = useAuth();

  const getActiveTab = () => {
    if (location.pathname === "/videos") return "videos";
    if (location.pathname === "/reports") return "reports";
    if (location.pathname === "/login") return isAuthenticated ? null : "login";
    return "home";
  };

  const handleTabChange = async (value: string | null) => {
    if (value === "home") navigate("/");
    else if (value === "videos") navigate("/videos");
    else if (value === "reports") navigate("/reports");
    else if (value === "login") navigate("/login");
    else if (value === "logout") {
      await logout();
      navigate("/");
    }
  };

  return (
    <Box
      style={{
        height: "200px",
        display: "flex",
        alignItems: "center",
        borderBottom: "1px solid #dee2e6",
        paddingLeft: "20px",
        paddingRight: "20px",
        backgroundColor: "#9e9e9e",
      }}
    >
      <Tabs value={getActiveTab()} onChange={handleTabChange}>
        <Tabs.List>
          {isAuthenticated ? (
            <Tabs.Tab value="logout">Logout</Tabs.Tab>
          ) : (
            <Tabs.Tab value="login">Login</Tabs.Tab>
          )}
          {isAuthenticated && user && canAccessPage(user.role, 'home') && (
            <Tabs.Tab value="home">Home</Tabs.Tab>
          )}
          {isAuthenticated && user && canAccessPage(user.role, 'videos') && (
            <Tabs.Tab value="videos">Videos</Tabs.Tab>
          )}
          {isAuthenticated && user && canAccessPage(user.role, 'reports') && (
            <Tabs.Tab value="reports">Reports</Tabs.Tab>
          )}
        </Tabs.List>
      </Tabs>
    </Box>
  );
}
