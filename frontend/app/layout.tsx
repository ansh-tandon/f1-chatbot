import "./globals.css";
import React from "react";

export const metadata = {
  title: "F1 Context Graph AI — Monaco 2024",
  description: "F1 Conversational AI built with FastF1, PostgreSQL, Neo4j, Qdrant & OpenAI",
};

export default function RootLayout({
  children,
}: {
  children: React.ReactNode;
}) {
  return (
    <html lang="en">
      <body>{children}</body>
    </html>
  );
}
