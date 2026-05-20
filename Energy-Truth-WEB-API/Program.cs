using Energy_Truth.Shared.Providers;
using Energy_Truth_WEB_API;
using Energy_Truth_WEB_API.Calculators;
using Energy_Truth_WEB_API.Services;
using Scalar.AspNetCore;

var builder = WebApplication.CreateBuilder(args);

// Add services to the container.

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

app.Run();
