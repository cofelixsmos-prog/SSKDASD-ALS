import { getToken, getUser, redirectByRole } from './auth.js';

export function requireAuth(allowedRoles = []) {
  const token = getToken();
  if (!token) {
    window.location.href = '/';
    return false;
  }
  if (allowedRoles.length > 0) {
    const user = getUser();
    if (!user || !allowedRoles.includes(user.role)) {
      if (user) redirectByRole(user.role);
      else window.location.href = '/';
      return false;
    }
  }
  return true;
}
