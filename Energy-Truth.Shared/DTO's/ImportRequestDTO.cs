using Energy_Truth.Shared.DTO_s;

namespace Energy_Truth.Shared.DTO_s
{
    public class ImportRequestDTO
    {
        public List<EnergyImportDTO> Data { get; set; }
        public CustomBatteryDTO? CustomBattery { get; set; }
    }
}
