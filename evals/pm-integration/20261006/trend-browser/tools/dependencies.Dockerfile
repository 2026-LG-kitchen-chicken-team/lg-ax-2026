FROM lgax-pm-trend-browser-base:aebef576-20261006
USER 0
WORKDIR /opt/lgax-web-dependencies
ENV NPM_CONFIG_CACHE=/opt/npm-cache-seed
COPY package.json package-lock.json ./
RUN npm config get cache && npm ci --ignore-scripts --offline --no-audit --no-fund && chmod -R a+rX /opt/lgax-web-dependencies
USER 1000:1000
WORKDIR /workspace
