using Energy_Truth.Shared;

namespace Energy_Truth_WEB_API.Services.Provider
{
    public interface IProviderService
    {
        Task<List<ProviderDTO>> GetProvidersAsync();
    }
}
