# Stap 1: Build-omgeving (bijv. Node.js voor React/Vue)
FROM node:18-alpine AS build
WORKDIR /app
COPY package*.json ./
RUN npm install
COPY . .
RUN npm run build

# Stap 2: Productie-omgeving (Nginx)
FROM nginx:stable-alpine
# Kopieer de output van de build-stap naar de Nginx map
COPY --from=build /app/dist /usr/share/nginx/html
EXPOSE 80
CMD ["nginx", "-g", "daemon off;"]
