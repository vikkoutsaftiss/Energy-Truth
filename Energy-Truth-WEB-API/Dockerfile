# Stage 1: Build
FROM mcr.microsoft.com/dotnet/sdk:10.0 AS build
WORKDIR /app

# Kopieer eerst alleen de .csproj bestanden voor betere Docker cache
COPY Energy-Truth-WEB-API/Energy-Truth-WEB-API.csproj Energy-Truth-WEB-API/
COPY Energy-Truth.Shared/Energy-Truth.Shared.csproj Energy-Truth.Shared/

# Herstel dependencies
RUN dotnet restore Energy-Truth-WEB-API/Energy-Truth-WEB-API.csproj

# Kopieer daarna de volledige broncode
COPY Energy-Truth-WEB-API/ Energy-Truth-WEB-API/
COPY Energy-Truth.Shared/ Energy-Truth.Shared/

# Publiceer de applicatie
RUN dotnet publish Energy-Truth-WEB-API/Energy-Truth-WEB-API.csproj -c Release -o /app/publish

# Stage 2: Runtime
FROM mcr.microsoft.com/dotnet/aspnet:10.0
WORKDIR /app
COPY --from=build /app/publish .
EXPOSE 8080
ENTRYPOINT ["dotnet", "Energy-Truth-WEB-API.dll"]