import { Routes, Route } from 'react-router-dom';
import { Container, Box } from '@mantine/core';
import Header from '../components/Header';
import ProtectedRoute from '../components/ProtectedRoute';
import Home from './Home';
import Videos from './Videos';
import Reports from './Reports';
import Login from './Login';

export default function App() {
  return (
    <Box style={{ backgroundColor: "#f0f0f0", minHeight: "100vh" }}>
      <Header />
      <Container size="xl" py="xl">
        <Routes>
          <Route path="/" element={
            <ProtectedRoute requiredPage="home">
              <Home />
            </ProtectedRoute>
          } />
          <Route path="/videos" element={
            <ProtectedRoute requiredPage="videos">
              <Videos />
            </ProtectedRoute>
          } />
          <Route path="/reports" element={
            <ProtectedRoute requiredPage="reports">
              <Reports />
            </ProtectedRoute>
          } />
          <Route path="/login" element={<Login />} />
        </Routes>
      </Container>
    </Box>
  );
}
