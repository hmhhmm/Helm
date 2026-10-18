# Decisions

Where the brief was silent, the simplest option was chosen. Newest last.

1. **Python 3.12** for the API (3.14 is installed but the data/optimiser stack is safest on 3.12).
2. **Next.js 16 scaffold**: `cacheComponents` and `partialPrefetching` switched off. The app is client-driven (TanStack Query against the API), so caching components add nothing and complicate dynamic data.
3. **shadcn CLI not used**: its current default is Base UI, the brief says Radix. Components are hand-written in `src/components/ui` on Radix primitives with shadcn-style APIs.
4. **Contrast-adjusted verdict colours** (WCAG AA 4.5:1 for text on white). The brief's swatches for ALLOW (#0E8A4F, ~4.4:1) and HOLD (#B26A00, ~4.2:1) just miss, so text uses ALLOW #0B7A45 and HOLD #9A5B00. ESCALATE, DENY and accent pass as given.
5. **Docker is not installed on the build machine.** `docker-compose.yml` is written to spec but only the SQLite fallback and local Postgres are verified here.
6. **Theme** is a `data-theme` attribute on `<html>` (light default, user toggle, persisted in localStorage), no extra library.
