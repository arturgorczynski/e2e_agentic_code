import { useState } from 'react'
import { Moon, Sun } from 'lucide-react'

export function ThemeToggle() {
  const [dark, setDark] = useState(document.documentElement.dataset.theme === 'dark')
  function toggle() {
    const next = !dark
    document.documentElement.dataset.theme = next ? 'dark' : 'light'
    localStorage.setItem('acme-theme', next ? 'dark' : 'light')
    setDark(next)
  }
  return <button className="theme-toggle" aria-label={dark ? 'Switch to light mode' : 'Switch to dark mode'} title={dark ? 'Light mode' : 'Dark mode'} onClick={toggle}>{dark ? <Sun size={18}/> : <Moon size={18}/>}<span>{dark ? 'Light' : 'Dark'}</span></button>
}
