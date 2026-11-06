/* eslint-disable react-refresh/only-export-components */
import { createContext, useCallback, useContext, useMemo, useState } from 'react';
import { useAuth, userHasRole } from './AuthContext';

const ROLE_KEY = 'fieldshift-role';
const RoleContext = createContext(null);

function getStoredRolePreference() {
  if (typeof window === 'undefined') return 'farmer';
  const stored = window.localStorage.getItem(ROLE_KEY);
  return stored === 'extension' ? 'extension' : 'farmer';
}

export function RoleProvider({ children }) {
  const { user } = useAuth();
  const [preferredRole, setPreferredRole] = useState(getStoredRolePreference);

  const canSwitchToExtension = useMemo(
    () => userHasRole(user, 'extension'),
    [user],
  );

  // Only allow extension mode when the server-verified user has the extension role
  const role = canSwitchToExtension && preferredRole === 'extension' ? 'extension' : 'farmer';

  const setRole = useCallback(
    (nextRole) => {
      if (!canSwitchToExtension) {
        setPreferredRole('farmer');
        if (typeof window !== 'undefined') {
          window.localStorage.removeItem(ROLE_KEY);
        }
        return;
      }
      const next = nextRole === 'extension' ? 'extension' : 'farmer';
      setPreferredRole(next);
      if (typeof window !== 'undefined') {
        window.localStorage.setItem(ROLE_KEY, next);
      }
    },
    [canSwitchToExtension],
  );

  const value = useMemo(
    () => ({
      role,
      setRole,
      canSwitchToExtension,
    }),
    [role, setRole, canSwitchToExtension],
  );

  return <RoleContext.Provider value={value}>{children}</RoleContext.Provider>;
}

export function useRole() {
  const context = useContext(RoleContext);
  if (!context) throw new Error('useRole must be used within RoleProvider');
  return context;
}
