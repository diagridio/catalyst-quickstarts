FROM node:lts-alpine
ENV NODE_ENV=production
EXPOSE 5001
ENV PORT 5001
WORKDIR /usr/src/app
COPY package*.json .
RUN npm ci --silent && mv node_modules ../
COPY . .
RUN chown -R node /usr/src/app
USER node
CMD ["npm", "start"]
