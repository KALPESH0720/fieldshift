import { StrictMode } from 'react'
import { createRoot } from 'react-dom/client'
import 'leaflet/dist/leaflet.css'
import './index.css'
import App from './App.jsx'
import { ThemeProvider } from './context/ThemeContext.jsx'
import { LanguageProvider } from './context/LanguageContext.jsx'
import { AuthProvider } from './context/AuthContext.jsx'
import { RoleProvider } from './context/RoleContext.jsx'

// Purge legacy v1 crop image runtime caches so stale synthetic tiles are never served
if (typeof window !== 'undefined') {
  if ('caches' in window) {
    const legacyCaches = ['crop-card-photos', 'image-cache', 'crop-card-images-v2', 'crop-thumb-images-v2'];
    void Promise.all(legacyCaches.map((name) => window.caches.delete(name))).catch(() => {});
  }
  if ('serviceWorker' in navigator) {
    void navigator.serviceWorker
      .getRegistrations()
      .then((registrations) => {
        for (const registration of registrations) {
          void registration.update();
        }
      })
      .catch(() => {});
  }
}

createRoot(document.getElementById('root')).render(
  <StrictMode>
    <ThemeProvider>
      <LanguageProvider>
        <AuthProvider>
          <RoleProvider>
            <App />
          </RoleProvider>
        </AuthProvider>
      </LanguageProvider>
    </ThemeProvider>
  </StrictMode>,
)
