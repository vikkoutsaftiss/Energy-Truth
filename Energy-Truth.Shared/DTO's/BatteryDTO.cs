using System.ComponentModel.DataAnnotations;

namespace Energy_Truth.Shared.DTO_s
{
    public class BatteryDTO
    {
        public int Id { get; set; }
        public string ProductName { get; set; }
        public string? ProductCategory { get; set; }
        public decimal Price { get; set; }
        public decimal CapacityKWh { get; set; }
        public int GuaranteedCycles { get; set; }
        public int WarrantyPeriodYears { get; set; }
        public decimal MaxChargePower { get; set; }
        public decimal MaxDischargePower { get; set; }
        public decimal UsableCapacityKWh { get; set; }
        public decimal RoundTripEfficiency { get; set; }
        public decimal? InstallationCost { get; set; }
        public string Chemistry { get; set; }
        public bool? IsActive { get; set; }
    }
}
