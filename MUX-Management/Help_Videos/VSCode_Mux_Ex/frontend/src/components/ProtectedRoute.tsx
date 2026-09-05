import { ReactNode, useEffect } from 'react';
import { useNavigate } from 'react-router-dom';
import { useAuth } from '../context/AuthContext';
import { canAccessPage, getDefaultPageForRole } from '../utils/permissions';

interface ProtectedRouteProps {
  children: ReactNode;
  requiredPage: 'home' | 'videos' | 'reports';
}

export default function ProtectedRoute({ children, requiredPage }: ProtectedRouteProps) {
  const { isAuthenticated, user } = useAuth();
  const navigate = useNavigate();

  useEffect(() => {
    if (!isAuthenticated) {
      // Not authenticated, redirect to login
      navigate('/login');
    } else if (user && !canAccessPage(user.role, requiredPage)) {
      // Authenticated but not authorized, redirect to their default page
      const defaultPage = getDefaultPageForRole(user.role);
      navigate(defaultPage);
    }
  }, [isAuthenticated, user, requiredPage, navigate]);

  // Don't render children if not authorized
  if (!isAuthenticated || !user || !canAccessPage(user.role, requiredPage)) {
    return null;
  }

  return <>{children}</>;
}
