using Energy_Truth.Shared;
using Energy_Truth.Shared.DTO_s;

namespace Energy_Truth_WEB_API.Calculators
{
    public interface ICumulativeCalculator
    {
        IEnumerable<UsageDataDTO> CalculateCumulativeImport(List<EnergyImportDTO> data, string provider);

    }
}
