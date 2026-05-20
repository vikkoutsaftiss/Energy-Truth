using Energy_Truth.Shared;

namespace Energy_Truth_WEB_API.Services
{
    public class ProviderService : IProviderService
    {
        private readonly Supabase.Client _supabaseClient;

        public ProviderService(Supabase.Client supabaseClient)
        {
            _supabaseClient = supabaseClient;
        }

        public async Task<List<ProviderDTO>> GetProvidersAsync()
        {
            var response = await _supabaseClient
                    .From<ProviderDTO>()
                    .Order("name", Supabase.Postgrest.Constants.Ordering.Descending)
                    .Get();

            return response.Models ?? new List<ProviderDTO>();

        }
    }
}
