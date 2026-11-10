import React from 'react'
import { createRoot } from 'react-dom/client'
import App from './App'
import './styles.css'
import './visuals.css'
import './database.css'
import './portal-enhancements.css'
import './insights.css'
import './experience.css'

document.documentElement.dataset.theme = localStorage.getItem('acme-theme') ?? 'dark'

createRoot(document.getElementById('root')!).render(<React.StrictMode><App /></React.StrictMode>)
