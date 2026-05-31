using Energy_Truth.Shared.DTO_s;
using Energy_Truth.Shared.Repositories;
using Infrastructure.DataAccess.DBContext;
using Microsoft.EntityFrameworkCore;

namespace Infrastructure.DataAccess
{
    public class BatteryRepository : IBatteryRepository
    {
        private readonly EnergyDbContext _dbContext;

        public BatteryRepository(EnergyDbContext energyDbContext)
        {
            _dbContext = energyDbContext;
        }

        public async Task<List<BatteryDTO>> GetBatteriesAsync()
        {
            List<BatteryDTO> batteries = await _dbContext.Battery.Select(b => new BatteryDTO
            {
                Id = b.Id,
                ProductName = b.ProductName,
                Price = b.Price,
                CapacityKWh = b.CapacityKWh,
                GuaranteedCycles = b.GuaranteedCycles,
                WarrantyPeriodYears = b.WarrantyPeriodYears,
                MaxChargePower = b.MaxChargePower,
                MaxDischargePower = b.MaxDischargePower,
                UsableCapacityKWh = b.UsableCapacityKWh,
                RoundTripEfficiency = b.RoundTripEfficiency,
                InstallationCost = b.InstallationCost,
                Chemistry = b.Chemistry
            }).ToListAsync();

            return batteries;
        }
    }
}
