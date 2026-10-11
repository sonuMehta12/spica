import { StrictMode } from 'react';
import { createRoot } from 'react-dom/client';
import Boot from './Boot';
import { cssVars } from './theme';
import './styles/global.css';

// global.css reads the tokens as custom properties, so it never names a hex.
for (const [k, v] of Object.entries(cssVars())) document.documentElement.style.setProperty(k, v);

const host = document.getElementById('root');
if (!host) throw new Error('#root missing from index.html');

createRoot(host).render(
  <StrictMode>
    <Boot />
  </StrictMode>,
);
