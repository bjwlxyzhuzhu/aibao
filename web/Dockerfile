FROM node:24-alpine AS build
WORKDIR /w
COPY web/package.json web/package-lock.json ./
ARG NPM_REGISTRY=https://registry.npmjs.org
RUN npm ci --registry=${NPM_REGISTRY}
COPY web/ ./
RUN npm run build

FROM nginx:1.27-alpine
COPY deploy/nginx.conf /etc/nginx/conf.d/default.conf
COPY --from=build /w/dist /usr/share/nginx/html
