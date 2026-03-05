import { IBM_Plex_Mono, IBM_Plex_Sans, Space_Grotesk } from 'next/font/google';
import PrototypeShell from './prototype-shell';

const headingFont = Space_Grotesk({
  subsets: ['latin'],
  variable: '--proto-heading-font',
});

const bodyFont = IBM_Plex_Sans({
  subsets: ['latin'],
  variable: '--proto-body-font',
});

const monoFont = IBM_Plex_Mono({
  subsets: ['latin'],
  weight: ['400', '500', '600'],
  variable: '--proto-mono-font',
});

export default function PrototypePage() {
  return (
    <PrototypeShell
      fontVars={`${headingFont.variable} ${bodyFont.variable} ${monoFont.variable}`}
    />
  );
}
