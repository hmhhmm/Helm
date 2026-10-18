FROM node:24-slim
WORKDIR /repo
RUN corepack enable
COPY package.json pnpm-workspace.yaml pnpm-lock.yaml ./
COPY apps/web/package.json apps/web/
RUN pnpm install --frozen-lockfile
COPY apps/web apps/web
WORKDIR /repo/apps/web
RUN pnpm build
CMD ["pnpm", "start", "-H", "0.0.0.0"]
