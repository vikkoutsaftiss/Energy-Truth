using Energy_Truth.Shared;
using Energy_Truth.Shared.DTO_s;

namespace Energy_Truth_WEB_API.Calculators
{
    public interface IImportCalculator
    {
        IEnumerable<UsageDataDTO> CalculateCumulativeImport(List<EnergyImportDTO> data, string provider);
        IEnumerable<UsageDataDTO> MapDirectImport(List<EnergyImportDTO> data, string provider);
         IEnumerable<UsageDataDTO> CalculateImport(List<EnergyImportDTO> data, string providerName);

    }
}
