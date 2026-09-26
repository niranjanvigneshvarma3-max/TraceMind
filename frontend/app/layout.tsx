import type { Metadata } from "next";
import "./globals.css";

export const metadata: Metadata = {
  title: "TraceMind | Evidence investigation",
  description: "Inspect evidence, compare hypotheses, and stress-test your conclusions.",
};

export default function RootLayout({ children }: Readonly<{ children: React.ReactNode }>) {
  return <html lang="en"><body>{children}</body></html>;
}

