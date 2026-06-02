# Stage 1: Build
FROM mcr.microsoft.com/dotnet/sdk:10.0 AS build
WORKDIR /app

# 1. Kopieer EERST alle .csproj bestanden voor optimale Docker caching
COPY Energy-Truth-WEB-API/Energy-Truth-WEB-API.csproj Energy-Truth-WEB-API/
COPY Energy-Truth.Shared/Energy-Truth.Shared.csproj Energy-Truth.Shared/
COPY Infrastructure.DataAcess/Infrastructure.DataAcess.csproj Infrastructure.DataAcess/ # TOEGEVOEGD

# Herstel alle dependencies op basis van de gecachte projectbestanden
RUN dotnet restore Energy-Truth-WEB-API/Energy-Truth-WEB-API.csproj

# 2. Kopieer DAARNA pas de volledige broncode van alle mappen
COPY Energy-Truth-WEB-API/ Energy-Truth-WEB-API/
COPY Energy-Truth.Shared/ Energy-Truth.Shared/
COPY Infrastructure.DataAcess/ Infrastructure.DataAcess/ # TOEGEVOEGD

# Publiceer de applicatie
RUN dotnet publish Energy-Truth-WEB-API/Energy-Truth-WEB-API.csproj -c Release -o /app/publish

# Stage 2: Runtime
FROM mcr.microsoft.com/dotnet/aspnet:10.0
WORKDIR /app
COPY --from=build /app/publish .
EXPOSE 8080
ENTRYPOINT ["dotnet", "Energy-Truth-WEB-API.dll"]
