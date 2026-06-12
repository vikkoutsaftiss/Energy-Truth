using Energy_Truth.Shared.DTO_s;
using System;
using System.Collections.Generic;
using System.Text;

namespace _04._Tests.Builders
{
    public class BatteryDTOBuilder
    {
        private int _id = 1;
        private string _productName = "Test Battery";
        private decimal _price = 1000m;
        private decimal _capacityKWh = 10;
        private int _guaranteedCycles = 5000;
        private int _warrantyPeriodYears = 10;
        private decimal _maxChargePower = 5;
        private decimal _maxDischargePower = 5;
        private decimal _usableCapacityKWh = 9;
        private decimal _roundTripEfficiency = 90;
        private decimal _installationCost = 500m;
        private string _chemistry = "Lithium-ion";
        private bool _isActive = true;

        public BatteryDTOBuilder WithProductName(string name)
        {
            _productName = name;
            return this;
        }

        public BatteryDTOBuilder WithPrice(decimal price)
        {
            _price = price;
            return this;
        }

        public BatteryDTOBuilder WithCapacityKWh(decimal capacity)
        {
            _capacityKWh = capacity;
            return this;
        }

        public BatteryDTOBuilder WithGuaranteedCycles(int cycles)
        {
            _guaranteedCycles = cycles;
            return this;
        }

        public BatteryDTOBuilder WithWarrantyPeriodYears(int years)
        {
            _warrantyPeriodYears = years;
            return this;
        }

        public BatteryDTOBuilder WithMaxChargePower(decimal power)
        {
            _maxChargePower = power;
            return this;
        }

        public BatteryDTOBuilder WithMaxDischargePower(decimal power)
        {
            _maxDischargePower = power;
            return this;
        }

        public BatteryDTOBuilder WithUsableCapacityKWh(decimal usableCapacity)
        {
            _usableCapacityKWh = usableCapacity;
            return this;
        }

        public BatteryDTOBuilder WithRoundTripEfficiency(decimal efficiency)
        {
            _roundTripEfficiency = efficiency;
            return this;
        }

        public BatteryDTOBuilder WithInstallationCost(decimal cost)
        {
            _installationCost = cost;
            return this;
        }

        public BatteryDTOBuilder WithChemistry(string chemistry)
        {
            _chemistry = chemistry;
            return this;
        }

        public BatteryDTO Build()
        {
            return new BatteryDTO
            {
                Id = _id,
                ProductName = _productName,
                Price = _price,
                CapacityKWh = _capacityKWh,
                GuaranteedCycles = _guaranteedCycles,
                WarrantyPeriodYears = _warrantyPeriodYears,
                MaxChargePower = _maxChargePower,
                MaxDischargePower = _maxDischargePower,
                UsableCapacityKWh = _usableCapacityKWh,
                RoundTripEfficiency = _roundTripEfficiency,
                InstallationCost = _installationCost,
                Chemistry = _chemistry,
                IsActive = _isActive
            };
        }
    }
}
