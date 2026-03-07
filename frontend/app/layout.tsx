
import "./globals.css";
import Link from "next/link";

export const metadata = {
  title: "FareRadar",
  description: "Flight deal anomaly detection"
};

export default function RootLayout({ children }: { children: React.ReactNode }) {
  return (
    <html lang="en">
      <body>
        <main className="mx-auto max-w-6xl px-4 py-8">
          <header className="mb-8 flex items-center justify-between">
            <Link href="/" className="text-2xl font-bold">FareRadar</Link>
            <nav className="flex gap-5 text-sm text-white/80">
              <Link href="/">Deals</Link>
              <Link href="/settings">Settings</Link>
              <Link href="/admin">Ops</Link>
            </nav>
          </header>
          {children}
        </main>
      </body>
    </html>
  );
}
