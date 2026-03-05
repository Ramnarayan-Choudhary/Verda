import { IBM_Plex_Mono, IBM_Plex_Sans, Space_Grotesk } from 'next/font/google';
import Prototype2Shell from './prototype2-shell';

const headingFont = Space_Grotesk({
  subsets: ['latin'],
  variable: '--proto2-heading-font',
});

const bodyFont = IBM_Plex_Sans({
  subsets: ['latin'],
  variable: '--proto2-body-font',
});

const monoFont = IBM_Plex_Mono({
  subsets: ['latin'],
  weight: ['400', '500', '600'],
  variable: '--proto2-mono-font',
});

export default function Prototype2Page() {
  return (
    <Prototype2Shell
      fontVars={`${headingFont.variable} ${bodyFont.variable} ${monoFont.variable}`}
    />
  );
}
