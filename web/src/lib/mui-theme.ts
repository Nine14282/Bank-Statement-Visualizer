import { createTheme } from '@mui/material/styles'

// MUI follows the app's Tailwind `.dark` class (colorSchemeSelector: 'class'); colours here only
// feed MUI internals (Chip, LinearProgress, Snackbar) - surfaces use our CSS variables via sx.
export const theme = createTheme({
  cssVariables: { colorSchemeSelector: 'class' },
  defaultColorScheme: 'dark',
  colorSchemes: {
    dark: { palette: { primary: { main: '#9a6bff' }, error: { main: '#f08a6a' } } },
    light: { palette: { primary: { main: '#6d28d9' }, error: { main: '#d9582f' } } },
  },
  typography: { fontFamily: "'Geist', 'Noto Sans Thai', 'Sarabun', system-ui, sans-serif" },
  shape: { borderRadius: 10 },
  components: { MuiPaper: { styleOverrides: { root: { backgroundImage: 'none' } } } },
})
