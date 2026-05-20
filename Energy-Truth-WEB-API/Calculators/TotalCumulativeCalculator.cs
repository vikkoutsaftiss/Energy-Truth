using Energy_Truth.Shared;

namespace Energy_Truth_WEB_API.Calculators
{
    public class TotalCumulativeCalculator : ITotalCumulativeCalculator
    {
        public CalculationResultDTO CalculateTotal(List<EnergyImportDTO> data)
        {
            var result = new CalculationResultDTO();

            var validData = data.Where(d => d.ImportT1.HasValue && d.ImportT2.HasValue || d.ExportT1.HasValue || d.ExportT2.HasValue).ToList();
            
            var first = validData.First();
            var last = validData.Last();

            // Berekening: (Laatste stand T1+T2) - (Eerste stand T1+T2)
            result.TotalImportKwh = (last.ImportT1.GetValueOrDefault()) + last.ImportT2.GetValueOrDefault()
                                    - (first.ImportT1.GetValueOrDefault() + first.ImportT2.GetValueOrDefault());

            result.TotalExportKwh = (last.ExportT1.GetValueOrDefault() + last.ExportT2.GetValueOrDefault()
                                    - (first.ExportT1.GetValueOrDefault() + first.ExportT2.GetValueOrDefault()));

            return result;
        }
    
    }
}
