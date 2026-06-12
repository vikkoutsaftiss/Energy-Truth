using Energy_Truth.Shared.DTO_s;

namespace Energy_Truth.Shared.Repositories
{
    public interface IBatteryRepository
    {
        Task<List<BatteryDTO>> GetBatteriesAsync();
        Task<bool> UpdateBatteryAsync(int batteryId, BatteryDTO dto);
        Task<BatteryDTO?> CreateBatteryAsync(BatteryDTO dto);
        Task<bool> GetBatteryByNameAndCapacity(string name, decimal capacity);
    }
}
