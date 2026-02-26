# ── Build Stage ──────────────────────────────────────────────────────
FROM node:20-alpine AS builder
WORKDIR /app

# Dependencies first (layer caching)
COPY package.json package-lock.json* ./
RUN npm ci

# Source code
COPY . .

# Build-time env for rewrites in next.config.ts
ARG GATEWAY_INTERNAL_URL=http://ariia-core:8000
ENV GATEWAY_INTERNAL_URL=${GATEWAY_INTERNAL_URL}

RUN npm run build

# ── Development Stage (Hot Reload) ──────────────────────────────────
FROM builder AS dev
CMD ["npm", "run", "dev"]

# ── Production Stage ────────────────────────────────────────────────
FROM node:20-alpine AS runner
WORKDIR /app

ENV NODE_ENV=production
ENV PORT=3000
ENV HOSTNAME=0.0.0.0

# Runtime env for API routes (app/api/*)
ENV GATEWAY_INTERNAL_URL=http://ariia-core:8000

# Standalone output: only what's needed to run
COPY --from=builder /app/.next/standalone ./
COPY --from=builder /app/.next/static ./.next/static
COPY --from=builder /app/public ./public

EXPOSE 3000
CMD ["node", "server.js"]
