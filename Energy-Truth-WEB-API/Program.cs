using Energy_Truth.Shared.Providers;
using Energy_Truth_WEB_API.Calculators;
using Energy_Truth_WEB_API.Services;
using Energy_Truth.Shared.Repositories;
using Scalar.AspNetCore;
using Microsoft.EntityFrameworkCore;
using Infrastructure.DataAccess;
using Infrastructure.DataAccess.DBContext;
using Energy_Truth_WEB_API.Services.Import;
using Energy_Truth_WEB_API.Services.DateFilter;
using Energy_Truth_WEB_API.Services.Provider;
using Energy_Truth_WEB_API.Services.Building;
using Energy_Truth_WEB_API.Services.Customer;
using Energy_Truth_WEB_API.Services.Battery;

var builder = WebApplication.CreateBuilder(args);

var dbName = Environment.GetEnvironmentVariable("POSTGRES_DB");
var dbUser = Environment.GetEnvironmentVariable("POSTGRES_USER");
var dbPassword = Environment.GetEnvironmentVariable("POSTGRES_PASSWORD");
var ip = Environment.GetEnvironmentVariable("DATABASE_IP") ?? "localhost";
var port = Environment.GetEnvironmentVariable("DATABASE_PORT") ?? "5432";

var connectionString = Environment.GetEnvironmentVariable("POSTGRES_DB") != null
    ? $"Host={ip};Port={port};Database={dbName};Username={dbUser};Password={dbPassword}"
    : builder.Configuration.GetConnectionString("DefaultConnection");
// Program.cs
builder.Services.AddControllers()
    .AddJsonOptions(options =>
    {
        // 1. Cruciaal: Negeer de interne read-only troep van BaseModel
        options.JsonSerializerOptions.IgnoreReadOnlyProperties = true;

        // 2. Zorg dat hij niet eigenwijs namen gaat veranderen naar CamelCase
        options.JsonSerializerOptions.PropertyNamingPolicy = null;

        // 3. Maak hem ongevoelig voor hoofdletters
        options.JsonSerializerOptions.PropertyNameCaseInsensitive = true;
    });



builder.Services.AddOpenApi();

builder.Services.AddCors(policy => policy.AddPolicy("Open", opt => opt.AllowAnyOrigin().AllowAnyHeader().AllowAnyMethod()));

builder.Services.AddScoped<IImportService, ImportService>();
builder.Services.AddScoped<IEnergyCalculationService, EnergyCalculationService>();
builder.Services.AddScoped<IEnergyProvider, HomeWizard>();
builder.Services.AddScoped<IEnergyProvider, UMeter>();
builder.Services.AddScoped<ITotalCumulativeCalculator, TotalCumulativeCalculator>();
builder.Services.AddScoped<ITotalNonCumulativeCalculator, TotalNonCumulativeCalculator>();
builder.Services.AddScoped<IPriceProviderCombineService, PriceProviderCombineService>();
builder.Services.AddScoped<IProviderService, ProviderService>();
builder.Services.AddScoped<IPriceService, PriceService>();
builder.Services.AddScoped<IImportBatchRepository, ImportBatchRepository>();
builder.Services.AddScoped<IUsageDataRepository, UsageDataRepository>();
builder.Services.AddScoped<IDateFilterService, DateFilterService>();
builder.Services.AddScoped<IBuildingRepository, BuildingRepository>();
builder.Services.AddScoped<ICustomerRepository, CustomerRepository>();
builder.Services.AddScoped<IBuildingService, BuildingService>();
builder.Services.AddScoped<ICustomerService, CustomerService>();
builder.Services.AddScoped<IBatteryService, BatteryService>();
builder.Services.AddScoped<IBatteryRepository, BatteryRepository>();
builder.Services.AddScoped<IImportCalculator, ImportCalculatorService>();
//builder.Services.AddDbContext<EnergyDbContext>(options =>
//    options.UseNpgsql(builder.Configuration.GetConnectionString("DefaultConnection")));
builder.Services.AddDbContext<EnergyDbContext>(options =>
    options.UseNpgsql(connectionString));


var supabaseUrl = builder.Configuration["Supabase:Url"];
var supabaseKey = builder.Configuration["Supabase:Key"];

builder.Services.AddScoped(_ => new Supabase.Client(supabaseUrl, supabaseKey));

var app = builder.Build();


app.UseCors("Open");

if (app.Environment.IsDevelopment())
{
    app.MapOpenApi();
    app.MapScalarApiReference();
}

app.UseHttpsRedirection();

app.UseAuthorization();

app.MapControllers();

await app.RunAsync();
