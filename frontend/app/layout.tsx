import type { Metadata } from "next";
import "./globals.css";

export const metadata: Metadata = {
  title: "Weather Lab",
  description: "气象大数据计算与可视化系统",
};

export default function RootLayout({ children }: Readonly<{ children: React.ReactNode }>) {
  return (
    <html lang="zh-CN">
      <body>{children}</body>
    </html>
  );
}
