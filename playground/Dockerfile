FROM node:20-alpine AS base

FROM base AS builder

WORKDIR /app

# COPY .env.example .env
COPY . .

RUN npm i && \
    npm run build


FROM base AS runner

WORKDIR /app

ENV NODE_ENV production

RUN mkdir .next

COPY --from=builder /app/.next/standalone ./
COPY --from=builder /app/.next/static ./.next/static

EXPOSE 3000

CMD HOSTNAME="0.0.0.0" node server.js