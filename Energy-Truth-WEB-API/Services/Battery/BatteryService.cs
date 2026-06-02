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
    }
}
