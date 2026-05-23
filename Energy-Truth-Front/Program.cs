using Energy_Truth;
using Energy_Truth.Shared.Providers;
using Energy_Truth_Presentation;
using Microsoft.AspNetCore.Components.Web;
using Microsoft.AspNetCore.Components.WebAssembly.Hosting;
using MudBlazor.Services;

var builder = WebAssemblyHostBuilder.CreateDefault(args);



builder.RootComponents.Add<App>("#app");
builder.RootComponents.Add<HeadOutlet>("head::after");
builder.Services.AddMudServices();

builder.Services.AddScoped<IEnergyProvider, HomeWizard>();
builder.Services.AddScoped<IEnergyProvider, UMeter>();

builder.Services.AddScoped(sp => new HttpClient
{
    BaseAddress = new Uri(builder.Configuration["ApiBaseUrl"])
});

await builder.Build().RunAsync();
