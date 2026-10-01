import { StrictMode } from 'react';
import { createRoot } from 'react-dom/client';
import './styles.css';
import { Donnees } from './donnees.jsx';
import App from './App.jsx';

createRoot(document.getElementById('racine')).render(
  <StrictMode>
    <Donnees>
      <App />
    </Donnees>
  </StrictMode>
);
