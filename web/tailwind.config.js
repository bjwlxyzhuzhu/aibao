/** @type {import('tailwindcss').Config} */
export default {
  content: ['./index.html', './src/**/*.{ts,tsx}'],
  theme: {
    extend: {
      colors: {
        cream: { DEFAULT: '#FBF6F1', 2: '#F6EEE6', 3: '#EFE3D7' },
        ink: { DEFAULT: '#2A2522', 2: '#5E544E', 3: '#958A82' },
        terra: { 50: '#FDF1EC', 100: '#FBE3D9', 200: '#F6CDBB', 300: '#EFAE94', 400: '#E58E6E', 500: '#D46A47', 600: '#C2563A', 700: '#9F4430' },
        brand: { green: '#019E33', lime: '#C4EA03', orange: '#F56D01' },
        sky: { 500: '#2F7BE0' },
      },
      fontFamily: { sans: ['"PingFang SC"', '"HarmonyOS Sans SC"', '"Microsoft YaHei"', 'system-ui', 'sans-serif'] },
      boxShadow: { card: '0 1px 2px rgba(80,50,30,.04), 0 8px 24px -12px rgba(120,70,40,.12)', pill: '0 6px 16px -6px rgba(212,106,71,.55)' },
      borderRadius: { xl2: '20px' },
    },
  },
  plugins: [],
}
