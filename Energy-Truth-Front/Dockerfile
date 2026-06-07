# Stage 1: Build met .NET SDK
FROM mcr.microsoft.com/dotnet/sdk:10.0 AS build
WORKDIR /app

# Kopieer eerst alleen de .csproj bestanden voor betere Docker cache
COPY Energy-Truth-Front/Energy-Truth_Presentation.csproj Energy-Truth-Front/
COPY Energy-Truth.Shared/Energy-Truth.Shared.csproj Energy-Truth.Shared/

# Herstel dependencies
RUN dotnet restore Energy-Truth-Front/Energy-Truth_Presentation.csproj

# Kopieer daarna de volledige broncode
COPY Energy-Truth-Front/ Energy-Truth-Front/
COPY Energy-Truth.Shared/ Energy-Truth.Shared/

# Publiceer de applicatie
RUN dotnet publish Energy-Truth-Front/Energy-Truth_Presentation.csproj -c Release -o /app/publish

# Stage 2: Serveer statische bestanden via nginx
FROM nginx:stable-alpine
COPY --from=build /app/publish/wwwroot /usr/share/nginx/html

# Kopieer de aangepaste nginx configuratie voor Blazor client-side routing
COPY nginx.conf /etc/nginx/conf.d/default.conf

# Installeer gettext
RUN apk add --no-cache gettext

# 1. Kopieer het start-script naar de root van de container
COPY entrypoint.sh /entrypoint.sh

# 2. Maak het script uitvoerbaar binnen Linux
RUN chmod +x /entrypoint.sh

# 3. Start de container via het script met de officiële exec form []
ENTRYPOINT ["/entrypoint.sh"]