"""确定性的 Next.js 14 (App Router) + Tailwind 脚手架。

样板文件不变、不需要 LLM（规则引擎能做的不用 LLM）。Builder 只生成特性文件，
write_app() 把脚手架与特性文件合并写盘（特性文件可覆盖同名脚手架文件）。
"""
from __future__ import annotations

import json
from pathlib import Path
from typing import Dict, List, Optional

from .schemas import GeneratedFile
from .util import npm_package_name, resolve_within

_PACKAGE_JSON = """{
  "name": "__PROJECT__",
  "version": "0.1.0",
  "private": true,
  "scripts": {
    "dev": "next dev",
    "build": "next build",
    "start": "next start",
    "lint": "next lint"
  },
  "dependencies": {
    "next": "14.2.5",
    "react": "^18.3.1",
    "react-dom": "^18.3.1"
  },
  "devDependencies": {
    "typescript": "^5.4.5",
    "@types/node": "^20.14.2",
    "@types/react": "^18.3.3",
    "@types/react-dom": "^18.3.0",
    "tailwindcss": "^3.4.4",
    "postcss": "^8.4.38",
    "autoprefixer": "^10.4.19"
  }
}
"""

_NEXT_CONFIG = """/** @type {import('next').NextConfig} */
const nextConfig = {};
export default nextConfig;
"""

_TSCONFIG = """{
  "compilerOptions": {
    "target": "ES2017",
    "lib": ["dom", "dom.iterable", "esnext"],
    "allowJs": true,
    "skipLibCheck": true,
    "strict": true,
    "noEmit": true,
    "esModuleInterop": true,
    "module": "esnext",
    "moduleResolution": "bundler",
    "resolveJsonModule": true,
    "isolatedModules": true,
    "jsx": "preserve",
    "incremental": true,
    "plugins": [{ "name": "next" }],
    "paths": { "@/*": ["./*"] }
  },
  "include": ["next-env.d.ts", "**/*.ts", "**/*.tsx", ".next/types/**/*.ts"],
  "exclude": ["node_modules"]
}
"""

_POSTCSS = """export default {
  plugins: {
    tailwindcss: {},
    autoprefixer: {},
  },
};
"""

_TAILWIND = """import type { Config } from "tailwindcss";

const config: Config = {
  content: [
    "./app/**/*.{js,ts,jsx,tsx,mdx}",
    "./components/**/*.{js,ts,jsx,tsx,mdx}",
  ],
  theme: {
    extend: {
      colors: {
        "ui-canvas": "rgb(var(--ui-canvas) / <alpha-value>)",
        "ui-surface": "rgb(var(--ui-surface) / <alpha-value>)",
        "ui-ink": "rgb(var(--ui-ink) / <alpha-value>)",
        "ui-muted": "rgb(var(--ui-muted) / <alpha-value>)",
        "ui-brand": "rgb(var(--ui-brand) / <alpha-value>)",
        "ui-brand-strong": "rgb(var(--ui-brand-strong) / <alpha-value>)",
        "ui-line": "rgb(var(--ui-line) / <alpha-value>)",
      },
      boxShadow: {
        soft: "0 24px 70px -32px rgb(15 23 42 / 0.28)",
        lift: "0 18px 36px -22px rgb(15 23 42 / 0.38)",
      },
      borderRadius: {
        "4xl": "2rem",
      },
    },
  },
  plugins: [],
};
export default config;
"""

