ARG NODE_IMAGE=public.ecr.aws/docker/library/node:24-alpine
ARG NGINX_IMAGE=public.ecr.aws/docker/library/nginx:1.28-alpine
FROM ${NODE_IMAGE} AS build
WORKDIR /app
COPY package*.json .
RUN npm ci
COPY . .
RUN npm run build
FROM ${NGINX_IMAGE}
COPY nginx.conf /etc/nginx/conf.d/default.conf
COPY --from=build /app/dist /usr/share/nginx/html
