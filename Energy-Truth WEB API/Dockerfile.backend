# Stage 1: Build
FROM mcr.microsoft.com/dotnet/sdk:10.0 AS build
WORKDIR /app
COPY "Energy-Truth WEB API/Energy-Truth WEB API.csproj" "Energy-Truth WEB API/"
COPY Energy-Truth.Shared/Energy-Truth.Shared.csproj Energy-Truth.Shared/
RUN dotnet restore "Energy-Truth WEB API/Energy-Truth WEB API.csproj"
COPY "Energy-Truth WEB API/" "Energy-Truth WEB API/"
COPY Energy-Truth.Shared/ Energy-Truth.Shared/
RUN dotnet publish -c Release -o /app/publish

# Stage 2: Runtime
FROM mcr.microsoft.com/dotnet/aspnet:10.0
WORKDIR /app
COPY --from=build /app/publish .
EXPOSE 8080
ENTRYPOINT ["dotnet", "Energy-Truth WEB API.dll"]
