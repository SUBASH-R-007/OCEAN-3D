import type { Metadata } from 'next';
import './globals.css';

export const metadata: Metadata = {
  title: 'Ocean3D | Ocean evidence workbench',
  description:
    'Explore ocean model volumes and quality-aware instrument comparisons. SIH26067 research prototype with clearly labeled demonstration data.',
};

export default function RootLayout({
  children,
}: Readonly<{
  children: React.ReactNode;
}>) {
  return (
    <html lang="en" className="dark">
      <body>{children}</body>
    </html>
  );
}
