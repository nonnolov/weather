import type { Metadata } from "next";
import type { ReactNode } from "react";
import "./globals.css";
import "./stitch.css";

export const metadata: Metadata = {
  title: "Weather · พยากรณ์อากาศ",
  description: "พยากรณ์อากาศรายชั่วโมง 7 วัน และค่าฝุ่น PM2.5 จากแบบจำลอง",
};
export default function RootLayout({ children }: Readonly<{ children: ReactNode }>) {
  return <html lang="th"><body>{children}</body></html>;
}
