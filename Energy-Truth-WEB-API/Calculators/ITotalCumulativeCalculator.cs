using Energy_Truth.Shared;

namespace Energy_Truth_WEB_API.Calculators
{
    public interface ITotalCumulativeCalculator
    {
        CalculationResultDTO CalculateTotal(List<EnergyImportDTO> data);
    }
}
