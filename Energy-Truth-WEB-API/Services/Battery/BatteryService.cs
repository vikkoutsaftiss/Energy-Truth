using Energy_Truth.Shared.Repositories;
using Energy_Truth.Shared.DTO_s;
using Microsoft.Identity.Client;

namespace Energy_Truth_WEB_API.Services.Battery
{
    public class BatteryService : IBatteryService
    {
        private readonly IBatteryRepository _batteryRepository;

        public BatteryService(IBatteryRepository batteryRepository)
        {
            _batteryRepository = batteryRepository;
        }

        public async Task<List<BatteryDTO>> GetBatteriesAsync()
        {
            List<BatteryDTO> batteries = await _batteryRepository.GetBatteriesAsync();
            return batteries;
        }

        public async Task<bool> UpdateBatteryAsync(int batteryId, BatteryDTO dto)
        {
            bool result = await _batteryRepository.UpdateBatteryAsync(batteryId, dto);
            return result;
        }

        public async Task<BatteryDTO?> CreateBatteryAsync(BatteryDTO dto)
        {
            var result = await _batteryRepository.GetBatteryByNameAndCapacity(dto.ProductName, dto.CapacityKWh);
            if (!result)
            {
                return await _batteryRepository.CreateBatteryAsync(dto);
            }
            return null;
                     
        }
    }
}
