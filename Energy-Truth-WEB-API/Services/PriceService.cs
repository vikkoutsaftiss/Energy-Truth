using Energy_Truth.Shared;
using Energy_Truth_WEB_API.Services;
using Microsoft.AspNetCore.Mvc;
using Supabase.Postgrest;

namespace Energy_Truth_WEB_API.Services
{
    public class PriceService : IPriceService
    {
        private readonly Supabase.Client _supabaseClient;

        public PriceService(Supabase.Client supabaseClient)
        {
            _supabaseClient = supabaseClient;
        }

        public async Task<List<PriceDTO>> GetCurrentPriceAsync()
        {
            var response = await _supabaseClient
                    .From<PriceDTO>()
                    .Order("valid_from", Supabase.Postgrest.Constants.Ordering.Descending)
                    .Get();

            return response.Models ?? new List<PriceDTO>();

        }
    }
}
