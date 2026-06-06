using Energy_Truth.Shared.DTO_s;
using Energy_Truth.Shared.Repositories;
using Infrastructure.DataAccess.DBContext;
using Infrastructure.DataAccess.Entities;
using Microsoft.EntityFrameworkCore;
using System.Runtime.InteropServices;

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
            List<BatteryDTO> batteries = await _dbContext.Batteries.Select(b => new BatteryDTO
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
                Chemistry = b.Chemistry,
                IsActive = b.IsActive
            }).ToListAsync();

            return batteries;
        }

        public async Task<bool> UpdateBatteryAsync(int batteryId, BatteryDTO dto)
        {
            var battery = await _dbContext.Batteries.FindAsync(batteryId);
            if (battery == null) return false;

            battery.ProductName = dto.ProductName;
            battery.Price = dto.Price;
            battery.ProductCategory = "Batterij";
            battery.CapacityKWh = dto.CapacityKWh;
            battery.GuaranteedCycles = dto.GuaranteedCycles;
            battery.WarrantyPeriodYears = dto.WarrantyPeriodYears;
            battery.MaxChargePower = dto.MaxChargePower;
            battery.MaxDischargePower = dto.MaxDischargePower;
            battery.RoundTripEfficiency = dto.RoundTripEfficiency;
            battery.InstallationCost = dto.InstallationCost;
            battery.Chemistry = dto.Chemistry;
            battery.IsActive = dto.IsActive;

            await _dbContext.SaveChangesAsync();
            return true;
        }

        public async Task<BatteryDTO?> CreateBatteryAsync(BatteryDTO dto)
        {
            var battery = new Battery
            {
                ProductName = dto.ProductName,
                ProductCategory = "Batterij",
                Price = dto.Price,
                CapacityKWh = dto.CapacityKWh,
                GuaranteedCycles = dto.GuaranteedCycles,
                WarrantyPeriodYears = dto.WarrantyPeriodYears,
                MaxChargePower = dto.MaxChargePower,
                MaxDischargePower = dto.MaxDischargePower,
                RoundTripEfficiency = dto.RoundTripEfficiency,
                InstallationCost = dto.InstallationCost,
                Chemistry = dto.Chemistry,
                IsActive = true
            };
            await _dbContext.Batteries.AddAsync(battery);
            await _dbContext.SaveChangesAsync();
            return dto;
        }

        public async Task<BatteryDTO?> GetBatteryByIDAsync(int batteryId)
        {
            var battery = await _dbContext.Batteries.FindAsync(batteryId);
            if (battery == null)
            {
                return null;
            }

            return new BatteryDTO
            {
                Id = battery.Id,
                ProductName = battery.ProductName,
                ProductCategory = battery.ProductCategory,
                Price = battery.Price,
                CapacityKWh = battery.CapacityKWh,
                GuaranteedCycles = battery.GuaranteedCycles,
                WarrantyPeriodYears = battery.WarrantyPeriodYears,
                MaxChargePower = battery.MaxChargePower,
                MaxDischargePower = battery.MaxDischargePower,
                RoundTripEfficiency = battery.RoundTripEfficiency,
                InstallationCost = battery.InstallationCost,
                Chemistry = battery.Chemistry,
                IsActive = battery.IsActive
            };
        }
    }
}
