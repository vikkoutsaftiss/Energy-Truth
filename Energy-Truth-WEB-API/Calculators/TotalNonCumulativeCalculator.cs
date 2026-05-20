using Energy_Truth.Shared;

namespace Energy_Truth_WEB_API.Calculators
{
    public class TotalNonCumulativeCalculator : ITotalNonCumulativeCalculator
    {
        public CalculationResultDTO CalculateTotal(List<EnergyImportDTO> data)
        {
            var result = new CalculationResultDTO();

            result.TotalImportKwh = data.Sum(item => item.ImportT1 ?? 0);
            result.TotalExportKwh = data.Sum(item => item.ExportT1 ?? 0);

            return result;
        }
    }
}
