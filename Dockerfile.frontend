FROM mcr.microsoft.com/dotnet/sdk:10.0 AS build
# Stage 1: Build met .NET SDK
FROM mcr.microsoft.com/dotnet/sdk:10.0 AS build
WORKDIR /app

# Kopieer eerst alleen de .csproj bestanden voor betere Docker cache
COPY "Energy-Truth-Front/Energy-Truth Presentation.csproj" "Energy-Truth-Front/"
COPY Energy-Truth.Shared/Energy-Truth.Shared.csproj Energy-Truth.Shared/

# Herstel dependencies
RUN dotnet restore "Energy-Truth-Front/Energy-Truth Presentation.csproj"

# Kopieer daarna de volledige broncode
COPY Energy-Truth-Front/ Energy-Truth-Front/
COPY Energy-Truth.Shared/ Energy-Truth.Shared/

# Publiceer de applicatie
RUN dotnet publish "Energy-Truth-Front/Energy-Truth Presentation.csproj" -c Release -o /app/publish

# Stage 2: Serveer statische bestanden via nginx
FROM nginx:stable-alpine
COPY --from=build /app/publish/wwwroot /usr/share/nginx/html

# Kopieer de aangepaste nginx configuratie voor Blazor client-side routing
COPY nginx.conf /etc/nginx/conf.d/default.conf

EXPOSE 80
CMD ["nginx", "-g", "daemon off;"]
