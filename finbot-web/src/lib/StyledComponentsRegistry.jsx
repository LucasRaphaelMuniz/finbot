"use client";

// lib/StyledComponentsRegistry.jsx — boilerplate exigido pelo App Router do
// Next.js 14 para SSR de styled-components (sem isso, style tag pisca no
// client / hydration mismatch). Ver next.config.mjs (compiler.styledComponents).
import { useState } from "react";
import { useServerInsertedHTML } from "next/navigation";
import { ServerStyleSheet, StyleSheetManager } from "styled-components";

export default function StyledComponentsRegistry({ children }) {
  const [sheet] = useState(() => new ServerStyleSheet());

  useServerInsertedHTML(() => {
    const styles = sheet.getStyleElement();
    sheet.instance.clearTag();
    return <>{styles}</>;
  });

  if (typeof window !== "undefined") return <>{children}</>;

  return (
    <StyleSheetManager sheet={sheet.instance}>{children}</StyleSheetManager>
  );
}
