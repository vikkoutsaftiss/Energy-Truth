using Energy_Truth.Shared.DTO_s;

namespace Energy_Truth_WEB_API.Services.Battery
{
    public interface IBatteryService
    {
        Task<List<BatteryDTO>> GetBatteriesAsync();
    }
}
