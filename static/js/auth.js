const TOKEN_KEY = 'edutrack_token';
const USER_KEY  = 'edutrack_user';

export function saveToken(token) { localStorage.setItem(TOKEN_KEY, token); }
export function getToken()       { return localStorage.getItem(TOKEN_KEY); }
export function clearToken()     { localStorage.removeItem(TOKEN_KEY); localStorage.removeItem(USER_KEY); }

export function saveUser(user)   { localStorage.setItem(USER_KEY, JSON.stringify(user)); }
export function getUser()        {
  try { return JSON.parse(localStorage.getItem(USER_KEY)); } catch { return null; }
}

export function logout() {
  clearToken();
  window.location.href = '/';
}

export function redirectByRole(role) {
  const map = {
    admin:   '/static/pages/admin/index.html',
    teacher: '/static/pages/teacher/index.html',
    student: '/static/pages/student/index.html',
    parent:  '/static/pages/parent/index.html',
  };
  window.location.href = map[role] || '/';
}

export function getInitials(name) {
  if (!name) return '?';
  return name.split(' ').map(w => w[0]).join('').slice(0, 2).toUpperCase();
}
