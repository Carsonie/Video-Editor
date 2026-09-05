// Role-based permissions

export const ROLES = {
  VISITOR: 'Visitor',
  BCP_ADMIN: 'BCP-Admin',
} as const;

export type Role = typeof ROLES[keyof typeof ROLES];

// Define which pages each role can access
export const ROLE_PERMISSIONS = {
  [ROLES.VISITOR]: {
    canAccessHome: false,
    canAccessVideos: true,
    canAccessReports: false,
    defaultPage: '/videos',
  },
  [ROLES.BCP_ADMIN]: {
    canAccessHome: true,
    canAccessVideos: true,
    canAccessReports: true,
    defaultPage: '/',
  },
};

export function getDefaultPageForRole(role: string): string {
  if (role === ROLES.VISITOR) {
    return ROLE_PERMISSIONS[ROLES.VISITOR].defaultPage;
  }
  if (role === ROLES.BCP_ADMIN) {
    return ROLE_PERMISSIONS[ROLES.BCP_ADMIN].defaultPage;
  }
  return '/';
}

export function canAccessPage(role: string, page: 'home' | 'videos' | 'reports'): boolean {
  const permissions = role === ROLES.VISITOR
    ? ROLE_PERMISSIONS[ROLES.VISITOR]
    : ROLE_PERMISSIONS[ROLES.BCP_ADMIN];

  switch (page) {
    case 'home':
      return permissions.canAccessHome;
    case 'videos':
      return permissions.canAccessVideos;
    case 'reports':
      return permissions.canAccessReports;
    default:
      return false;
  }
}
