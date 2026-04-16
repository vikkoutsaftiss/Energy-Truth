using Energy_Truth.Shared;

namespace Energy_Truth_WEB_API.Services
{
    public class EnergyCalculationService : IEnergyCalculationService
    {
    public CalculationResultDTO CalculateEnergy(List<EnergyImportDTO> data)
    {
        var result = new CalculationResultDTO();

        if (data == null || data.Count < 2) return result;

        // Sorteer op tijd (ervan uitgaande dat Time in EnergyImportDTO een DateTime is)
        var sorted = data.Where(d => d.Time.HasValue).OrderBy(d => d.Time).ToList();

        if (sorted.Count < 2) return result;

        var first = sorted.First();
        var last = sorted.Last();

        // Berekening: (Laatste stand T1+T2) - (Eerste stand T1+T2)
        result.TotalImportKwh = (last.ImportT1.GetValueOrDefault() + last.ImportT2.GetValueOrDefault()) 
                               - (first.ImportT1.GetValueOrDefault() + first.ImportT2.GetValueOrDefault());

        result.TotalExportKwh = (last.ExportT1.GetValueOrDefault() + last.ExportT2.GetValueOrDefault()) 
                               - (first.ExportT1.GetValueOrDefault() + first.ExportT2.GetValueOrDefault());

        return result;
    }
}

    
}
