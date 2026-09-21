import { useState, useEffect } from 'react';
import { useNavigate } from 'react-router-dom';
import {
  Container,
  Paper,
  Title,
  Text,
  TextInput,
  PasswordInput,
  Button,
  Stack,
  Alert,
  Center,
} from '@mantine/core';
import { loginUser } from '../api/client';
import { useAuth } from '../context/AuthContext';
import { getDefaultPageForRole } from '../utils/permissions';

export default function Login() {
  const [name, setName] = useState('');
  const [password, setPassword] = useState('');
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const { login, isAuthenticated, user } = useAuth();
  const navigate = useNavigate();

  // Redirect authenticated users away from login page
  useEffect(() => {
    if (isAuthenticated && user) {
      const defaultPage = getDefaultPageForRole(user.role);
      navigate(defaultPage);
    }
  }, [isAuthenticated, user, navigate]);

  const handleSubmit = async (e: React.FormEvent) => {
    e.preventDefault();

    if (!name || !password) {
      setError('Name and password are required');
      return;
    }

    try {
      setLoading(true);
      setError(null);

      const response = await loginUser({ name, password });

      if (response.success) {
        login(response.user, response.token);
        const defaultPage = getDefaultPageForRole(response.user.role);
        navigate(defaultPage);
      } else {
        setError(response.message || 'Login failed');
      }
    } catch (err) {
      setError(err instanceof Error ? err.message : 'Login failed');
    } finally {
      setLoading(false);
    }
  };

  return (
    <Container size="xs" py="xl">
      <Center>
        <Paper shadow="md" p="xl" radius="md" withBorder style={{ width: '100%', maxWidth: 400 }}>
          <Stack gap="md">
            <div>
              <Title order={2} ta="center" mb="xs">
                Welcome Back
              </Title>
              <Text size="sm" c="dimmed" ta="center">
                Sign in to your account
              </Text>
            </div>

            {error && (
              <Alert color="red" title="Error">
                {error}
              </Alert>
            )}

            <form onSubmit={handleSubmit}>
              <Stack gap="md">
                <TextInput
                  label="Name"
                  placeholder="Enter your name"
                  required
                  value={name}
                  onChange={(e) => setName(e.target.value)}
                  disabled={loading}
                />

                <PasswordInput
                  label="Password"
                  placeholder="Enter your password"
                  required
                  value={password}
                  onChange={(e) => setPassword(e.target.value)}
                  disabled={loading}
                />

                <Button type="submit" fullWidth loading={loading} mt="md">
                  Sign In
                </Button>
              </Stack>
            </form>

            <Text size="xs" c="dimmed" ta="center">
              Don't have an account? Contact your administrator
            </Text>
          </Stack>
        </Paper>
      </Center>
    </Container>
  );
}
