import { defineConfig } from 'vitest/config'

// Test config: jsdom environment + shared setup (design doc §5.2 D7/M6).
export default defineConfig({
  test: {
    environment: 'jsdom',
    setupFiles: ['./src/test/setup.ts'],
    globals: true,
    css: false,
  },
})