_GLOBALS_CSS = """@tailwind base;
@tailwind components;
@tailwind utilities;

@layer base {
  :root {
    color-scheme: light;
    --ui-canvas: 247 248 252;
    --ui-surface: 255 255 255;
    --ui-ink: 15 23 42;
    --ui-muted: 71 85 105;
    --ui-brand: 79 70 229;
    --ui-brand-strong: 67 56 202;
    --ui-line: 226 232 240;
  }

  * {
    @apply border-ui-line;
  }

  html {
    @apply bg-ui-canvas;
    scroll-behavior: smooth;
  }

  body {
    @apply min-h-screen bg-ui-canvas font-sans text-ui-ink antialiased;
    background-image:
      radial-gradient(circle at 8% 0%, rgb(var(--ui-brand) / 0.10), transparent 30rem),
      radial-gradient(circle at 92% 12%, rgb(14 165 233 / 0.08), transparent 26rem);
  }

  ::selection {
    background: rgb(var(--ui-brand) / 0.18);
  }

  :where(a, button, input, select, textarea):focus-visible {
    outline: 3px solid rgb(var(--ui-brand) / 0.34);
    outline-offset: 3px;
  }
}

@layer components {
  .ui-shell {
    @apply mx-auto w-full max-w-7xl px-4 py-6 sm:px-6 sm:py-10 lg:px-8;
  }

  .ui-panel {
    @apply rounded-3xl border border-ui-line/80 bg-ui-surface/95 shadow-soft backdrop-blur;
  }

  .ui-kicker {
    @apply text-xs font-semibold uppercase tracking-[0.18em] text-ui-brand;
  }

  .ui-title {
    @apply text-3xl font-semibold tracking-[-0.035em] text-ui-ink sm:text-4xl lg:text-5xl;
  }

  .ui-copy {
    @apply max-w-2xl text-sm leading-7 text-ui-muted sm:text-base;
  }

  .ui-button-primary {
    @apply inline-flex min-h-11 items-center justify-center gap-2 rounded-xl bg-ui-brand px-4 py-2.5 text-sm font-semibold text-white shadow-lift transition hover:-translate-y-0.5 hover:bg-ui-brand-strong focus-visible:outline-none focus-visible:ring-4 focus-visible:ring-ui-brand/20 disabled:cursor-not-allowed disabled:opacity-50;
  }

  .ui-button-secondary {
    @apply inline-flex min-h-11 items-center justify-center gap-2 rounded-xl border border-ui-line bg-ui-surface px-4 py-2.5 text-sm font-semibold text-ui-ink transition hover:-translate-y-0.5 hover:border-ui-brand/35 hover:text-ui-brand focus-visible:outline-none focus-visible:ring-4 focus-visible:ring-ui-brand/15 disabled:cursor-not-allowed disabled:opacity-50;
  }

  .ui-field {
    @apply min-h-11 w-full rounded-xl border border-ui-line bg-white px-3.5 py-2.5 text-sm text-ui-ink outline-none transition placeholder:text-slate-400 focus:border-ui-brand focus:ring-4 focus:ring-ui-brand/15;
  }

  .ui-status {
    @apply rounded-2xl border border-ui-line/80 bg-slate-50 px-4 py-3 text-sm text-ui-muted;
  }
}

@media (prefers-reduced-motion: reduce) {
  *,
  *::before,
  *::after {
    scroll-behavior: auto !important;
    animation-duration: 0.01ms !important;
    animation-iteration-count: 1 !important;
    transition-duration: 0.01ms !important;
  }
}
"""

_LAYOUT = """import type { Metadata, Viewport } from "next";
import "./globals.css";

export const metadata: Metadata = {
  title: "__PROJECT__",
  description: "Generated by One-Person Company AI Factory (v1)",
};

export const viewport: Viewport = {
  colorScheme: "light",
  themeColor: "#f7f8fc",
};

export default function RootLayout({ children }: { children: React.ReactNode }) {
  return (
    <html lang="zh-CN">
      <body className="min-h-screen">{children}</body>
    </html>
  );
}
"""

_GITIGNORE = """node_modules
.next
out
"""

_ENV_LOCAL_EXAMPLE = """# Supabase（可选）：填入后生成的 app 真连 Supabase；留空则降级为本地 mock/localStorage。
NEXT_PUBLIC_SUPABASE_URL=
NEXT_PUBLIC_SUPABASE_ANON_KEY=
"""


def scaffold_files(project: str, extra_deps: Optional[Dict[str, str]] = None) -> Dict[str, str]:
    extra_deps = extra_deps or {}
    pkg = json.loads(_PACKAGE_JSON.replace("__PROJECT__", npm_package_name(project)))
    pkg["dependencies"].update(extra_deps)  # 合并白名单额外依赖
    files = {
        "package.json": json.dumps(pkg, indent=2) + "\n",
        "next.config.mjs": _NEXT_CONFIG,
        "tsconfig.json": _TSCONFIG,
        "postcss.config.mjs": _POSTCSS,
        "tailwind.config.ts": _TAILWIND,
        "app/globals.css": _GLOBALS_CSS,
        "app/layout.tsx": _LAYOUT.replace("__PROJECT__", project),
        ".gitignore": _GITIGNORE,
    }
    if "@supabase/supabase-js" in extra_deps:
        files[".env.local.example"] = _ENV_LOCAL_EXAMPLE
    return files


def write_app(
    target: Path,
    project: str,
    feature_files: List[GeneratedFile],
    extra_deps: Optional[Dict[str, str]] = None,
) -> List[Path]:
    """写脚手架 + 特性文件到 target/。特性文件覆盖同名脚手架文件。"""
    files: Dict[str, str] = scaffold_files(project, extra_deps)
    for f in feature_files:
        files[f.path] = f.content

    # Validate every untrusted path before the first write to avoid partial output.
    resolved_files = [(resolve_within(target, rel), content) for rel, content in files.items()]
    written: List[Path] = []
    for p, content in resolved_files:
        p.parent.mkdir(parents=True, exist_ok=True)
        p.write_text(content, encoding="utf-8")
        written.append(p)
    return written
