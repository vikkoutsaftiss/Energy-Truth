using Energy_Truth.Shared;

namespace Energy_Truth_WEB_API.Services
{
    public interface IEnergyCalculationService
    {
        public CalculationResultDTO CalculateEnergy(List<EnergyImportDTO> data, string providerName);
    }
}
