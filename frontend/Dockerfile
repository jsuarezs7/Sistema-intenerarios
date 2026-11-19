FROM alpine:3.20 AS assets
WORKDIR /assets
COPY frontend/ .

FROM nginx:1.27-alpine AS runtime
COPY --from=assets /assets /usr/share/nginx/html
COPY frontend/nginx.conf /etc/nginx/conf.d/default.conf
RUN sed -i 's/user  nginx;/user  nginx;/' /etc/nginx/nginx.conf \
    && sed -i 's|^pid .*;|pid /tmp/nginx.pid;|' /etc/nginx/nginx.conf \
    && chown -R nginx:nginx /usr/share/nginx/html /var/cache/nginx /var/log/nginx /etc/nginx/conf.d
USER nginx
EXPOSE 80
