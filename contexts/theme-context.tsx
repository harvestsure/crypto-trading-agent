'use client'

import React, { createContext, useContext, useEffect, useState } from 'react'

type Theme = 'light' | 'dark' | 'system'

interface ThemeContextType {
  theme: Theme
  setTheme: (theme: Theme) => void
  resolvedTheme: 'light' | 'dark'
}

const ThemeContext = createContext<ThemeContextType | undefined>(undefined)

export function ThemeContextProvider({ children }: { children: React.ReactNode }) {
  const [theme, setThemeState] = useState<Theme>('system')
  const [resolvedTheme, setResolvedTheme] = useState<'light' | 'dark'>('dark')
  const [mounted, setMounted] = useState(false)

  // 初始化主题
  useEffect(() => {
    // 从 localStorage 读取保存的主题
    const savedTheme = localStorage.getItem('theme') as Theme | null
    if (savedTheme && ['light', 'dark', 'system'].includes(savedTheme)) {
      setThemeState(savedTheme)
    } else {
      setThemeState('system')
    }
    setMounted(true)
  }, [])

  // 监听系统主题变化和更新 DOM
  useEffect(() => {
    if (!mounted) return

    const updateTheme = () => {
      let effectiveTheme: 'light' | 'dark' = 'dark'

      if (theme === 'system') {
        // 检测系统主题偏好
        if (window.matchMedia && window.matchMedia('(prefers-color-scheme: light)').matches) {
          effectiveTheme = 'light'
        } else {
          effectiveTheme = 'dark'
        }
      } else {
        effectiveTheme = theme
      }

      setResolvedTheme(effectiveTheme)

      // 更新 HTML 元素的 class
      const htmlElement = document.documentElement
      if (effectiveTheme === 'dark') {
        htmlElement.classList.add('dark')
        htmlElement.classList.remove('light')
      } else {
        htmlElement.classList.remove('dark')
        htmlElement.classList.add('light')
      }
    }

    updateTheme()

    // 监听系统主题变化
    const mediaQuery = window.matchMedia('(prefers-color-scheme: light)')
    const handleChange = () => {
      if (theme === 'system') {
        updateTheme()
      }
    }

    mediaQuery.addEventListener('change', handleChange)
    return () => mediaQuery.removeEventListener('change', handleChange)
  }, [theme, mounted])

  const setTheme = (newTheme: Theme) => {
    setThemeState(newTheme)
    localStorage.setItem('theme', newTheme)
  }

  const contextValue = { theme, setTheme, resolvedTheme }

  return (
    <ThemeContext.Provider value={contextValue}>
      {children}
    </ThemeContext.Provider>
  )
}

export function useTheme() {
  const context = useContext(ThemeContext)
  if (context === undefined) {
    throw new Error('useTheme must be used within a ThemeContextProvider')
  }
  return context
}
