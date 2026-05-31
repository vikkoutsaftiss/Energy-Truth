using Energy_Truth.Shared.DTO_s;

namespace Energy_Truth.Shared.Repositories
{
    public interface IBatteryRepository
    {
        Task<List<BatteryDTO>> GetBatteriesAsync();
    }
}
