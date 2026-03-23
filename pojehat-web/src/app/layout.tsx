import { ThemeProvider } from '@/components/theme-provider';
import type { Metadata } from 'next';
import { Hubot_Sans, Space_Grotesk, Space_Mono } from 'next/font/google';
import { Analytics } from '@vercel/analytics/next';
import { SpeedInsights } from '@vercel/speed-insights/next';
import './globals.css';

const spaceMono = Space_Mono({
  variable: '--font-mono',
  subsets: ['latin'],
  weight: ['400', '700'],
});

const spaceGrotesk = Space_Grotesk({
  variable: '--font-heading',
  subsets: ['latin'],
  weight: ['600', '700'],
});

const hubotSans = Hubot_Sans({
  variable: '--font-sans',
  subsets: ['latin'],
  weight: ['300'],
  // Hubot Sans supports width axis; we can set width: 100 via style
  style: 'normal',
  // Use variable font with width axis; we'll set CSS custom property
  // The font's variable axes include 'wdth' 100-125; we'll rely on default.
});

export const metadata: Metadata = {
  title: 'Pojehat - Tier-3 Automotive Diagnostics',
  description: 'AI-driven technical insights for automotive engineers.',
  icons: {
    icon: '/pojehat-logo.png',
  },
};

export default function RootLayout({
  children,
}: Readonly<{
  children: React.ReactNode;
}>) {
  return (
    <html lang="en" suppressHydrationWarning>
      <body
        className={`${spaceMono.variable} ${spaceGrotesk.variable} ${hubotSans.variable} font-sans antialiased`}
      >
        <ThemeProvider
          attribute="class"
          defaultTheme="system"
          enableSystem
          disableTransitionOnChange
        >
          {children}
          <Analytics />
          <SpeedInsights />
        </ThemeProvider>
      </body>
    </html>
  );
}
